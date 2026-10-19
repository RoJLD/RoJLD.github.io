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
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

# La déclaration des chemins servis par un AUTRE dépôt est PARTAGÉE avec le
# scanner, à la différence d'`OUTILLAGE` ci-dessous. Ce n'est pas une constante
# du scanner que ce module surveille : c'est un fait de déploiement (GitHub Pages
# sert `/academy/` depuis RoJLD/academy), et elle est tenue dans les deux sens
# par ses propres tests — retirer une entrée rougit le scan des liens, en
# ajouter une qui existe sur le disque rougit
# `test_un_chemin_servi_ailleurs_n_existe_pas_dans_ce_site`.
import servi_ailleurs  # noqa: E402

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
_LECTURE_LANGUE = "getItem('lang')"
_ECRITURE_THEME = "setItem('theme'"
_ECRITURE_LANGUE = "setAttribute('lang'"
_DICTIONNAIRE_I18N = "const i18n"
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
def pages_qui_basculent_la_langue() -> tuple[str, ...]:
    """Pages qui LISENT la langue mémorisée (`getItem('lang')`).

    Symétrique exact de `pages_a_boot()` pour le thème, et la propriété
    défendue est la même : *mon choix suit la navigation*. Mesuré le
    2026-10-15 : `/projects/` et `/demos/` ne portaient AUCUN mécanisme de
    langue — ni bouton, ni `data-lang`, ni lecture de la clé. Un visiteur qui
    avait choisi EN sur l'accueil les recevait en français, et aucune garde ne
    le disait : la seule qui exerce la bascule
    (`test_lang_switch_behaviour`) énumère ses deux pages à la main.
    """
    return tuple(p for p in pages_publiees() if _LECTURE_LANGUE in _texte(p))


@functools.lru_cache(maxsize=1)
def pages_qui_ecrivent_l_attribut_langue() -> tuple[str, ...]:
    """Pages qui POSENT `lang` sur le document (`setAttribute('lang'`).

    Second témoin de la bascule, distinct de `pages_qui_basculent_la_langue()` :
    celui-là voit la LECTURE du choix mémorisé, celui-ci l'ÉCRITURE de l'attribut
    que lit le lecteur d'écran. C'est cette écriture-là que WCAG 3.1.1 juge — une
    page pourrait traduire ses textes sans toucher `lang`, ou l'inverse (poser
    `lang="en"` sur un corps français : c'est exactement ce que `/projects/` et
    `/demos/` ont fait du 2026-10-19 au correctif du même jour).
    """
    return tuple(p for p in pages_publiees() if _ECRITURE_LANGUE in _texte(p))


class _CompteurDeTextes(HTMLParser):
    """Compte le texte VISIBLE d'une page, traduisible ou nu, nav mise à part.

    Un élément est traduisible s'il porte `data-fr` ET `data-en` (dialecte des
    sous-pages), ou `data-i18n` SI la page embarque le dictionnaire
    (`const i18n`, dialecte de l'accueil) — sans dictionnaire, `data-i18n` est un
    marqueur mort : mesuré le 2026-10-19, `/demos/` en porte deux (`bs_vol`,
    `bs_mat`) qu'aucun script de cette page ne lit. Les compter comme traduits
    aurait fausse le verdict de la page.

    Le texte hérite : ce qui est dans un élément traduisible l'est aussi.
    """

    _SANS_FERMETURE = {"br", "img", "input", "meta", "link", "hr", "source",
                       "path", "circle", "rect", "line", "polygon", "polyline",
                       "use", "stop", "area", "col", "embed", "track", "wbr"}

    def __init__(self, dictionnaire: bool):
        super().__init__(convert_charrefs=True)
        self._dico = dictionnaire
        self._pile: list[tuple[str, bool, bool]] = []   # (balise, traduisible, nav)
        self.traduisibles: list[str] = []
        self.nues: list[str] = []
        self.nav: list[str] = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        trad = (any(t for _, t, _ in self._pile)
                or ("data-fr" in d and "data-en" in d)
                or ("data-i18n" in d and self._dico))
        nav = any(n for _, _, n in self._pile) or tag == "nav"
        if tag not in self._SANS_FERMETURE:
            self._pile.append((tag, trad, nav))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        for i in range(len(self._pile) - 1, -1, -1):
            if self._pile[i][0] == tag:
                del self._pile[i:]
                return

    def handle_data(self, data):
        texte = " ".join(data.split())
        if not texte or not any(c.isalnum() for c in texte):
            return
        balise = self._pile[-1][0] if self._pile else "?"
        if balise in ("script", "style"):
            return
        if any(n for _, _, n in self._pile):
            self.nav.append(texte)
        elif any(t for _, t, _ in self._pile):
            self.traduisibles.append(texte)
        else:
            self.nues.append(texte)


@functools.lru_cache(maxsize=1)
def traduction_par_page() -> dict[str, dict[str, int]]:
    """Pour chaque page servie : combien de chaînes visibles sont traduisibles.

    Ce module ne décide de rien, il rapporte. C'est au test d'exiger que la
    langue ANNONCÉE par une page soit celle que son contenu livre.
    """
    out: dict[str, dict[str, int]] = {}
    for rel in pages_publiees():
        texte = _texte(rel)
        c = _CompteurDeTextes(_DICTIONNAIRE_I18N in texte)
        c.feed(texte)
        out[rel] = {"traduisibles": len(c.traduisibles),
                    "nues": len(c.nues),
                    "nav": len(c.nav)}
    return out


def pages_majoritairement_traduites() -> tuple[str, ...]:
    """Pages dont PLUS DE LA MOITIÉ du texte visible hors nav est traduisible.

    Le seuil n'est pas un réglage : c'est l'énoncé de WCAG 3.1.1. L'attribut
    `lang` déclare la langue PAR DÉFAUT du document ; une page ne peut l'annoncer
    en anglais que si son texte est, en majorité, disponible en anglais.

    Marge mesurée le 2026-10-19, et elle est large : la pire page verte est
    l'accueil à 67,4 % (186 traduisibles contre 90 nues), puis `/highlights/` à
    70,4 % (69 contre 29) ; les deux pages rouges sont à 0,0 % tout rond
    (`/projects/` 0 contre 174, `/demos/` 0 contre 33). Entre 0 % et 67 %, le
    seuil n'est pas une valeur à régler.
    """
    return tuple(rel for rel, n in traduction_par_page().items()
                 if n["traduisibles"] > n["nues"])


def _servie_ailleurs(nom: str) -> bool:
    """`/nom/` est servi par un autre dépôt du domaine (cf. `servi_ailleurs`)."""
    return servi_ailleurs.depot_qui_sert(nom + "/") is not None


@functools.lru_cache(maxsize=1)
def _groupe_ferme_de_la_nav() -> frozenset[str]:
    """Le plus grand groupe fermé de la nav partagée, membres servis ailleurs compris.

    Une nav partagée est un groupe fermé : chacune de ses pages déclare
    exactement les mêmes destinations, et ce sont ses propres membres. On cherche
    donc les groupes `S` tels que la nav de chaque `d` de `S` déclare exactement
    `S`, et on retient le plus grand. `/life-architect/` en formait un aussi —
    mais de taille 1, sa nav ne pointant que sur elle-même : c'était bien une page
    à part, pas une section de la nav partagée.

    Un membre servi par un AUTRE dépôt (`/academy/`, RoJLD/academy, depuis le
    2026-10-14) n'a pas de page sur ce disque : sa nav ne peut pas être lue, il
    est donc admis dans le groupe sans elle. Il ne dispense personne d'autre :
    chaque page LOCALE du groupe doit toujours le déclarer, si bien qu'une seule
    nav qui le perd casse la fermeture. Un groupe fait de seuls membres servis
    ailleurs ne serait fermé que par vacuité : il est écarté.
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
              if any(not _servie_ailleurs(d) for d in s)
              and all(liens.get(d) == set(s) for d in s if not _servie_ailleurs(d))]
    if not fermes:
        return frozenset()
    return max(fermes, key=len)


def sections_par_topologie_de_la_nav() -> tuple[str, ...]:
    """Les sections LOCALES de la nav partagée, déduites de la TOPOLOGIE des liens.

    Second témoin de `destinations_nav()`, et il ne partage avec lui aucun
    marqueur : celui-ci ne regarde pas `nav-brand`, seulement qui pointe qui
    (cf. `_groupe_ferme_de_la_nav`).

    Pourquoi ce détour plutôt qu'une liste de six noms : la liste était
    l'attendu écrit à la main d'une valeur découverte. Elle divergeait, donc elle
    défendait quelque chose — mais elle demandait à être tenue à jour, et rien
    ne l'ancrait au site. Deux dérivations qui doivent coïncider n'ont ni l'un ni
    l'autre défaut.
    """
    return tuple(sorted(d for d in _groupe_ferme_de_la_nav() if not _servie_ailleurs(d)))


def destinations_nav_servies_ailleurs() -> tuple[str, ...]:
    """Les destinations de la nav partagée qu'un AUTRE dépôt sert (`academy`).

    Découvertes dans la même topologie que les sections locales : un lien que
    toutes les navs portent, et que la déclaration `servi_ailleurs` attribue à
    un autre dépôt. Ni `destinations_nav()` ni `pages_atteintes_par_la_nav()` ne
    peuvent les voir — elles lisent le disque, où ces pages n'existent pas.
    """
    return tuple(sorted(d for d in _groupe_ferme_de_la_nav() if _servie_ailleurs(d)))


# ── Les destinations COMPLÈTES de la nav : ancres comprises, accueil compris ──
#
# `_LIEN_REPERTOIRE` ne reconnaît qu'une destination écrite `href="/x/"`, et
# `_groupe_ferme_de_la_nav()` n'itère que les RÉPERTOIRES du dépôt. Deux angles
# morts qui se cumulaient, mesurés le 2026-10-15 :
#
#   * `index.html` à la racine n'est pas un répertoire : la nav de l'accueil
#     n'entrait dans AUCUN calcul de fermeture ;
#   * une entrée de nav qui pointe une section (`/#education`, `/#skills`,
#     `/#blog`, `/#contact`) n'est pas un répertoire : elle était invisible.
#
# Résultat : l'accueil portait 11 entrées, /projects/ et /demos/ 8, les trois
# autres 7 — et la fermeture tenait quand même, parce qu'elle ne comparait que
# les six répertoires. Quatre destinations manquaient sur cinq pages, et la
# suite entière restait verte.
_DESTINATION_NAV = re.compile(r'href="(/[^"]*|#[^"]*)"')


# Préfixe d'une destination que la normalisation NE RECONNAÎT PAS.
#
# `_normaliser_destination` rendait `None` dans ce cas, et son unique appelant
# écrivait `if dest: vues.add(dest)` : toute forme inattendue était donc écartée
# EN SILENCE. Mesuré le 2026-10-19 : `href="/graph"` (sans barre finale),
# `href="/a/b/"` ou `href="/x.html"` dans la nav disparaissaient du témoin, et la
# page semblait déclarer une destination de moins — mais si les SIX pages
# portaient la même forme, l'ensemble comparé rétrécissait partout à la fois et
# l'égalité restait verte. Un témoin qui jette ce qu'il ne comprend pas ne
# rapporte plus ce que les pages déclarent : il rapporte ce qu'il sait lire.
#
# La destination inconnue est donc NOMMÉE et rendue, à charge pour le test de la
# refuser (`test_chaque_page_de_la_nav_declare_les_memes_destinations_ancres_comprises`).
NON_RECONNUE = "?? forme de destination non reconnue : "


def _normaliser_destination(rel: str, href: str) -> str:
    """Destination canonique d'un href de nav, vue depuis la page `rel`.

    `#education` écrit sur l'accueil et `/#education` écrit sur une sous-page
    désignent la MÊME chose : la section `education` de l'accueil. Les deux se
    normalisent donc en `/#education` — sans quoi la nav de l'accueil et celle
    des sous-pages seraient incomparables, et c'est précisément pour cela que
    quatre destinations ont pu manquer sur cinq pages sans un rouge.

    Une ancre NUE écrite ailleurs que sur l'accueil (`#contact` sur
    /projects/) désigne une section de la page courante, pas celle de
    l'accueil : elle rend une destination qui lui est propre, afin de ne jamais
    pouvoir passer pour l'ancre de l'accueil (c'est la régression publiée que
    `test_validateur_refuse_une_ancre_nue` garde côté profil).

    Une forme inconnue rend `NON_RECONNUE + href` et JAMAIS `None` : cf. le
    commentaire ci-dessus. Le silence est le seul verdict qu'un témoin n'a pas le
    droit de rendre.
    """
    href = href.strip()
    if href.startswith("#"):
        return "/" + href if rel == "index.html" else rel + href
    if href in ("/", "/index.html"):
        return "/"
    if href.startswith("/#"):
        return href
    m = re.fullmatch(r"/([^/#?]+)/", href)
    return f"/{m.group(1)}/" if m else NON_RECONNUE + href


@functools.lru_cache(maxsize=1)
def pages_de_la_nav_partagee() -> tuple[str, ...]:
    """Les pages QUI PORTENT la nav partagée — l'accueil compris.

    Population dérivée de deux témoins déjà en place, aucun nom écrit ici :
      * `sections_par_topologie_de_la_nav()` — les répertoires du groupe fermé ;
      * `pages_atteintes_par_la_nav()` — les cibles des `href` de la nav,
        résolues sur le disque. C'est elle qui fait entrer `index.html` : toutes
        les sous-pages pointent la racine par leur marque
        (`<a class="nav-brand" href="/">`), donc l'accueil EST un membre — mais
        aucun calcul fondé sur les répertoires ne pouvait le voir.

    Les deux pages d'articles sont hors population, comme `/life-architect/`
    l'était : elles portent la marque mais une nav d'une seule entrée (retour à
    l'accueil). Elles restent dans le champ de `pages_atteintes_par_la_nav()` et
    des gardes de thème ; elles ne sont pas des sections de la nav partagée.
    """
    sections = {f"{d}/index.html" for d in sections_par_topologie_de_la_nav()}
    if "index.html" in pages_atteintes_par_la_nav():
        sections.add("index.html")
    return tuple(sorted(sections))


@functools.lru_cache(maxsize=1)
def destinations_ordonnees_de_la_nav_par_page() -> dict[str, tuple[str, ...]]:
    """Pour chaque page de la nav partagée, ses destinations DANS L'ORDRE du document.

    Une SÉQUENCE, pas un ensemble, et c'est la correction du 2026-10-19 : un
    ensemble perd l'ORDRE et perd les DOUBLONS. Deux pertes mesurées sur ce
    corpus — l'ordre des onze entrées n'était vérifié par rien (une nav
    réordonnée passait verte sur les six pages), et une entrée dupliquée pendant
    qu'une autre disparaît laisse l'ensemble inchangé en taille comme en contenu
    dès que les deux partagent un href.

    Ce module ne décide de rien : il rapporte ce que chaque page déclare, y
    compris une forme qu'il ne sait pas lire (préfixe `NON_RECONNUE`). C'est au
    test d'exiger que les séquences coïncident.
    """
    out: dict[str, tuple[str, ...]] = {}
    for rel in pages_de_la_nav_partagee():
        vues: list[str] = []
        for bloc in _BLOC_NAV.findall(_texte(rel)):
            if _NAV_PARTAGEE not in bloc:
                continue
            vues += [_normaliser_destination(rel, href)
                     for href in _DESTINATION_NAV.findall(bloc)]
        out[rel] = tuple(vues)
    return out


def destinations_de_la_nav_par_page() -> dict[str, frozenset[str]]:
    """Même relevé, vu comme un ensemble — vue dérivée, conservée pour ses lecteurs."""
    return {rel: frozenset(dests)
            for rel, dests in destinations_ordonnees_de_la_nav_par_page().items()}


@functools.lru_cache(maxsize=1)
def cles_nav_de_site_texts() -> tuple[str, ...]:
    """Les clés `nav_*` de `site_texts.json`, dans l'ordre du fichier.

    TROISIÈME témoin de la liste des entrées de nav, et le seul qui ne vive ni
    dans `tools/nav.py` ni dans un artefact publié. Il est nécessaire, et la
    mesure du 2026-10-19 dit pourquoi : `nav.ENTREES` était à la fois la SOURCE
    des cinq sous-pages et l'ATTENDU de la garde qui les juge. Retirer une entrée
    de cette liste, régénérer les cinq pages et retirer la même ligne de
    l'accueil écrit à la main laissait la suite ENTIÈREMENT VERTE — onze entrées
    devenaient dix et tous les témoins étaient d'accord. C'est exactement la
    classe de régression pour laquelle la nav unifiée a été écrite.

    `site_texts.json` est un témoin indépendant parce qu'il existe pour une autre
    raison : c'est la source des LIBELLÉS, éditable depuis le cockpit, et deux
    gardes la tiennent déjà dans les deux langues
    (`test_site_texts.py::test_chaque_cle_de_la_page_existe_en_francais_et_en_anglais`
    et `::test_le_texte_statique_fr_egale_le_dictionnaire`). Une entrée de nav
    supprimée y laisse donc sa clé, en français comme en anglais.
    """
    textes = json.loads((ROOT / "site_texts.json").read_text(encoding="utf-8"))
    return tuple(k for k in textes["fr"] if k.startswith("nav_"))


@functools.lru_cache(maxsize=1)
def cles_i18n_de_la_nav_de_l_accueil() -> tuple[str, ...]:
    """Les `data-i18n` du bloc `<nav>` de l'accueil, dans l'ordre du document.

    QUATRIÈME témoin, et il porte l'ORDRE. L'accueil n'est pas généré (arbitrage
    1 du 2026-10-15) : ces onze attributs sont écrits à la main, donc ils ne
    peuvent pas suivre une mutation de `nav.ENTREES` sans que quelqu'un les
    édite. Ils disent à la fois quelles entrées existent et dans quel ordre la
    barre les montre.
    """
    for bloc in _BLOC_NAV.findall(_texte("index.html")):
        if _NAV_PARTAGEE in bloc:
            return tuple(re.findall(r'data-i18n="([^"]+)"', bloc))
    return ()


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
