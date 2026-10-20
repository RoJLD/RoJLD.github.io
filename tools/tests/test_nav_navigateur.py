"""La barre de nav MESURÉE dans un navigateur : la rangée tient, et le focus suit l'œil.

Pourquoi ce fichier existe, et pourquoi il ne pouvait pas être écrit autrement.

La garde livrée le 2026-10-19 avec la mise en page
(`test_liens_internes.py::test_aucune_regle_ne_cache_un_lien_de_nav_sans_le_rendre`)
interdit une règle `display:none` sur les liens de la nav. Elle défend un
INDICE, pas la propriété : la rangée est un scrollport à barre masquée
(`scrollbar-width:none`, `::-webkit-scrollbar{display:none}`), donc un
débordement ne se VOIT pas. Un lien poussé hors de la fenêtre n'est pas caché par
une règle CSS : il est simplement derrière un geste que rien ne signale. C'est
« 9 liens derrière un glissement non signalé », le motif que la décision mobile
du 2026-10-19 écarte explicitement — et aucune expression régulière sur le HTML
ne peut le voir, parce que la réponse dépend de la mise en page réelle, donc d'un
moteur de rendu.

Ce dépôt n'a PAS Playwright dans ses dépendances : `requirements.txt` ne contient
que `markdown`, et ses oracles de comportement tournent dans node, sans moteur
de rendu (cf. `oracle_node`) — 47 cas qui sautent quand node manque, comptés le
2026-10-20 sur une copie vierge, suite entière lancée sans node dans le PATH.
Mais il a déjà la PORTE — `oracle_playwright.porte` — et deux gardes qui s'en servent (`test_cockpit_smoke_navigateur`,
`test_cockpit_calque_navigateur`). La mesure du 2026-10-19 sur ce poste :
Playwright présent, Chromium 145, les deux gardes PASSENT (les 6 skips de la
suite viennent de career-ops et d'un module frère d'ELYSIUM, pas du navigateur).
Une garde de dépôt était donc possible, et la voici. Sur un poste sans
Playwright, la porte rend un skip honnête ; `ELYSIUM_REQUIRE_PLAYWRIGHT=1` le
transforme en échec.

Trois propriétés mesurées, aux 13 largeurs, sur les pages de la nav partagée —
sept depuis la page 404 du 2026-10-20, servie ici à `/404.html` (population
DÉCOUVERTE par `corpus_publie`, aucune liste de pages écrite ici) :

  1. LA RANGÉE TIENT        `scrollWidth <= clientWidth` de `.nav-r` — zéro
                            débordement, donc aucune destination derrière un
                            geste. Mesuré le 2026-10-19 sur la branche : 0 px de
                            débordement aux 78 cas. Avant la mise en page de PR2,
                            la même mesure donnait 543 px à 390 px et 208 px à
                            1024 px.
  2. L'ORDRE DE TABULATION  = l'ordre visuel (rangée visuelle, puis x). Mesuré
                            par `Tab` RÉEL aux deux largeurs que la décision
                            nomme (390 et 1280 px), et par la géométrie aux 13.
  3. LA CIBLE FAIT 24 px    hauteur d'entrée >= 24 px (WCAG 2.5.8). Mesuré le
                            2026-10-20 sur les sept pages : 28 à 29 px sous
                            1024 px, 25 à 27 au-dessus — les plus basses sur
                            `/graph/`, dont le `body` porte `line-height:1.6`.

Et, sur la page 404, sur le même serveur : LA BASCULE DE LANGUE EXÉCUTÉE, au
clic sur la 404 elle-même, au rechargement, et après un choix fait au clic sur
l'accueil ou sur /explorer/ (dernière section du fichier). Les autres gardes
de langue de la 404 sont statiques : jusqu'au 2026-10-20, aucune ne cliquait le
bouton.

Ce fichier est HORS de la porte du cockpit (`tools/cockpit/publication.py::
verifier()` lance `validate_profile.py` et `build_site.py`, puis joue en entier
`test_liens_internes.py` et `test_cockpit_public_isole.py`, plus deux node-ids de
`test_validate_profile.py` — et rien d'autre). C'est une limite nommée : un « Publier » ne
mesure pas la mise en page, et n'exécute pas la bascule de langue de la 404. L'y
ajouter ferait dépendre le bouton de Robin d'un Chromium et de
fonts.googleapis.com — à arbitrer, pas à décider ici.
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import socket
import socketserver
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_404  # noqa: E402
import corpus_publie  # noqa: E402
import nav  # noqa: E402
import oracle_playwright  # noqa: E402

# Les 13 largeurs, et la raison de chacune. Les trois paliers de la décision
# mobile sont exercés des DEUX côtés : un palier qui ne tient qu'à l'intérieur de
# sa borne est un palier mal placé (mesuré le 2026-10-19 : la marge la plus
# serrée est à 1151 px, le premier pixel SANS le second cran typographique).
LARGEURS = (
    320,    # le plus petit téléphone encore vendu
    390,    # iPhone de référence de la mesure
    480,    # ancien seuil d'amputation de l'accueil, supprimé par PR2
    640,    # ancien seuil d'amputation des quatre générateurs, supprimé par PR2
    768,    # tablette portrait
    1023,   # dernier pixel du repli
    1024,   # premier pixel de la barre fixe — portable en fenêtre, cas du recruteur
    1150,   # dernier pixel du second cran typographique
    1151,   # premier pixel sans lui : le point le plus serré mesuré (49 px)
    1280,   # portable courant
    1440,   # portable 16 pouces
    1620,   # dernier pixel du premier cran typographique
    1920,   # écran de bureau
)

# Au-dessus de ce seuil la barre est fixe et d'une seule rangée ; en dessous elle
# est `position:static` et se replie. Les deux régimes n'ont pas la même forme
# attendue, et c'est le seul endroit du fichier où le seuil est nommé.
SEUIL_REPLI = 1023

# Tabulation RÉELLE à ces deux largeurs (les deux que la décision nomme) : une
# frappe `Tab` par arrêt, `document.activeElement` relu à chaque fois. Les 13
# largeurs sont couvertes par la géométrie ; le clavier coûte une frappe et une
# relecture par arrêt (~170 allers-retours et ~12 s, mesurés sur les six pages
# d'alors le 2026-10-19), on ne le paie pas à chaque largeur de chaque page
# — 13 × 7 = 91 cas depuis la page 404 — pour mesurer la même chose.
LARGEURS_AU_CLAVIER = (390, 1280)

# Familles que ces pages chargent depuis fonts.googleapis.com. Sans elles, la
# largeur du texte n'est pas celle du site publié et la mesure porterait sur une
# autre page. `document.fonts.check()` ne prouve RIEN ici : il rend `true` aussi
# quand la feuille n'a jamais été chargée, puisqu'il n'y a alors aucune
# `@font-face` en attente. On compte donc les faces réellement `loaded` dans
# l'inventaire `FontFaceSet`.
POLICES_ATTENDUES = ("DM Sans", "Instrument Serif")

_JS_MESURE = r"""
() => {
  const boite = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y),
            w: Math.round(r.width), h: Math.round(r.height)};
  };
  const rangee = document.querySelector('.nav-r');
  // `new Set` : un element portant a la fois `href` et `tabindex` ne doit pas
  // entrer deux fois dans la sequence — un doublon fabriquerait une inversion.
  const focalisables = Array.from(new Set(document.querySelectorAll(
    'nav a[href], nav button, nav [tabindex]')));
  return {
    rangee: rangee ? {scrollW: Math.round(rangee.scrollWidth),
                      clientW: Math.round(rangee.clientWidth)} : null,
    entrees: Array.from(document.querySelectorAll('.nav-r a')).map(boite),
    // Ordre du DOM : c'est l'ordre de tabulation tant qu'aucun `tabindex`
    // positif ne le réécrit — ce que l'assertion ci-dessous vérifie.
    focalisables: focalisables.map(el => Object.assign(
      boite(el), {quoi: (el.textContent || '').trim().slice(0, 20),
                  tabindex: el.getAttribute('tabindex')})),
    nav_h: Math.round(document.querySelector('nav').getBoundingClientRect().height),
    polices_chargees: Array.from(document.fonts)
      .filter(f => f.status === 'loaded').map(f => f.family),
  };
}
"""

_JS_ACTIF = r"""
() => {
  const el = document.activeElement;
  if (!el || el === document.body || !el.closest('nav')) return null;
  const r = el.getBoundingClientRect();
  return {x: Math.round(r.x), y: Math.round(r.y),
          w: Math.round(r.width), h: Math.round(r.height),
          quoi: (el.textContent || '').trim().slice(0, 20)};
}
"""


def _url(rel: str) -> str:
    """`projects/index.html` -> `/projects/`, `index.html` -> `/`, `404.html` -> `/404.html`.

    Un fichier à la racine qui n'est pas `index.html` garde son nom. L'écriture
    précédente ne connaissait que des `index.html` et rendait `/404.html/` pour la
    page d'erreur, et le `SimpleHTTPRequestHandler` de ce fichier répond 404 à
    `/404.html/` et 200 à `/404.html` (mesuré le 2026-10-20) : la vérification
    des octets servis aurait échoué pour une raison étrangère à la page.
    """
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def rangees_visuelles(boites: list[dict]) -> list[int]:
    """Index de rangée visuelle de chaque boîte, par CHEVAUCHEMENT vertical.

    Comparer les `y` bruts ne marche pas : un bouton fait 34 à 38 px et une
    entrée 26 à 29, tous centrés sur la même ligne — le `y` du bouton est donc
    PLUS PETIT de 4 px que celui de l'entrée qui le précède, sans qu'aucun ordre
    ne soit inversé. Deux boîtes dont les intervalles verticaux se chevauchent
    sont sur la même rangée ; l'ordre visuel est (rangée, puis x).
    """
    bornes: list[tuple[int, int]] = []
    brut: list[int] = []
    for b in boites:
        haut, bas = b["y"], b["y"] + b["h"]
        for i, (h, bb) in enumerate(bornes):
            if haut < bb and h < bas:
                bornes[i] = (min(h, haut), max(bb, bas))
                brut.append(i)
                break
        else:
            bornes.append((haut, bas))
            brut.append(len(bornes) - 1)
    de_haut_en_bas = {i: r for r, (i, _) in enumerate(
        sorted(enumerate(bornes), key=lambda kv: kv[1][0]))}
    return [de_haut_en_bas[i] for i in brut]


def inversions(boites: list[dict]) -> list[tuple]:
    """Couples consécutifs où l'ordre donné n'est pas l'ordre visuel (rangée, x)."""
    rg = rangees_visuelles(boites)
    cles = [(rg[i], boites[i]["x"]) for i in range(len(boites))]
    return [(i, boites[i - 1].get("quoi"), cles[i - 1], boites[i].get("quoi"), cles[i])
            for i in range(1, len(cles)) if cles[i] < cles[i - 1]]


class _Silencieux(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture(scope="module")
def site_servi():
    """Le site servi en HTTP sur un port LIBRE, et les octets servis vérifiés.

    En `file://`, les polices Google ne chargent pas et toutes les largeurs de
    texte changent : la mesure porterait sur une autre page. Et le port est pris
    par l'OS (`bind(0)`) puis les octets servis sont comparés au disque — un port
    déjà occupé par un autre serveur ferait mesurer les fichiers de quelqu'un
    d'autre (mesuré comme piège réel le 2026-10-19).
    """
    oracle_playwright.porte()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    classe = functools.partial(http.server.SimpleHTTPRequestHandler,
                               directory=str(ROOT))
    srv = _Silencieux(("127.0.0.1", port), classe)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        for rel in corpus_publie.pages_de_la_nav_partagee():
            servi = urllib.request.urlopen(base + _url(rel), timeout=20).read()
            assert servi == (ROOT / rel).read_bytes(), (
                f"{_url(rel)} : les octets servis ne sont pas ceux du disque — "
                f"le port {port} sert autre chose que ce dépôt")
        yield base
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture(scope="module")
def mesures(site_servi):
    """Une mesure par (page, largeur), et la tabulation à deux largeurs.

    Géométrie : `set_viewport_size` au lieu d'un rechargement par largeur — les
    polices restent chargées, et les 13 largeurs coûtent un chargement par page
    au lieu de 13. Clavier : un rechargement par largeur de
    `LARGEURS_AU_CLAVIER` (deux), cf. ci-dessous. Mesuré le 2026-10-20 en
    comptant les `Page.goto` : 21 chargements pour les 7 pages (3 chacune :
    un pour la géométrie, deux pour le clavier). La géométrie seule en
    coûterait 91 (7 × 13) si elle rechargeait à chaque largeur.
    """
    from playwright.sync_api import sync_playwright

    out: dict[tuple[str, int], dict] = {}
    erreurs: dict[str, list[str]] = {}
    with sync_playwright() as pw:
        navigateur = pw.chromium.launch()
        for rel in corpus_publie.pages_de_la_nav_partagee():
            page = navigateur.new_page(viewport={"width": 1280, "height": 900})
            vues: list[str] = []
            page.on("pageerror", lambda e, v=vues: v.append(str(e)))
            page.goto(site_servi + _url(rel), wait_until="load")
            page.evaluate("() => document.fonts.ready")
            for largeur in LARGEURS:
                page.set_viewport_size({"width": largeur, "height": 900})
                out[(rel, largeur)] = page.evaluate(_JS_MESURE)
            # La tabulation est mesurée sur un document NEUF à chaque largeur.
            # Mesuré le 2026-10-19 : `blur()` ne remet pas le « point de départ de
            # la navigation séquentielle » de Chromium. En rejouant `Tab` après une
            # première passe, le focus repartait APRÈS la nav — 7 arrêts relevés au
            # lieu de 13 sur /explorer/ et /projects/, et la garde accusait la page.
            # Un rechargement local coûte quelques millisecondes et ne laisse aucun
            # doute sur l'origine du focus.
            for largeur in LARGEURS_AU_CLAVIER:
                page.set_viewport_size({"width": largeur, "height": 900})
                page.goto(site_servi + _url(rel), wait_until="load")
                page.evaluate("() => document.fonts.ready")
                sequence = []
                for _ in range(40):
                    page.keyboard.press("Tab")
                    actif = page.evaluate(_JS_ACTIF)
                    if actif is None:
                        if sequence:
                            break
                        continue
                    sequence.append(actif)
                out[(rel, largeur)]["clavier"] = sequence
            erreurs[rel] = vues
            page.close()
        navigateur.close()
    return {"par_cas": out, "erreurs": erreurs}


def _cas() -> list[tuple[str, int]]:
    return [(rel, l) for rel in corpus_publie.pages_de_la_nav_partagee()
            for l in LARGEURS]


def test_la_population_mesuree_est_celle_de_la_nav_partagee():
    """Contre-vacuité : sept pages et treize largeurs, ou la garde ne mesure rien.

    Les pages sont DÉCOUVERTES (`corpus_publie`), donc une page qui perdrait la
    marque de la nav sortirait du champ sans un rouge — c'est le défaut que
    `corpus_publie` documente. Ce plancher le refuse, à condition d'égaler la
    population : sept pages depuis la 404 du 2026-10-20. Resté à six, il laissait
    sortir une page en silence, et son énoncé décrivait le plancher et non la
    population ; il est donc relevé, et l'énoncé avec lui.
    """
    pages = corpus_publie.pages_de_la_nav_partagee()
    assert len(pages) >= 7, f"seules {len(pages)} page(s) mesurées : {pages}"
    assert "index.html" in pages, "l'accueil est sorti de la population mesurée"
    assert len(LARGEURS) == 13, f"{len(LARGEURS)} largeurs au lieu de 13"
    assert min(LARGEURS) <= 320 and max(LARGEURS) >= 1920
    assert SEUIL_REPLI in LARGEURS and SEUIL_REPLI + 1 in LARGEURS, (
        "les deux côtés du seuil de repli ne sont pas mesurés")


def test_les_polices_du_site_sont_bien_chargees(mesures):
    """Sans les polices, la mesure de largeur porte sur une autre page.

    Prouvé par l'INVENTAIRE `FontFaceSet` (faces dont `status === 'loaded'`), pas
    par `document.fonts.check()`, qui rend `true` aussi quand la feuille Google
    n'a jamais été chargée — il n'y a alors aucune `@font-face` en attente.
    """
    manquantes = {}
    for (rel, largeur), m in mesures["par_cas"].items():
        absentes = [f for f in POLICES_ATTENDUES if f not in m["polices_chargees"]]
        if absentes:
            manquantes[(rel, largeur)] = absentes
    if manquantes:
        message = (f"police(s) non chargée(s) : {sorted(manquantes.items())[:3]} — "
                   "sans réseau vers fonts.googleapis.com, les largeurs de texte "
                   "ne sont pas celles du site publié")
        if os.environ.get("ELYSIUM_REQUIRE_PLAYWRIGHT") == "1":
            pytest.fail(message)
        pytest.skip(message)


@pytest.mark.parametrize("rel, largeur", _cas(), ids=lambda v: str(v))
def test_la_rangee_de_nav_tient_sans_debordement(rel, largeur, mesures):
    """AUCUNE destination derrière un geste : la rangée ne déborde pas.

    La propriété, et non son indice. `.nav-r` est un scrollport dont la barre est
    masquée : un débordement ne se peint pas. Mesuré avant la mise en page de
    PR2 : 543 px de débordement à 390 px (2 onglets visibles sur 11), 208 px à
    1024 px, 80 px à 1280 px. Après, le 2026-10-19 : 0 px aux 78 cas des six
    pages d'alors.
    """
    r = mesures["par_cas"][(rel, largeur)]["rangee"]
    assert r is not None, f"{rel} : plus de `.nav-r` à {largeur} px"
    debord = r["scrollW"] - r["clientW"]
    assert debord <= 0, (
        f"{rel} à {largeur} px : la rangée de nav déborde de {debord} px "
        f"({r['scrollW']} px de contenu pour {r['clientW']} px de fenêtre) — "
        "la barre de défilement étant masquée, ces destinations sont derrière un "
        "geste que rien ne signale")


@pytest.mark.parametrize("rel, largeur", _cas(), ids=lambda v: str(v))
def test_l_ordre_de_tabulation_est_l_ordre_visuel(rel, largeur, mesures):
    """Le focus ne doit jamais remonter : WCAG 2.4.3 (niveau A) et 1.3.2.

    Mesuré le 2026-10-19 sur les huit premiers commits de PR2 : le bloc
    `@media(max-width:1023px)` plaçait `.nav-btns{order:2}` avant `.nav-r{order:3}`
    alors que le DOM garde les boutons APRÈS la rangée — 36 inversions, les 6
    pages × les 6 largeurs <= 1023 px. À 390 px, le focus descendait jusqu'à
    « Contact » (y=115) puis remontait de 105 px sur « FR » (y=10).

    L'ordre du DOM n'est l'ordre de tabulation que si aucun `tabindex` positif ne
    le réécrit : c'est vérifié ici même, sinon cette garde mesurerait une
    propriété qui n'est pas celle du clavier.
    """
    m = mesures["par_cas"][(rel, largeur)]
    tabindex = [f["quoi"] for f in m["focalisables"]
                if f["tabindex"] not in (None, "0", "-1")]
    assert not tabindex, (
        f"{rel} : `tabindex` positif dans la nav ({tabindex}) — l'ordre du DOM "
        "n'est plus l'ordre de tabulation, cette garde ne mesure plus le clavier")
    fautes = inversions(m["focalisables"])
    assert not fautes, (
        f"{rel} à {largeur} px : l'ordre de tabulation n'est pas l'ordre visuel — "
        f"{fautes} (couple : indice, texte précédent, (rangée, x) précédent, "
        "texte suivant, (rangée, x) suivant)")


@pytest.mark.parametrize("rel", sorted(corpus_publie.pages_de_la_nav_partagee()))
@pytest.mark.parametrize("largeur", LARGEURS_AU_CLAVIER)
def test_la_tabulation_reelle_ne_remonte_jamais(rel, largeur, mesures):
    """La même propriété, mesurée au CLAVIER et non par la géométrie du DOM.

    Le test ci-dessus déduit l'ordre de tabulation de l'ordre du DOM. Celui-ci
    appuie réellement sur `Tab` et relit `document.activeElement` : il attrape
    aussi ce qu'on n'a pas prévu (un `inert`, un `display:contents`, un élément
    rendu non focalisable). Deux largeurs seulement, de part et d'autre du seuil
    de repli — le clavier coûte une frappe et une relecture par arrêt (cf.
    `LARGEURS_AU_CLAVIER`), la géométrie couvre les 13.
    """
    sequence = mesures["par_cas"][(rel, largeur)]["clavier"]
    attendu = len(mesures["par_cas"][(rel, largeur)]["focalisables"])
    assert len(sequence) == attendu, (
        f"{rel} à {largeur} px : {len(sequence)} arrêt(s) au clavier pour "
        f"{attendu} élément(s) focalisable(s) dans la nav — "
        f"séquence relevée : {[a['quoi'] for a in sequence]}")
    fautes = inversions(sequence)
    assert not fautes, (
        f"{rel} à {largeur} px : la tabulation réelle remonte — {fautes} ; "
        f"y successifs : {[a['y'] for a in sequence]}")


@pytest.mark.parametrize("rel, largeur", _cas(), ids=lambda v: str(v))
def test_chaque_entree_de_nav_fait_au_moins_24_px_de_haut(rel, largeur, mesures):
    """WCAG 2.5.8 Target Size (Minimum), niveau AA : 24 × 24 px.

    Mesuré sur `main` avant PR2 : 17 px de hauteur d'entrée à 390 px. Une rangée
    d'onglets n'est pas « un lien en ligne dans une phrase » — l'exception du
    critère ne s'applique pas, et elle ne s'applique pas davantage à 1024 px, où
    le pointeur est une souris. Mesuré le 2026-10-20 sur les sept pages : 28 à
    29 px sous le seuil, 25 à 27 au-dessus (les plus basses sur `/graph/`).
    """
    hauteurs = [e["h"] for e in mesures["par_cas"][(rel, largeur)]["entrees"]]
    assert hauteurs, f"{rel} : aucune entrée de nav mesurée à {largeur} px"
    assert min(hauteurs) >= 24, (
        f"{rel} à {largeur} px : entrée de nav de {min(hauteurs)} px de haut "
        f"(minimum 24 px) — hauteurs relevées {sorted(set(hauteurs))}")


def test_aucune_erreur_js_sur_les_pages_mesurees(mesures):
    """Une page qui jette une exception au chargement ne mesure plus rien de sûr."""
    fautives = {rel: v for rel, v in mesures["erreurs"].items() if v}
    assert not fautives, f"erreur(s) JS au chargement : {fautives}"


# ── La bascule de langue de la 404, EXÉCUTÉE dans le navigateur ──────────────
#
# Les autres gardes de langue de la 404 sont STATIQUES : chaque texte porte
# `data-fr` et `data-en` (`test_liens_internes.py`), chaque entrée de nav porte
# les attributs que sa page lit (`test_nav_unifiee.py`), la page lit le choix
# mémorisé et écrit `lang` (`test_lang_switch_behaviour.py`). Aucune ne faisait
# tourner la bascule. Relecture adverse du 2026-10-20, porte complète à deux
# drapeaux sur une copie vierge de 2b777a5, générateur muté puis site régénéré :
# trois mutations d'une ligne de `applyBrowseLang` (`tools/build_404.py`) la
# laissaient verte, 1756 passed chacune —
#
#     `el.dataset.En`                    titre, h1 et les 11 entrées VIDES en
#                                        anglais (`dataset.En` est `undefined`) ;
#     `el.textContent = el.dataset.fr`   `lang="en"`, mais titre, h1 et nav en
#                                        français ;
#     `'main [data-fr][data-en]'`        `lang="en"`, mais titre et nav en
#                                        français.
#
# Le test clique le bouton comme un visiteur — `page.click("#langBtn")`, avec les
# vérifications d'actionnabilité de Playwright (visible, stable, atteint par le
# pointeur), et non un appel direct de `toggleLang()` — puis lit le DOM RENDU :
# `lang` sur `<html>`, `document.title`, le libellé du bouton de langue (« FR »
# ou « EN »), et CHAQUE texte traduit visible de la page — le h1, les entrées de
# la nav, le paragraphe, « Adresse demandée », le bouton de retour et les
# raccourcis —, chacun égal à la valeur `data-en` ou `data-fr` qu'il porte, et
# cette valeur non vide. Un texte traduit invisible ne serait jugé par rien : il
# n'en faut aucun. Mesuré le 2026-10-20 à 1280 px, dans les six états : 11
# entrées de nav, 6 autres textes, 0 caché.
#
# Six états, chacun dans un contexte de navigateur NEUF au départ.
#   * Quatre sur une même page : au chargement (français), après un clic
#     (anglais), après un second clic (français), puis la page RECHARGÉE après
#     un troisième clic, qui mémorise l'anglais. Le rechargement prouve que la
#     404 relit ce qu'ELLE a écrit, et rien de plus.
#   * Deux autres, où le choix est fait AILLEURS : un clic sur le bouton de
#     l'accueil, puis — dans un autre contexte — sur celui de /explorer/, et la
#     404 ouverte ensuite dans le même contexte, sans aucun clic sur elle.
#     C'est le chemin principal d'une page d'erreur : on n'y clique pas le
#     bouton, on y arrive avec sa langue déjà choisie, et la page doit relire
#     ce choix (`getItem('lang')` en fin de corps) sous la clé et dans la casse
#     où les autres pages l'écrivent (`localStorage`, `'lang'`, `'en'`). La
#     page d'origine est relue avant et après son clic : si elle n'a pas
#     basculé, le message l'accuse, elle, au lieu de la 404.
# Et le sens inverse, testé à part : après `rechargement-en`, le même contexte
# ouvre /explorer/, qui doit être en anglais (`lang="en"`, bouton « EN ») — ce
# que la 404 écrit, les autres pages le comprennent.
#
# Le texte comparé est `textContent`, pas `innerText` : la nav est en
# `text-transform:uppercase`, et `innerText` rendrait « EXPERIENCE ».
#
# Hors champ, et dit pour ne pas être cru gardé :
#   * le MOMENT où la langue mémorisée est posée (avant ou après le premier
#     rendu) : relevé, avec sa limite, dans le docstring de `tools/build_404.py`,
#     et gardé par rien ;
#   * une seule largeur, 1280 px ;
#   * le `title` des deux boutons (« Langue », « Thème »), qu'aucune bascule ne
#     réécrit (cf. `tools/build_404.py`) ;
#   * les autres pages au bouton de langue : leur bascule n'est exécutée ici que
#     pour ce qu'elle ÉCRIT (l'accueil et /explorer/, `lang` relu avant et après
#     le clic) et pour ce que /explorer/ LIT du choix de la 404 ; leurs textes
#     ne sont pas relus (ceux de /explorer/ et /highlights/ le sont dans node,
#     sur le seul `href` des cartes, par `test_lang_switch_behaviour.py`) ;
#     /graph/ et /highlights/ ne servent pas de page d'origine.

_JS_LANGUE = r"""
() => {
  const lire = (el) => ({texte: el.textContent,
                         fr: el.getAttribute('data-fr'),
                         en: el.getAttribute('data-en')});
  const visible = (el) => el.checkVisibility({visibilityProperty: true});
  // Désignation d'un élément dans un message de faute : balise, id, classes.
  const quoi = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
    + Array.from(el.classList).map(c => '.' + c).join('');
  const titre = document.querySelector('title');
  const bouton = document.getElementById('langBtn');
  const traduits = Array.from(document.body.querySelectorAll('[data-fr][data-en]'));
  return {
    lang: document.documentElement.getAttribute('lang'),
    titre: {texte: document.title,
            fr: titre ? titre.getAttribute('data-fr') : null,
            en: titre ? titre.getAttribute('data-en') : null},
    bouton: bouton ? bouton.textContent : null,
    h1: Array.from(document.querySelectorAll('h1')).map(lire),
    entrees: Array.from(document.querySelectorAll('.nav-r a'))
      .filter(visible).map(lire),
    // Tout AUTRE texte traduit du corps, visible : le paragraphe, « Adresse
    // demandée », le bouton de retour et les raccourcis.
    autres: traduits.filter(el => !el.matches('h1, .nav-r a') && visible(el))
      .map(el => Object.assign(lire(el), {quoi: quoi(el)})),
    // Un texte traduit invisible n'est jugé par rien : il doit n'y en avoir aucun.
    caches: traduits.filter(el => !visible(el)).map(quoi),
  };
}
"""

# La langue que la page affiche, relue sur une AUTRE page que la 404 (sens
# inverse : le choix fait sur la 404 doit être compris ailleurs).
_JS_LANGUE_AILLEURS = r"""
() => ({lang: document.documentElement.getAttribute('lang'),
        bouton: (document.getElementById('langBtn') || {}).textContent || null})
"""

# Les blancs que le navigateur replie sous `white-space:normal` — la même
# définition que `test_liens_internes._BLANCS_REPLIES`, et pour la même raison :
# un attribut ou un texte coupé sur deux lignes s'affiche pareil, et l'espace
# insécable, qui ne se replie pas, ne doit pas être replié ici.
_BLANCS_REPLIES = re.compile(r"[ \t\n\r]+")


def _rendu(texte: str | None) -> str:
    return _BLANCS_REPLIES.sub(" ", texte or "").strip(" ")


# Les pages où le visiteur choisit l'anglais AVANT d'arriver sur la 404, dans
# l'ordre où la fixture les parcourt : l'accueil, où l'on entre, puis la page
# d'exploration. Toutes deux portent le bouton de langue et écrivent le choix
# sous la même clé que la 404 (`localStorage`, `'lang'`, `'en'` ou `'fr'`).
_PAGES_OU_L_ON_CHOISIT = ("/", "/explorer/")

# (identifiant, langue attendue, ce qui a précédé le relevé) — dans l'ordre où
# la fixture les produit. Les quatre premiers sur une même page ; chacun des
# deux derniers dans son propre contexte de navigateur, neuf.
_ETATS_DE_LA_BASCULE = (
    ("chargement-fr", "fr", "au chargement, sans choix mémorisé"),
    ("premier-clic-en", "en", "après un clic sur son bouton de langue"),
    ("second-clic-fr", "fr", "après un second clic"),
    ("rechargement-en", "en",
     "rechargée après un troisième clic, qui a mémorisé l'anglais"),
) + tuple(
    (f"choisi-sur-{'accueil' if origine == '/' else origine.strip('/')}-en", "en",
     f"ouverte après un clic sur le bouton de langue de {origine}")
    for origine in _PAGES_OU_L_ON_CHOISIT)

# Le sens inverse : après `rechargement-en`, le même contexte ouvre cette page.
_PAGE_QUI_RELIT_LE_CHOIX_DE_LA_404 = "/explorer/"


@pytest.fixture(scope="module")
def bascule_de_la_404(site_servi):
    """Les six états de la 404, et la page qui relit son choix (cf. ci-dessus).

    Chaque contexte de navigateur est NEUF, donc sans choix de langue mémorisé :
    une page part en français, et ce sont les clics qui la font changer. Les
    erreurs JavaScript sont relevées à chaque état, celles de la page d'origine
    comprises : une bascule qui jette après avoir écrit `lang` laisserait un
    état à moitié fait.
    """
    from playwright.sync_api import sync_playwright

    etats: dict[str, dict] = {}
    adresse_404 = site_servi + _url(corpus_publie.PAGE_D_ERREUR)

    def ouvrir_404(page) -> None:
        reponse = page.goto(adresse_404, wait_until="load")
        assert reponse is not None and reponse.status == 200, (
            f"/{corpus_publie.PAGE_D_ERREUR} n'est pas servie "
            f"({reponse.status if reponse else 'aucune réponse'})")

    with sync_playwright() as pw:
        navigateur = pw.chromium.launch()

        def contexte_neuf():
            contexte = navigateur.new_context(viewport={"width": 1280, "height": 900})
            page = contexte.new_page()
            erreurs: list[str] = []
            page.on("pageerror", lambda e: erreurs.append(str(e)))
            return contexte, page, erreurs

        # 1. La bascule de la 404 elle-même : trois clics, puis un rechargement.
        contexte, page, erreurs = contexte_neuf()

        def relever(nom: str) -> None:
            etats[nom] = dict(page.evaluate(_JS_LANGUE), erreurs=list(erreurs))

        ouvrir_404(page)
        relever("chargement-fr")
        page.click("#langBtn")
        relever("premier-clic-en")
        page.click("#langBtn")
        relever("second-clic-fr")
        page.click("#langBtn")
        page.reload(wait_until="load")
        relever("rechargement-en")
        # Sens inverse, même contexte : le choix que la 404 vient de mémoriser.
        page.goto(site_servi + _PAGE_QUI_RELIT_LE_CHOIX_DE_LA_404, wait_until="load")
        etats["relu-ailleurs"] = dict(page.evaluate(_JS_LANGUE_AILLEURS),
                                      erreurs=list(erreurs))
        contexte.close()

        # 2. Le choix fait AILLEURS : un clic sur le bouton d'une autre page,
        #    puis la 404 ouverte dans le même contexte, sans aucun clic sur elle.
        for (nom, _, _), origine in zip(_ETATS_DE_LA_BASCULE[4:],
                                        _PAGES_OU_L_ON_CHOISIT):
            contexte, page, erreurs = contexte_neuf()
            page.goto(site_servi + origine, wait_until="load")
            avant = page.evaluate(_JS_LANGUE_AILLEURS)
            page.click("#langBtn")
            apres = page.evaluate(_JS_LANGUE_AILLEURS)
            ouvrir_404(page)
            relever(nom)
            etats[nom]["origine"] = {"page": origine, "avant": avant, "apres": apres}
            contexte.close()
        navigateur.close()
    return etats


@pytest.mark.parametrize("nom, langue, quand",
                         [pytest.param(*e, id=e[0]) for e in _ETATS_DE_LA_BASCULE])
def test_la_404_rend_chaque_texte_traduit_dans_la_langue_choisie(nom, langue, quand,
                                                                 bascule_de_la_404):
    """La page DIT la langue choisie et l'AFFICHE, où que ce choix ait été fait.

    WCAG 3.1.1 (niveau A) : la langue annoncée doit être celle du contenu.
    `build_404.py` le promet (« LES DEUX LANGUES SONT LIVRÉES ») ; les gardes
    statiques vérifient les attributs, celle-ci vérifie ce qu'ils deviennent :
    `lang`, le titre, le libellé du bouton de langue, et chaque texte traduit
    visible (h1, nav, paragraphe, « Adresse demandée », bouton de retour,
    raccourcis). Chaque faute est nommée : (élément, texte rendu, texte attendu).
    """
    etat = bascule_de_la_404[nom]
    attr = f"data-{langue}"
    assert not etat["erreurs"], f"/404.html {quand} : erreur(s) JavaScript {etat['erreurs']}"
    origine = etat.get("origine")
    if origine is not None:
        # La page d'origine doit avoir basculé, sinon c'est ELLE qui est en faute,
        # et la 404 serait accusée à sa place.
        assert (origine["avant"]["lang"], origine["apres"]["lang"]) == ("fr", "en"), (
            f"{origine['page']} : `lang` {origine['avant']['lang']!r} avant le clic "
            f"et {origine['apres']['lang']!r} après — le choix n'y a pas été fait, "
            "la 404 n'est pas jugée")
    assert etat["h1"], f"/404.html {quand} : plus de h1"
    assert len(etat["entrees"]) == len(nav.ENTREES), (
        f"/404.html {quand} : {len(etat['entrees'])} entrée(s) de nav visible(s) "
        f"pour {len(nav.ENTREES)} dans `nav.ENTREES` — le test ne jugerait pas "
        "toute la nav")
    assert not etat["caches"], (
        f"/404.html {quand} : texte(s) traduit(s) invisible(s) {etat['caches']} — "
        "aucun ne serait jugé")
    assert len(etat["autres"]) >= 3 + len(build_404.RACCOURCIS), (
        f"/404.html {quand} : {len(etat['autres'])} texte(s) traduit(s) hors h1 et "
        f"nav ({[a['quoi'] for a in etat['autres']]}) — il en faut au moins "
        f"{3 + len(build_404.RACCOURCIS)} : le paragraphe, « Adresse demandée », "
        f"le bouton de retour et les {len(build_404.RACCOURCIS)} raccourcis")
    fautes = []
    if etat["lang"] != langue:
        fautes.append(("<html lang>", etat["lang"], langue))
    if (etat["bouton"] or "").strip() != langue.upper():
        fautes.append(("#langBtn", etat["bouton"], langue.upper()))
    juges = ([("<title>", etat["titre"])]
             + [("h1", h) for h in etat["h1"]]
             + [("nav", e) for e in etat["entrees"]]
             + [(a["quoi"], a) for a in etat["autres"]])
    for quoi, el in juges:
        attendu, rendu = _rendu(el[langue]), _rendu(el["texte"])
        if not attendu:
            fautes.append((quoi, rendu, f"{attr} absent ou vide"))
        elif rendu != attendu:
            fautes.append((quoi, rendu, attendu))
    assert not fautes, (
        f"/404.html {quand}, langue attendue {langue!r} — "
        f"{len(fautes)} faute(s) : {fautes}")


def test_le_choix_fait_sur_la_404_est_compris_par_les_autres_pages(bascule_de_la_404):
    """Le sens inverse du même contrat : la 404 écrit ce que les autres pages lisent.

    Après `rechargement-en`, le même contexte ouvre /explorer/, sans clic : elle
    doit être en anglais, `lang="en"` et son bouton sur « EN ». Une 404 qui
    écrirait `'EN'` et relirait sans casse resterait verte sur les six états
    ci-dessus, et enverrait /explorer/ en `lang="EN"`.
    """
    relu = bascule_de_la_404["relu-ailleurs"]
    page = _PAGE_QUI_RELIT_LE_CHOIX_DE_LA_404
    assert not relu["erreurs"], f"{page} : erreur(s) JavaScript {relu['erreurs']}"
    assert (relu["lang"], (relu["bouton"] or "").strip()) == ("en", "EN"), (
        f"{page} ouverte après l'anglais choisi sur la 404 : `lang` "
        f"{relu['lang']!r}, bouton {relu['bouton']!r} — attendu 'en' et 'EN'")
