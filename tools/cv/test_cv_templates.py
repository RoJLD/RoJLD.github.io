"""Le template `sobre` doit régénérer le CSS actuel À L'OCTET.

C'est le garde-fou central de l'extraction : tant qu'il tient, la banque de
templates ne peut pas altérer le CV par défaut — celui qui part réellement aux
recruteurs. Même motif que la migration de l'article : l'artefact d'origine est
figé en fixture, la génération doit le reproduire.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

LEGACY_CSS = (HERE / "fixtures" / "cv_css.legacy.txt").read_text(encoding="utf-8")
TEMPLATES = ROOT / "cv" / "templates"

_SCV_MINIMAL = {"lang": "fr", "identity": {"name": "N"}, "sections": [],
                "skills_top": [], "footer": {}}


def _charge(tid: str) -> dict:
    return json.loads((TEMPLATES / f"{tid}.json").read_text(encoding="utf-8"))


def _px(v: str) -> float:
    """Valeur numérique d'une longueur CSS, unité ignorée (comparaisons homogènes)."""
    return float(v.rstrip("abcdefghijklmnopqrstuvwxyz%"))


def test_sobre_regenere_le_css_a_l_octet():
    import cv_templates
    assert cv_templates.build_css(_charge("sobre")["style"]) == LEGACY_CSS


def test_fixture_non_vide():
    """Garde anti-vacuité : une fixture vide ferait passer le test précédent
    contre un moteur qui ne produit rien."""
    assert len(LEGACY_CSS) == 1483
    assert LEGACY_CSS.count("{") >= 23


def test_build_css_est_pur():
    """Mêmes entrées, même sortie — condition nécessaire de la parité."""
    import cv_templates
    st = _charge("sobre")["style"]
    assert cv_templates.build_css(st) == cv_templates.build_css(st)


def test_build_css_reflete_la_palette():
    """Garde anti-gabarit-figé : un moteur qui ignorerait `style` et renverrait la
    constante passerait le test d'identité octet de la tâche 1."""
    import cv_templates
    st = json.loads(json.dumps(_charge("sobre")["style"]))
    st["palette"]["accent"] = "#ff0000"
    css = cv_templates.build_css(st)
    assert "#ff0000" in css and "#4361ee" not in css


def test_build_css_reflete_le_rythme_vertical():
    """`density` doit réellement piloter les gaps : c'est le levier qui permet à un
    template dense de tenir un parcours plus long sur une page."""
    import cv_templates
    st = json.loads(json.dumps(_charge("sobre")["style"]))
    st["density"]["section_gap"] = "3px"
    st["density"]["bullet_gap"] = "0px"
    css = cv_templates.build_css(st)
    assert ".cv-section { margin-bottom: 3px;" in css
    assert "ul.cv-bullets li { margin-bottom: 0px; }" in css


def test_style_incomplet_fail_loud():
    """Une clé absente ne doit pas produire un CSS silencieusement dégradé."""
    import cv_templates
    st = json.loads(json.dumps(_charge("sobre")["style"]))
    del st["palette"]["accent"]
    with pytest.raises(cv_templates.TemplateError, match="accent"):
        cv_templates.build_css(st)


def test_charger_template_inconnu_fail_loud():
    import cv_templates
    with pytest.raises(cv_templates.TemplateError, match="inconnu|introuvable"):
        cv_templates.charger("nexistepas")


def test_meta_declare_les_champs_attendus():
    """`meta` est ce que le ciblage lira pour CHOISIR un template : ses champs sont
    un contrat, pas de la documentation."""
    import cv_templates
    for t in cv_templates.lister():
        for champ in ("pages", "market", "tone", "ats_safe", "sections"):
            assert champ in t["meta"], f"{t['id']} : meta.{champ} manquant"
        assert isinstance(t["meta"]["sections"], list) and t["meta"]["sections"]


@pytest.mark.parametrize("tid", ["sobre", "dense", "ats"])
def test_chaque_template_produit_un_css_valide(tid):
    import cv_templates
    css = cv_templates.build_css(_charge(tid)["style"])
    assert css.count("{") == css.count("}")
    assert "@page" in css and "None" not in css


def test_les_templates_different_vraiment():
    """Trois fichiers produisant le même CSS seraient une banque en trompe-l'œil."""
    import cv_templates
    css = {t: cv_templates.build_css(_charge(t)["style"]) for t in ("sobre", "dense", "ats")}
    assert len(set(css.values())) == 3


def test_ats_na_aucune_couleur_chromatique():
    """`meta.ats_safe` est lu par le ciblage : il doit décrire le fichier, pas le
    flatter. Un template ATS est en niveaux de gris — aucune teinte, donc les trois
    composantes RVB égales sur chaque couleur de la palette."""
    import cv_templates
    t = _charge("ats")
    assert t["meta"]["ats_safe"] is True
    for nom, valeur in t["style"]["palette"].items():
        h = valeur.lstrip("#")
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        r, v, b = h[0:2], h[2:4], h[4:6]
        assert r == v == b, f"palette.{nom} = {valeur} porte une teinte"


def test_dense_est_reellement_plus_dense_que_sobre():
    """`dense` doit gagner de la place, pas seulement porter le nom. Chaque levier
    vertical doit être strictement inférieur à celui de `sobre` — sinon le template
    ne tient pas la promesse que `meta` fait au ciblage."""
    import cv_templates
    s, d = _charge("sobre")["style"], _charge("dense")["style"]
    assert float(d["density"]["line"]) < float(s["density"]["line"])
    for cle in ("section_gap", "bullet_gap"):
        assert _px(d["density"][cle]) < _px(s["density"][cle]), cle
    assert _px(d["type"]["base"]) < _px(s["type"]["base"])
    assert _px(d["page"]["margin"].split()[0]) < _px(s["page"]["margin"].split()[0])


def test_lister_rejette_un_template_malforme(tmp_path, monkeypatch):
    """`lister()` doit VALIDER, pas seulement lire.

    `meta` est ce que le ciblage consulte pour CHOISIR un template : un `meta`
    amputé qui traverse silencieusement ferait arbitrer sur un contrat incomplet.

    Ce test existe parce qu'un mutant a survécu : retirer la validation de
    `lister()` était indétectable tant que tous les fichiers de la banque sont
    sains. Aucun test ne lui donnait jamais un fichier cassé à avaler.
    """
    import cv_templates
    (tmp_path / "casse.json").write_text(json.dumps({
        "id": "casse",
        "label": {"fr": "Cassé", "en": "Broken"},
        "meta": {"pages": 1, "market": ["FR"], "tone": "corporate"},
        "style": _charge("sobre")["style"],
    }), encoding="utf-8")
    monkeypatch.setattr(cv_templates, "TEMPLATES", tmp_path)
    with pytest.raises(cv_templates.TemplateError, match="ats_safe|sections"):
        cv_templates.lister()


def test_render_html_sans_template_est_inchange():
    """Non-régression : l'appel historique à un argument doit produire exactement
    ce qu'il produisait."""
    import cv_render
    assert LEGACY_CSS in cv_render.render_html(_SCV_MINIMAL)


def test_template_explicite_introuvable_ne_retombe_pas_en_silence():
    """Le repli sur `CV_CSS` ne vaut que pour le défaut sur une banque absente
    (clone partiel). Un template DEMANDÉ et introuvable doit lever : sinon le PDF
    sort au mauvais design sans que rien ne le signale — c'est exactement
    Σ-SILENT-FALLBACK-HIDES-A-DEAD-DEPENDENCY (le `except → _default_cfg` de
    cv_target qui rendait le ciblage inerte tout en produisant un PDF)."""
    import cv_render
    import cv_templates
    with pytest.raises(cv_templates.TemplateError):
        cv_render.render_html(_SCV_MINIMAL, template="nexistepas")


def test_atelier_expose_les_templates():
    """Le sélecteur est alimenté par la banque, pas par une liste écrite en dur :
    déposer un fichier dans cv/templates/ doit suffire à le rendre choisissable."""
    import atelier
    page = atelier._page()
    for tid in ("sobre", "dense", "ats"):
        assert f'value="{tid}"' in page
    assert "Sobre" in page and "Dense" in page


def test_generate_pdf_transmet_le_template(monkeypatch):
    """Le choix du sélecteur doit atteindre le rendu.

    Sans ce témoin, l'atelier afficherait un menu parfaitement fonctionnel dont
    aucune option ne changerait le PDF — un menu inerte. C'est la classe
    Σ-A-FAKE-AT-THE-SEAM-NEVER-EXERCISES-THE-WIRING : tout est vert, rien n'est câblé.
    """
    import atelier
    vu = {}

    def _faux_render(scv, template=None):
        vu["template"] = template
        return "<html></html>"

    monkeypatch.setattr(atelier.cv_target, "targeted_structured_cv",
                        lambda *a, **k: ({}, {"lang": "fr"}))
    monkeypatch.setattr(atelier.cv_render, "render_html", _faux_render)
    monkeypatch.setattr(atelier.cv_pdf, "html_to_pdf_bytes", lambda h: b"%PDF-")
    atelier.generate_pdf("fiche", {}, "fr", template="ats")
    assert vu["template"] == "ats"


def test_render_html_accepte_un_template_charge():
    """Le paramètre accepte un dict déjà chargé, pour éviter une relecture disque
    par PDF dans la génération de la banque préfabriquée."""
    import cv_render
    import cv_templates
    t = json.loads(json.dumps(cv_templates.charger("sobre")))
    t["style"]["palette"]["accent"] = "#ff0000"
    assert "#ff0000" in cv_render.render_html(_SCV_MINIMAL, template=t)
