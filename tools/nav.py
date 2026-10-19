#!/usr/bin/env python3
"""nav.py — LA barre de navigation des pages du site, émise d'une seule source.

Pourquoi ce module existe, mesuré et non supposé. La nav était écrite SIX fois à
la main : dans `index.html` (11 entrées) et dans les littéraux de
`build_projects`, `build_demos` (8 entrées), `build_highlights`, `build_browse`,
`build_graph` (7 entrées). Mesuré le 2026-10-15 sur le site publié : `/#education`,
`/#skills`, `/#blog` et `/#contact` sont ABSENTS du HTML de `/highlights/`,
`/explorer/` et `/graph/` — pas mal pointés, absents. Et l'accueil ne portait
aucun lien vers `/demos/` : son entrée « Démos » désignait sa propre section
`#demos`, si bien que la galerie n'était atteignable depuis l'accueil que par les
deux vignettes de cette section.

Six copies d'une liste ne restent pas d'accord. Les gardes de
`tools/tests/test_liens_internes.py` tenaient les six destinations de
RÉPERTOIRE ; rien ne tenait les ancres de l'accueil, qui se sont donc perdues
une page après l'autre.

Ce que ce module décide, et ce qu'il ne décide pas :

  * il décide la LISTE et son ORDRE (`ENTREES`), donc l'ensemble des
    destinations est le même sur les six pages, par construction ;
  * il ne décide AUCUN libellé : ils viennent de `site_texts.json`, la source
    déjà éditable depuis le cockpit. Un libellé écrit ici serait une deuxième
    source de vérité, et le texte statique FR de l'accueil doit de toute façon
    égaler le dictionnaire (`build_site.synchroniser_textes_statiques`, tenu par
    `test_le_texte_statique_fr_egale_le_dictionnaire`).

L'ACCUEIL N'EST PAS GÉNÉRÉ (arbitrage 1 du 2026-10-15). `index.html` garde son
balisage de nav écrit à la main, et c'est un TEST qui tient l'accord
(`tools/tests/test_nav_unifiee.py`), pas ce module. La raison est mesurée :
`index.html` porte 10 régions `<!-- BUILD:x -->` et aucune pour la nav ; en
ajouter une fait entrer `build_site.synchroniser_textes_statiques` dans le
circuit, et celle-ci lève `BuildError` quand l'élément porteur d'un `data-i18n`
contient du balisage. Or la marque EST du balisage :
`<span class="nav-brand">R<b>.</b> Denis</span>`. On achèterait un plantage de
build pour économiser onze lignes de HTML. `render_nav("accueil")` reste donc le
rendu de RÉFÉRENCE — ce que l'accueil devrait déclarer — et non ce que le build
y injecte.

Deux dialectes de traduction coexistent dans le site, et ce module les sert tous
les deux au lieu d'en imposer un :

  * l'accueil traduit par `data-i18n="<clé>"` + le dictionnaire `const i18n`
    injecté par `build_site` ;
  * les sous-pages traduisent par `data-fr` / `data-en` lus par leur propre
    `applyBrowseLang`.

Unifier les deux dialectes serait un autre chantier (il faudrait embarquer le
dictionnaire dans cinq pages, ou le retirer de l'accueil) ; unifier la LISTE n'a
pas à l'attendre.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_TEXTS = ROOT / "site_texts.json"


class NavError(Exception):
    """Fail-loud : une nav incomplète est un cul-de-sac publié, pas un détail."""


# ── La liste, et elle seule ───────────────────────────────────────────────────
#
# (clé de site_texts.json, cible). L'ordre est celui de la barre, de gauche à
# droite : les trois sections de l'accueil, puis les six pages, puis les deux
# dernières sections.
#
# Deux formes de cible, et la différence porte tout le module :
#   "#<id>"   une section de l'accueil — `#<id>` sur l'accueil, `/#<id>` ailleurs
#   "<nom>/"  une page du site         — `/<nom>/` partout
#
# « Démos » désigne la GALERIE `/demos/`, pas la section `#demos` de l'accueil.
# Un libellé ne peut pas avoir deux destinations selon la page qui l'affiche :
# c'était le cas avant (section sur l'accueil, galerie sur les cinq autres), et
# c'est ce qui privait l'accueil du seul lien de nav vers la galerie. La section
# `#demos` reste sur l'accueil, atteignable au défilement, et ses deux vignettes
# mènent à `/demos/#bs` et `/demos/#mc`.
ENTREES: tuple[tuple[str, str], ...] = (
    ("nav_exp", "#experience"),
    ("nav_edu", "#education"),
    ("nav_skills", "#skills"),
    ("nav_demos", "demos/"),
    ("nav_projects", "projects/"),
    ("nav_explorer", "explorer/"),
    ("nav_highlights", "highlights/"),
    ("nav_academy", "academy/"),
    ("nav_graph", "graph/"),
    ("nav_blog", "#blog"),
    ("nav_contact", "#contact"),
)

# ── Ce qui distingue les pages, et rien de plus ──────────────────────────────
#
# Tout ce qui diffère d'une page à l'autre est ici, nommé. Le reste est commun
# par construction. Ces écarts ne sont pas des caprices :
#
#   `id="nav"`      l'accueil seule : `index.html` fait
#                   `document.getElementById('nav').classList.toggle('scrolled', …)`
#                   au défilement. Les sous-pages n'ont pas ce comportement.
#   marque <span>   l'accueil ne se lie pas à elle-même ; les sous-pages portent
#                   `<a class="nav-brand" href="/">`. La marque `nav-brand` doit
#                   vivre DANS le bloc <nav> : deux témoins indépendants la
#                   cherchent là (cf. `tools/tests/corpus_publie.py`).
#   dialecte        voir le docstring du module.
#   `tgTheme`       nom du basculeur de thème dans les sous-pages ; l'accueil
#                   l'appelle `toggleTheme`. Renommer l'un des deux toucherait
#                   le témoin du thème (`test_theme_clair.BASCULEUR`) sans rien
#                   corriger ici.
_PAGES: dict[str, dict[str, object]] = {
    "accueil": {
        "nav_attrs": ' id="nav"',
        "marque": "span",
        "dialecte": "i18n",
        "indent": " " * 4,
        "pas": " " * 4,
        "theme_fn": "toggleTheme()",
        "titre_langue": "Switch language",
        "titre_theme": "Toggle theme",
    },
    "projects": {},
    "demos": {},
    "explorer": {},
    "highlights": {},
    "graph": {},
}

_DEFAUTS: dict[str, object] = {
    "nav_attrs": "",
    "marque": "a",
    "dialecte": "fr_en",
    "indent": " " * 2,
    "pas": " " * 2,
    "theme_fn": "tgTheme()",
    "titre_langue": "Langue",
    "titre_theme": "Thème",
}

MARQUE = "R<b>.</b> Denis"


def _reglage(page: str, nom: str) -> object:
    if page not in _PAGES:
        raise NavError(f"page inconnue de la nav partagée : {page!r} "
                       f"(connues : {', '.join(sorted(_PAGES))})")
    return _PAGES[page].get(nom, _DEFAUTS[nom])


def pages_connues() -> tuple[str, ...]:
    """Les pages que ce module sait rendre — témoin pour les tests."""
    return tuple(sorted(_PAGES))


def charger_libelles(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    """`{"fr": {...}, "en": {...}}` restreint aux clés de la nav. Fail-loud.

    Une clé manquante d'un côté ne doit pas produire une entrée sans libellé :
    `site_texts.json` est validé par `build_site.valider_site_texts` (mêmes clés
    en fr et en), mais ce module est aussi appelé par les cinq générateurs de
    sous-page, qui ne jouent pas cette validation. Il la refait sur SES clés.
    """
    p = Path(path) if path else SITE_TEXTS
    textes = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for lang in ("fr", "en"):
        if not isinstance(textes.get(lang), dict):
            raise NavError(f'{p.name} : section {lang!r} absente ou non-objet')
        manquantes = [cle for cle, _ in ENTREES if not str(textes[lang].get(cle, "")).strip()]
        if manquantes:
            raise NavError(f"{p.name} : libellé(s) de nav absent(s) en {lang} : "
                           f"{', '.join(manquantes)}")
        out[lang] = {cle: textes[lang][cle] for cle, _ in ENTREES}
    return out


def href(cible: str, page: str) -> str:
    """URL écrite dans la page `page` pour la cible `cible`.

    Une ancre reste NUE sur l'accueil (`#blog`) et devient absolue ailleurs
    (`/#blog`). L'ancre nue est refusée hors de l'accueil par
    `validate_profile` et par le scan anti-404 : sa cible dépend de la page qui
    l'affiche, et `#blog` sur `/explorer/` est un cul-de-sac silencieux. La forme
    `/#blog` est la bonne — et jamais `/blog/`, qui n'existe pas (mesuré le
    2026-10-15 : https://robin-denis.com/blog/ -> 404).
    """
    if page not in _PAGES:
        raise NavError(f"page inconnue de la nav partagée : {page!r} "
                       f"(connues : {', '.join(sorted(_PAGES))})")
    if not cible.startswith("#"):
        return "/" + cible
    return cible if page == "accueil" else "/" + cible


def _attrs_langue(cle: str, libelles: dict[str, dict[str, str]], dialecte: str) -> str:
    if dialecte == "i18n":
        return f' data-i18n="{cle}"'
    fr = html.escape(libelles["fr"][cle], quote=True)
    en = html.escape(libelles["en"][cle], quote=True)
    return f' data-fr="{fr}" data-en="{en}"'


def render_entrees(page: str, libelles: dict[str, dict[str, str]] | None = None) -> str:
    """Les onze `<a>` de la barre, une par ligne, pour la page `page`.

    L'entrée active porte `class="on"` — et rien d'autre. `build_projects`
    écrivait `class="nav-projects on"`, la première classe ne servant qu'à sa
    propre règle d'amputation mobile (`.nav-r a:not(.nav-projects)`) : une classe
    de plus pour exprimer ce que `.on` dit déjà sur les cinq autres pages.
    """
    lib = libelles if libelles is not None else charger_libelles()
    dialecte = str(_reglage(page, "dialecte"))
    indent = str(_reglage(page, "indent")) + str(_reglage(page, "pas"))
    lignes = []
    for cle, cible in ENTREES:
        actif = cible == f"{page}/"
        classe = ' class="on"' if actif else ""
        texte = html.escape(lib["fr"][cle], quote=False)
        lignes.append(f'{indent}<a{classe} href="{href(cible, page)}"'
                      f'{_attrs_langue(cle, lib, dialecte)}>{texte}</a>')
    return "\n".join(lignes)


def render_boutons(page: str) -> str:
    """Les deux boutons de contrôle (langue, thème), dans leur `.nav-btns`.

    Le groupe est un FRÈRE de la rangée défilante, jamais dedans (arbitrage 2 du
    2026-10-15, mesuré sur deux copies patchées servies en HTTP) : boutons hors
    de `.nav-r`, `#langBtn` et `#themeBtn` à l'écran aux six largeurs testées ;
    boutons DANS `.nav-r`, `#langBtn` à x=1002 pour une fenêtre de 390 px, 1016
    pour 768, 1028 pour 1024 — les deux boutons hors écran, et la nav étant
    `position:fixed`, plus atteignables que par un glissement horizontal de la
    rangée. Un contrôle qui se déplace avec le contenu défilant n'est plus un
    contrôle.

    Le bouton de langue est émis sur les SIX pages. Mesuré le 2026-10-15 :
    `document.getElementById('langBtn')` rend `null` sur `/projects/` et
    `/demos/`, dont le `<html>` n'a pas de `data-lang` — un visiteur qui choisit
    EN sur l'accueil arrive sur ces deux pages sans aucun moyen d'en changer, et
    l'attribut `lang` du document annonce `fr` quoi qu'il ait choisi.
    """
    pas = str(_reglage(page, "pas"))
    indent = str(_reglage(page, "indent"))
    dedans = indent + pas
    return (f'{indent}<div class="nav-btns">\n'
            f'{dedans}<button class="ctrl-btn lang-btn" onclick="toggleLang()" id="langBtn"'
            f' title="{_reglage(page, "titre_langue")}">FR</button>\n'
            f'{dedans}<button class="ctrl-btn" onclick="{_reglage(page, "theme_fn")}"'
            f' id="themeBtn" title="{_reglage(page, "titre_theme")}">🌙</button>\n'
            f'{indent}</div>')


def render_nav(page: str) -> str:
    """Le bloc `<nav>` complet de la page `page`, marque et boutons compris.

    `page` vaut `"accueil"` ou le nom du répertoire servi (`"projects"`,
    `"demos"`, `"explorer"`, `"highlights"`, `"graph"`). Une page inconnue est
    refusée : c'est elle qui décide quelle entrée est active, donc une faute de
    frappe produirait une barre sans entrée active, silencieusement.
    """
    lib = charger_libelles()
    indent = str(_reglage(page, "indent"))
    if _reglage(page, "marque") == "span":
        marque = f'{indent}<span class="nav-brand">{MARQUE}</span>'
    else:
        marque = f'{indent}<a class="nav-brand" href="/">{MARQUE}</a>'
    return (f'<nav{_reglage(page, "nav_attrs")}><div class="nav-i">\n'
            f"{marque}\n"
            f'{indent}<div class="nav-r">\n'
            f"{render_entrees(page, lib)}\n"
            f"{indent}</div>\n"
            f"{render_boutons(page)}\n"
            "</div></nav>")


def destinations(page: str = "accueil") -> tuple[str, ...]:
    """Les onze URL émises pour `page` — outil de test et de diagnostic.

    La marque (`/`) n'en fait pas partie : elle n'est pas une entrée de la barre,
    et l'accueil n'en porte pas (cf. `test_nav_unifiee.py`).
    """
    return tuple(href(cible, page) for _, cible in ENTREES)


def main() -> int:
    for page in pages_connues():
        print(f"[nav] {page:11s} {len(ENTREES)} entrées -> {' '.join(destinations(page))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
