"""Tests du rendu HTML Σ-CV-ATELIER (sous-projet A)."""
from __future__ import annotations

import cv_render


def _cv(**over):
    base = {
        "lang": "fr",
        "identity": {"name": "Robin Denis", "title": "Quant Dev", "email": "r@x.io"},
        "sections": [
            {"kind": "experience", "company": "ALTEN", "title": "Quant Dev",
             "dates": "2024-09 → présent", "bullets": ["Pilotage CryptoExploration", "Vasicek/CIR"]},
        ],
        "skills_top": ["Python", "C++", "SQL"],
        "footer": {"updated": "2026-07-07"},
    }
    base.update(over)
    return base


def test_document_skeleton_and_lang():
    out = cv_render.render_html(_cv(lang="en"))
    assert out.startswith("<!doctype html>")
    assert '<html lang="en">' in out
    assert "<style>" in out and "@page" in out  # CSS inline
    assert out.rstrip().endswith("</html>")


def test_identity_rendered():
    out = cv_render.render_html(_cv())
    assert "Robin Denis" in out
    assert "Quant Dev" in out
    assert "r@x.io" in out


def test_all_section_fields_present():
    out = cv_render.render_html(_cv())
    assert "ALTEN" in out
    assert "2024-09 → présent" in out
    assert "Pilotage CryptoExploration" in out
    assert "Vasicek/CIR" in out
    assert out.count("<li>") == 2


def test_html_escaping_prevents_injection():
    cv = _cv(sections=[{"kind": "experience", "company": "X&Co", "title": "t",
                        "dates": "d", "bullets": ["<script>alert(1)</script>"]}])
    out = cv_render.render_html(cv)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
    assert "X&amp;Co" in out


def test_skills_and_footer():
    out = cv_render.render_html(_cv())
    assert "Python · C++ · SQL" in out
    assert "Compétences" in out  # label FR
    assert "Mis à jour 2026-07-07" in out


def test_english_labels():
    out = cv_render.render_html(_cv(lang="en"))
    assert "Skills" in out
    assert "Updated" in out


def test_empty_sections_still_valid_doc():
    out = cv_render.render_html(_cv(sections=[], skills_top=[]))
    assert out.startswith("<!doctype html>")
    assert "Robin Denis" in out
    assert "<li>" not in out


def test_deterministic():
    cv = _cv()
    assert cv_render.render_html(cv) == cv_render.render_html(cv)


# ── la garde vit a la FRONTIERE, pas dans le moteur de rendu ──────────────────
#
# `_css_du_template` accepte un dict a dessein : la banque prefabriquee charge le
# template une fois puis le reutilise par PDF, au lieu de relire le disque (contrat
# documente dans test_cv_templates.test_render_html_accepte_un_template_charge).
# Cette branche court-circuite donc `charger()`, et c'est correct — le dict en sort.
#
# Le danger n'etait pas la branche, mais le fait qu'un dict CLIENT y parvienne : le
# gestionnaire HTTP ne coercait pas `template`, alors qu'il coercait `skeleton` deux
# methodes plus bas. Des valeurs choisies par le client atterrissaient dans le
# <style> rendu par Chromium. Le test ci-dessous garde la FRONTIERE.

def test_le_handler_coerce_le_template_en_chaine(monkeypatch):
    """Coercion A LA FRONTIERE : ce que recoit generate_pdf n'est jamais un dict.

    C'est la meme discipline que `skeleton=str(...)` dans _handle_letter. Et c'est le
    SEUL endroit ou elle peut vivre : `cv_render` ne peut pas refuser les dicts, la
    banque prefabriquee lui en passe legitimement. Distinguer "dict de confiance" de
    "dict client" est impossible en aval — donc on tranche en amont, la ou l'origine
    est connue.
    """
    import atelier
    vus = {}

    def faux_generate_pdf(job, profile, lang, template=None, **_):
        vus["template"] = template
        return ({"relevance_key": "x", "min_relevance": 0.5}, b"%PDF-")

    monkeypatch.setattr(atelier, "generate_pdf", faux_generate_pdf)
    monkeypatch.setattr(atelier, "_PROFILE", _profil_bidon(monkeypatch))

    handler = atelier.Handler.__new__(atelier.Handler)
    handler._send = lambda *a, **k: None
    handler._handle_generate({"job": "fiche", "lang": "fr",
                              "template": {"style": {"page": {"marge": "0"}}}})

    # PREUVE DE PASSAGE d'abord : `_handle_generate` enveloppe tout dans un
    # `except Exception`. Sans cette assertion, une exception levee AVANT l'appel
    # laisserait `vus` vide, `vus.get(...)` rendrait None, et le test passerait a
    # VIDE en pretendant avoir verifie la frontiere.
    assert "template" in vus, "generate_pdf n'a jamais ete appele — test vide"
    assert not isinstance(vus["template"], dict), \
        f"un dict a traverse la frontiere : {vus['template']!r}"


def _profil_bidon(monkeypatch, tmp=[]):
    """Profil minimal sur disque, suffisant pour que _handle_generate le lise."""
    import json
    import pathlib
    import tempfile
    if not tmp:
        p = pathlib.Path(tempfile.mkdtemp()) / "profile.json"
        p.write_text(json.dumps({"identity": {"name": "Robin Denis"}}), encoding="utf-8")
        tmp.append(p)
    return tmp[0]
