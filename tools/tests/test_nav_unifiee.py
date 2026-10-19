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


def _destinations_ecrites(rel: str) -> set[str]:
    """Les `href` écrits dans le bloc `<nav>` de la page servie `rel`.

    Lu sur l'ARTEFACT publié, pas sur la sortie du générateur : c'est ce qu'un
    visiteur reçoit. La garde jumelle sur la sortie des générateurs vit dans
    `test_liens_internes.py::test_le_generateur_emet_toute_la_nav`.
    """
    txt = (ROOT / rel).read_text(encoding="utf-8")
    vus: set[str] = set()
    for bloc in _BLOC_NAV.findall(txt):
        if _MARQUE not in bloc:
            continue
        vus |= {h.strip() for h in _HREF.findall(bloc)}
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
    """Les destinations écrites dans la page servie sont celles que `nav.py` rend.

    L'attendu ne vient pas d'une liste recopiée ici : il vient de `nav.ENTREES`,
    l'unique source. Une entrée ajoutée à `nav.py` et non republiée rougit ; une
    entrée perdue par une page rougit ; et comme `nav.py` rend la même liste aux
    six pages (aux ancres près, `#blog` sur l'accueil et `/#blog` ailleurs),
    l'égalité deux à deux des six navs en découle.
    """
    page = PAGES[rel]
    ecrites = _destinations_ecrites(rel) - {RETOUR_ACCUEIL}
    attendues = set(nav.destinations(page))
    assert ecrites == attendues, (
        f"{rel} : la nav ne déclare pas les destinations de nav.py — "
        f"absente(s) {sorted(attendues - ecrites)}, "
        f"en trop {sorted(ecrites - attendues)}")


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
