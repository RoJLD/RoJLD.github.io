"""Garde anti-lien-mort : tout href local des pages publiées doit se résoudre.

Cette garde n'existait pas — c'est pour cela que `/projects/` a été publié avec
un lien vers `/projects/articles/couverture-dynamique.html` (404) et deux boutons
« Démo » pointant sur une ancre `#demos` absente de la page courante.

Règles vérifiées, pour chaque page HTML publiée du dépôt :
  * un href local (ni http(s), ni mailto/tel/javascript/data) doit désigner un
    fichier existant, résolu **comme le ferait le navigateur** (relatif au
    répertoire de la page, absolu depuis la racine du site) ;
  * un répertoire (ou un chemin terminé par `/`) est résolu en `index.html` ;
  * si l'URL porte un fragment `#ancre`, la page cible doit contenir cette ancre ;
  * un chemin ABSENT du disque n'est accepté que s'il est déclaré servi par un
    autre dépôt du même domaine (`servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT`,
    aujourd'hui le seul `/academy/` -> RoJLD/academy) ; tout autre absent reste
    une erreur.

Aucun réseau : les liens externes sont hors périmètre par construction.

Ce fichier porte AUSSI les gardes des liens RoJLD du corpus (§ « Les liens RoJLD
du profil »), qui ne sont pas des liens internes. Ce n'est pas un fourre-tout,
c'est la porte : `tools/cockpit/publication.py::verifier()` — ce que joue le
bouton « Publier » — lance ce FICHIER en entier, plus `validate_profile.py`,
`build_site.py` et trois node-ids de confidentialité, et rien d'autre. Mesuré le
2026-10-15 sur une copie de l'arbre : les deux liens morts remis dans
`profile.json`, la porte rendait 5 contrôles sur 5 « OK » et régénérait
`/projects/` avec les deux boutons morts, pendant que la suite pytest, elle,
rougissait. Une garde de corpus posée ailleurs que dans ce fichier est hors de la
porte, donc muette à l'instant où elle compterait.
"""
from __future__ import annotations

import functools
import json
import os
import pathlib
import re
import sys
from html.parser import HTMLParser as _HTMLParser

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate_profile import validate  # noqa: E402
import corpus_publie  # noqa: E402
import radar_boot_harness  # noqa: E402
import servi_ailleurs  # noqa: E402
import sync_github_projects  # noqa: E402
import validate_profile as vp  # noqa: E402

# Schémas non résolvables sur le disque -> hors périmètre.
EXTERNAL = ("http://", "https://", "//", "mailto:", "tel:", "javascript:", "data:")

# Répertoires qui ne sont pas publiés (fixtures de test, outillage, git).
EXCLUDED_DIRS = {".git", "tools", "node_modules"}

# Attributs porteurs d'une URL dans les gabarits générés (`data-href-*` sert au
# basculement de langue de /explorer/ et /highlights/, `data-article-*` à celui
# des liens d'article de l'accueil).
#
# `src`/`poster` ont été ajoutés après mesure : le scan n'en couvrait aucun, et
# laissait donc passer 6 références locales — dont les trois scripts du CV
# (`assets/js/cv-*.js`) et la photo de l'accueil. Toutes valides aujourd'hui,
# mais une image ou un script mort serait passé vert : une garde qui ne regarde
# que la navigation ne garde pas la page.
#
# `data-href-fr`, `data-article-fr` et `data-article-en` ont été ajoutés après une
# mesure d'un autre genre : au lieu de relire la liste, on a DÉCOUVERT sur le site
# publié tous les attributs dont la valeur désigne un fichier local existant (cf.
# `attributs_porteurs_de_chemins_locaux`). Trois manquaient — dont la version
# FRANÇAISE de l'article, alors que la version anglaise, elle, était couverte.
# Une liste relue à l'œil ne trouve pas ça ; une liste confrontée au corpus, si.
#
# `content` (52 occurrences, balises meta) est délibérément EXCLU : il porte du
# texte libre et des URL absolues (`og:image` pointe https://robin-denis.com/…),
# donc l'y inclure fabriquerait des faux positifs sans couvrir un fichier local.
URL_ATTR = re.compile(
    r'(?:href|data-href-en|data-href-fr|data-href|data-article-en|data-article-fr'
    r'|src|poster)\s*=\s*"([^"]*)"')

# Tout attribut HTML, sans présupposé : c'est le témoin qui dit lesquels portent
# réellement un chemin local, pas la liste ci-dessus.
_TOUT_ATTRIBUT = re.compile(r'([a-zA-Z][\w:-]*)\s*=\s*"([^"]*)"')

# `url(...)` des feuilles de style embarquées.
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+?)["']?\s*\)""")


def css_urls(text: str) -> list[str]:
    """URL de fichiers référencées en CSS, hors références internes au document.

    L'accueil embarque un SVG en `data:` dont le `filter='url(%23n)'` désigne un
    filtre défini DANS ce SVG (`%23` = `#`). Le résoudre sur le disque
    inventerait un lien mort là où il n'y en a pas — un faux positif rend une
    garde inutilisable aussi sûrement qu'un angle mort.
    """
    return [u.strip() for u in CSS_URL.findall(text)
            if u.strip() and not u.strip().startswith(("#", "%23"))]


def published_pages() -> list[pathlib.Path]:
    """Toutes les pages HTML réellement servies par GitHub Pages."""
    return sorted(
        p for p in ROOT.rglob("*.html")
        if not (EXCLUDED_DIRS & set(p.relative_to(ROOT).parts))
    )


def _index_html() -> str:
    return (ROOT / "index.html").read_text(encoding="utf-8")


def _has_anchor(text: str, frag: str) -> bool:
    return any(pat in text for pat in (f'id="{frag}"', f"id='{frag}'", f'name="{frag}"'))


def resolve(page: pathlib.Path, url: str, root: pathlib.Path = ROOT) -> pathlib.Path | None:
    """Chemin disque visé par `url` depuis `page`, ou None si hors périmètre.

    `root` = racine du site servie ; paramétrable pour que le scanner puisse
    être exercé sur une page synthétique hors du dépôt (cf. plus bas), sans
    fabriquer de fichiers dans un site publié.
    """
    if not url or url == "#" or url.startswith(EXTERNAL):
        return None
    path = url.partition("#")[0]
    if not path:                      # ancre pure -> la page elle-même
        return page
    path = path.partition("?")[0]
    if not path:
        return page
    target = (root / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target


def servi_par_un_autre_depot(target: pathlib.Path, root: pathlib.Path = ROOT) -> str | None:
    """Dépôt qui sert `target` sous le domaine à la place de ce site, ou None.

    Consulté par `broken_links_in` SEULEMENT quand la cible manque sur le
    disque : la déclaration excuse une absence, elle ne masque jamais un
    fichier présent — un dossier déclaré qui réapparaît est lu normalement, et
    fait rougir `test_un_chemin_servi_ailleurs_n_existe_pas_dans_ce_site`.
    """
    try:
        rel = os.path.relpath(target, root)
    except ValueError:                # autre lecteur (Windows) : hors du site
        return None
    return servi_ailleurs.depot_qui_sert(pathlib.PurePath(rel).as_posix())


def broken_links(page: pathlib.Path, root: pathlib.Path = ROOT) -> list[str]:
    """Liste des liens locaux non résolvables de `page` (vide = page saine)."""
    return broken_links_in(page.read_text(encoding="utf-8", errors="replace"),
                           page, root)


def broken_links_in(text: str, page: pathlib.Path,
                    root: pathlib.Path = ROOT) -> list[str]:
    """Idem, mais sur un HTML fourni — `page` ne sert plus qu'à situer la page.

    Séparé de `broken_links` pour pouvoir scanner un HTML **produit en mémoire**
    par un générateur, à l'emplacement où il sera servi, sans l'écrire sur le
    disque du site.
    """
    here = page.relative_to(root).as_posix()
    bad: list[str] = []
    for url in URL_ATTR.findall(text) + css_urls(text):
        url = url.strip()
        target = resolve(page, url, root)
        if target is None:
            continue
        if not target.exists():
            if servi_par_un_autre_depot(target, root):
                continue              # vivant, mais servi par un autre dépôt
            bad.append(f"{here} -> {url!r} : fichier absent ({target})")
            continue
        frag = url.partition("#")[2]
        if frag and target.suffix == ".html":
            if not _has_anchor(target.read_text(encoding="utf-8", errors="replace"), frag):
                bad.append(f"{here} -> {url!r} : ancre #{frag} absente de "
                           f"{target.relative_to(root).as_posix()}")
    return bad


def test_des_pages_sont_publiees():
    """Garde-fou : un scan qui ne trouve rien passerait vert pour rien."""
    pages = published_pages()
    assert len(pages) >= 10, f"trop peu de pages scannées : {len(pages)}"
    names = {p.relative_to(ROOT).as_posix() for p in pages}
    assert {"index.html", "projects/index.html", "demos/index.html"} <= names


def test_le_corpus_scanne_couvre_TOUT_le_site_publie():
    """Le CHAMP du scan, tenu par un témoin qui n'est pas sa propre constante.

    Mesuré : ajouter `life-architect` à `EXCLUDED_DIRS` retirait du scan la page
    la plus fragile du dépôt — celle qu'aucun builder ne répare — et la suite
    restait verte (487 passed, un cas paramétré de moins, zéro rouge). Le test
    ci-dessus n'exige que trois noms et un plancher de dix pages : il survit
    largement à l'amputation.
    """
    scannees = {p.relative_to(ROOT).as_posix() for p in published_pages()}
    attendues = set(corpus_publie.pages_publiees())
    assert scannees == attendues, (
        f"pages publiées hors du scan : {sorted(attendues - scannees)} ; "
        f"pages scannées qui ne sont pas servies : {sorted(scannees - attendues)}")
    # `life-architect/index.html` en formait le témoin nommé jusqu'au 2026-09-29
    # (D13a : bêta morte, retirée du site). La propriété exercée ci-dessus (scan
    # == découverte) ne dépend d'aucun nom de page — seulement de leur égalité —
    # et reste tenue sans lui.


@pytest.mark.parametrize("page", published_pages(), ids=lambda p: p.relative_to(ROOT).as_posix())
def test_liens_internes_resolus(page):
    bad = broken_links(page)
    assert not bad, "lien(s) local(aux) non résolvable(s) :\n  " + "\n  ".join(bad)


def test_le_scan_couvre_les_ressources_pas_seulement_la_navigation():
    """Le champ du scanner est lui-même mesuré, sinon il rétrécit en silence.

    Mesuré : `href` seul laissait 6 `src`/`poster` locaux hors du champ. Tous
    valides ce jour-là — c'est bien le problème : une image ou un script mort
    serait passé vert.
    """
    vus = {u.strip() for u in URL_ATTR.findall(_index_html())}
    attendus = {"photo_avatar.jpg", "assets/js/cv-render.js",
                "assets/js/cv-select.js", "assets/js/cv-export.js"}
    assert attendus <= vus, f"hors du champ du scanner : {sorted(attendus - vus)}"


@functools.lru_cache(maxsize=1)
def attributs_porteurs_de_chemins_locaux() -> dict:
    """Attributs du site PUBLIÉ dont la valeur désigne un fichier local existant.

    Le témoin indépendant du champ du scanner. Il n'interroge pas `URL_ATTR` : il
    lit toutes les paires `attribut="valeur"` des pages servies et retient celles
    qui se résolvent sur le disque. Le résultat est donc un fait du corpus, que
    le scanner doit couvrir — et non une liste qu'on relit à l'œil.

    Filtre : la valeur doit ressembler à un chemin (un `/`, ou un suffixe de
    fichier). Sans lui, `id="demos"` serait retenu — il « se résout » parce qu'un
    répertoire `demos/` existe, alors qu'il ne désigne aucune ressource.
    """
    porteurs: dict[str, set[str]] = {}
    for rel in corpus_publie.pages_publiees():
        page = ROOT / rel
        texte = page.read_text(encoding="utf-8", errors="replace")
        for attribut, valeur in _TOUT_ATTRIBUT.findall(texte):
            valeur = valeur.strip()
            if not valeur or valeur.startswith(EXTERNAL) or valeur.startswith("#"):
                continue
            chemin = valeur.partition("#")[0].partition("?")[0]
            if not chemin:
                continue
            if "/" not in chemin and not pathlib.PurePosixPath(chemin).suffix:
                continue
            cible = resolve(page, valeur)
            if cible is not None and cible.is_file():
                porteurs.setdefault(attribut, set()).add(valeur)
    return porteurs


def test_le_champ_du_scanner_couvre_tout_attribut_qui_porte_un_chemin_local():
    """Le champ déclaré est confronté au CORPUS, pas relu.

    `URL_ATTR` était une liste écrite à la main dont ce fichier était le seul
    lecteur : la relire ne pouvait pas révéler ce qui n'y avait jamais été mis.
    En dérivant l'attente du site publié, trois attributs manquants sont apparus
    d'un coup — `data-href-fr`, `data-article-fr`, `data-article-en` — dont la
    version française de l'article, quand l'anglaise était couverte. Chacun
    portait un lien local réel, hors du scan anti-404.

    L'appartenance au champ est vérifiée par COMPORTEMENT (on soumet à la regex
    un fragment portant l'attribut), pas en inspectant son motif : le test
    mesure ce que le scanner capture, pas ce qu'il déclare capturer.
    """
    porteurs = attributs_porteurs_de_chemins_locaux()
    assert {"href", "src"} <= set(porteurs), (
        f"la découverte des attributs porteurs ne mesure plus rien : {sorted(porteurs)}")
    assert sum(len(v) for v in porteurs.values()) >= 40, porteurs
    hors_champ = sorted(
        attribut for attribut, valeurs in porteurs.items()
        if not URL_ATTR.findall(f'<x {attribut}="{sorted(valeurs)[0]}">'))
    assert not hors_champ, (
        f"attributs portant un chemin local réel mais hors du champ du "
        f"scanner : {hors_champ} — leurs cibles ne sont jamais vérifiées")


def test_le_scan_couvre_les_href_de_la_version_anglaise():
    """`data-href-en` porte de VRAIS liens locaux, sur deux pages publiées.

    Mesuré : retirer `data-href-en` de `URL_ATTR` laissait la suite à
    488 passed — le compte EXACT du vert de référence. Le test ci-dessus nomme
    quatre URL, toutes fournies par `href`/`src` : il ne pouvait pas voir le
    rétrécissement. Or `/explorer/` et `/highlights/` référencent la version
    anglaise de l'article par ce seul attribut ; hors du scan, un lien anglais
    mort partait en production sans un mot.
    """
    for page in ("explorer/index.html", "highlights/index.html"):
        vus = {u.strip() for u in URL_ATTR.findall((ROOT / page).read_text(encoding="utf-8"))}
        assert "/articles/couverture-dynamique.en.html" in vus, (
            f"{page} : le lien de la version anglaise est hors du champ du scanner")


# Les attributs exercés un par un : ceux que le CORPUS porte réellement
# (découverts), plus les DORMANTS, qu'aucune page n'utilise aujourd'hui et que
# seule une liste peut nommer. La partie découverte est la seule qui compte pour
# la non-régression : elle ne peut pas rétrécir avec la constante qu'elle garde.
_ATTRIBUTS_DORMANTS = ["data-href", "poster"]
_ATTRIBUTS_EXERCES = (sorted(attributs_porteurs_de_chemins_locaux())
                      + _ATTRIBUTS_DORMANTS)


@pytest.mark.parametrize("attribut", _ATTRIBUTS_EXERCES)
def test_chaque_attribut_du_champ_est_reellement_scanne(attribut, tmp_path):
    """Le champ déclaré doit être le champ EFFECTIF — vérifié par comportement.

    Mesuré : retirer `poster` de `URL_ATTR` laissait la suite entière verte
    (488 passed), parce qu'aucune page du corpus n'en porte aujourd'hui. Comme
    la branche `url()` du CSS, l'attribut est dormant : la mutation n'a pas
    d'effet OBSERVABLE sur le corpus actuel, ce qui n'en fait pas une mutation
    bénigne — elle retire au scanner une capacité que la première vidéo publiée
    rendrait décisive, sans que rien ne le signale.

    D'où une page synthétique par attribut : le contrat est vérifié là où le
    corpus est muet, et un attribut retiré de la regex rougit immédiatement.

    La liste des cas est DÉRIVÉE du corpus pour tout ce qu'il porte : une liste
    écrite à la main aurait pu perdre `src` en même temps que `URL_ATTR`, et le
    cas de test aurait disparu avec la couverture. Seuls restent nommés les deux
    attributs dormants — nul corpus ne peut les découvrir, c'est ce qui les
    définit.
    """
    page = _page_synthetique(tmp_path, f'<x {attribut}="ressources/absente.bin"></x>')
    bad = broken_links(page, root=tmp_path)
    assert any("absente.bin" in b for b in bad), (
        f"l'attribut {attribut} est déclaré dans URL_ATTR mais n'entre pas dans "
        f"le scan (rapporté : {bad})")


def test_le_scan_ecarte_les_references_internes_au_document():
    """`url(%23n)` vise un filtre DU SVG inline, pas un fichier du dépôt.

    Un faux positif condamne une garde aussi sûrement qu'un angle mort : elle
    devient rouge en permanence, donc on cesse de la lire.
    """
    idx = _index_html()
    # Le scan brut voit la référence interne ; le scan filtré doit la jeter.
    # (L'URI `data:` qui l'englobe n'est elle-même jamais capturée : elle
    # contient des quotes, que la classe `[^"')]` exclut. Sans effet ici —
    # `data:` est hors périmètre disque de toute façon — mais l'écrire évite
    # de croire ce test plus large qu'il n'est.)
    assert "%23n" in CSS_URL.findall(idx), (
        "le SVG inline a disparu de l'accueil — ce test ne mesure plus rien")
    assert not [u for u in css_urls(idx) if "23n" in u], \
        "une référence interne au SVG est traitée comme un fichier"


# --- Le BRANCHEMENT du scan CSS, et pas seulement sa fonction ----------------
#
# Mesuré : débrancher la branche CSS de `broken_links` — retirer le terme
# « + css_urls(text) » de sa boucle, en ne gardant que le champ des attributs —
# laissait la suite à 406 passed. Les deux tests ci-dessus exercent `css_urls`
# et `CSS_URL` isolément ; aucun ne prouvait que leur résultat entrait dans le
# scan. Une fonction juste, jamais appelée, garde exactement zéro chose.
#
# Pourquoi le corpus réel ne pouvait pas fournir cette preuve : il ne contient
# qu'UNE occurrence de `url(...)` en tout et pour tout, `url(%23n)` sur
# l'accueil, qui désigne un filtre interne au SVG et non un fichier (compté :
# `CSS_URL` rend 1 résultat sur les 15 pages publiées, `css_urls` en rend 0).
# Sur ce corpus-là, la branche est donc dormante — la mutation est sans effet
# OBSERVABLE aujourd'hui, ce qui n'en fait pas une mutation bénigne : elle
# retire au scanner une capacité que la première `url(assets/…)` écrite dans un
# `<style>` rendra décisive, sans que rien ne le signale.
#
# D'où une page SYNTHÉTIQUE : le contrat du scanner est vérifié là où le corpus
# est muet, sans écrire de fichier dans un site publié.

def _page_synthetique(dossier: pathlib.Path, corps: str) -> pathlib.Path:
    page = dossier / "page.html"
    page.write_text(corps, encoding="utf-8")
    return page


# --- Ce qui compte comme ANCRE : un parseur HTML tranche, pas une sous-chaîne --
#
# `_has_anchor` cherche trois motifs littéraux. Mesuré 2026-07-29 : le réduire au
# seul `id="…"` — donc rendre le scanner aveugle à `id='…'` et à `name="…"` —
# laissait la suite ENTIÈREMENT VERTE (458 passed). Le jumeau de cette fonction,
# dans `validate_profile`, est tenu par un test paramétré sur les trois formes ;
# la copie du scanner ne l'était par rien.
#
# L'attendu ne peut pas être la liste des trois motifs : ce serait la constante
# testée recopiée dans son test. Il vient d'un PARSEUR HTML (`html.parser`, la
# bibliothèque standard), qui lit les attributs au lieu de chercher des chaînes,
# et qui ne partage aucune ligne avec le scanner. C'est lui qui dit quels
# fragments existent ; le scanner doit dire la même chose.

def _ancres_selon_un_parseur(texte: str) -> set[str]:
    """Fragments atteignables dans `texte`, vus par un parseur HTML de la stdlib."""
    class _Collecteur(_HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.vues: set[str] = set()

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            self.vues |= {d[k] for k in ("id", "name") if d.get(k)}

    c = _Collecteur()
    c.feed(texte)
    return c.vues


def test_le_scanner_voit_les_memes_ancres_qu_un_parseur_html(tmp_path):
    """Les trois façons d'écrire une ancre valent la même chose pour le navigateur.

    L'ENTRÉE est décrite ici (une page cible qui déclare ses ancres en guillemets
    doubles, en guillemets simples et par `name`) ; la SORTIE attendue est ce que
    le parseur y trouve. Le scanner doit accepter exactement ces fragments-là —
    et signaler celui que le parseur ne trouve pas, sans quoi l'acceptation ne
    prouverait rien.
    """
    cible = tmp_path / "cible.html"
    cible.write_text('<h2 id="doubles">a</h2>'
                     "<h2 id='simples'>b</h2>"
                     '<a name="nommee"></a>', encoding="utf-8")
    attendues = _ancres_selon_un_parseur(cible.read_text(encoding="utf-8"))
    assert len(attendues) == 3, attendues

    page = tmp_path / "page.html"
    liens = "".join(f'<a href="cible.html#{a}">x</a>' for a in sorted(attendues))
    manques = broken_links_in(liens, page, tmp_path)
    assert manques == [], (
        f"le scanner ignore des ancres qu'un parseur HTML trouve : {manques}")

    absente = "fragment-que-le-parseur-ne-voit-pas"
    assert absente not in attendues
    bad = broken_links_in(f'<a href="cible.html#{absente}">x</a>', page, tmp_path)
    assert len(bad) == 1 and absente in bad[0], bad


@pytest.mark.parametrize("page", [p.relative_to(ROOT).as_posix()
                                  for p in published_pages()])
def test_sur_le_site_publie_scanner_et_parseur_saccordent_sur_les_ancres(page):
    """Même accord, sur la DONNÉE RÉELLE plutôt que sur une page fabriquée.

    Pour chaque lien à fragment d'une page servie, le verdict du scanner
    (`_has_anchor`) doit être celui du parseur. Une divergence est soit un lien
    mort que le scan laisse passer, soit un faux positif — les deux rendent la
    garde inutilisable.
    """
    texte = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    for url in URL_ATTR.findall(texte):
        cible = resolve(ROOT / page, url.strip())
        frag = url.strip().partition("#")[2]
        if not frag or cible is None or cible.suffix != ".html" or not cible.exists():
            continue
        cible_txt = cible.read_text(encoding="utf-8", errors="replace")
        assert _has_anchor(cible_txt, frag) == (frag in _ancres_selon_un_parseur(cible_txt)), (
            f"{page} -> {url!r} : le scanner et le parseur HTML ne s'accordent pas "
            f"sur l'ancre #{frag} de {cible.relative_to(ROOT).as_posix()}")


def _href_a_fragment_selon_le_parseur(texte: str) -> list[str]:
    """`href` portant un fragment non nu, relevés par le parseur HTML."""
    class _Collecteur(_HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.vus: list[str] = []

        def handle_starttag(self, tag, attrs):
            h = dict(attrs).get("href") or ""
            if "#" in h and not h.startswith("#"):
                self.vus.append(h)

    c = _Collecteur()
    c.feed(texte)
    return sorted(c.vus)


def test_le_corpus_publie_porte_bien_des_liens_a_fragment_a_confronter():
    """Contre-vacuité du test précédent, SANS nombre écrit à la main.

    Le test ci-dessus ne dit rien si le corpus ne contient aucun lien à
    fragment, ou si `URL_ATTR`/`resolve` cessent d'en trouver. Le compte attendu
    ne peut pas être une constante (elle bougera au premier article ajouté) : il
    vient d'une SECONDE lecture, faite par un parseur HTML là où la première est
    une expression régulière. Les deux doivent voir exactement les mêmes liens,
    et il doit y en avoir.
    """
    par_regex, par_parseur = {}, {}
    for p in published_pages():
        rel = p.relative_to(ROOT).as_posix()
        texte = p.read_text(encoding="utf-8", errors="replace")
        par_regex[rel] = sorted(u for u in URL_ATTR.findall(texte)
                                if "#" in u and not u.startswith("#")
                                and not u.startswith(EXTERNAL))
        par_parseur[rel] = [u for u in _href_a_fragment_selon_le_parseur(texte)
                            if not u.startswith(EXTERNAL)]
    manquants = {k: sorted(set(par_parseur[k]) - set(par_regex[k])) for k in par_regex}
    manquants = {k: v for k, v in manquants.items() if v}
    assert not manquants, (
        f"des liens à fragment échappent au champ du scanner : {manquants}")
    total = sum(len(v) for v in par_parseur.values())
    assert total > 0, "plus aucun lien à fragment dans le site publié : le test "\
                      "d'accord scanner/parseur ne mesure plus rien"


def test_le_scan_signale_un_fichier_absent_reference_en_css(tmp_path):
    """`background:url(...)` vers un fichier absent doit être rapporté."""
    page = _page_synthetique(
        tmp_path, '<style>.hero{background:url(images/fond-absent.png)}</style>')
    bad = broken_links(page, root=tmp_path)
    assert any("fond-absent.png" in b for b in bad), (
        "une ressource CSS morte n'est pas rapportée — la branche `css_urls` "
        f"n'entre pas dans le scan (rapporté : {bad})")


def test_le_scan_css_ne_crie_pas_sur_un_fichier_present(tmp_path):
    """Contre-épreuve : la branche discrimine, elle ne rapporte pas tout.

    Un scanner qui rougirait aussi sur les ressources valides passerait le test
    précédent sans rien garder.
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "fond.png").write_bytes(b"\x89PNG")
    page = _page_synthetique(
        tmp_path, '<style>.hero{background:url("images/fond.png")}</style>')
    assert broken_links(page, root=tmp_path) == []


def test_le_scan_css_couvre_les_polices_et_les_chemins_absolus(tmp_path):
    """Les deux autres formes réellement écrites en CSS : `src:url()` et `/…`."""
    page = _page_synthetique(tmp_path, """
      <style>
        @font-face{font-family:X;src:url('assets/fonts/x.woff2') format('woff2')}
        body{background-image:url(/images/absolue.svg)}
      </style>""")
    bad = broken_links(page, root=tmp_path)
    assert any("x.woff2" in b for b in bad), f"police morte non vue : {bad}"
    assert any("absolue.svg" in b for b in bad), f"chemin absolu CSS non vu : {bad}"


def test_le_scan_synthetique_reste_aveugle_aux_references_internes(tmp_path):
    """Le filtre `#`/`%23` tient aussi dans le chemin branché sur le disque."""
    page = _page_synthetique(
        tmp_path, '<svg><filter id="n"></filter></svg>'
                  '<style>.x{filter:url(#n);backdrop-filter:url(%23n)}</style>')
    assert broken_links(page, root=tmp_path) == []


# --- Le branchement du scan d'ATTRIBUTS : le même trou, découvert en le cherchant
#
# La contre-épreuve de la mutation précédente a mis au jour un défaut qui n'était
# pas dans la commande : débrancher l'AUTRE terme de la boucle — ne garder que
# `css_urls(text)` et jeter le champ des attributs — laissait la suite à 448
# passed. Le test `..._couvre_les_ressources_...` verrouille bien le CHAMP du
# scanner (quels attributs la regex capture), jamais son BRANCHEMENT.
#
# Raison de fond, valable pour les deux branches : sur un corpus sain,
# `broken_links` doit rendre `[]`. Un scanner débranché rend `[]` lui aussi.
# `test_liens_internes_resolus` ne peut donc pas distinguer « aucun lien mort »
# de « aucun lien regardé » — il ne le pourra jamais tant qu'il n'existe pas de
# page qui contienne réellement un lien mort. C'est ce que les pages
# synthétiques fournissent, et rien d'autre ne le peut sans casser le site.

def test_le_scan_signale_un_href_mort(tmp_path):
    page = _page_synthetique(tmp_path, '<a href="pages/disparue.html">Lire</a>')
    bad = broken_links(page, root=tmp_path)
    assert any("disparue.html" in b for b in bad), (
        f"un href local mort n'est pas rapporté — le champ des attributs "
        f"n'entre pas dans le scan (rapporté : {bad})")


def test_le_scan_signale_une_ressource_src_morte(tmp_path):
    page = _page_synthetique(
        tmp_path, '<img src="images/absente.jpg"><script src="assets/js/mort.js"></script>')
    bad = broken_links(page, root=tmp_path)
    assert any("absente.jpg" in b for b in bad), f"image morte non vue : {bad}"
    assert any("mort.js" in b for b in bad), f"script mort non vu : {bad}"


def test_le_scan_signale_une_ancre_absente_de_la_cible(tmp_path):
    (tmp_path / "demos").mkdir()
    (tmp_path / "demos" / "index.html").write_text(
        '<h2 id="present">ok</h2>', encoding="utf-8")
    page = _page_synthetique(
        tmp_path, '<a href="/demos/#present">ok</a><a href="/demos/#absent">ko</a>')
    bad = broken_links(page, root=tmp_path)
    assert any("#absent" in b for b in bad), f"ancre absente non vue : {bad}"
    assert not any("#present" in b for b in bad), f"ancre valide rapportée à tort : {bad}"


def test_le_scan_ignore_la_query_dun_lien(tmp_path):
    """`?v=2` n'est pas dans le nom du fichier — dormant, donc à exercer ici.

    Mesuré : retirer le retrait de la query (`path.partition("?")[0]`) laissait
    la suite entière verte, aucune page du corpus n'en portant aujourd'hui. La
    première ressource versionnée (`style.css?v=3`, geste courant contre le
    cache) serait alors rapportée comme morte, et la garde deviendrait un rouge
    permanent — c'est-à-dire une garde qu'on désactive.
    """
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("//", encoding="utf-8")
    page = _page_synthetique(tmp_path, '<script src="assets/app.js?v=3"></script>')
    assert broken_links(page, root=tmp_path) == []


def test_le_scan_laisse_passer_une_page_saine(tmp_path):
    """Contre-épreuve des trois précédents : le scanner discrimine.

    Sans elle, un `broken_links` qui rapporterait TOUT les passerait aussi.
    """
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "ok.jpg").write_bytes(b"\xff\xd8")
    (tmp_path / "voisine.html").write_text('<h2 id="ancre">x</h2>', encoding="utf-8")
    page = _page_synthetique(
        tmp_path,
        '<a href="voisine.html#ancre">ok</a><img src="/images/ok.jpg">'
        '<a href="https://example.com/absent.html">externe</a>'
        '<a href="mailto:x@y.z">mail</a>'
        '<a href="#local">ancre nue</a><h2 id="local">ici</h2>')
    assert broken_links(page, root=tmp_path) == []


# --- Les chemins servis par un AUTRE dépôt du domaine ------------------------
#
# Le 2026-10-14, `/academy/` a quitté ce site : le dépôt-projet RoJLD/academy la
# sert sous robin-denis.com (un dépôt-projet Pages l'emporte sur un dossier du
# même nom du site utilisateur). Le lien de nav reste ; le dossier `academy/`,
# mort, est retiré. Mesuré, déclaration vidée : 12 rouges parmi les gardes qui
# existaient déjà — le scan anti-404 sur les 6 pages publiées qui portent ce lien
# vivant (accueil compris) et sur la sortie des 5 générateurs de nav, plus la
# topologie de la nav, qui ne fermait plus. Un lien vivant refusé partout, c'est
# une garde qu'on finit par éteindre.
#
# La déclaration (`tools/servi_ailleurs.py`) est NOMMÉE — chemin et dépôt — et
# ne s'élargit à rien d'autre. Les quatre tests suivants tiennent ses bords : ce
# qu'elle laisse passer, ce qu'elle laisse rouge, ce qu'elle ne masque pas sur
# le disque, et ce qu'elle interdit au site de reprendre.

_LIENS_VERS_L_ACADEMY = ('<a href="/academy/">a</a>'
                         '<a href="/academy">b</a>'
                         '<a href="/academy/cours/intro.html#q1">c</a>'
                         '<a href="../academy/#certifications">d</a>')


def test_un_lien_vers_un_chemin_servi_par_un_autre_depot_passe(tmp_path, monkeypatch):
    """`/academy/` et tout ce qui est dessous : vivant, sans fichier local.

    Quatre écritures du même chemin, dont une relative à la page (`../academy/`
    depuis `/projects/`) : la déclaration est consultée sur la cible RÉSOLUE,
    pas sur la chaîne écrite.

    Contre-épreuve dans le même test : la déclaration vidée, les quatre liens
    redeviennent des « fichier absent ». Le vert vient donc bien d'elle, et pas
    d'un autre chemin du scanner qui sauterait ces liens.
    """
    (tmp_path / "projects").mkdir()
    page = tmp_path / "projects" / "index.html"
    page.write_text(_LIENS_VERS_L_ACADEMY, encoding="utf-8")
    assert broken_links(page, root=tmp_path) == []

    monkeypatch.setattr(servi_ailleurs, "SERVI_PAR_UN_AUTRE_DEPOT", {})
    bad = broken_links(page, root=tmp_path)
    assert len(bad) == 4 and all("fichier absent" in b for b in bad), bad


def test_un_dossier_absent_non_declare_reste_une_erreur(tmp_path):
    """La déclaration n'ouvre que ce qu'elle nomme, par SEGMENT de chemin.

    Chaque lien ci-dessous ressemble à `/academy/` sans l'être : un nom qui la
    prolonge (`/academyx/`), un segment homonyme plus bas (`/cours/academy/`),
    l'ancienne source retirée avec elle (`academy.json`), et un dossier sans
    rapport. Une correspondance par préfixe de chaîne ou par sous-chaîne en
    laisserait passer au moins un.
    """
    liens = ["/academyx/", "/cours/academy/", "academy.json", "/fantome/"]
    page = _page_synthetique(tmp_path, "".join(f'<a href="{u}">x</a>' for u in liens))
    bad = broken_links(page, root=tmp_path)
    rapportes = {u for u in liens if any(repr(u) in b and "fichier absent" in b for b in bad)}
    assert rapportes == set(liens), (
        f"lien(s) absent(s) laissé(s) passer : {sorted(set(liens) - rapportes)} "
        f"(rapporté : {bad})")


def test_la_declaration_n_excuse_que_l_absence(tmp_path):
    """Un dossier déclaré qui EXISTE sur le disque est scanné comme les autres.

    Si la déclaration était consultée avant le disque, elle masquerait tout ce
    qu'elle couvre : une ancre morte dans un `academy/` ressuscité passerait
    verte. Ici l'ancre absente doit être rapportée, la présente acceptée.
    """
    (tmp_path / "academy").mkdir()
    (tmp_path / "academy" / "index.html").write_text(
        '<h2 id="present">ok</h2>', encoding="utf-8")
    page = _page_synthetique(
        tmp_path, '<a href="/academy/#present">ok</a><a href="/academy/#absent">ko</a>')
    bad = broken_links(page, root=tmp_path)
    assert len(bad) == 1 and "#absent" in bad[0], bad


def test_un_chemin_servi_ailleurs_n_existe_pas_dans_ce_site():
    """Un dossier mort ne doit pas pouvoir masquer le dépôt-projet.

    GitHub Pages sert `/academy/` depuis RoJLD/academy, quel que soit le contenu
    d'un dossier `academy/` de ce dépôt — mesuré le 2026-10-14 : l'app du
    dépôt-projet était servie alors que l'ancien dossier existait encore. Un
    tel dossier, s'il réapparaissait (restauration, fusion d'une vieille
    branche, build d'un ancien générateur), ne serait jamais servi, mais les
    gardes le liraient à la place de la vraie page : l'ancre morte, le thème, la
    nav seraient vérifiés sur un fantôme. Il doit donc faire rougir ici.
    """
    presents = {prefixe: depot
                for prefixe, depot in servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT.items()
                if (ROOT / prefixe).exists()}
    assert not presents, (
        f"chemin(s) servi(s) par un autre dépôt mais présent(s) dans ce site : "
        f"{presents} — GitHub Pages ne les sert jamais ; retirer le dossier, ou la "
        "déclaration si ce site reprend ce chemin")


# Les destinations de la nav sont DÉCOUVERTES sur le disque (répertoires dont
# l'`index.html` porte la marque de la nav partagée), pas listées à la main.
#
# Mesuré : retirer `"demos"` de la constante écrite ici faisait disparaître
# TROIS cas de test avec elle — 485 passed, aucun rouge. La garde cessait de
# viser la destination que H3 venait justement de rétablir. Une constante ne
# peut pas se surveiller elle-même ; le témoin est le site publié
# (`corpus_publie.destinations_nav`), qui continue de voir `/demos/` exister.
NAV_DESTINATIONS = corpus_publie.destinations_nav()

# Les destinations de la nav qu'un AUTRE dépôt sert (`/academy/` -> RoJLD/academy
# depuis le 2026-10-14). Le disque ne peut pas les découvrir : elles viennent de
# la topologie de la nav, filtrée par la déclaration `servi_ailleurs`. Les gardes
# « la nav pointe toute la nav » exigent les deux familles de liens.
NAV_SERVIE_AILLEURS = corpus_publie.destinations_nav_servies_ailleurs()
NAV_COMPLETE = NAV_DESTINATIONS + NAV_SERVIE_AILLEURS


def test_les_destinations_de_nav_viennent_bien_du_disque():
    """Plancher du témoin : découvrir ne doit pas pouvoir vouloir dire rétrécir.

    L'attendu était ici une liste de six noms écrite à la main. Elle divergeait
    bien de la découverte (une nav amputée la faisait rougir), mais elle restait
    un vœu recopié : rien ne l'ancrait au site, et une septième section publiée
    l'aurait laissée muette jusqu'à ce qu'on pense à l'y ajouter.

    L'attendu est maintenant un SECOND calcul, qui ne partage aucun marqueur avec
    le premier : `destinations_nav()` reconnaît une section à la marque
    `nav-brand` de sa page ; `sections_par_topologie_de_la_nav()` la reconnaît à
    la fermeture des liens (chaque page de la nav déclare exactement le même
    groupe, et ce groupe est elle-même). Fausser un marqueur, retirer une
    destination des navs, ou retirer sa marque à une page : les deux calculs
    divergent dans les trois cas.
    """
    topologie = set(corpus_publie.sections_par_topologie_de_la_nav())
    assert set(NAV_DESTINATIONS) == topologie, (
        f"les deux lectures de la nav divergent — marquées {sorted(NAV_DESTINATIONS)}, "
        f"fermées par les liens {sorted(topologie)}")
    assert NAV_DESTINATIONS, "aucune destination de nav découverte"


def test_les_cibles_de_navigation_existent():
    """Les destinations LOCALES de la nav partagée sont des pages réelles.

    Nécessaire, très insuffisant : cette assertion ne regarde que le disque.
    Une revue par mutation l'a mesuré — retirer `/demos/` de la nav de
    `build_highlights.py` laissait la suite ENTIÈREMENT verte (351 passed),
    alors que c'est exactement le défaut que H3 venait de corriger. Un
    répertoire qui existe ne prouve pas qu'un lien y mène. Les deux tests
    suivants ferment ce trou.
    """
    for dest in NAV_DESTINATIONS:
        assert (ROOT / dest / "index.html").is_file(), dest


@pytest.mark.parametrize("page", NAV_DESTINATIONS)
def test_la_page_publiee_pointe_toute_la_nav(page):
    """L'artefact servi porte tous les liens de la nav, ceux servis ailleurs
    compris — attrape une page laissée périmée."""
    html = (ROOT / page / "index.html").read_text(encoding="utf-8")
    manquants = [d for d in NAV_COMPLETE if f'href="/{d}/"' not in html]
    assert not manquants, (
        f"{page}/index.html : destination(s) absente(s) de la nav {manquants} — "
        "la page devient un cul-de-sac pour ces sections")


@functools.lru_cache(maxsize=1)
def _rendu_des_builders():
    """(nom, html) produit en mémoire par chaque générateur de page de nav."""
    import build_browse, build_demos                         # noqa: E401
    import build_graph, build_highlights, build_projects     # noqa: E401
    p = _real_profile()
    return {
        "projects": build_projects.build_projects(p, write=False),
        "explorer": build_browse.build_browse(p, write=False),
        "highlights": build_highlights.build_highlights(p, write=False),
        "graph": build_graph.build_graph(p, write=False),
        "demos": build_demos.build_demos(p, write=False),
    }


def test_la_table_des_generateurs_couvre_toutes_les_destinations():
    """La table ci-dessus est écrite à la main : le disque la tient.

    Sans ce test, en retirer une entrée retirerait les deux cas paramétrés qui
    l'exercent — la couverture rétrécirait sans un seul rouge.
    """
    assert set(_rendu_des_builders()) == set(NAV_DESTINATIONS), (
        f"table des générateurs {sorted(_rendu_des_builders())} désaccordée avec "
        f"les destinations publiées {sorted(NAV_DESTINATIONS)}")


@pytest.mark.parametrize("page", NAV_DESTINATIONS)
def test_le_generateur_emet_des_liens_qui_se_resolvent(page):
    """Le scan anti-404, appliqué à la SORTIE du générateur, pas au disque.

    Mesuré : neutraliser `_abs_url` de `build_projects` (rendre l'URL telle
    quelle au lieu de la préfixer par `/`) laissait la suite verte. C'est
    pourtant la régression exacte que H2 venait de corriger : servi depuis
    `/projects/`, `articles/x.html` désigne `/projects/articles/x.html` (404).
    Le disque, lui, restait juste — jusqu'au prochain build, qui aurait publié
    le défaut sans que rien ne le signale.
    """
    html = _rendu_des_builders()[page]
    bad = broken_links_in(html, ROOT / page / "index.html")
    assert not bad, ("le générateur émet un ou des liens non résolvables :\n  "
                     + "\n  ".join(bad))


@pytest.mark.parametrize("page", NAV_DESTINATIONS)
def test_le_generateur_emet_toute_la_nav(page):
    """La même garde une couche plus tôt : sur la SORTIE du générateur.

    Assertion sur le disque seul, un builder amputé passerait vert tant que
    personne ne reconstruit. C'est la source qui doit être tenue, pas seulement
    l'artefact qu'elle a produit un jour.
    """
    html = _rendu_des_builders()[page]
    manquants = [d for d in NAV_COMPLETE if f'href="/{d}/"' not in html]
    assert not manquants, (
        f"le générateur de /{page}/ n'émet plus {manquants} dans sa nav")


# ── Les artefacts publiés SONT la sortie de leurs générateurs ───────────────
#
# Mesuré le 2026-10-19 sur une copie VIERGE de la branche (`git archive HEAD |
# tar -x`, `git init` + commit, puis `py -3.13 tools/build_site.py`, rc 0) : DEUX
# fichiers suivis bougeaient — `projects/index.html` et `demos/index.html`.
# L'écart était un commentaire JS resté dans sa version d'avant la dernière
# édition du générateur, et il publiait un chiffre FAUX : `/demos/` annonçait
# « 31 chaînes de texte visible hors nav » quand le parseur qu'il cite en mesure
# 33 (28 distinctes). Les quatre autres pages étaient identiques à leur sortie :
# la divergence n'était donc pas un artefact de la comparaison.
#
# Aucune garde de ce dépôt ne voyait cela. Les cinq `test_*_idempotent` existants
# (`test_build_demos.py::test_idempotent` et ses quatre frères) comparent le
# générateur À LUI-MÊME (`render(p) == render(p)`) : ils prouvent qu'il est
# déterministe, pas que le fichier publié est sa sortie. Mesuré avec les deux
# pages périmées : 1631 passed, 6 skipped — le vert de référence exact.
#
# Un fichier dérivé qui peut diverger de son générateur sans un seul rouge est un
# deuxième lieu de vérité — le défaut même que la nav unifiée corrige, replacé
# une couche plus bas. La garde vit ICI parce que `test_liens_internes.py` est le
# seul fichier que joue la porte « Publier » (cf. docstring du module) : posée
# ailleurs, elle serait muette à l'instant où elle compterait.


@functools.lru_cache(maxsize=1)
def _html_regenere() -> dict[str, str]:
    """{page publiée: le HTML que son générateur produit MAINTENANT}.

    Population dérivée, aucune liste de pages écrite ici : les cinq sous-pages
    viennent de `_rendu_des_builders()` (table tenue par
    `test_la_table_des_generateurs_couvre_toutes_les_destinations`), l'accueil de
    `build_site.build_html`.

    LIMITE NOMMÉE pour l'accueil : `build_html` INJECTE dans le fichier qu'on lui
    donne (régions `<!-- BUILD:x -->` et `/* BUILD:i18n_x */`, puis
    synchronisation du texte statique FR) au lieu de le réécrire. La comparaison
    couvre donc ses dix régions générées et ce texte statique, pas son balisage
    écrit à la main — qui n'a aucun générateur, donc rien d'où diverger
    (arbitrage 1 du 2026-10-15, cf. le docstring de `tools/nav.py`).
    """
    import build_site  # noqa: E401
    out = {f"{page}/index.html": html
           for page, html in _rendu_des_builders().items()}
    out["index.html"] = build_site.build_html(_index_html(), _real_profile())
    return out


def test_la_table_des_artefacts_couvre_toutes_les_pages_de_la_nav():
    """Plancher : la garde ci-dessous ne doit pas pouvoir rétrécir en silence.

    Ses cas sont paramétrés sur une population DÉCOUVERTE
    (`corpus_publie.pages_de_la_nav_partagee()`), et `_html_regenere()` doit la
    couvrir en entier : une page qui sortirait de la table perdrait son cas de
    test en même temps que la couverture qu'il apporte — c'est le défaut que
    `corpus_publie` documente en tête.
    """
    nav = set(corpus_publie.pages_de_la_nav_partagee())
    assert len(nav) >= 6, f"seules {len(nav)} page(s) de nav découvertes : {sorted(nav)}"
    assert set(_html_regenere()) == nav, (
        f"la table des artefacts régénérés {sorted(_html_regenere())} ne couvre pas "
        f"les pages de la nav partagée {sorted(nav)}")


@pytest.mark.parametrize("rel", sorted(corpus_publie.pages_de_la_nav_partagee()))
def test_l_artefact_publie_est_la_sortie_de_son_generateur(rel):
    """Le fichier servi est, caractère pour caractère, ce que son générateur produit.

    Prouvée ROUGE par mutation le 2026-10-19, dans les deux sens qui comptent :
    une édition du générateur sans régénération (un chiffre du commentaire de
    `build_demos.py` changé) et une édition de l'artefact sans son générateur.
    Les deux nomment la page et la première ligne qui diverge.
    """
    attendu = _html_regenere()[rel]
    publie = (ROOT / rel).read_text(encoding="utf-8")
    if publie == attendu:
        return
    a, b = attendu.splitlines(), publie.splitlines()
    no = next((i for i in range(max(len(a), len(b)))
               if a[i:i + 1] != b[i:i + 1]), 0) + 1
    vu = (b[no - 1] if no - 1 < len(b) else "<fin de fichier>")[:160]
    veut = (a[no - 1] if no - 1 < len(a) else "<fin de fichier>")[:160]
    pytest.fail(f"""{rel} n'est plus la sortie de son générateur — premier écart ligne {no} ({len(b)} lignes publiées, {len(a)} attendues)
  publié  : {vu}
  attendu : {veut}
  remède : `py -3.13 tools/build_site.py`, puis committer l'artefact régénéré""")


def test_la_nav_partagee_mene_toujours_a_l_academy():
    """Spec § 9.3 : retirer la page n'est pas retirer le lien.

    `/academy/` n'est plus une page de ce site — le dépôt-projet RoJLD/academy
    la sert sous le même domaine. Elle est donc sortie de `NAV_DESTINATIONS`, qui
    ne découvre que des pages du disque, et les gardes ci-dessus ne l'exigent
    plus qu'à travers `NAV_SERVIE_AILLEURS`, découverte dans la nav elle-même.
    Retirer `/academy/` de TOUTES les navs ferait disparaître l'exigence avec le
    lien : la fermeture du groupe tiendrait encore, sur cinq membres. Mesuré, ce
    test neutralisé : le lien retiré des six pages publiées ne faisait plus
    rougir que `test_nav_academy_link_everywhere` — et seulement parce qu'il
    relit l'accueil ; les cinq pages de nav passaient. (Retiré d'UNE seule
    page, la topologie ne ferme plus et rougit d'elle-même.)

    D'où ce nom écrit en clair, à la manière des attributs dormants plus haut :
    rien sur ce disque ne peut découvrir une page servie ailleurs, c'est ce qui
    la définit. Le dépôt qui la sert est vérifié avec elle — sans déclaration,
    le scan anti-404 la refuserait.
    """
    assert "academy" in NAV_SERVIE_AILLEURS, (
        f"la nav partagée ne mène plus à /academy/ (destinations servies ailleurs "
        f"découvertes : {NAV_SERVIE_AILLEURS}) — le lien devait survivre au retrait "
        "de la page (spec § 9.3)")
    assert servi_ailleurs.depot_qui_sert("academy/") == "RoJLD/academy"


def test_chaque_page_de_la_nav_declare_les_memes_destinations_ancres_comprises():
    """La nav des six pages : MÊMES destinations, MÊME ordre, ancres comprises.

    `test_les_destinations_de_nav_viennent_bien_du_disque` compare deux lectures
    qui ne regardent que les répertoires : elles s'accordaient sur six noms
    pendant que l'accueil portait 11 entrées, /projects/ et /demos/ 8, et
    /explorer/, /highlights/, /graph/ 7. Mesuré le 2026-10-15 : `/#education`,
    `/#skills` et `/#blog` n'existaient sur AUCUNE page sauf l'accueil, et
    `/#contact` manquait sur trois des cinq sous-pages. Aucun rouge — un
    visiteur de /explorer/ n'avait aucun chemin de nav vers la formation, les
    compétences, le blog ni le contact, et la nav étant `position:fixed`, rien
    ne défilait pour les atteindre.

    CE QUE CE TEST DISAIT DE FAUX JUSQU'AU 2026-10-19, et qu'il ne dit plus :
    « une entrée retirée de toutes quitte l'union, mais la topologie des
    répertoires rougit alors dans le test cité ci-dessus ». C'est vrai d'une
    destination de RÉPERTOIRE (`destinations_nav()` continue de voir le dossier,
    la topologie ne ferme plus) et FAUX d'une ANCRE : aucun calcul topologique de
    ce dépôt ne voit `/#education`. Mesuré par mutation, les onze entrées passées
    à dix sur les SIX pages : la perte d'un répertoire (`/graph/`) rougissait,
    la perte d'une ancre (`/#education`) laissait la suite ENTIÈREMENT VERTE —
    c'est-à-dire précisément la classe de régression pour laquelle la nav unifiée
    a été écrite. Un commentaire qui affirme une couverture qu'on n'a pas est
    pire qu'un angle mort : il invite à ne pas chercher.

    Trois exigences, chacune fermant une des trois fuites mesurées :

      1. les six pages déclarent la MÊME SÉQUENCE, pas le même ensemble.
         L'union ne peut plus servir d'attendu — elle n'a pas d'ordre — donc la
         comparaison est deux à deux contre la séquence de l'accueil, la seule
         page écrite à la main. L'ordre des onze entrées n'était tenu par rien
         (une barre réordonnée passait verte sur les six pages) et un ensemble
         perd les doublons ;
      2. un PLANCHER, qui est la seule réponse à une perte uniforme : le nombre
         d'entrées vient des clés `nav_*` de `site_texts.json`, un témoin qui ne
         vit ni dans `nav.py` ni dans les artefacts (cf.
         `corpus_publie.cles_nav_de_site_texts`) ;
      3. aucune destination ne doit porter le préfixe `NON_RECONNUE` : une forme
         d'href que le témoin ne sait pas lire était écartée en silence.

    Témoin DISTINCT de `test_nav_unifiee.py`, et c'est délibéré : celui-là
    confronte chaque page à la source (`tools/nav.py`), celui-ci ne regarde que
    les artefacts, plus `site_texts.json` pour son plancher. Un dépôt où
    `nav.py` disparaîtrait garde cette garde-ci.

    `/` est exclu, et il faut le dire : les cinq sous-pages portent
    `<a class="nav-brand" href="/">`, l'accueil un `<span class="nav-brand">`
    SANS href — il ne se lie pas à lui-même. `/` est donc le résidu
    irréductible de l'égalité, et le soustraire sans le nommer est la façon
    dont une garde pourrit. L'invariant réel vit à côté, dans
    `test_nav_unifiee.py::test_chaque_sous_page_ramene_a_l_accueil` : chaque
    sous-page porte un lien vers `/`, l'accueil n'en a pas besoin.
    """
    ordonnees = corpus_publie.destinations_ordonnees_de_la_nav_par_page()
    par_page = {rel: tuple(d for d in dests if d != "/")
                for rel, dests in ordonnees.items()}
    assert len(par_page) >= 6, (
        f"seules {len(par_page)} page(s) portent la nav partagée : {sorted(par_page)}")
    assert "index.html" in par_page, (
        "l'accueil ne porte plus la marque de la nav partagée — il sortait déjà "
        "du calcul de fermeture par répertoires, il ne doit pas sortir de celui-ci")

    # (3) Le silence d'abord : une forme non reconnue fausserait tout le reste.
    illisibles = {rel: [d for d in dests if d.startswith(corpus_publie.NON_RECONNUE)]
                  for rel, dests in par_page.items()}
    illisibles = {rel: v for rel, v in illisibles.items() if v}
    assert not illisibles, (
        "des href de la nav ne se normalisent pas, donc ne sont comparés à rien : "
        f"{illisibles} — écrire `/x/` (répertoire) ou `/#x` (section de l'accueil)")

    # (2) Le plancher : une perte UNIFORME ne peut pas se cacher dans l'union.
    attendu = len(corpus_publie.cles_nav_de_site_texts())
    assert attendu >= 11, (
        f"`site_texts.json` ne déclare plus que {attendu} clé(s) `nav_*` : le "
        "plancher de ce test rétrécirait avec la nav qu'il garde (11 le 2026-10-19)")
    courtes = {rel: len(dests) for rel, dests in par_page.items()
               if len(dests) != attendu}
    assert not courtes, (
        f"la nav ne déclare plus {attendu} destinations (le nombre de clés `nav_*` "
        f"de site_texts.json) : {courtes} — une entrée perdue sur TOUTES les pages "
        "ne se voit pas dans leur union, seul ce plancher la nomme")

    # (1) L'égalité deux à deux, ordre et doublons compris.
    reference = par_page["index.html"]
    ecarts = {rel: list(dests) for rel, dests in par_page.items()
              if dests != reference}
    assert not ecarts, (
        "la nav partagée n'est pas la même partout, ou pas dans le même ordre — "
        f"{ecarts} (l'accueil déclare : {list(reference)})")


@pytest.mark.parametrize("href, reconnue", [
    ("/graph/", True),             # la forme correcte d'une page du site
    ("/#education", True),         # la forme correcte d'une section de l'accueil
    ("/", True),                   # la marque
    ("/graph", False),             # la faute de frappe : barre finale oubliée
    ("/articles/x.html", False),   # un fichier, pas un répertoire
    ("/a/b/", False),              # deux segments
    ("/graph/?v=2", False),        # une query dans une destination de nav
])
def test_une_destination_non_reconnue_est_nommee_et_jamais_jetee(href, reconnue):
    """Le témoin n'a pas le droit de rendre le silence — capacité DORMANTE.

    `_normaliser_destination` rendait `None` pour toute forme inattendue, et son
    unique appelant écrivait `if dest: vues.add(dest)` : la destination était
    écartée sans un mot. Mesuré le 2026-10-19 : si les SIX pages portaient la
    même forme inattendue, l'ensemble comparé rétrécissait partout à la fois et
    l'égalité restait verte — un témoin qui jette ce qu'il ne comprend pas ne
    rapporte plus ce que les pages déclarent, il rapporte ce qu'il sait lire.

    Pourquoi un test à entrées fabriquées plutôt qu'une mutation du corpus :
    aucune page publiée ne porte aujourd'hui une de ces formes (mesuré, les 6
    navs ne déclarent que `/x/`, `/#x` et `/`), donc la branche est DORMANTE, au
    même titre que `poster` dans `URL_ATTR` ou la query de `resolve`. Et la
    mutation qui en fabrique une rougit AVANT d'arriver jusqu'ici : écrire
    `/graph` au lieu de `/graph/` sort `graph/` du groupe fermé de la nav, et
    c'est le plancher de population du test ci-dessus qui parle (mesuré :
    « seules 5 page(s) portent la nav partagée »). Le contrat se vérifie donc là
    où le corpus est muet.

    Les deux sens sont exercés : un témoin qui préfixerait TOUT passerait la
    moitié de ce test sans rien distinguer.
    """
    vu = corpus_publie._normaliser_destination("explorer/index.html", href)
    assert vu.startswith(corpus_publie.NON_RECONNUE) != reconnue, (
        f"{href!r} : le témoin rend {vu!r} — une forme "
        f"{'reconnue' if reconnue else 'inconnue'} ne doit "
        f"{'pas ' if reconnue else ''}être nommée comme non reconnue")
    assert vu, f"{href!r} : le témoin rend une valeur vide, donc jetable en silence"


# ── L'amputation mobile : aucune destination ne disparaît au doigt ───────────
#
# Quatre générateurs et l'accueil portaient une règle qui CACHE les liens de la
# nav sous un seuil de largeur, chacun la sienne :
#
#   build_browse.py     @media(max-width:640px){… .nav-r a:not(.on){display:none} …}
#   build_graph.py      @media(max-width:640px){… .nav-r a:not(.on){display:none} …}
#   build_highlights.py @media(max-width:640px){… .nav-r a:not(.on){display:none} …}
#   build_projects.py   @media(max-width:640px){… .nav-r a:not(.nav-projects){display:none} …}
#   index.html          @media(max-width:480px){.nav-r a:not(:nth-child(-n+3)){display:none}}
#
# Mesuré au navigateur à 390 px : l'accueil ne gardait que 3 onglets sur 11, les
# sous-pages 1 sur 7 — et aucun menu dépliant n'existait. Dans tout le document,
# à cette largeur, il n'y avait AUCUN lien visible vers /projects/, /explorer/,
# /highlights/, /academy/ ni /graph/. La nav étant `position:fixed`, rien ne
# défilait pour les atteindre : les sections étaient inaccessibles au téléphone.
#
# Cacher un lien est légitime — derrière un dépliant qui le rend. Le supprimer de
# l'affichage sans contrepartie ne l'est pas.
_CACHE_UN_LIEN_DE_NAV = re.compile(
    r"\.nav-r[^{};]*\ba\b[^{}]*\{[^{}]*display\s*:\s*none")
# Le dépliant : une règle d'ÉTAT qui rend aux liens un `display` autre que
# `none`. `aria-expanded` seul ne suffit pas comme preuve — l'accueil en porte
# quatre, sur les accordéons de section, qui n'ont rien à voir avec la nav.
_REND_LES_LIENS = re.compile(
    r'(?::checked|\[aria-expanded="true"\]|\.(?:open|ouvert))[^{}]*\.nav-r'
    r"[^{}]*\{[^{}]*display\s*:\s*(?!none)")


@pytest.mark.parametrize("page", NAV_DESTINATIONS)
def test_aucune_regle_ne_cache_un_lien_de_nav_sans_le_rendre(page):
    html = (ROOT / page / "index.html").read_text(encoding="utf-8")
    caches = _CACHE_UN_LIEN_DE_NAV.findall(html)
    assert not caches or _REND_LES_LIENS.search(html), (
        f"{page}/index.html : une règle cache les liens de la nav "
        f"({caches[:1]}) et rien ne les rend — au téléphone, les sections "
        "deviennent inatteignables, la nav étant `position:fixed`")


def test_l_accueil_non_plus_ne_cache_aucun_lien_de_nav_sans_le_rendre():
    """Même garde sur l'accueil, qui n'est pas dans `NAV_DESTINATIONS` : ce
    n'est pas un répertoire. C'est la page la plus amputée que la mesure ait
    trouvée (3 onglets sur 11 à 390 px) et elle sortait du champ paramétré."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    caches = _CACHE_UN_LIEN_DE_NAV.findall(html)
    assert not caches or _REND_LES_LIENS.search(html), (
        f"index.html : une règle cache les liens de la nav ({caches[:1]}) et "
        "rien ne les rend")


# --- La marque de la nav doit vivre DANS la nav ------------------------------
#
# `destinations_nav()` cherche `nav-brand` n'importe où dans la page ;
# `pages_atteintes_par_la_nav()` la cherche DANS le bloc `<nav>`. Les deux
# lectures se rejoignent aujourd'hui, mais rien ne l'exigeait. Mesuré 2026-07-29 :
# renommer la seule occurrence de `class="nav-brand"` du bloc `<nav>` de
# `highlights/index.html` — puis celle de son générateur — laissait la suite
# VERTE (496 passed) dans les deux cas. La règle CSS `.nav-brand{…}`, restée en
# tête de page, suffisait à faire croire au premier témoin que la page portait
# toujours la nav partagée, pendant que le second cessait d'y voir une source.
#
# Deux conséquences, aucune signalée : le lien « R. Denis » vers l'accueil perdait
# sa classe (et son style), et le témoin du thème rétrécissait en silence — ce
# que `corpus_publie` a précisément été écrit pour rendre impossible.

@pytest.mark.parametrize("page", NAV_DESTINATIONS)
def test_la_marque_de_la_nav_vit_dans_la_nav_et_pas_seulement_dans_le_css(page):
    """Les deux lectures de la marque doivent porter sur le même objet.

    L'attendu n'est pas un motif recopié : c'est l'ACCORD entre le témoin de
    page (`destinations_nav`, qui a retenu cette page) et le témoin de bloc
    (celui de `pages_atteintes_par_la_nav`). Une page retenue par l'un et ignorée
    par l'autre est un désaccord, quelle que soit la marque choisie.
    """
    marque = corpus_publie._NAV_PARTAGEE
    for source, html in ((f"{page}/index.html",
                          (ROOT / page / "index.html").read_text(encoding="utf-8")),
                         (f"générateur de /{page}/", _rendu_des_builders()[page])):
        blocs = corpus_publie._BLOC_NAV.findall(html)
        assert blocs, f"{source} : aucun bloc <nav>"
        assert [b for b in blocs if marque in b], (
            f"{source} : la marque {marque!r} n'est plus DANS la nav (elle ne "
            f"subsiste que dans la feuille de style) — la page reste comptée "
            f"comme destination mais n'est plus vue comme source de nav")


# --- validate_profile : la même garde, une couche plus tôt (sur la donnée) ----

def _real_profile():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def test_profil_reel_valide_liens_compris():
    assert validate(_real_profile(), root=ROOT) == []


def test_validateur_refuse_un_lien_mort():
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["article"] = "articles/fantome.html"
    errs = validate(p, root=ROOT)
    assert any("cible inexistante" in e and "fantome" in e for e in errs), errs


def test_validateur_refuse_une_ancre_absente():
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["demo"] = "demos/#ancre-inexistante"
    errs = validate(p, root=ROOT)
    assert any("ancre #ancre-inexistante" in e for e in errs), errs


def test_validateur_refuse_un_lien_relatif_a_la_page():
    """La régression exacte publiée : `index.html#demos` sur /projects/."""
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["demo"] = "index.html#demos"
    errs = validate(p, root=ROOT)
    assert any("relatif à la page" in e for e in errs), errs
    # ... et il est refusé même sans accès disque (règle structurelle).
    assert any("relatif à la page" in e for e in validate(p, root=None)), "root=None"


def test_validateur_refuse_une_ancre_nue():
    """`#demos` dans le corpus : la cible dépend de la page qui rend le lien.

    Mesuré : désactiver ce refus (`if not path:` -> `if False:`) laissait la
    suite à 507 passed — la branche n'avait aucun test, alors qu'elle défend la
    variante la plus insidieuse du défaut publié. `index.html#demos` était au
    moins visiblement faux ; `#demos` a l'air correct sur l'accueil, et devient
    un cul-de-sac silencieux dès que le même lien est rendu par /projects/ ou
    /explorer/, où aucune section `#demos` n'existe.

    Règle structurelle : refusée même sans accès disque, parce que l'ambiguïté
    est dans la forme du lien, pas dans l'état du site.
    """
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["demo"] = "#demos"
    for racine in (ROOT, None):
        errs = validate(p, root=racine)
        assert any("ancre nue" in e and "demo" in e for e in errs), (racine, errs)


def test_validateur_accepte_le_meme_lien_ancre_a_la_racine():
    """Contre-épreuve : c'est bien la NUDITÉ de l'ancre qui est refusée.

    Sans elle, un validateur qui refuserait tout lien portant un `#` passerait
    le test précédent en cassant `/#demos`, la forme correcte.
    """
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["demo"] = "/demos/#grid"
    assert validate(p, root=ROOT) == []


@pytest.mark.parametrize("relatif, absolu", [
    ("demos/#grid", "/demos/#grid"),                       # vivant
    ("demos/#ancre-fantome", "/demos/#ancre-fantome"),     # ancre morte
    ("repertoire-fantome/", "/repertoire-fantome/"),       # répertoire mort
    ("fantome.html", "/fantome.html"),                     # fichier mort
])
def test_le_validateur_juge_pareil_un_lien_ecrit_a_la_racine_ou_relatif(relatif, absolu):
    """Un lien écrit `/demos/#x` doit être RÉSOLU, pas classé « externe ».

    Mesuré 2026-07-29 : ajouter `"/"` à `_EXTERNAL` — donc faire sortir du champ
    du validateur tout lien écrit depuis la racine — laissait la suite VERTE. Le
    corpus n'écrit aujourd'hui que des chemins relatifs (`articles/x.html`,
    `demos/#bs`, mesuré : 4 URL locales, aucune absolue), alors que le site
    publié, lui, n'écrit QUE des chemins absolus (`href="/demos/"`). La première
    entrée de corpus écrite dans cette forme-là aurait donc échappé à toute
    validation, et `test_validateur_accepte_le_meme_lien_ancre_a_la_racine`
    serait resté vert sans rien distinguer : « accepté parce que valide » et
    « jamais examiné » y rendent la même liste vide.

    L'attendu vient du DISQUE, jamais d'une constante : c'est l'existence réelle
    de la cible qui dit si le lien doit passer, et les deux écritures du MÊME
    chemin doivent donner le même verdict.
    """
    verdicts = []
    for forme in (relatif, absolu):
        p = _real_profile()
        p["projects"][0].setdefault("links", {})["demo"] = forme
        verdicts.append([e for e in validate(p, root=ROOT) if "demo" in e])
    assert bool(verdicts[0]) == bool(verdicts[1]), (
        f"{relatif!r} et {absolu!r} désignent la même cible mais reçoivent des "
        f"verdicts différents : {verdicts}")
    cible = ROOT / absolu.partition("#")[0].lstrip("/")
    if cible.is_dir():
        cible = cible / "index.html"
    frag = absolu.partition("#")[2]
    attendu_sain = cible.exists() and (
        not frag or _has_anchor(cible.read_text(encoding="utf-8", errors="replace"), frag))
    assert bool(verdicts[1]) != attendu_sain, (
        f"{absolu!r} : cible {'saine' if attendu_sain else 'morte'} sur le disque, "
        f"verdict du validateur {verdicts[1]}")


def test_validateur_refuse_un_lien_mort_dans_identity_links():
    """Le validateur regarde les TROIS sources d'URL du corpus, pas deux.

    Mesuré : supprimer la boucle `identity.links` de `_local_urls` laissait la
    suite à 488 passed — le compte exact du vert de référence. Les trois liens
    d'identité publiés sont externes aujourd'hui (portfolio, LinkedIn, GitHub),
    donc la branche est dormante sur le corpus réel ; elle cesserait de l'être
    au premier lien local (un CV, une page de contact), et personne ne le
    saurait. Le champ du validateur se vérifie par comportement, avec une donnée
    qui l'exerce.
    """
    p = _real_profile()
    p.setdefault("identity", {}).setdefault("links", {})["cv"] = "cv/fantome.html"
    errs = validate(p, root=ROOT)
    assert any("identity.links.cv" in e and "cible inexistante" in e for e in errs), errs


def test_validateur_refuse_un_lien_mort_dans_un_article():
    """Même mesure pour `articles[].url`, l'autre branche de `_local_urls`."""
    p = _real_profile()
    p["articles"] = [{"id": "fantome", "url": "articles/jamais-ecrit.html"}]
    errs = validate(p, root=ROOT)
    assert any("article 'fantome'.url" in e and "cible inexistante" in e for e in errs), errs


def test_validateur_laisse_passer_les_liens_externes():
    p = _real_profile()
    p["projects"][0].setdefault("links", {})["github"] = "https://github.com/RoJLD/rien"
    assert validate(p, root=ROOT) == []


# --- Les liens RoJLD du profil, confrontés au relevé des dépôts publics ------
#
# Le test juste au-dessus dit que le validateur laisse passer les liens
# EXTERNES, et c'est voulu. Ce qui suit est donc ce qui les juge à sa place.
#
# Pourquoi ces gardes vivent ICI et pas dans `test_sync_github_projects.py`, où
# elles sont nées le 2026-10-15 : `publication.py::verifier()`, la porte du
# bouton « Publier », joue CE fichier en entier et ne joue pas celui-là. Mesuré
# sur une copie de l'arbre, les deux liens morts remis dans `profile.json` :
#     porte du cockpit   -> 5 contrôles sur 5 « OK », verdict ACCEPTE
#                           (et `/projects/` régénéré avec les deux boutons morts)
#     pytest du fichier  -> 2 failed, 37 passed
# Les gardes mordaient — ailleurs qu'à l'endroit où Robin publie.
#
# Le FICHIER plutôt que des node-ids ajoutés à la liste de `verifier()` : un
# node-id FAUX est bruyant (mesuré : `pytest f.py::test_absent` sort en 4,
# « ERROR: not found », donc la porte passe au rouge), mais un node-id OUBLIÉ est
# silencieux — et c'est exactement le défaut qu'on répare ici. Un fichier déjà
# dans la porte y fait entrer toute garde future qu'on y pose, sans que personne
# ait à se souvenir d'aller éditer `publication.py`.
#
# Elles ne pouvaient pas non plus aller dans `validate_profile` :
# `test_validateur_laisse_passer_les_liens_externes` exige `validate(p) == []`
# sur un `https://github.com/RoJLD/rien`, et l'y mettre aurait obligé à
# affaiblir ce test.
#
# Pourquoi un relevé committé et pas un appel réseau : un test qui interroge
# github.com punit un poste hors ligne et rend la suite non déterministe. Le
# réseau n'intervient donc qu'à la régénération, à la main :
#     python tools/sync_github_projects.py --temoin data/depots_publics_rojld.json
#
# Ce que ces gardes attrapent, mesuré le 2026-10-15 en visiteur anonyme :
#   * `projects[anthropos].links.github` -> https://github.com/RoJLD/Anthropos
#     rend 404 (dépôt passé privé). Le piège du diagnostic : `gh api
#     repos/RoJLD/Anthropos` AUTHENTIFIÉ rend 200 et `private: true` — la vue du
#     propriétaire, pas celle du recruteur. Le relevé, lui, vient de
#     `users/RoJLD/repos`, qui ne liste que le public (vérifié : le même ensemble
#     de 27 dépôts avec et sans jeton).
#   * `projects[hmm-studio].links.live` -> https://rojld.github.io/HMMstudio/
#     rend 301 vers http://robin-denis.com/HMMstudio/, qui rend 404 : le dépôt ne
#     publie pas de Pages (`has_pages: false`, et
#     `api.github.com/repos/RoJLD/HMMstudio/pages` -> 404). La carte de /projects/
#     affichait deux boutons dont un mort.
#
# Et le second défaut échappe au détecteur du dépôt MÊME CORRIGÉ : mesuré,
# `normalize_repo_url("https://rojld.github.io/HMMstudio/")` rend None, donc
# `catalog_github_refs` ne voit rien et `dead_links` reste vide. Élargir la
# fonction à tous les champs de `links` ferme l'angle mort du CHAMP, pas celui de
# l'HÔTE. La garde `fautifs_pages_sans_publication` ci-dessous est la seule à
# couvrir celui-là — bâtir la garde sur `dead_links` seul aurait refermé le
# dossier en y laissant le lien mort.
#
# Ce qu'elles n'attrapent PAS, et il faut le dire : le relevé vieillit. Un dépôt
# refermé demain ne sera vu qu'à la prochaine régénération. Ces gardes empêchent
# la RÉCIDIVE et tout lien NEUF vers un dépôt non public ; elles ne remplacent
# pas `python tools/sync_github_projects.py` joué de temps en temps avec le
# réseau. Elles ne voient rien d'un domaine tiers (l'URL d'un article), rien de
# `projects_meta.github_profile` (hors des trois sources de `_local_urls`), et
# `has_pages` dit qu'un dépôt publie des Pages, pas que le chemin exact existe.

_TEMOIN = ROOT / "data" / "depots_publics_rojld.json"

# GitHub Pages sert `/<segment>/` depuis le dépôt-projet `RoJLD/<segment>` quand
# celui-ci publie des Pages ; sinon le site utilisateur répond 404. Les deux
# écritures mènent au même endroit, le domaine personnalisé n'y change rien
# (mesuré : rojld.github.io/HMMstudio/ -> 301 -> robin-denis.com/HMMstudio/ -> 404).
_PAGE_PROJET = re.compile(
    r"^https?://(?:www\.)?(?:rojld\.github\.io|robin-denis\.com)/([^/#?]+)", re.IGNORECASE)


def _temoin():
    return json.loads(_TEMOIN.read_text(encoding="utf-8"))


def depots_rojld_vises(profil):
    """[(label, url, nom)] de chaque URL du profil qui vise github.com/RoJLD/<nom>.

    L'énumération des URL est empruntée à `validate_profile._local_urls` : les
    trois sources du corpus (TOUS les champs de `projects[].links`,
    `articles[].url`, `identity.links.*`), déjà tenues par leurs propres tests
    (`test_validateur_refuse_un_lien_mort_dans_identity_links` et sa jumelle sur
    les articles rougissent si une source disparaît). La ré-écrire ici donnerait
    un second recensement à maintenir, qui dériverait du premier sans bruit —
    c'est exactement le défaut que `catalog_github_refs` portait.
    """
    vises = []
    for label, url in vp._local_urls(profil):
        cle = sync_github_projects.normalize_repo_url(url)
        if not cle:
            continue
        owner, nom = cle.split("/", 1)
        if owner == "rojld":
            vises.append((label, url, nom))
    return vises


def pages_projet_visees(profil):
    """[(label, url, segment)] de chaque URL du profil visant `/<segment>/` du domaine."""
    vises = []
    for label, url in vp._local_urls(profil):
        m = _PAGE_PROJET.match(url or "")
        if m:
            vises.append((label, url, m.group(1)))
    return vises


def fautifs_depots_non_publics(profil, temoin):
    """Liens visant un dépôt RoJLD absent du relevé public : 404 pour un visiteur."""
    publics = {r["name"].lower() for r in temoin["repos"]}
    return [f"{label} -> {url}" for label, url, nom in depots_rojld_vises(profil)
            if nom not in publics]


def fautifs_pages_sans_publication(profil, temoin, root):
    """Liens visant `/<segment>/` que personne ne sert.

    Deux façons légitimes d'être servi, une seule suffit : le dépôt-projet
    `RoJLD/<segment>` publie des Pages, ou `<segment>` est écrit sur CE disque et
    le site utilisateur le sert. On ne consulte PAS `servi_ailleurs` : il déclare
    qu'un autre dépôt sert un chemin, pas qu'il le publie — le relevé est le plus
    exigeant des deux témoins, et c'est celui qu'on veut ici.
    """
    avec_pages = {r["name"].lower() for r in temoin["repos"] if r.get("has_pages")}
    return [f"{label} -> {url}" for label, url, seg in pages_projet_visees(profil)
            if seg.lower() not in avec_pages and not (root / seg).exists()]


def test_le_temoin_des_depots_publics_est_renseigne():
    """Contre-vacuité côté relevé : un relevé vide rendrait les gardes muettes."""
    t = _temoin()
    assert t["owner"] == "RoJLD"
    noms = {r["name"] for r in t["repos"]}
    assert "RoJLD.github.io" in noms, "le dépôt du site lui-même manque au relevé"
    assert len(noms) >= 20, f"relevé suspect : {len(noms)} dépôts (27 relevés le 2026-10-15)"
    assert any(r.get("has_pages") for r in t["repos"]), \
        "aucun dépôt à Pages : la garde des pages-projets ne jugerait plus rien"


def test_le_profil_declare_bien_des_liens_rojld_a_juger():
    """Contre-vacuité côté profil : sans ce plancher, la garde suivante passerait
    en ne jugeant rien le jour où l'énumération des URL rétrécit.

    Mesuré le 2026-10-15 : 4 liens RoJLD avant correctif (anthropos, hmm-studio,
    ppe-politique-monetaire, portfolio-site), 3 après le retrait d'Anthropos.
    """
    vises = depots_rojld_vises(_real_profile())
    assert len(vises) >= 3, f"seulement {len(vises)} liens RoJLD examinés : {vises}"


def test_aucun_lien_ne_vise_un_depot_rojld_absent_du_temoin():
    """La garde du premier défaut mesuré : un recruteur ne doit pas tomber sur un 404."""
    fautifs = fautifs_depots_non_publics(_real_profile(), _temoin())
    assert not fautifs, (
        f"depot RoJLD absent du releve des depots publics (404 anonyme) : {fautifs} — "
        "si le depot vient d'etre ouvert, regenerer le releve : "
        "python tools/sync_github_projects.py --temoin data/depots_publics_rojld.json")


def test_aucun_lien_ne_vise_une_page_projet_que_personne_ne_sert():
    """La garde du second défaut, celui du champ `links.live` : /HMMstudio/ rend 404.

    Asymétrie assumée avec sa sœur ci-dessus, qui a un plancher de contre-vacuité
    (`test_le_profil_declare_bien_des_liens_rojld_a_juger`) là où ce test-ci n'en
    a aucun. Mesuré le 2026-10-15 sur le corpus corrigé : `pages_projet_visees`
    rend 0 sur les 10 URL énumérées — le profil ne porte plus AUCUNE URL absolue
    vers son propre hôte, et c'est l'état CORRECT (une page du site se lie en
    relatif ; `identity.links.portfolio` vise `https://robin-denis.com` sans
    chemin, donc la racine, qui est servie). Un plancher du genre « au moins un
    lien absolu vers /<segment>/ » exigerait donc une donnée qu'on ne veut pas
    voir revenir : il rougirait sur le bon corpus. Ce qui tient le prédicat à sa
    place, ce sont les deux tests à profil fabriqué ci-dessous
    (`test_la_garde_des_pages_juge_les_deux_sens` et
    `test_les_gardes_lisent_tous_les_champs_de_links`) : les vider ou neutraliser
    `fautifs_pages_sans_publication` les fait rougir.
    """
    fautifs = fautifs_pages_sans_publication(_real_profile(), _temoin(), ROOT)
    assert not fautifs, f"`/<segment>/` sans Pages publiees ni dossier sur ce disque : {fautifs}"


# Les deux gardes ci-dessus sont DORMANTES sur le corpus corrigé : le profil
# publié n'a plus aucun lien mort, donc les vider les laisserait vertes. Le
# corpus ne pouvant plus fournir la preuve, on la fabrique — même procédé que les
# capacités dormantes du validateur, § suivant.

def test_la_garde_des_depots_nomme_un_depot_prive_injecte():
    """Le lien retiré du profil le 2026-10-15, rejoué sur un profil fabriqué."""
    profil = {"projects": [{"id": "fantome",
                            "links": {"github": "https://github.com/RoJLD/Anthropos"}}]}
    assert [v[2] for v in depots_rojld_vises(profil)] == ["anthropos"]
    fautifs = fautifs_depots_non_publics(profil, _temoin())
    assert len(fautifs) == 1 and "Anthropos" in fautifs[0], fautifs


def test_la_garde_des_pages_juge_les_deux_sens():
    """Une garde qui crie à tort est une garde qu'on éteint : `/demos/` est écrit
    sur ce disque et le site utilisateur le sert, alors que `/HMMstudio/` ne l'est
    nulle part (ni dossier local, ni Pages du dépôt-projet).
    """
    vivant = {"identity": {"links": {"demos": "https://robin-denis.com/demos/"}}}
    assert pages_projet_visees(vivant), "le lien doit entrer dans le champ de la garde"
    assert fautifs_pages_sans_publication(vivant, _temoin(), ROOT) == []

    mort = {"projects": [{"id": "fantome",
                          "links": {"live": "https://rojld.github.io/HMMstudio/"}}]}
    assert len(fautifs_pages_sans_publication(mort, _temoin(), ROOT)) == 1


def test_les_gardes_lisent_tous_les_champs_de_links():
    """Le défaut du 2026-10-15 n'était pas dans `links.github` : il était dans
    `links.live`. Une garde qui ne lit qu'un champ nommé referme le dossier en
    laissant le lien mort dedans.
    """
    profil = {"projects": [{"id": "x", "links": {
        "live": "https://github.com/RoJLD/jamais-public",
        "demo": "https://github.com/RoJLD/jamais-public-non-plus",
        "pdf": "https://rojld.github.io/jamais-publie/",
    }}]}
    fautifs = fautifs_depots_non_publics(profil, _temoin())
    assert len(fautifs) == 2, fautifs
    assert {f.split(" -> ")[0].rsplit(".", 1)[-1] for f in fautifs} == {"live", "demo"}
    assert len(fautifs_pages_sans_publication(profil, _temoin(), ROOT)) == 1


# --- Les capacités DORMANTES du validateur -----------------------------------
#
# Trois branches ne sont exercées par aucune donnée du corpus actuel, donc les
# neutraliser laissait la suite entière verte (mesuré : 534 passed dans les trois
# cas). Ce ne sont pas des mutations bénignes : chacune retire une capacité que
# la première donnée du bon genre rendrait décisive — et le jour où cette donnée
# arrive, personne ne se souvient d'aller relire le validateur.
#
# Le corpus ne pouvant pas fournir la preuve, on la fabrique : un mini-site en
# `tmp_path` et un profil minimal. Les assertions portent uniquement sur les
# erreurs de LIEN — un profil minimal en déclenche d'autres, sans rapport.

def _erreurs_de_lien(profile, root):
    return [e for e in validate(profile, root=root)
            if "ancre" in e or "cible inexistante" in e or "relatif" in e]


@pytest.mark.parametrize("balise, forme", [
    ('<h2 id="cible">x</h2>', 'id="…"'),
    ("<h2 id='cible'>x</h2>", "id='…'"),
    ('<a name="cible"></a>', 'name="…"'),
])
def test_validateur_reconnait_les_trois_formes_d_ancre(tmp_path, balise, forme):
    """Une ancre écrite autrement reste une ancre — sinon, faux 404.

    Mesuré : retirer `name="…"` ou `id='…'` des formes reconnues ne faisait
    rougir personne (le corpus n'écrit ses ancres qu'en `id="…"`), et aurait
    transformé la première ancre en apostrophes en lien mort imaginaire.
    """
    (tmp_path / "cible.html").write_text(balise, encoding="utf-8")
    p = {"projects": [{"id": "x", "links": {"demo": "cible.html#cible"}}]}
    assert _erreurs_de_lien(p, tmp_path) == [], f"forme {forme} non reconnue"
    q = {"projects": [{"id": "x", "links": {"demo": "cible.html#absente"}}]}
    assert _erreurs_de_lien(q, tmp_path), (
        f"forme {forme} : une ancre RÉELLEMENT absente n'est plus signalée")


@pytest.mark.parametrize("url", ["mailto:robin@example.com", "tel:+33100000000",
                                 "//cdn.example.com/x.js"])
def test_validateur_laisse_passer_les_schemas_non_resolvables(tmp_path, url):
    """`mailto:`, `tel:`, `//` ne désignent aucun fichier : les résoudre est un faux positif.

    Mesuré : retirer `mailto:` des schémas hors périmètre laissait la suite
    verte — les trois liens d'identité publiés sont des `https://`. La première
    adresse de contact écrite dans `identity.links` aurait produit une erreur
    « cible inexistante mailto:… », et une garde qui crie à tort est une garde
    qu'on éteint.
    """
    p = {"identity": {"links": {"contact": url}}}
    assert _erreurs_de_lien(p, tmp_path) == []


# --- Outils autonomes : ils doivent parler du MÊME corpus que profile.json ----
# `radar.html` portait 10 compétences en dur (dont 2 non déclarées) et
# `match.html` ne parcourait que 4 catégories sur 5 : deux dérives silencieuses
# qu'aucun test ne voyait, parce que ces pages ne sont produites par aucun build.

def _skill_categories():
    return [c for c in _real_profile()["skills"] if c != "radar_scores"]


def _skill_names():
    p = _real_profile()
    return [s["name"] for c, v in p["skills"].items() if c != "radar_scores" for s in v]


def _slug(name):
    import unicodedata
    n = unicodedata.normalize("NFD", str(name).lower())
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", n))


def test_radar_lit_profile_json():
    """Test de PRÉSENCE, et rien de plus — la lecture effective est tenue plus bas.

    Mesuré : garder cet appel et JETER son résultat (`DEFAULT_SKILLS` réassigné
    à un tableau en dur juste après) laissait la suite ENTIÈRE à 506 passed.
    La chaîne cherchée ici était toujours là, et la page affichait un profil
    inventé — le défaut exact que H13 corrigeait.
    """
    txt = (ROOT / "radar.html").read_text(encoding="utf-8")
    assert 'fetch("profile.json")' in txt, "radar.html ne lit toujours pas le corpus"


# Ce qui reçoit les compétences du radar, et ce qui a le droit de les lui donner.
_AFFECTATION_SKILLS = re.compile(r"\bDEFAULT_SKILLS\s*=\s*([^;\n]+)")


def test_le_radar_assigne_ses_competences_depuis_le_corpus():
    """Substitut TEXTUEL de l'oracle : il rougit même sans node.

    Mesuré, et c'est la raison d'être de ce test : sur une machine SANS node,
    `radar.html` muté pour garder son `fetch` et jeter le corpus laissait la
    suite à 472 passed / 37 skipped — un vert franc sur le défaut exact de H13.
    La garde d'exécution est la bonne, mais elle s'évapore avec son interpréteur ;
    il lui faut un doublon portable, comme le thème en a un
    (`test_le_script_qui_lit_le_theme_l_applique`).

    Propriété tenue : `DEFAULT_SKILLS` — la seule variable d'où partent les axes —
    ne reçoit jamais autre chose que le résultat de `skillsFromProfile(...)`
    appliqué à la charge utile du `fetch`. Un littéral réintroduit à côté du
    `fetch` (la mutation mesurée) rougit ici sans exécuter une ligne de JS.

    Nécessaire et insuffisant : une valeur qui traverserait `skillsFromProfile`
    sans venir du réseau passerait. C'est l'oracle d'exécution qui ferme ce
    reste — les deux gardes se relaient, aucune ne remplace l'autre.
    """
    txt = (ROOT / "radar.html").read_text(encoding="utf-8")
    affectations = [rhs.strip().rstrip(";") for rhs in _AFFECTATION_SKILLS.findall(txt)]
    assert affectations, "DEFAULT_SKILLS n'existe plus — ce test ne mesure plus rien"
    depuis_le_corpus = [a for a in affectations if a.startswith("skillsFromProfile(")]
    assert depuis_le_corpus, (
        "aucune affectation de DEFAULT_SKILLS ne passe par skillsFromProfile — "
        f"les compétences ne viennent plus du corpus lu ({affectations})")
    intrus = [a for a in affectations
              if not a.startswith("skillsFromProfile(") and a != "[]"]
    assert not intrus, (
        f"DEFAULT_SKILLS reçoit une valeur qui ne vient pas de profile.json : "
        f"{intrus} — la page afficherait un profil inventé")
    # ... et la charge utile transmise doit bien être celle du fetch. La forme
    # exacte de l'appel n'est pas figée (un intermédiaire est légitime) : ce qui
    # est exigé, c'est que la réponse de `fetch("profile.json")` soit désérialisée
    # et que ce soit elle qui alimente `skillsFromProfile`.
    lecture = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+fetch\(\"profile\.json\"\)", txt)
    assert lecture, ("la réponse de fetch(\"profile.json\") n'est plus liée à une "
                     "variable — l'affectation ci-dessus ne prouve plus rien sur "
                     "la source des données")
    assert re.search(rf"skillsFromProfile\([^)]*\b{lecture.group(1)}\b", txt) or \
           re.search(rf"\b\w+\s*=\s*await\s+{lecture.group(1)}\.json\(\)", txt), (
        f"la charge utile de fetch (`{lecture.group(1)}`) n'atteint pas "
        "skillsFromProfile — le corpus est lu puis jeté")


def test_radar_construit_ses_axes_depuis_le_corpus_servi(node_requis):
    """Le radar EXÉCUTÉ : ses axes doivent être les compétences déclarées.

    Oracle de comportement (cf. `radar_boot_harness`) : le script réel de la page
    tourne dans node contre un `fetch` qui sert le vrai `profile.json` et refuse
    toute autre URL. Attrape les trois formes du défaut qu'aucun test textuel ne
    distingue : la copie en dur, la lecture d'une autre source, et le résultat
    lu puis jeté.
    """
    axes = radar_boot_harness.axes_du_radar(
        (ROOT / "radar.html").read_text(encoding="utf-8"), _real_profile())
    assert axes, "le radar ne construit aucun axe — son boot n'atteint pas le corpus"
    attendus = set(_skill_names())
    assert set(axes) == attendus, (
        f"axes désaccordés avec profile.json — inventés : {sorted(set(axes) - attendus)} ; "
        f"déclarés mais absents : {sorted(attendus - set(axes))}")


def test_le_harnais_du_radar_ne_sert_le_corpus_qu_a_l_url_demandee(node_requis):
    """L'INSTRUMENT est mesuré, pas seulement ce qu'il mesure.

    Le harnais revendique noir sur blanc de « refuser toute autre URL », et c'est
    cette capacité — et elle seule — qui distingue « la page lit le corpus » de
    « la page lit quelque chose ». Mesuré : remplacer la vérification d'URL par
    `true` laissait la suite à 507 passed. Le seul test qui bronchait encore
    était `test_radar_lit_profile_json`, celui dont la docstring dit qu'il est
    nécessaire et insuffisant.

    Sans cette contre-épreuve, un radar qui lirait `profile-fige.json` serait
    servi comme s'il avait demandé `profile.json`, et l'oracle ci-dessus
    approuverait un profil figé.
    """
    html = (ROOT / "radar.html").read_text(encoding="utf-8")
    servis = radar_boot_harness.axes_du_radar(
        html, _real_profile(), url_servie="profile-fige.json")
    assert servis == [], (
        "le harnais a servi le corpus à une page qui demandait une AUTRE URL "
        f"— il ne distingue plus la source lue (axes rendus : {servis[:3]}…)")


def test_radar_taxonomie_ancree_sur_profile_json():
    """Chaque clé de SKILL_KEYWORDS doit désigner une compétence déclarée."""
    txt = (ROOT / "radar.html").read_text(encoding="utf-8")
    body = re.search(r"const SKILL_KEYWORDS = \{(.*?)\n\};", txt, re.S).group(1)
    keys = re.findall(r"^\s*([a-z0-9_]+):\s*\{", body, re.M)
    known = {_slug(n) for n in _skill_names()}
    assert keys, "SKILL_KEYWORDS introuvable"
    assert set(keys) <= known, f"clés orphelines : {sorted(set(keys) - known)}"


def test_match_parcourt_toutes_les_categories():
    txt = (ROOT / "match.html").read_text(encoding="utf-8")
    line = re.search(r"for \(const cat of \[([^\]]+)\]\)", txt).group(1)
    cats = set(re.findall(r"'([a-z_]+)'", line))
    assert set(_skill_categories()) <= cats, \
        f"catégories ignorées par match.html : {sorted(set(_skill_categories()) - cats)}"


def test_match_declare_un_alias_par_competence():
    txt = (ROOT / "match.html").read_text(encoding="utf-8")
    body = re.search(r"const SKILL_ALIASES = \{(.*?)\n\};", txt, re.S).group(1)
    aliased = set(re.findall(r'^\s*"([^"]+)":\s*\[', body, re.M))
    missing = [n for n in _skill_names() if n not in aliased]
    assert not missing, f"compétences sans alias (jamais détectables) : {missing}"


# ---------------------------------------------------------------------------
# Le sitemap et robots.txt
#
# Ils vivent ICI, et non dans un `test_sitemap.py`, pour la raison que la
# docstring de ce fichier donne deja : `publication.py::verifier()` ne joue que ce
# FICHIER, plus validate_profile.py, build_site.py et trois node-ids de
# confidentialite. Une garde de corpus posee ailleurs est hors de la porte.
# ---------------------------------------------------------------------------


def _sitemap_module():
    import build_sitemap
    return build_sitemap


def _urls_du_fichier() -> set[str]:
    txt = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    return set(re.findall(r"<loc>([^<]+)</loc>", txt))


def test_le_sitemap_declare_exactement_les_pages_suivies_et_servies():
    """Les URL du fichier egalent celles que la derivation rend.

    Deux lectures independantes du meme fait : le fichier commite d'un cote, la
    derivation depuis `git ls-files` de l'autre. Si l'une derive, l'egalite rougit.
    """
    bs = _sitemap_module()
    attendu = set(bs.urls())
    trouve = _urls_du_fichier()
    assert trouve == attendu, (
        f"sitemap.xml a derive — en trop : {sorted(trouve - attendu)} ; "
        f"manquantes : {sorted(attendu - trouve)}")


def test_le_sitemap_ne_declare_aucune_page_que_git_ne_suit_pas():
    """Le piege mesure : `pages_publiees()` lit le DISQUE, pas git.

    Sur le poste de l'Architecte elle rend 20 pages contre 14 dans un checkout
    propre : les six de plus sont les maquettes internes de
    `.superpowers/brainstorm/`, ignorees par `.gitignore` parce que ce depot est
    PUBLIC. Un sitemap derive du disque les declarerait a un explorateur. Cette
    garde refuse qu'une URL du sitemap designe un fichier que git ne suit pas.
    """
    bs = _sitemap_module()
    suivies = set(bs.pages_suivies())
    h = bs.hote()
    connues = {bs.url_de(p, h) for p in suivies} | set(bs.racines_deleguees(h))
    intrus = sorted(_urls_du_fichier() - connues)
    assert not intrus, (
        "URL ne correspondant ni a une page suivie par git ni a une racine "
        f"declaree dans servi_ailleurs : {intrus}")


def test_toute_page_servie_est_declaree_ou_ecartee_sciemment():
    """Aucune page ne peut apparaitre sans qu'on ait tranche son sort.

    C'est le but de `PAS_DES_PAGES_D_ATTERRISSAGE` : une liste explicite, et non un
    filtre malin. Ajouter une page au site sans decider si elle doit etre indexee
    fait rougir ce test.
    """
    bs = _sitemap_module()
    h = bs.hote()
    declarees = _urls_du_fichier()
    ecartees = set(bs.PAS_DES_PAGES_D_ATTERRISSAGE)
    sans_verdict = sorted(
        p for p in bs.pages_suivies()
        if p not in ecartees and bs.url_de(p, h) not in declarees)
    assert not sans_verdict, (
        "pages servies ni declarees ni ecartees — tranchez leur sort dans "
        f"build_sitemap.PAS_DES_PAGES_D_ATTERRISSAGE : {sans_verdict}")


def test_robots_declare_le_sitemap_sur_l_hote_du_CNAME():
    """L'hote se lit dans CNAME, jamais en dur : sinon il peut diverger du servi."""
    bs = _sitemap_module()
    h = bs.hote()
    assert h == (ROOT / "CNAME").read_text(encoding="utf-8").strip()
    txt = (ROOT / "robots.txt").read_text(encoding="utf-8")
    assert f"Sitemap: https://{h}/sitemap.xml" in txt, txt
    assert "Allow: /" in txt, txt
    assert f"https://{h}/" in _sitemap_module().rendu_sitemap(bs.urls())


def test_les_deux_fichiers_du_depot_sont_a_jour():
    """Anti-derive : le fichier commite doit etre EXACTEMENT ce que rend le build.

    Sans cette garde, un fichier derive vieillit en silence — le motif mesure le
    2026-10-15 sur `pending_pushes.jsonl`, arrete au 14 septembre pendant que la
    porte affichait « enqueue ».
    """
    bs = _sitemap_module()
    xml, txt = bs.build_sitemap(write=False)
    assert (ROOT / "sitemap.xml").read_text(encoding="utf-8") == xml,         "sitemap.xml du depot != generation fraiche ; relancez tools/build_site.py"
    assert (ROOT / "robots.txt").read_text(encoding="utf-8") == txt,         "robots.txt du depot != generation fraiche ; relancez tools/build_site.py"


def test_la_derivation_ecarte_bien_l_outillage_et_les_widgets():
    """Contre-vacuite de la DERIVATION, sur une entree dont la reponse est connue.

    Sans cette epreuve, un filtre casse (qui laisserait tout passer, ou rien)
    rendrait les egalites ci-dessus vertes en ne gardant rien du tout.
    """
    bs = _sitemap_module()
    suivies = bs.pages_suivies()
    assert "index.html" in suivies
    assert not [p for p in suivies if p.startswith("tools/")],         "une fixture de test est entree dans le corpus servi"
    liste = bs.urls()
    h = bs.hote()
    assert f"https://{h}/" in liste
    for widget in bs.PAS_DES_PAGES_D_ATTERRISSAGE:
        assert bs.url_de(widget, h) not in liste, f"{widget} devait etre ecarte"
    assert bs.url_de("index.html", h) == f"https://{h}/"
    assert bs.url_de("projects/index.html", h) == f"https://{h}/projects/"
    assert bs.url_de("radar.html", h) == f"https://{h}/radar.html"


def test_le_sitemap_declare_les_racines_servies_par_un_autre_depot():
    """`/academy/` appartient au domaine meme si ce depot ne la sert pas.

    Mesure du 2026-10-14 : le depot-projet RoJLD/academy l'emporte sur le dossier
    `academy/` de ce depot (retire depuis). L'URL repond 200 sur l'hote ; la
    laisser hors du sitemap reviendrait a decrire le deploiement au lieu du site.
    La source est `servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT`, pas une liste ecrite
    a la main ici : ajouter une delegation la fait entrer dans le sitemap, et ce
    test rougit si le generateur cesse de la lire.
    """
    import servi_ailleurs
    bs = _sitemap_module()
    h = bs.hote()
    declarees = _urls_du_fichier()
    assert servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT, \
        "aucune delegation declaree : ce test ne garderait rien"
    for prefixe in servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT:
        attendue = f"https://{h}/{prefixe}"
        assert attendue in declarees, (
            f"{attendue} est servie par "
            f"{servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT[prefixe]} et absente du sitemap")
    # Et seule la RACINE : ce depot ne connait pas les URL internes de l'autre.
    profondes = sorted(
        u for u in declarees
        for prefixe in servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT
        if u.startswith(f"https://{h}/{prefixe}") and u != f"https://{h}/{prefixe}")
    assert not profondes, f"URL internes d'un autre depot, inventees ici : {profondes}"
