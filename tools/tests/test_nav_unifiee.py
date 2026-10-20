"""La nav de chaque page qui la porte déclare les mêmes destinations, venues de `nav.py`.

Sept pages depuis la page 404 du 2026-10-20 : l'accueil, les cinq sous-pages et
`404.html`.

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

Arbitrage 1 du 2026-10-15 : `tools/nav.py` est la source des CINQ sous-pages
(et, depuis le 2026-10-20, de la 404) ; l'accueil garde son balisage à la main
(y mettre une zone BUILD ferait lever `BuildError` à
`build_site.synchroniser_textes_statiques`, la marque contenant `<b>`). Le lien entre les deux est donc ce fichier : un test, pas un générateur.

Depuis le 2026-10-20, ce fichier tient aussi la TRADUCTION de la nav : sur chaque
page qui porte le bouton de langue, chaque entrée porte les attributs que la
bascule de cette page lit (cf. la dernière section).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from html.parser import HTMLParser

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
#
# La page d'erreur (`404.html`, servie par GitHub Pages à toute adresse absente)
# vit elle aussi à la racine et n'est la cible d'aucun lien : elle vient de
# `corpus_publie.page_d_erreur()`, qui la nomme par la convention de l'hébergeur.
# Son nom de page pour `nav.py` est son nom servi sans extension, comme celui
# d'un répertoire est son nom.
PAGES = {"index.html": "accueil"}
PAGES.update({f"{d}/index.html": d for d in corpus_publie.destinations_nav()})
PAGES.update({rel: pathlib.PurePosixPath(rel).stem for rel in corpus_publie.page_d_erreur()})

_BLOC_NAV = re.compile(r"<nav\b.*?</nav>", re.S)
_HREF = re.compile(r'href="([^"]*)"')
_MARQUE = "nav-brand"

# La marque, et elle seule, est exclue de la comparaison d'égalité.
#
# Elle n'est pas une entrée de la barre : les cinq sous-pages et la 404 portent
# `<a class="nav-brand" href="/">`, l'accueil un `<span class="nav-brand">` SANS
# href (celui de sa nav écrite à la main) — il ne se lie pas à lui-même. Une
# égalité stricte des ensembles resterait donc ROUGE pour toujours, et `/` en est
# le résidu irréductible (mesuré : `TOUS LES ENSEMBLES EGAUX ? False`). Soustraire
# `/` sans le dire est la façon dont une garde pourrit ; l'invariant réel est
# gardé à côté, par `test_chaque_sous_page_ramene_a_l_accueil`.
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
    entrée perdue par une page rougit ; et comme `nav.py` rend la même liste à
    toutes les pages de `PAGES` (aux ancres près, `#blog` sur l'accueil et
    `/#blog` ailleurs), l'égalité deux à deux de leurs navs en découle.

    Séquences et non ensembles depuis le 2026-10-19 : l'ordre de la barre est ce
    qu'un visiteur lit et ce que la tabulation suit, et rien ne le tenait. Deux
    entrées permutées entre `nav.py` et une page publiée passaient vertes.

    Ce que ce test ne peut PAS voir, et c'est pourquoi les deux planchers
    ci-dessous existent : `nav.ENTREES` est ici l'attendu ET la source des six
    pages générées (les cinq sous-pages et la 404). Une entrée retirée de
    `nav.ENTREES`, ces six pages régénérées et la même ligne retirée de l'accueil
    écrit à la main — tout coïncide, et ce test est vert sur une nav amputée.
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
    la barre, et les six générateurs de page (cinq sous-pages et la 404) ne
    jouent pas `valider_site_texts`."""
    import json

    textes = json.loads((ROOT / "site_texts.json").read_text(encoding="utf-8"))
    del textes["en"]["nav_graph"]
    p = tmp_path / "site_texts.json"
    p.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(nav.NavError, match="nav_graph"):
        nav.charger_libelles(p)


# ── La nav est traduite sur chaque page qui promet les deux langues ──────────
#
# La garde de traduction de la 404 (`test_liens_internes.py`) écartait la nav au
# motif que ses entrées étaient « tenues par leurs propres gardes ». Aucune garde
# ne les tenait. Relecture adverse du 2026-10-20, porte complète à deux drapeaux
# sur copie vierge : retirer `data-en` de chaque entrée (`nav._attrs_langue`)
# laissait la porte verte ; passer la 404 au dialecte `i18n` (`nav._PAGES`) aussi
# — ses onze entrées portaient alors `data-i18n`, que rien ne lit sur cette page,
# et restaient en français sous `lang="en"`.
#
# Le mécanisme réel, mesuré le 2026-10-20 sur les 15 pages publiées : cinq portent
# le bouton de langue (`id="langBtn"`) — l'accueil, la 404, /explorer/, /graph/
# et /highlights/ — et leur nav suit l'un des deux dialectes de `nav.py` :
#
#     accueil            11 entrées `data-i18n`, lues par `[data-i18n]` dans le
#                        dictionnaire `const i18n` que la page embarque ;
#     les quatre autres  11 entrées `data-fr` + `data-en`, lues par
#                        `applyBrowseLang` (`[data-fr][data-en]`).
#
# Une entrée est donc traduite si elle porte, non vides, les attributs QUE SA
# PAGE LIT : `data-fr` et `data-en` sur une page dont un script lit
# `[data-fr][data-en]` ; ou une clé `data-i18n` présente en français ET en
# anglais dans le dictionnaire `const i18n` d'une page dont un script lit
# `[data-i18n]`. Les attributs d'un dialecte que la page ne lit pas laissent
# l'entrée en français.
#
# Hors champ, et pourquoi :
#   * les pages SANS bouton de langue (`/projects/`, `/demos/`, les deux
#     articles). Elles ne promettent pas l'anglais (retrait assumé du 2026-10-19,
#     cf. `nav.render_boutons`), et les entrées de `/projects/` et `/demos/`
#     portent `data-fr`/`data-en` sans qu'aucun de leurs scripts ne les lise : les
#     juger ferait rougir la garde sur une promesse que ces pages ne font pas ;
#   * la marque (un nom propre) et les deux boutons, qui ne sont pas des entrées.
# Non gardé, et dit pour ne pas être cru gardé : le `title` des deux boutons
# (« Langue » et « Thème » sur les quatre pages du second dialecte, « Switch
# language » et « Toggle theme » sur l'accueil), qu'aucune bascule ne réécrit.

_LECTEUR_FR_EN = "[data-fr][data-en]"
_LECTEUR_I18N = "[data-i18n]"
_BOUTON_LANGUE = "langBtn"
_PAIRE_DU_DICTIONNAIRE = re.compile(r'(\w+):\s*("(?:[^"\\]|\\.)*")')


def _dictionnaire_i18n(scripts: str) -> dict[str, dict[str, str]] | None:
    """Le dictionnaire `const i18n = {fr: {…}, en: {…}}` des scripts, ou None.

    Même lecture que `test_site_texts._dictionnaire`, qui tient ce dictionnaire
    dans les deux langues pour l'accueil : un objet littéral dont les valeurs
    sont des chaînes entre guillemets doubles. Les deux langues manquent-elles,
    la fonction rend None, et chaque entrée `data-i18n` est nommée.
    """
    debut = scripts.find(corpus_publie._DICTIONNAIRE_I18N)
    if debut < 0:
        return None
    fin = re.compile(r"\n\s*\};").search(scripts, debut)
    d = scripts[debut:fin.start() if fin else len(scripts)]
    fr_i, en_i = d.find("fr: {"), d.find("en: {")
    if fr_i < 0 or en_i < 0:
        return None
    return {lang: {k: json.loads(v) for k, v in _PAIRE_DU_DICTIONNAIRE.findall(seg)}
            for lang, seg in (("fr", d[fr_i:en_i]), ("en", d[en_i:]))}


class _NavEtSaBascule(HTMLParser):
    """Ce qu'il faut pour juger la traduction de la nav partagée, et rien d'autre.

    Rapporte, sans rien décider :
      * `bouton_langue` : un élément de la page porte `id="langBtn"` ;
      * `blocs` : pour chaque bloc `<nav>`, s'il porte la marque `nav-brand`, et
        le texte et les attributs de chacun de ses `<a>`, la marque exceptée ;
      * `scripts` : le texte des `<script>` de la page, à la suite.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bouton_langue = False
        self.blocs: list[dict] = []
        self.scripts = ""
        self._profondeur_nav = 0
        self._a: dict | None = None
        self._dans_script = False

    def handle_starttag(self, tag, attrs):
        d = {k.lower(): (v or "") for k, v in attrs}
        if d.get("id") == _BOUTON_LANGUE:
            self.bouton_langue = True
        if tag == "script":
            self._dans_script = True
        elif tag == "nav":
            self._profondeur_nav += 1
            if self._profondeur_nav == 1:
                self.blocs.append({"marque": False, "entrees": []})
        if not self._profondeur_nav:
            return
        if _MARQUE in d.get("class", "").split():
            self.blocs[-1]["marque"] = True
        elif tag == "a":
            self._a = {"texte": "", "attrs": d}
            self.blocs[-1]["entrees"].append(self._a)

    def handle_endtag(self, tag):
        if tag == "script":
            self._dans_script = False
            self.scripts += "\n"
        elif tag == "nav" and self._profondeur_nav:
            self._profondeur_nav -= 1
        elif tag == "a":
            self._a = None

    def handle_data(self, data):
        if self._dans_script:
            self.scripts += data
        elif self._a is not None:
            self._a["texte"] += data


def juger_la_traduction_de_la_nav(texte: str) -> dict:
    """Pour le texte d'une page : bouton de langue ou non, entrées lues, fautes.

    Fonction PURE (ni disque ni corpus), prouvée sur des cas fabriqués ci-dessous.
    `fautes` nomme chaque entrée de la nav partagée que la bascule de la page ne
    traduit pas, avec la raison. Elle est calculée même sans bouton de langue :
    c'est au test de corpus d'écarter ces pages, et le cas `sans-bouton` montre
    qu'il le peut.
    """
    p = _NavEtSaBascule()
    p.feed(texte)
    p.close()
    lit_fr_en = _LECTEUR_FR_EN in p.scripts
    dico = _dictionnaire_i18n(p.scripts) if _LECTEUR_I18N in p.scripts else None
    entrees = [e for b in p.blocs if b["marque"] for e in b["entrees"]]
    fautes: list[tuple[str, str]] = []
    for e in entrees:
        a = e["attrs"]
        fr, en, cle = (a.get(k, "").strip() for k in ("data-fr", "data-en", "data-i18n"))
        if lit_fr_en and fr and en:
            continue
        if (dico is not None and cle and str(dico["fr"].get(cle, "")).strip()
                and str(dico["en"].get(cle, "")).strip()):
            continue
        if cle:
            raison = (f"data-i18n={cle!r} absente ou vide du dictionnaire, en fr ou en en"
                      if dico is not None else
                      f"data-i18n={cle!r}, mais la page ne lit pas `[data-i18n]` "
                      "dans un dictionnaire `const i18n`")
        elif "data-fr" in a or "data-en" in a:
            raison = ("data-fr ou data-en absent ou vide" if lit_fr_en else
                      "data-fr/data-en, mais aucun script de la page ne lit "
                      "`[data-fr][data-en]`")
        else:
            raison = "aucun attribut de traduction"
        fautes.append((" ".join(e["texte"].split()), raison))
    return {"bouton": p.bouton_langue, "entrees": len(entrees), "fautes": fautes}


_SCRIPT_FR_EN = ("<script>document.querySelectorAll('[data-fr][data-en]')"
                 ".forEach(function (el) {});</script>")
_SCRIPT_I18N = ('<script>const i18n = {\n  fr: {nav_exp: "Expérience"},\n'
                '  en: {nav_exp: "Experience"}\n};\n'
                "document.querySelectorAll('[data-i18n]').forEach(el => {});</script>")


def _page_fabriquee(entrees: str, script: str, bouton: bool = True) -> str:
    return ('<html><body><nav><a class="nav-brand" href="/">R<b>.</b> Denis</a>'
            f'<div class="nav-r">{entrees}</div>'
            + ('<button id="langBtn">FR</button>' if bouton else "")
            + f'<button id="themeBtn">🌙</button></nav>{script}</body></html>')


@pytest.mark.parametrize("html, bouton, entrees, fautives", [
    pytest.param(_page_fabriquee('<a data-fr="Expérience" data-en="Experience">Expérience</a>',
                                 _SCRIPT_FR_EN), True, 1, [], id="fr-en-lu"),
    pytest.param(_page_fabriquee('<a data-fr="Expérience">Expérience</a>', _SCRIPT_FR_EN),
                 True, 1, ["Expérience"], id="data-en-absent"),
    pytest.param(_page_fabriquee('<a data-fr="Expérience" data-en=" ">Expérience</a>',
                                 _SCRIPT_FR_EN), True, 1, ["Expérience"], id="data-en-vide"),
    pytest.param(_page_fabriquee('<a data-i18n="nav_exp">Expérience</a>', _SCRIPT_I18N),
                 True, 1, [], id="i18n-et-son-dictionnaire"),
    pytest.param(_page_fabriquee('<a data-i18n="nav_exp">Expérience</a>', _SCRIPT_FR_EN),
                 True, 1, ["Expérience"], id="i18n-sans-dictionnaire"),
    pytest.param(_page_fabriquee('<a data-i18n="nav_edu">Formation</a>', _SCRIPT_I18N),
                 True, 1, ["Formation"], id="i18n-cle-absente-du-dictionnaire"),
    pytest.param(_page_fabriquee('<a data-fr="Expérience" data-en="Experience">Expérience</a>',
                                 _SCRIPT_I18N), True, 1, ["Expérience"], id="fr-en-sans-lecteur"),
    pytest.param(_page_fabriquee('<a data-fr="Expérience">Expérience</a>', _SCRIPT_FR_EN,
                                 bouton=False), False, 1, ["Expérience"], id="sans-bouton"),
    pytest.param(_page_fabriquee("", _SCRIPT_FR_EN), True, 0, [],
                 id="marque-et-boutons-ne-sont-pas-des-entrees"),
    pytest.param('<nav><a href="/x">Ailleurs</a></nav>'
                 + _page_fabriquee('<a data-fr="Blog" data-en="Blog">Blog</a>', _SCRIPT_FR_EN),
                 True, 1, [], id="nav-sans-marque-hors-champ"),
])
def test_la_sonde_de_la_nav_nomme_toute_entree_non_traduite_et_rien_d_autre(
        html, bouton, entrees, fautives):
    """La sonde ci-dessus, prouvée sur des cas FABRIQUÉS, dans les deux sens.

    Les cas `i18n-sans-dictionnaire` et `fr-en-sans-lecteur` sont les deux
    passages d'une page au dialecte qu'elle ne lit pas : le premier est la
    mutation de la 404 que la relecture adverse a laissée verte.
    """
    r = juger_la_traduction_de_la_nav(html)
    assert (r["bouton"], r["entrees"], [libelle for libelle, _ in r["fautes"]]) == \
        (bouton, entrees, fautives), r


def test_chaque_entree_de_nav_est_traduite_sur_les_pages_au_bouton_de_langue():
    """Sur toute page publiée qui porte le bouton de langue, la nav est traduite.

    Population DÉCOUVERTE : les pages publiées (`corpus_publie.pages_publiees`)
    qui portent `id="langBtn"`. Le jugement est celui de
    `juger_la_traduction_de_la_nav` : chaque entrée porte, non vides, les
    attributs que la bascule de SA page lit.

    Plancher : au moins cinq pages au bouton dont la nav partagée a des entrées
    (cinq mesurées le 2026-10-20), l'accueil compris — seule page du dialecte
    `i18n`, sans elle une branche du jugement ne verrait plus rien. Un parseur
    qui ne lirait plus aucune entrée rendrait la garde verte sur le vide.
    """
    jugees = {}
    for rel in corpus_publie.pages_publiees():
        r = juger_la_traduction_de_la_nav((ROOT / rel).read_text(encoding="utf-8"))
        if r["bouton"]:
            jugees[rel] = r
    avec_entrees = sorted(rel for rel, r in jugees.items() if r["entrees"])
    assert len(avec_entrees) >= 5 and "index.html" in avec_entrees, (
        f"seules {len(avec_entrees)} page(s) au bouton de langue avec une nav "
        f"partagée lue : {avec_entrees} (toutes les pages au bouton : {sorted(jugees)})")
    fautes = {rel: r["fautes"] for rel, r in sorted(jugees.items()) if r["fautes"]}
    assert not fautes, (
        "entrées de nav que la bascule de leur page ne traduit pas — elles restent "
        f"en français sous lang=\"en\" : {fautes}")
