"""Le thème clair doit exister sur CHAQUE page, et rester complet.

Pourquoi cette garde existe : une revue par mutation a supprimé le bloc
`[data-theme="light"]` de `/life-architect/` — la suite est restée verte. Ce
défaut-là est le plus coûteux du dépôt, parce que **aucun builder ne produit
cette page** : elle est maintenue à la main. Une régression sur les pages
générées se répare en relançant le build ; sur `/life-architect/`, elle est
définitive jusqu'à ce qu'un humain la remarque — et le symptôme (page noire
pour un visiteur en thème clair) n'est visible que d'un navigateur.

Trois propriétés sont tenues ici :
  1. toute page qui déclare une palette sombre déclare aussi une palette claire ;
  2. les deux palettes déclarent EXACTEMENT les mêmes variables — une palette
     claire amputée ne blanchit pas la page, elle la casse à moitié, ce qu'un
     test « le bloc existe » laisserait passer ;
  3. le thème est lu au démarrage et persisté au basculement, sous la même clé
     `localStorage` que les autres pages — sinon le choix du visiteur est perdu
     d'une page à l'autre.

La couche générateur est tenue en plus de la couche disque : muter un builder
sans reconstruire laisserait sinon la garde muette.
"""
from __future__ import annotations

import functools
import json
import pathlib
import re
import sys
import uuid

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from theme_boot_harness import extract_script, run_scenarios, run_theme  # noqa: E402
import corpus_publie  # noqa: E402

# Les pages à thème sont DÉCOUVERTES sur le disque, plus énumérées à la main.
#
# Mesuré : la liste écrite en dur ici — qui nommait `life-architect/index.html` —
# pouvait perdre cette entrée sans un seul rouge (488 -> 481 passed). Sept tests
# disparaissaient avec elle, dont la garde que ce fichier présente comme la plus
# importante du lot. Un test qui énumère ses cas depuis une constante ne peut pas
# détecter la mutation de cette constante ; il lui faut un témoin extérieur, ici
# le site publié (cf. `corpus_publie`).
#
# Deux champs distincts, parce que les propriétés le sont :
#   * `PAGES_A_PALETTE` — déclare une palette sombre, doit en déclarer une claire.
#     (Découverte : les deux pages d'articles en portent une, et n'étaient dans
#     aucune liste.)
#   * `PAGES_A_BOOT` — lit le thème mémorisé, doit l'appliquer. Sous-ensemble
#     strict : les pages d'articles portent les deux palettes mais aucun script
#     de restauration.
PAGES_A_PALETTE = corpus_publie.pages_a_palette()
PAGES_A_BOOT = corpus_publie.pages_a_boot()

# Les 6 pages de nav, découvertes elles aussi (témoin : leur `index.html` porte
# la marque de la nav partagée).
PAGES_GENEREES = corpus_publie.destinations_nav()

# La page sans builder : toute régression y est définitive.
PAGE_MANUELLE = "life-architect/index.html"


# ── Le plancher : dérivé, parce que deux versions écrites à la main sont mortes ─
#
# Historique mesuré, deux fois de suite :
#   1. le plancher vivait dans `corpus_publie.exiger_le_plancher()` — lui faire
#      rendre `[]` laissait la suite à 506 passed ;
#   2. il a déménagé ici, en un ensemble de huit noms écrits à la main. Le VIDER
#      (`= set()`) laissait la suite à 507 passed : le compte EXACT du vert de
#      référence, pas même un cas en moins. Et l'omission était portante — une
#      page publiée pouvait perdre `getItem('theme')` sans un seul rouge.
#
# Déplacer une attente ne la garde pas : une liste que son unique lecteur compare
# à elle-même ne peut pas diverger. Elle DÉRIVE donc, de trois signaux disjoints
# du site publié qui doivent coïncider (cf. `test_les_trois_temoins_du_theme_...`).
PAGES_ATTEIGNABLES = corpus_publie.pages_atteintes_par_la_nav()
PAGES_QUI_PERSISTENT = corpus_publie.pages_qui_persistent_le_theme()


def test_les_trois_temoins_du_theme_disent_la_meme_chose():
    """LE plancher, et il n'est écrit nulle part : il est constaté trois fois.

    Trois lectures indépendantes du site publié, qui n'ont aucune ligne de code
    ni aucun marqueur en commun :

      * `pages_atteintes_par_la_nav()` — les `href` des blocs `<nav>`, résolus
        sur le disque comme le ferait un navigateur. Ne regarde pas le thème.
      * `pages_a_boot()` — `getItem('theme')`, le script de démarrage.
      * `pages_qui_persistent_le_theme()` — `setItem('theme'`, le basculeur.

    La propriété défendue est celle du visiteur, pas celle d'une liste : *mon
    choix de thème survit à chaque saut de la nav*. Une page atteinte d'un clic
    qui ne restaure pas est une page noire pour qui a choisi le clair ; une page
    qui mémorise sans relire enregistre un choix qu'elle jettera.

    Aucune mutation d'un seul signal ne peut rétrécir les trois ensembles à la
    fois : c'est ce qui rend cette égalité imperméable au rabotage, là où les
    deux planchers écrits à la main qui l'ont précédée pouvaient être vidés sans
    un rouge.
    """
    nav, boot, persist = (set(PAGES_ATTEIGNABLES), set(PAGES_A_BOOT),
                          set(PAGES_QUI_PERSISTENT))
    assert nav == boot, (
        f"pages de la nav qui ne restaurent plus le thème : {sorted(nav - boot)} ; "
        f"pages qui le restaurent sans être dans la nav : {sorted(boot - nav)}")
    assert boot == persist, (
        f"pages qui restaurent sans mémoriser : {sorted(boot - persist)} ; "
        f"pages qui mémorisent sans restaurer (choix perdu au rechargement) : "
        f"{sorted(persist - boot)}")
    # Une page à thème sans palette claire est une page noire : le troisième
    # signal (les palettes) doit couvrir les trois premiers.
    assert boot <= set(PAGES_A_PALETTE), sorted(boot - set(PAGES_A_PALETTE))


def test_aucune_section_de_la_nav_n_est_hors_du_champ_du_theme():
    """Contre-vacuité : le témoin de la nav ne peut pas se vider en silence.

    Les trois témoins ci-dessus sont solidaires par égalité ; encore faut-il
    qu'ils ne rétrécissent pas ENSEMBLE. Un quatrième signal, encore disjoint —
    les répertoires du dépôt dont l'`index.html` porte la marque de la nav —
    borne le champ par le bas : chaque section publiée doit être atteignable
    depuis la nav, et donc porter le thème.
    """
    sections = {f"{d}/index.html" for d in corpus_publie.destinations_nav()}
    assert sections <= set(PAGES_ATTEIGNABLES), (
        f"sections publiées qu'aucun lien de nav n'atteint : "
        f"{sorted(sections - set(PAGES_ATTEIGNABLES))}")
    assert PAGE_MANUELLE in PAGES_ATTEIGNABLES, (
        f"{PAGE_MANUELLE} n'est plus atteinte par la nav — la page qu'aucun "
        "builder ne répare sortirait du champ de toutes les gardes")
    assert len(PAGES_A_PALETTE) >= 10, PAGES_A_PALETTE
    assert len(corpus_publie.pages_publiees()) >= 20, corpus_publie.pages_publiees()


def _palette(html: str, theme: str) -> set[str] | None:
    """Variables CSS déclarées par `[data-theme="<theme>"]`, ou None si absent."""
    m = re.search(r'\[data-theme="%s"\]\s*\{(.*?)\}' % theme, html, re.S)
    if not m:
        return None
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", m.group(1)))


def _html_disque(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES_A_PALETTE)
def test_la_page_declare_une_palette_claire(page):
    sombre = _palette(_html_disque(page), "dark")
    claire = _palette(_html_disque(page), "light")
    assert sombre, f"{page} : palette sombre introuvable — le test mesure-t-il la bonne chose ?"
    assert claire is not None, (
        f"{page} : aucun bloc [data-theme=\"light\"] — un visiteur en thème clair "
        "arrive sur une page noire")


@pytest.mark.parametrize("page", PAGES_A_PALETTE)
def test_les_deux_palettes_declarent_les_memes_variables(page):
    html = _html_disque(page)
    sombre, claire = _palette(html, "dark"), _palette(html, "light")
    assert claire is not None, f"{page} : palette claire absente"
    assert sombre == claire, (
        f"{page} : palettes désaccordées — absentes du clair {sorted(sombre - claire)}, "
        f"absentes du sombre {sorted(claire - sombre)}")


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_la_cle_localstorage_est_partagee(page):
    """Même clé `localStorage` partout : le choix survit à la navigation.

    Test de PRÉSENCE, et rien de plus — il ne prouve pas que la valeur lue est
    appliquée. Il s'appelait `test_le_theme_est_restaure_et_persiste` et
    revendiquait la restauration ; une mutation qui jetait la valeur lue
    (`if(t)…setAttribute(…)` -> `if(t){}`) le laissait vert. Renommé pour dire
    ce qu'il mesure ; la restauration elle-même est tenue plus bas, en exécutant
    le script.
    """
    html = _html_disque(page)
    assert "getItem('theme')" in html, f"{page} : la clé 'theme' n'est plus lue"
    assert "setItem('theme'" in html, f"{page} : basculement non persisté"


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_le_script_qui_lit_le_theme_l_applique(page):
    """Lire et appliquer sont dans le MÊME bloc — garde portable, sans node.

    Cherchée sur la page entière, la chaîne `setAttribute('data-theme'` est
    fournie par le basculeur : la restauration peut disparaître sans que rien
    ne bouge. Restreinte au script qui lit `localStorage`, elle rougit sous la
    mutation mesurée. Nécessaire, pas suffisante (une valeur en dur passerait) :
    les tests d'exécution qui suivent ferment ce reste.
    """
    boot = extract_script(_html_disque(page), "getItem('theme')")
    assert "setAttribute('data-theme'" in boot, (
        f"{page} : le script qui lit le thème ne l'applique jamais à la racine — "
        "la valeur mémorisée est lue puis jetée")


def test_la_page_manuelle_bascule_reellement_lattribut():
    """`/life-architect/` n'a pas de builder : son mécanisme est vérifié en propre.

    Déclarer la palette ne suffit pas — encore faut-il que quelque chose écrive
    `data-theme` sur la racine, sinon le bloc clair n'est jamais atteint.
    """
    html = _html_disque(PAGE_MANUELLE)
    assert "setAttribute('data-theme'" in html, "aucune bascule de l'attribut data-theme"
    assert re.search(r"function tgTheme\s*\(", html), "fonction de bascule tgTheme absente"
    assert 'onclick="tgTheme()"' in html, "aucun contrôle ne déclenche la bascule"


# --- La même garde une couche plus tôt : sur la sortie des générateurs -------

@functools.lru_cache(maxsize=1)
def _rendu_des_builders() -> dict[str, str]:
    import build_academy, build_browse, build_demos          # noqa: E401
    import build_graph, build_highlights, build_projects     # noqa: E401
    p = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    return {
        "projects": build_projects.build_projects(p, write=False),
        "explorer": build_browse.build_browse(p, write=False),
        "highlights": build_highlights.build_highlights(p, write=False),
        "academy": build_academy.build_academy(write=False),
        "graph": build_graph.build_graph(p, write=False),
        "demos": build_demos.build_demos(p, write=False),
    }


def test_les_generateurs_couvrent_toutes_les_pages_de_nav():
    """La table des générateurs est tenue par le disque, pas par elle-même.

    Mesuré : retirer `demos` de la liste paramétrée retirait le cas de test
    correspondant — 487 passed, aucun rouge. La table ci-dessus a la même
    faiblesse ; ce test la referme en la confrontant aux pages réellement
    servies.
    """
    assert set(_rendu_des_builders()) == set(PAGES_GENEREES), (
        f"table des générateurs {sorted(_rendu_des_builders())} désaccordée avec "
        f"les pages de nav publiées {sorted(PAGES_GENEREES)}")


@pytest.mark.parametrize("page", PAGES_GENEREES)
def test_le_generateur_emet_les_deux_palettes(page):
    html = _rendu_des_builders()[page]
    sombre, claire = _palette(html, "dark"), _palette(html, "light")
    assert claire is not None, f"le générateur de /{page}/ n'émet plus de palette claire"
    assert sombre == claire, (
        f"le générateur de /{page}/ émet des palettes désaccordées : "
        f"absentes du clair {sorted(sombre - claire)}")


# --- Le thème EXÉCUTÉ, pas lu ------------------------------------------------
# Déclarer une palette claire et lire la clé `theme` ne fait pas une page
# claire : encore faut-il que la valeur mémorisée atteigne `data-theme`. Ces
# tests exécutent le script réel de la page servie dans node.

# Le basculeur ne porte pas le même nom partout (l'accueil est antérieur aux
# pages générées). L'écrire ici plutôt que de le deviner : un nom faux doit
# faire échouer l'extraction, pas rendre le test muet.
BASCULEUR = {
    "index.html": "toggleTheme",
    "life-architect/index.html": "tgTheme",
    "projects/index.html": "tgTheme",
    "explorer/index.html": "tgTheme",
    "highlights/index.html": "tgTheme",
    "academy/index.html": "tgTheme",
    "graph/index.html": "tgTheme",
    "demos/index.html": "tgTheme",
}

# Le contrôle qui déclenche la bascule, tel qu'il est ÉCRIT dans la page servie.
_DECLENCHEUR = re.compile(r'onclick="([A-Za-z_$][\w$]*)\(\)"')


def test_chaque_page_a_boot_a_un_basculeur_nomme():
    """Une page découverte sans entrée ici doit crier, pas sortir du champ.

    `BASCULEUR` est la dernière table écrite à la main de ce fichier. Elle ne
    peut plus rétrécir la couverture (les cas viennent du disque), mais une page
    NEUVE y serait absente et lèverait un `KeyError` sec au milieu d'un test
    d'exécution. Ce test-ci nomme le manque.
    """
    manquants = sorted(set(PAGES_A_BOOT) - set(BASCULEUR))
    assert not manquants, (
        f"pages lisant le thème sans basculeur déclaré : {manquants} — "
        "ajouter le nom de leur fonction de bascule")


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_le_nom_du_basculeur_est_celui_que_la_page_declenche(page):
    """La table ci-dessus est confrontée à la page, pas à elle-même.

    Sans ce test, `BASCULEUR` reste un nom recopié : `run_scenarios` appelle
    `tgTheme()` parce que la table le dit, et la table le dit parce qu'on l'y a
    écrit. Le témoin extérieur est le `onclick=` du bouton réellement servi —
    c'est lui que le visiteur déclenche. Un basculeur renommé dans la page mais
    pas ici (ou l'inverse) rend le scénario BASCULE fictif : il exercerait une
    fonction que personne ne peut appeler.
    """
    html = _html_disque(page)
    declenches = set(_DECLENCHEUR.findall(html))
    assert BASCULEUR[page] in declenches, (
        f"{page} : aucun contrôle ne déclenche {BASCULEUR[page]}() — "
        f"la page déclenche {sorted(declenches)}")


RESTAURE, DEFAUT, BASCULE, RECHARGE = range(4)

# Témoin tiré au hasard À CHAQUE EXÉCUTION, déposé dans le `localStorage` avant
# la bascule. Il ne sert à aucune page : il sert à PROUVER que le scénario de
# rechargement repart bien du stockage laissé par la bascule, et non d'un état
# reconstitué à la main.
#
# Mesuré : remplacer `{"__depuis__": BASCULE}` par `{"theme": "light"}` laissait
# la suite à 507 passed — le test du rechargement devenait une redite du test de
# restauration, alors qu'il revendique d'être « la seule mesure qui prouve que la
# persistance et la restauration parlent bien de la même clé ». Comparer les deux
# stockages ne suffisait pas à le détecter : la bascule partant d'un stockage
# vide, elle laisse exactement `{"theme": "light"}`, donc la contrefaçon écrite à
# la main était indiscernable de l'original. Le témoin aléatoire, lui, ne peut
# pas être écrit dans le test : il n'existe qu'à l'exécution.
_TEMOIN_DE_CHAINAGE = f"chainage-{uuid.uuid4().hex}"


def test_le_temoin_de_chainage_ne_peut_pas_etre_ecrit_a_la_main():
    """Le témoin ne vaut que s'il est INÉCRIVABLE dans ce fichier.

    Figé en constante (`"chainage-fixe"`), il resterait recopiable dans un
    scénario contrefait, et le chaînage redeviendrait une affirmation. Mesuré :
    la mutation qui le fige laissait la suite à 541 passed — la garde ci-dessous
    ne se gardait pas elle-même. Tiré au sort à chaque exécution, il ne peut par
    construction figurer dans la source.
    """
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert _TEMOIN_DE_CHAINAGE not in source, (
        f"le témoin de chaînage ({_TEMOIN_DE_CHAINAGE!r}) est une constante du "
        "fichier : il peut être recopié dans un faux scénario de rechargement, "
        "qui passerait alors pour l'original")


@functools.lru_cache(maxsize=None)
def _mesures(page: str) -> tuple:
    """Les quatre observations faites sur une page, en un seul appel à node.

    Groupées parce que chaque lancement de node coûte ~0,4 s : mesurées une par
    une, ces gardes triplaient la durée de la suite (25 s -> 73 s), et une garde
    qu'on finit par désactiver pour sa lenteur ne garde plus rien.
    """
    tg = BASCULEUR[page]
    return tuple(run_scenarios(_html_disque(page), [
        {"stored": {"theme": "light"}},                             # RESTAURE
        {"stored": {}},                                             # DEFAUT
        {"needle": f"function {tg}", "call": f"{tg}()",             # BASCULE
         "stored": {"__temoin__": _TEMOIN_DE_CHAINAGE}},
        {"stored": {"__depuis__": BASCULE}},                        # RECHARGE
    ]))


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_le_theme_memorise_est_reellement_applique(page, node_requis):
    """LA garde du lot : `theme=light` en mémoire -> la racine passe en clair.

    Mutation qui laissait la suite verte (`/life-architect/`, ligne 13) :
        if(t)document.documentElement.setAttribute('data-theme',t)  ->  if(t){}
    Le visiteur qui avait choisi le thème clair recevait une page noire.
    """
    etat = _mesures(page)[RESTAURE]
    assert etat["theme"] == "light", (
        f"{page} : thème mémorisé 'light' non appliqué au chargement "
        f"(data-theme reste {etat['theme']!r}) — la valeur lue est jetée")


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_sans_choix_memorise_la_page_garde_son_theme_par_defaut(page, node_requis):
    """Contre-épreuve : la restauration doit SUIVRE la mémoire, pas forcer une valeur.

    Sans elle, `setAttribute('data-theme','light')` inconditionnel passerait le
    test précédent tout en cassant la page pour tous les autres visiteurs.
    """
    etat = _mesures(page)[DEFAUT]
    assert etat["theme"] == "dark", (
        f"{page} : sans préférence mémorisée le thème servi est modifié "
        f"({etat['theme']!r} au lieu de 'dark')")


@pytest.mark.parametrize("page", PAGES_A_BOOT)
def test_le_choix_survit_au_rechargement(page, node_requis):
    """Aller-retour complet : je bascule, je recharge, je retrouve mon thème.

    Deux exécutions dans des contextes distincts, reliées par le seul
    `localStorage` — c'est le parcours réel du visiteur, et la seule mesure qui
    prouve que la persistance et la restauration parlent bien de la même clé.

    Le chaînage lui-même est vérifié, et non postulé : le second contexte doit
    partir EXACTEMENT du stockage que le premier a laissé, témoin aléatoire
    compris. Sans cette vérification, un scénario de rechargement reconstitué à
    la main (`{"theme": "light"}`) passait pour l'original et le test se réduisait
    à une redite de la restauration.
    """
    bascule, rechargement = _mesures(page)[BASCULE], _mesures(page)[RECHARGE]
    assert bascule["theme"] == "light", (
        f"{page} : la bascule ne passe pas en clair ({bascule['theme']!r})")
    assert bascule["store"].get("theme") == "light", (
        f"{page} : la bascule n'a rien mémorisé ({bascule['store']})")
    assert rechargement["store_initial"] == bascule["store"], (
        f"{page} : le rechargement ne repart pas du stockage laissé par la "
        f"bascule — parti de {rechargement['store_initial']}, la bascule avait "
        f"laissé {bascule['store']}")
    assert rechargement["store_initial"].get("__temoin__") == _TEMOIN_DE_CHAINAGE, (
        f"{page} : le témoin déposé avant la bascule n'a pas traversé la chaîne — "
        "les deux exécutions ne sont pas reliées par le même localStorage")
    assert rechargement["theme"] == "light", (
        f"{page} : le choix du visiteur est perdu au rechargement "
        f"(data-theme = {rechargement['theme']!r})")


@pytest.mark.parametrize("page", PAGES_GENEREES)
def test_le_generateur_emet_une_restauration_qui_applique(page, node_requis):
    """La même garde sur la SOURCE : un builder amputé passerait vert sur disque.

    Les six pages de nav sont régénérées à chaque build ; tenir l'artefact seul
    laisserait une régression du générateur invisible jusqu'à ce qu'elle soit
    propagée par le prochain `build_site.py`.
    """
    etat = run_theme(_rendu_des_builders()[page], stored={"theme": "light"}, initial="dark")
    assert etat["theme"] == "light", (
        f"le générateur de /{page}/ n'applique plus le thème mémorisé "
        f"(data-theme reste {etat['theme']!r})")
