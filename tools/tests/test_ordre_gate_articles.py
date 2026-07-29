"""Le gate de résolution ne doit pas exiger sur disque ce que le build produit.

Piège désamorcé ici : `validate(profile, root=ROOT)` résout `articles[].url` sur
le disque, et il s'exécutait AVANT `build_articles` — le générateur qui écrit
précisément ces pages, dix lignes plus bas. Inoffensif tant que les `.html` sont
commités ; armé au premier article ajouté (tâche H17 du backlog) : déclarer
l'`url` d'un article dont la page n'existe pas encore faisait échouer le BUILD
ENTIER, en désignant l'URL sans jamais nommer le générateur situé juste après.

Mesuré avant correctif, scénario H17 joué en vrai :
    BuildError: profile.json invalide : article 'onchain_analytics'.url:
    cible inexistante 'articles/onchain-analytics.html'   (EXIT=1)

Deux propriétés sont verrouillées ici, et elles tirent en sens opposé :
  * la résolution disque doit passer APRÈS la génération (sinon le piège) ;
  * les règles de FORME doivent passer AVANT toute écriture (sinon un profil
    invalide laisse des fichiers derrière lui — mesuré : aujourd'hui il n'en
    laisse aucun, et perdre ça serait une régression silencieuse).
D'où deux passes, et deux tests qui les épinglent chacune.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_articles  # noqa: E402
import build_site as bs  # noqa: E402
import validate_profile  # noqa: E402


def _profil_reel() -> dict:
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


# --- 1. L'ordre lui-même -----------------------------------------------------

def test_la_resolution_disque_passe_apres_la_generation_des_articles(monkeypatch):
    """Ordre observé sur un vrai build : forme → articles → résolution.

    Remettre `_gate(ROOT)` avant `build_articles` réarme le piège H17 ; ce test
    est ce qui l'en empêche.
    """
    evenements: list[str] = []

    vrai_articles = build_articles.build_articles

    def espion_articles(profile=None, write=True):
        evenements.append("articles")
        return vrai_articles(profile, write=write)

    vrai_validate = validate_profile.validate

    def espion_validate(profile, root=None):
        evenements.append("gate:resolution" if root is not None else "gate:forme")
        return vrai_validate(profile, root=root)

    monkeypatch.setattr(build_articles, "build_articles", espion_articles)
    monkeypatch.setattr(validate_profile, "validate", espion_validate)

    bs.build(write=False)

    assert "gate:resolution" in evenements, f"le gate de résolution ne tourne plus : {evenements}"
    assert "articles" in evenements, f"build_articles ne tourne plus : {evenements}"
    assert evenements.index("articles") < evenements.index("gate:resolution"), (
        "le gate de résolution repasse AVANT la génération des articles : "
        f"il exigerait à nouveau sur disque des pages qu'il produit ({evenements})"
    )


def test_les_regles_de_forme_passent_avant_toute_ecriture(monkeypatch):
    """Un profil structurellement invalide ne doit produire aucun fichier.

    C'est la propriété que l'ordre historique garantissait ; la corriger sans la
    préserver aurait échangé un défaut contre un autre.
    """
    evenements: list[str] = []

    vrai_articles = build_articles.build_articles

    def espion_articles(profile=None, write=True):
        evenements.append("articles")
        return vrai_articles(profile, write=write)

    vrai_validate = validate_profile.validate

    def espion_validate(profile, root=None):
        evenements.append("gate:resolution" if root is not None else "gate:forme")
        return vrai_validate(profile, root=root)

    monkeypatch.setattr(build_articles, "build_articles", espion_articles)
    monkeypatch.setattr(validate_profile, "validate", espion_validate)

    bs.build(write=False)

    assert evenements[0] == "gate:forme", (
        f"une écriture précède la validation de forme : {evenements}"
    )


# --- 2. L'effet que l'ordre produit ------------------------------------------

def test_un_article_neuf_est_refuse_avant_generation_puis_accepte_apres(tmp_path, monkeypatch):
    """Le fait causal qui rend l'ordre décisif, mesuré des deux côtés.

    Le même profil, le même validateur, la même racine : seule la génération a
    eu lieu entre les deux mesures. C'est exactement ce que le build inversait.
    """
    profile = _profil_reel()
    art = {
        "id": "article_neuf",
        "domains": ["data"],
        "title": {"fr": "Titre", "en": "Title"},
        "desc": {"fr": "Desc", "en": "Desc"},
        "url": "articles/article-neuf.html",
        "date": "2026-08",
        "tags": ["Test"],
        "status": "published",
    }
    profile["articles"] = [art]

    src = tmp_path / "articles" / "src"
    src.mkdir(parents=True)
    for lang in ("fr", "en"):
        (src / f"article-neuf.{lang}.md").write_text(
            "---\ntldr: t\n---\n\n## S\n\nCorps.\n", encoding="utf-8")
    monkeypatch.setattr(build_articles, "ROOT", tmp_path)
    monkeypatch.setattr(build_articles, "SRC", src)

    def erreurs_sur_larticle():
        return [e for e in validate_profile.validate(profile, root=tmp_path)
                if "article-neuf.html" in e]

    avant = erreurs_sur_larticle()
    assert any("cible inexistante" in e for e in avant), (
        f"le gate devrait refuser une page non encore générée : {avant}")

    produced, missing = build_articles.build_articles(profile, write=True)
    assert produced, f"aucune page produite (manques : {missing})"

    apres = erreurs_sur_larticle()
    assert apres == [], f"le gate refuse encore une page pourtant générée : {apres}"


def test_une_url_darticle_typotee_reste_refusee(tmp_path, monkeypatch):
    """La garde doit garder : générer ne blanchit pas une `url` qui ne mène nulle part.

    Sans ce test, « faire passer le build » se confondrait avec « désarmer le
    gate », et un lien mort repartirait en production.
    """
    profile = _profil_reel()
    profile["articles"] = [{
        "id": "article_typo",
        "domains": ["data"],
        "title": {"fr": "T", "en": "T"},
        "desc": {"fr": "D", "en": "D"},
        "url": "articles/article-typote.html",   # la source s'appelle autrement
        "date": "2026-08",
        "tags": [],
        "status": "published",
    }]
    src = tmp_path / "articles" / "src"
    src.mkdir(parents=True)
    (src / "article-neuf.fr.md").write_text("---\ntldr: t\n---\n\nx\n", encoding="utf-8")
    monkeypatch.setattr(build_articles, "ROOT", tmp_path)
    monkeypatch.setattr(build_articles, "SRC", src)

    produced, missing = build_articles.build_articles(profile, write=True)
    assert not produced and missing, "une page a été produite sans source"

    errs = [e for e in validate_profile.validate(profile, root=tmp_path)
            if "article-typote.html" in e]
    assert any("cible inexistante" in e for e in errs), (
        f"une url d'article sans page produite passe le gate : {errs}")
