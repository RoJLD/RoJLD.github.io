"""Le corpus publié, DÉCOUVERT sur le disque — témoin indépendant des listes.

Pourquoi ce module existe, mesuré et non supposé. Sept gardes de ce dépôt
paramétraient leurs cas de test sur une liste écrite à la main :

    PAGES_A_THEME  = (…, "life-architect/index.html", …)
    NAV_DESTINATIONS = (…, "demos")
    @parametrize("page", ("projects", …, "demos"))

Retirer une entrée de ces listes ne fait rougir personne : le cas de test
correspondant disparaît en même temps que la couverture qu'il apportait. Mesuré,
suite entière :

    PAGES_A_THEME perd "life-architect/index.html"  ->  481 passed (au lieu de 488)
    NAV_DESTINATIONS perd "demos"                   ->  485 passed
    la liste des générateurs perd "demos"           ->  487 passed

Aucun rouge, sept tests de moins — et la page la plus fragile du dépôt, celle
qu'aucun builder ne répare, sortait du champ de sa propre garde. C'est le même
défaut que `HTML_SECTIONS` (cf. `test_build_site.py`), et il se corrige de la
même façon : **un test ne peut pas énumérer ses cas depuis l'objet qu'il
surveille**. Il lui faut un témoin qui vit ailleurs.

Ici le témoin est le SITE PUBLIÉ lui-même : les fichiers présents sur le disque
et ce qu'ils déclarent. Une liste ne peut plus rétrécir sans que le disque le
contredise ; et une page NEUVE entre automatiquement dans le champ des gardes,
au lieu d'attendre que quelqu'un pense à l'ajouter.

Les planchers (`_exiger_au_moins`) ferment l'autre sens : si c'est le CORPUS qui
se vide (une page qui perd son script de thème), la découverte rétrécirait sans
bruit. Les planchers nomment donc explicitement ce qui doit exister.
"""
from __future__ import annotations

import functools
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Répertoires d'outillage : jamais servis par GitHub Pages.
#
# Délibérément DUPLIQUÉ depuis `test_liens_internes.EXCLUDED_DIRS` au lieu d'être
# importé : ce module sert de témoin AU scanner de liens, dont c'est justement la
# constante à surveiller. L'importer rendrait le témoin solidaire de ce qu'il
# mesure — mesuré : ajouter `life-architect` à `EXCLUDED_DIRS` retirait la page
# du scan et laissait la suite verte.
OUTILLAGE = {".git", "tools", "node_modules", ".pytest_cache", ".github"}

# Marqueurs observés dans les pages servies.
_PALETTE_SOMBRE = '[data-theme="dark"]'
_LECTURE_THEME = "getItem('theme')"
_ECRITURE_THEME = "setItem('theme'"
_NAV_PARTAGEE = "nav-brand"

_BLOC_NAV = re.compile(r"<nav\b.*?</nav>", re.S)
_HREF = re.compile(r'href="([^"]*)"')
_LIEN_REPERTOIRE = re.compile(r'href="/([^"/]+)/"')
_HORS_DISQUE = ("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")


def _texte(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


@functools.lru_cache(maxsize=1)
def pages_publiees() -> tuple[str, ...]:
    """Toute page HTML réellement servie (chemin relatif POSIX)."""
    return tuple(sorted(
        p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.html")
        if not (OUTILLAGE & set(p.relative_to(ROOT).parts))))


@functools.lru_cache(maxsize=1)
def pages_a_palette() -> tuple[str, ...]:
    """Pages déclarant une palette sombre — elles doivent en déclarer une claire.

    Découvert, pas listé : les deux pages d'articles portent une palette et
    n'étaient dans aucune liste écrite à la main.
    """
    return tuple(p for p in pages_publiees() if _PALETTE_SOMBRE in _texte(p))


@functools.lru_cache(maxsize=1)
def pages_a_boot() -> tuple[str, ...]:
    """Pages qui LISENT le thème mémorisé — elles doivent l'appliquer."""
    return tuple(p for p in pages_publiees() if _LECTURE_THEME in _texte(p))


@functools.lru_cache(maxsize=1)
def pages_qui_persistent_le_theme() -> tuple[str, ...]:
    """Pages qui MÉMORISENT le choix du visiteur (`setItem('theme'`).

    Signal distinct de `pages_a_boot` : il vient du basculeur, pas du script de
    démarrage. Une page qui mémorise sans restaurer perd le choix qu'elle vient
    d'enregistrer ; une page qui restaure sans mémoriser ne peut rien restaurer.
    Les deux ensembles doivent coïncider, et c'est au test de l'exiger.
    """
    return tuple(p for p in pages_publiees() if _ECRITURE_THEME in _texte(p))


@functools.lru_cache(maxsize=1)
def sections_par_topologie_de_la_nav() -> tuple[str, ...]:
    """Les sections de la nav partagée, déduites de la TOPOLOGIE des liens.

    Second témoin de `destinations_nav()`, et il ne partage avec lui aucun
    marqueur : celui-ci ne regarde pas `nav-brand`, seulement qui pointe qui.

    Une nav partagée est un groupe fermé : chacune de ses pages déclare
    exactement les mêmes destinations, et ce sont ses propres membres. On cherche
    donc les groupes `S` tels que la nav de chaque `d` de `S` déclare exactement
    `S`, et on retient le plus grand. `/life-architect/` en forme un aussi — mais
    de taille 1, sa nav ne pointant que sur elle-même : c'est bien une page à
    part, pas une section de la nav partagée.

    Pourquoi ce détour plutôt qu'une liste de six noms : la liste était
    l'attendu écrit à la main d'une valeur découverte. Elle divergeait, donc elle
    défendait quelque chose — mais elle demandait à être tenue à jour, et rien
    ne l'ancrait au site. Deux dérivations qui doivent coïncider n'ont ni l'un ni
    l'autre défaut.
    """
    liens: dict[str, set[str]] = {}
    for d in ROOT.iterdir():
        idx = d / "index.html"
        if not d.is_dir() or d.name in OUTILLAGE or not idx.exists():
            continue
        txt = idx.read_text(encoding="utf-8", errors="replace")
        vus: set[str] = set()
        for bloc in _BLOC_NAV.findall(txt):
            vus |= set(_LIEN_REPERTOIRE.findall(bloc))
        liens[d.name] = vus
    fermes = [s for s in {frozenset(v) for v in liens.values()}
              if s and all(liens.get(d) == set(s) for d in s)]
    if not fermes:
        return ()
    return tuple(sorted(max(fermes, key=len)))


def _resoudre(depuis: str, href: str) -> str | None:
    """Page visée par `href` écrit dans `depuis` (chemin relatif POSIX), ou None.

    Résolution du NAVIGATEUR : `/x/` part de la racine du site, `../y.html` du
    répertoire de la page, un répertoire se lit `index.html`. Hors périmètre :
    schémas externes et ancres pures (elles désignent la page courante, qui est
    déjà dans le corpus).
    """
    if not href or href.startswith(_HORS_DISQUE) or href.startswith("#"):
        return None
    chemin = href.partition("#")[0].partition("?")[0]
    if not chemin:
        return None
    base = ROOT if chemin.startswith("/") else (ROOT / depuis).parent
    cible = pathlib.Path(base / chemin.lstrip("/")).resolve()
    if cible.is_dir():
        cible = cible / "index.html"
    try:
        return cible.relative_to(ROOT).as_posix()
    except ValueError:
        return None


@functools.lru_cache(maxsize=1)
def pages_atteintes_par_la_nav() -> tuple[str, ...]:
    """Pages qu'un visiteur atteint d'un clic depuis la nav partagée.

    Témoin INDÉPENDANT du mécanisme de thème : il ne regarde ni `getItem`, ni
    `setItem`, ni les palettes — seulement les `href` écrits dans les blocs
    `<nav>` qui portent la marque partagée, résolus sur le disque.

    C'est la source d'où doit dériver « quelles pages doivent porter le thème » :
    le choix du visiteur doit survivre à chaque saut de la nav. Écrire cette
    liste à la main la rend rabotable en silence (mesuré : la vider laissait la
    suite à 507 passed) ; la dériver la rend impossible à raboter sans que le
    site publié le contredise.

    Redondance délibérée : chaque page de nav pointe les autres, donc perdre la
    nav d'UNE page ne fait pas disparaître sa cible du témoin — elle reste vue
    depuis les sept autres.
    """
    cibles: set[str] = set()
    for rel in pages_publiees():
        txt = _texte(rel)
        if _NAV_PARTAGEE not in txt:
            continue
        for bloc in _BLOC_NAV.findall(txt):
            if _NAV_PARTAGEE not in bloc:
                continue
            for href in _HREF.findall(bloc):
                cible = _resoudre(rel, href.strip())
                if cible and (ROOT / cible).is_file() and cible.endswith(".html"):
                    cibles.add(cible)
    return tuple(sorted(cibles))


@functools.lru_cache(maxsize=1)
def destinations_nav() -> tuple[str, ...]:
    """Répertoires dont l'`index.html` porte la nav partagée.

    Témoin de `NAV_DESTINATIONS` : une destination retirée de la constante reste
    visible ici, parce que la page continue d'exister et de porter la nav. Le
    marqueur retenu est la marque (`nav-brand`), pas les liens de la nav —
    prendre les liens ferait disparaître le témoin en même temps que le défaut
    à détecter (retirer `/demos/` de la nav).
    """
    return tuple(sorted(
        d.name for d in ROOT.iterdir()
        if d.is_dir() and d.name not in OUTILLAGE
        and (d / "index.html").exists()
        and _NAV_PARTAGEE in (d / "index.html").read_text(encoding="utf-8", errors="replace")))


# ── Le plancher : trois fois écrit à la main, trois fois rabotable ────────────
#
# Sans plancher, une page qui PERDRAIT son script de thème sortirait du champ des
# gardes sans un seul rouge : la découverte rétrécirait avec le défaut.
#
# Ce module a d'abord porté ce plancher, dans une fonction `exiger_le_plancher()`.
# Mesuré : lui faire rendre `[]` laissait la suite à 506 passed. L'attente vivait
# dans le module qu'elle devait tenir.
#
# Le plancher a donc déménagé dans le test, sous la forme d'un ensemble de huit
# noms écrit à la main (`PAGES_QUI_DOIVENT_PORTER_LE_THEME`). Mesuré à son tour :
# le VIDER (`= set()`) laissait la suite à 507 passed — le compte exact du vert de
# référence. Déplacer l'attente d'un module vers un test ne supprime pas le
# défaut, il le remonte d'un étage : une liste que son unique lecteur compare à
# elle-même ne peut pas diverger, donc ne défend rien.
#
# La seule sortie est de faire DÉRIVER l'attente. Elle vient désormais de trois
# signaux disjoints du site publié, qui doivent coïncider :
#
#   `pages_atteintes_par_la_nav()`      les `href` de la nav, résolus sur disque
#   `pages_a_boot()`                    `getItem('theme')` — le script de démarrage
#   `pages_qui_persistent_le_theme()`   `setItem('theme'`  — le basculeur
#
# Aucune mutation d'un seul de ces trois signaux ne peut rétrécir les trois à la
# fois : l'égalité est le plancher, et personne ne peut l'écrire à la main.
# Ce module ne fait que rapporter ce qu'il observe. Il ne décide de rien.
