"""Non-régression de la migration : la page générée doit porter le même texte que la
page écrite à la main.

L'égalité octet pour octet n'est PAS exigée — Markdown normalise le balisage, et
l'exiger ferait entrer dans le générateur les particularités d'une page manuelle.
Ce qui est comparé : le texte dépouillé, la structure des titres, et le contenu
littéral des blocs de données (formules, code).

Exception assumée : le temps de lecture. L'original annonçait « 8 min » pour 509
mots — une valeur fabriquée qu'aucune source ne contredisait. La génération la
corrige, donc un test qui exigerait l'identité défendrait l'erreur.
"""
from __future__ import annotations

import html as _html
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

LEGACY = pathlib.Path(__file__).resolve().parent / "fixtures" / "couverture-dynamique.legacy.html"


def _body(page: str) -> str:
    """Corps rédactionnel seul : entre le TL;DR et le pied d'auteur, APRÈS le CSS.

    Le découpage part de `</style>` : les noms de classe apparaissent d'abord dans la
    feuille de style, et un `find` naïf y découpe deux règles CSS au lieu de deux
    éléments — l'erreur a réellement été commise pendant la conception (elle donnait
    un corps de 46 mots au lieu de 509).
    """
    after_css = page[page.find("</style>") + len("</style>"):]
    i, j = after_css.find("article-tldr"), after_css.find("article-footer")
    assert i != -1 and j != -1, "bornes du corps introuvables"
    return after_css[i:j]


def _text(fragment: str) -> str:
    """Texte nu. Les balises tombent AVANT le déséchappement : dans l'autre ordre,
    un `&lt;script&gt;` littéral redeviendrait une balise et serait supprimé."""
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def _headings(fragment: str) -> list[str]:
    return [f"{m.group(1)}:{_text(m.group(2))}"
            for m in re.finditer(r"<(h2|h3)[^>]*>(.*?)</\1>", fragment, re.S)]


def _blocks(fragment: str, cls: str) -> list[str]:
    return [_text(m) for m in re.findall(rf'<div class="{cls}"[^>]*>(.*?)</div>', fragment, re.S)]


def _code(fragment: str) -> list[str]:
    return [_html.unescape(m).strip()
            for m in re.findall(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", fragment, re.S)]


@pytest.fixture(scope="module")
def legacy() -> str:
    return LEGACY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def generated() -> str:
    import build_articles
    return build_articles.render_article_page(build_articles.load_profile(),
                                              "couverture_dynamique", "fr")


# ── Non-régression de la migration ────────────────────────────────────────────

def test_titres_identiques(generated, legacy):
    assert _headings(_body(generated)) == _headings(_body(legacy))


def test_formules_identiques(generated, legacy):
    """La formule porte des espaces insécables. Écrites `&nbsp;` dans l'original et
    en caractères U+00A0 dans le Markdown, elles ne se comparent qu'après
    déséchappement — sinon le test échoue sur une différence qui n'en est pas une."""
    assert _blocks(_body(generated), "formula") == _blocks(_body(legacy), "formula")
    assert _blocks(_body(generated), "formula") != []


def test_bloc_de_code_identique(generated, legacy):
    """Le code est une donnée, pas de la mise en forme : identité exigée."""
    assert _code(_body(generated)) == _code(_body(legacy))


def test_texte_integralement_preserve(generated, legacy):
    """Chaque phrase substantielle de l'original se retrouve dans la page générée.

    Comparaison par phrase plutôt qu'égalité globale : l'espacement diffère
    légitimement (Markdown normalise), mais aucune phrase ne doit disparaître."""
    legacy_text, gen_text = _text(_body(legacy)), _text(_body(generated))
    manquantes = [p.strip() for p in re.split(r"(?<=[.!?]) ", legacy_text)
                  if len(p.strip()) > 40 and p.strip() not in gen_text]
    assert manquantes == [], f"phrases perdues : {manquantes[:3]}"


def test_temps_de_lecture_corrige(generated, legacy):
    """L'écart assumé, verrouillé dans les deux sens : la valeur fabriquée disparaît
    et la valeur dérivée apparaît. Sans ce test, la correction pourrait régresser
    sans que rien ne l'attrape."""
    assert "8 min" in _text(_body(legacy)) or "8 min" in legacy
    assert "8 min" not in generated
    assert "3 min de lecture" in generated


# ── Chrome : hors du corps comparé, donc à couvrir explicitement ──────────────
#
# `_body()` découpe entre le TL;DR et le pied d'auteur : les tags et le <h1> sont
# hors de son champ par construction. Deux mutants l'ont prouvé en survivant à la
# suite de non-régression (tags non rendus, titre non échappé). Ces tests-là sont
# leur filet.

def test_tags_tous_rendus(generated):
    """La page écrite à la main n'affichait que 3 des 4 tags déclarés — `EY` avait
    été oublié. Rien ne pouvait le dire : aucune source ne contredisait le HTML."""
    import build_articles
    art = next(a for a in build_articles.load_profile()["articles"]
               if a["id"] == "couverture_dynamique")
    rendus = re.findall(r'class="article-tag">([^<]+)<', generated)
    assert rendus == art["tags"]
    assert len(rendus) == 4


def test_titre_echappe(tmp_path, monkeypatch):
    """Le titre vient de profile.json et transite par <title> ET <h1>."""
    import build_articles
    profile = build_articles.load_profile()
    for a in profile["articles"]:
        if a["id"] == "couverture_dynamique":
            a["title"] = {"fr": 'X <script>alert("i")</script>', "en": "X"}
    page = build_articles.render_article_page(profile, "couverture_dynamique", "fr")
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


# ── Fonctions pures ───────────────────────────────────────────────────────────

def test_slug_vient_de_url_pas_de_id():
    """Cas DISCRIMINANT : id et url ne se correspondent pas.

    Sur le seul article réel, `couverture_dynamique` → `couverture-dynamique` par
    simple `_`→`-` : un test bâti sur lui passe aussi bien avec l'implémentation
    correcte qu'avec la fausse. Un mutant remplaçant `url` par `id.replace('_','-')`
    y survivait. Il faut un couple où les deux divergent."""
    import build_articles
    assert build_articles.slug_of({"id": "un_identifiant",
                                   "url": "articles/tout-autre-chose.html"}) == "tout-autre-chose"
    # et le cas réel, pour que la correspondance publique reste verrouillée
    assert build_articles.slug_of({"id": "couverture_dynamique",
                                   "url": "articles/couverture-dynamique.html"}) == "couverture-dynamique"


def test_slug_absent_fail_loud():
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.slug_of({"id": "x"})


def test_chemin_en_derive_du_fr():
    import build_articles
    assert build_articles.en_path_for("articles/couverture-dynamique.html") \
        == "articles/couverture-dynamique.en.html"


def test_chemin_en_refuse_une_url_inattendue():
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.en_path_for("articles/x.php")


@pytest.mark.parametrize("mots,attendu", [(0, 1), (1, 1), (200, 1), (201, 2), (509, 3)])
def test_temps_de_lecture(mots, attendu):
    """200 mots/min, arrondi au supérieur, plancher à 1."""
    import build_articles
    assert build_articles.reading_minutes(" ".join(["mot"] * mots)) == attendu


def test_frontmatter_separe_du_corps():
    import build_articles
    fm, body = build_articles.parse_source("---\ntldr: Résumé\n---\n\n## Titre\n\nTexte.\n")
    assert fm["tldr"] == "Résumé"
    assert body.lstrip().startswith("## Titre")


def test_tldr_avec_deux_points_preserve():
    """Le `partition(':')` coupe au PREMIER deux-points : la valeur peut en contenir."""
    import build_articles
    fm, _ = build_articles.parse_source("---\ntldr: a : b : c\n---\ncorps\n")
    assert fm["tldr"] == "a : b : c"


@pytest.mark.parametrize("source", ["## Titre\n\nTexte.\n", "---\nautre: x\n---\ncorps\n"])
def test_source_invalide_fail_loud(source):
    """Le TL;DR n'a pas de valeur par défaut sensée : son absence est une erreur de
    rédaction, pas un cas à combler silencieusement."""
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.parse_source(source)


def test_formula_non_interpretee_comme_markdown():
    """Le contenu d'une formule est une donnée : ses `*` et `_` ne sont pas de
    l'emphase Markdown."""
    import build_articles
    out = build_articles.md_to_html("::formula\na*b*c_d_e\n::\n")
    assert '<div class="formula">a*b*c_d_e</div>' in out
    assert "<em>" not in out


def test_formula_echappee():
    import build_articles
    out = build_articles.md_to_html("::formula\na < b & c\n::\n")
    assert "a &lt; b &amp; c" in out


def test_article_inconnu_fail_loud():
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.render_article_page(build_articles.load_profile(), "nexistepas", "fr")


def test_url_absente_fail_loud():
    """`onchain_analytics` n'a pas d'`url` (statut `soon`) : la génération s'arrête
    dans `slug_of`, avant même de chercher une source."""
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.render_article_page(build_articles.load_profile(),
                                           "onchain_analytics", "fr")


def test_source_absente_fail_loud():
    """Une source manquante ne doit jamais produire une page au corps vide.

    Distinct du test précédent : ici l'`url` EXISTE, donc `slug_of` passe et c'est
    bien le contrôle de présence du fichier qui doit lever. Rédigé d'abord avec
    `onchain_analytics`, ce test passait pour la mauvaise raison — un mutant
    remplaçant la levée par `return ""` y survivait."""
    import build_articles
    profile = build_articles.load_profile()
    profile["articles"] = [{"id": "fantome", "url": "articles/fantome.html",
                            "title": {"fr": "F", "en": "F"}, "date": "2026-01", "tags": []}]
    with pytest.raises(build_articles.BuildError, match="source absente"):
        build_articles.render_article_page(profile, "fantome", "fr")
