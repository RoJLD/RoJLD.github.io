"""La nav des six pages déclare les mêmes destinations, et elles viennent de `nav.py`.

Pourquoi cette garde existe, mesuré le 2026-10-15 sur le site publié. La barre
était écrite six fois à la main et les six copies avaient divergé :

    index.html           11 entrées
    projects/, demos/     8 entrées   (manquaient /#education /#skills /#blog)
    explorer/, highlights/, graph/
                          7 entrées   (manquait /#contact en plus)

Aucun test ne le voyait. `test_liens_internes.py` tient les six destinations de
RÉPERTOIRE (`href="/x/"`) : les ancres de l'accueil (`/#education`, `/#skills`,
`/#blog`, `/#contact`) n'entrent dans aucun de ses calculs, et `index.html` à la
racine n'est pas un répertoire — la nav de l'accueil n'était dans aucun groupe
fermé. Un visiteur de `/explorer/` n'avait aucun chemin de nav vers la formation,
les compétences, le blog ni le contact, et la nav étant `position:fixed`, rien ne
défilait pour les atteindre.

Arbitrage 1 du 2026-10-15 : `tools/nav.py` est la source des CINQ sous-pages ;
l'accueil garde son balisage à la main (y mettre une zone BUILD ferait lever
`BuildError` à `build_site.synchroniser_textes_statiques`, la marque contenant
`<b>`). Le lien entre les deux est donc ce fichier : un test, pas un générateur.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import corpus_publie  # noqa: E402
import nav  # noqa: E402

# Population : les cinq répertoires DÉCOUVERTS sur le disque (témoin de
# `corpus_publie`, pas une liste écrite ici), plus l'accueil.
#
# L'accueil est nommé en clair parce que rien ne peut le découvrir : tous les
# calculs de fermeture de `corpus_publie` itèrent les RÉPERTOIRES du dépôt, et
# `index.html` vit à la racine. C'est précisément l'angle mort qui a laissé sa
# nav diverger des cinq autres. `test_la_table_des_pages_couvre_exactement_nav_py`
# ci-dessous empêche cette table de rétrécir ou de dériver de `nav.py`.
PAGES = {"index.html": "accueil"}
PAGES.update({f"{d}/index.html": d for d in corpus_publie.destinations_nav()})

_BLOC_NAV = re.compile(r"<nav\b.*?</nav>", re.S)
_HREF = re.compile(r'href="([^"]*)"')
_MARQUE = "nav-brand"

# La marque, et elle seule, est exclue de la comparaison d'égalité.
#
# Elle n'est pas une entrée de la barre : les cinq sous-pages portent
# `<a class="nav-brand" href="/">`, l'accueil un `<span class="nav-brand">` SANS
# href (index.html:207) — il ne se lie pas à lui-même. Une égalité stricte des
# ensembles resterait donc ROUGE pour toujours, et `/` en est le résidu
# irréductible (mesuré : `TOUS LES ENSEMBLES EGAUX ? False`). Soustraire `/` sans
# le dire est la façon dont une garde pourrit ; l'invariant réel est gardé à côté,
# par `test_chaque_sous_page_ramene_a_l_accueil`.
RETOUR_ACCUEIL = "/"


def _destinations_ecrites(rel: str) -> list[str]:
    """Les `href` écrits dans le bloc `<nav>` de la page servie `rel`, EN ORDRE.

    Une LISTE depuis le 2026-10-19, et non plus un ensemble : un ensemble perd
    l'ordre des onze entrées (que rien ne vérifiait) et perd les doublons.

    Lu sur l'ARTEFACT publié, pas sur la sortie du générateur : c'est ce qu'un
    visiteur reçoit. La garde jumelle sur la sortie des générateurs vit dans
    `test_liens_internes.py::test_le_generateur_emet_toute_la_nav`.
    """
    txt = (ROOT / rel).read_text(encoding="utf-8")
    vus: list[str] = []
    for bloc in _BLOC_NAV.findall(txt):
        if _MARQUE not in bloc:
            continue
        vus += [h.strip() for h in _HREF.findall(bloc)]
    assert vus, f"{rel} : aucun bloc <nav> portant la marque {_MARQUE!r}"
    return vus


def test_la_table_des_pages_couvre_exactement_nav_py():
    """Plancher : la table ci-dessus ne peut ni rétrécir ni dériver de `nav.py`.

    Sans cette assertion, retirer une page de `PAGES` retirerait son cas
    paramétré avec elle — la couverture rétrécirait sans un seul rouge, défaut
    que `corpus_publie` documente et que ce fichier n'a pas le droit de rejouer.
    Et une page ajoutée à `nav._PAGES` sans être publiée (ou l'inverse) serait un
    rendu que personne ne confronte au disque.
    """
    assert set(PAGES.values()) == set(nav.pages_connues()), (
        f"pages publiées portant la nav {sorted(PAGES.values())} désaccordées "
        f"avec celles que nav.py sait rendre {sorted(nav.pages_connues())}")


@pytest.mark.parametrize("rel", sorted(PAGES))
def test_chaque_page_declare_exactement_les_destinations_de_nav_py(rel):
    """Les destinations écrites dans la page servie sont celles que `nav.py` rend,
    dans le même ORDRE.

    L'attendu ne vient pas d'une liste recopiée ici : il vient de `nav.ENTREES`,
    l'unique source. Une entrée ajoutée à `nav.py` et non republiée rougit ; une
    entrée perdue par une page rougit ; et comme `nav.py` rend la même liste aux
    six pages (aux ancres près, `#blog` sur l'accueil et `/#blog` ailleurs),
    l'égalité deux à deux des six navs en découle.

    Séquences et non ensembles depuis le 2026-10-19 : l'ordre de la barre est ce
    qu'un visiteur lit et ce que la tabulation suit, et rien ne le tenait. Deux
    entrées permutées entre `nav.py` et une page publiée passaient vertes.

    Ce que ce test ne peut PAS voir, et c'est pourquoi les deux planchers
    ci-dessous existent : `nav.ENTREES` est ici l'attendu ET la source des cinq
    sous-pages. Une entrée retirée de `nav.ENTREES`, les cinq pages régénérées et
    la même ligne retirée de l'accueil écrit à la main — tout coïncide, et ce
    test est vert sur une nav amputée.
    """
    page = PAGES[rel]
    ecrites = [d for d in _destinations_ecrites(rel) if d != RETOUR_ACCUEIL]
    attendues = list(nav.destinations(page))
    assert ecrites == attendues, (
        f"{rel} : la nav ne déclare pas les destinations de nav.py dans son ordre "
        f"— écrit {ecrites}, attendu {attendues} ; "
        f"absente(s) {sorted(set(attendues) - set(ecrites))}, "
        f"en trop {sorted(set(ecrites) - set(attendues))}")


def test_la_liste_de_nav_py_egale_les_cles_nav_de_site_texts():
    """PLANCHER 1 : la liste des entrées, confrontée à un fichier qui n'est pas elle.

    Mesuré le 2026-10-19 par mutation, sur une copie vierge
    (`git archive | tar -x`) : retirer `("nav_edu", "#education")` de
    `nav.ENTREES`, régénérer les cinq sous-pages et retirer la ligne
    correspondante de `index.html` laissait la suite ENTIÈREMENT VERTE. Onze
    entrées devenaient dix, et tous les témoins étaient d'accord — parce qu'ils
    dérivaient tous de la même liste. La même mutation sur une entrée de
    RÉPERTOIRE (`("nav_graph", "graph/")`) rougissait, elle, parce que le dossier
    `graph/` reste sur le disque et que la topologie ne ferme plus. Les ancres
    n'ont aucun équivalent topologique : il leur faut ce plancher.

    `site_texts.json` est le témoin parce qu'il existe pour une AUTRE raison —
    les libellés, éditables depuis le cockpit — et qu'il est déjà tenu dans les
    deux langues par `test_site_texts.py`. Les deux sens sont exigés : une clé
    sans entrée est un libellé que personne n'affiche, une entrée sans clé fait
    lever `NavError` à la construction.
    """
    cles_nav = [cle for cle, _ in nav.ENTREES]
    cles_textes = list(corpus_publie.cles_nav_de_site_texts())
    assert cles_nav == cles_textes, (
        f"`nav.ENTREES` et les clés `nav_*` de site_texts.json divergent — "
        f"nav.py {cles_nav}, site_texts {cles_textes} ; "
        f"entrée(s) sans libellé {sorted(set(cles_nav) - set(cles_textes))}, "
        f"libellé(s) sans entrée {sorted(set(cles_textes) - set(cles_nav))}")


def test_l_accueil_declare_les_memes_entrees_dans_le_meme_ordre():
    """PLANCHER 2 : l'accueil écrit à la main, témoin de la liste ET de l'ordre.

    L'accueil n'est pas généré (arbitrage 1) : ses onze `data-i18n` sont tapés à
    la main. Ils ne peuvent donc pas suivre une mutation de `nav.ENTREES` sans
    que quelqu'un les édite — c'est ce qui en fait un témoin, et pas un reflet.

    Avec le plancher 1, la mutation « ancre » doit désormais franchir TROIS
    fichiers écrits pour des raisons différentes (`tools/nav.py`,
    `site_texts.json`, `index.html`) pour passer inaperçue, là où elle n'en
    franchissait qu'un seul plus un `git`-régénère.
    """
    assert list(corpus_publie.cles_i18n_de_la_nav_de_l_accueil()) == \
        [cle for cle, _ in nav.ENTREES], (
        f"la nav de l'accueil ne déclare plus les entrées de nav.py dans l'ordre "
        f"— accueil {list(corpus_publie.cles_i18n_de_la_nav_de_l_accueil())}, "
        f"nav.py {[cle for cle, _ in nav.ENTREES]}")


def test_chaque_sous_page_ramene_a_l_accueil():
    """L'invariant que l'exclusion de `/` ci-dessus ne doit pas emporter.

    Chaque sous-page porte un lien vers `/` (sa marque) ; l'accueil n'en a pas
    besoin — c'est lui. Si demain la marque de l'accueil devenait un lien vers
    `/`, c'est cette assertion qui bougerait, d'une ligne, et le commentaire dit
    où regarder.
    """
    for rel, page in sorted(PAGES.items()):
        liens = _destinations_ecrites(rel)
        if page == "accueil":
            assert RETOUR_ACCUEIL not in liens, (
                "l'accueil porte maintenant un lien vers `/` — l'exclusion de la "
                "marque dans la garde d'égalité n'a plus de raison d'être")
        else:
            assert RETOUR_ACCUEIL in liens, (
                f"{rel} : plus aucun lien de nav vers l'accueil — la page devient "
                "un cul-de-sac, comme /academy/ l'est depuis un autre dépôt")


def test_nav_py_refuse_une_page_inconnue():
    """Fail-loud : une faute de frappe sur le nom de page ne doit pas produire
    une barre sans entrée active, silencieusement."""
    with pytest.raises(nav.NavError, match="page inconnue"):
        nav.render_nav("highlight")
    with pytest.raises(nav.NavError, match="page inconnue"):
        nav.destinations("explorateur")


def test_nav_py_refuse_un_libelle_manquant(tmp_path):
    """Fail-loud sur `site_texts.json` : une entrée sans libellé est un trou dans
    la barre, et les cinq générateurs ne jouent pas `valider_site_texts`."""
    import json

    textes = json.loads((ROOT / "site_texts.json").read_text(encoding="utf-8"))
    del textes["en"]["nav_graph"]
    p = tmp_path / "site_texts.json"
    p.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(nav.NavError, match="nav_graph"):
        nav.charger_libelles(p)
