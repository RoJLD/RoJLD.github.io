"""Garde anti-lien-mort : tout href local des pages publiées doit se résoudre.

Cette garde n'existait pas — c'est pour cela que `/projects/` a été publié avec
un lien vers `/projects/articles/couverture-dynamique.html` (404) et deux boutons
« Démo » pointant sur une ancre `#demos` absente de la page courante.

Règles vérifiées, pour chaque page HTML publiée du dépôt :
  * un href local (ni http(s), ni mailto/tel/javascript/data) doit désigner un
    fichier existant, résolu **comme le ferait le navigateur** (relatif au
    répertoire de la page, absolu depuis la racine du site) ;
  * un répertoire (ou un chemin terminé par `/`) est résolu en `index.html` ;
  * si l'URL porte un fragment `#ancre`, la page cible doit contenir cette ancre.

Aucun réseau : les liens externes sont hors périmètre par construction.
"""
from __future__ import annotations

import functools
import json
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
    assert "life-architect/index.html" in scannees


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


# Les destinations de la nav sont DÉCOUVERTES sur le disque (répertoires dont
# l'`index.html` porte la marque de la nav partagée), pas listées à la main.
#
# Mesuré : retirer `"demos"` de la constante écrite ici faisait disparaître
# TROIS cas de test avec elle — 485 passed, aucun rouge. La garde cessait de
# viser la destination que H3 venait justement de rétablir. Une constante ne
# peut pas se surveiller elle-même ; le témoin est le site publié
# (`corpus_publie.destinations_nav`), qui continue de voir `/demos/` exister.
NAV_DESTINATIONS = corpus_publie.destinations_nav()


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
    """Les 6 destinations de la nav partagée sont des pages réelles.

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
    """L'artefact servi porte les 6 liens — attrape une page laissée périmée."""
    html = (ROOT / page / "index.html").read_text(encoding="utf-8")
    manquants = [d for d in NAV_DESTINATIONS if f'href="/{d}/"' not in html]
    assert not manquants, (
        f"{page}/index.html : destination(s) absente(s) de la nav {manquants} — "
        "la page devient un cul-de-sac pour ces sections")


@functools.lru_cache(maxsize=1)
def _rendu_des_builders():
    """(nom, html) produit en mémoire par chaque générateur de page de nav."""
    import build_academy, build_browse, build_demos          # noqa: E401
    import build_graph, build_highlights, build_projects     # noqa: E401
    p = _real_profile()
    return {
        "projects": build_projects.build_projects(p, write=False),
        "explorer": build_browse.build_browse(p, write=False),
        "highlights": build_highlights.build_highlights(p, write=False),
        "academy": build_academy.build_academy(write=False),
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
    manquants = [d for d in NAV_DESTINATIONS if f'href="/{d}/"' not in html]
    assert not manquants, (
        f"le générateur de /{page}/ n'émet plus {manquants} dans sa nav")


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
