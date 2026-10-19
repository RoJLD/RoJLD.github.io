"""La bascule de langue est vérifiée en l'exécutant, pas en la lisant.

Les tests textuels voisins (test_build_site.py) épinglent l'expression de
mapping ; ils attrapent les mutations qu'on a su anticiper. Ceux-ci exécutent
le JS réel dans node et regardent où pointe le lien : ils attrapent aussi
celles qu'on n'a pas prévues.

Portée : `explorer/` et `highlights/`, les deux pages générées qui partagent
`applyBrowseLang`. L'accueil (index.html) reste couvert par l'assert épinglé —
son `applyLang` redessine le radar et sort du périmètre de ce stub.
"""
from __future__ import annotations

import functools
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import build_site as bs  # noqa: E402
import build_browse  # noqa: E402
import build_highlights  # noqa: E402
from lang_switch_harness import run_lang_switch  # noqa: E402
import corpus_publie  # noqa: E402

# La porte de l'oracle est commune à tout le dépôt (`conftest.node_requis`) :
# skip sur un poste sans node, ÉCHEC si `ELYSIUM_REQUIRE_NODE=1`. Le `skipif`
# local qui vivait ici échappait à ce drapeau — quatre gardes de comportement
# pouvaient s'évaporer en laissant du vert dans une chaîne d'intégration.

CARDS = [
    {
        "dataset": {"hrefFr": "/articles/x.html", "hrefEn": "/articles/x.en.html"},
        "attrs": {"href": "/articles/x.html"},
    }
]


# On paramètre par nom, pas par page : passer le HTML en paramètre le fait
# entrer dans l'identifiant de test, qui finit en variable d'environnement et
# dépasse la limite Windows de 32767 caractères.
BUILDERS = {
    "explorer": lambda p: build_browse.build_browse(p, write=False),
    "highlights": lambda p: build_highlights.build_highlights(p, write=False),
}


@functools.lru_cache(maxsize=None)
def _page(nom: str) -> str:
    """Chaque page est demandée une fois par sens de bascule ; on la construit
    une seule fois. Gain mesuré modeste (l'ensemble du fichier coûte ~0,9 s
    dans la suite) — c'est de l'hygiène, pas une optimisation nécessaire."""
    return BUILDERS[nom](bs.load_profile())


@pytest.mark.parametrize("nom", sorted(BUILDERS))
def test_la_bascule_en_envoie_vers_la_page_anglaise(nom, node_requis):
    out = run_lang_switch(_page(nom), entry="applyBrowseLang", lang="en", cards=CARDS)
    assert out[0]["attrs"]["href"] == "/articles/x.en.html", (
        f"{nom} : en anglais le lien doit pointer vers la version .en"
    )


@pytest.mark.parametrize("nom", sorted(BUILDERS))
def test_la_bascule_fr_ramene_vers_la_page_francaise(nom, node_requis):
    out = run_lang_switch(_page(nom), entry="applyBrowseLang", lang="fr", cards=CARDS)
    assert out[0]["attrs"]["href"] == "/articles/x.html", (
        f"{nom} : en français le lien doit revenir sur la version FR"
    )


# ── Langue annoncée / langue livrée : l'invariant, et ses cas fabriqués ──────
#
# La contre-vacuité livrée le 2026-10-19 avec cette garde exigeait qu'AU MOINS
# UNE page de la nav reste NON TRADUITE (`assert nav - traduites`). Prouvé par
# mutation le même jour : le jour où `/projects/` et `/demos/` seront traduites
# et rebasculeront — la suite que le correctif annonce lui-même — la garde
# ÉCHOUE (« 1 failed », message « toutes les pages de la nav sont traduites : le
# sens "annonce sans livrer" de cette garde ne juge plus rien »).
#
# Une contre-vacuité adossée à une propriété TRANSITOIRE du corpus se retourne
# contre la réussite : celle-ci faisait du paiement de la dette de traduction un
# rouge. Et le rouge serait arrivé au pire moment — pendant la livraison de la
# traduction, en accusant la garde de langue d'un défaut qui n'existe pas.
#
# Elle est remplacée par des CAS FABRIQUÉS, le procédé déjà retenu le même jour
# pour `NON_RECONNUE` (`test_liens_internes.py::
# test_une_destination_non_reconnue_est_nommee_et_jamais_jetee`) : le verdict est
# rendu par une fonction PURE, et les deux sens de l'invariant sont exercés sur
# des ensembles construits — donc sans rien exiger de l'état du corpus. Le
# corpus, lui, n'a plus qu'à n'avoir aucun écart, ce qui reste vrai avant comme
# après le paiement de la dette.


def ecarts_de_langue(lecture: frozenset[str], ecriture: frozenset[str],
                     traduites: frozenset[str]) -> dict[str, list[str]]:
    """Les trois familles de fautes de langue, nommées. Aucune ne doit être peuplée.

    Fonction PURE : elle ne lit ni le disque ni le corpus, et c'est tout son
    intérêt. Les deux sens de l'invariant « la langue annoncée est celle du
    contenu » sont donc vérifiables sur des ensembles fabriqués, y compris pour
    un état du corpus qui n'existe pas encore.

      annoncent_sans_livrer      la page bascule sans être traduite : elle pose
                                 `lang="en"` sur un corps français, et un lecteur
                                 d'écran lit du français avec une voix anglaise
                                 (WCAG 3.1.1, niveau A) — le défaut mesuré le
                                 2026-10-19 sur `/projects/` et `/demos/`.
      traduites_sans_basculer    la page est traduite et ne bascule pas : le
                                 choix du visiteur meurt au premier saut de nav
                                 — le défaut mesuré le 2026-10-15.
      temoins_divergents         la page LIT le choix mémorisé sans ÉCRIRE
                                 `lang`, ou l'inverse : les deux témoins de la
                                 bascule ne voient pas la même chose, donc l'un
                                 des deux ne mesure plus ce qu'on croit.
    """
    return {
        "annoncent_sans_livrer": sorted(lecture - traduites),
        "traduites_sans_basculer": sorted(traduites - lecture),
        "temoins_divergents": sorted(lecture ^ ecriture),
    }


_RIEN: dict[str, list[str]] = {"annoncent_sans_livrer": [],
                               "traduites_sans_basculer": [],
                               "temoins_divergents": []}

# Noms VOLONTAIREMENT synthétiques (`p1`…`p6`) : ce ne sont pas des pages de ce
# dépôt, et aucun de ces cas ne doit être retouché quand le corpus change. C'est
# la différence exacte avec la contre-vacuité qu'ils remplacent.
_CAS_FABRIQUES = [
    ("état du 2026-10-19 : quatre pages traduites basculent, deux non traduites "
     "ne basculent pas",
     frozenset({"p1", "p2", "p3", "p4"}), frozenset({"p1", "p2", "p3", "p4"}),
     frozenset({"p1", "p2", "p3", "p4"}), _RIEN),
    ("état FUTUR : la dette de traduction est payée, les six pages basculent",
     frozenset({"p1", "p2", "p3", "p4", "p5", "p6"}),
     frozenset({"p1", "p2", "p3", "p4", "p5", "p6"}),
     frozenset({"p1", "p2", "p3", "p4", "p5", "p6"}), _RIEN),
    ("une page bascule sans être traduite (le défaut du 2026-10-19)",
     frozenset({"p1", "p2", "p5"}), frozenset({"p1", "p2", "p5"}),
     frozenset({"p1", "p2"}),
     {"annoncent_sans_livrer": ["p5"], "traduites_sans_basculer": [],
      "temoins_divergents": []}),
    ("une page traduite ne bascule pas (le défaut du 2026-10-15)",
     frozenset({"p1", "p2"}), frozenset({"p1", "p2"}),
     frozenset({"p1", "p2", "p5"}),
     {"annoncent_sans_livrer": [], "traduites_sans_basculer": ["p5"],
      "temoins_divergents": []}),
    ("la page lit le choix mémorisé mais n'écrit pas `lang`",
     frozenset({"p1", "p2"}), frozenset({"p1"}), frozenset({"p1", "p2"}),
     {"annoncent_sans_livrer": [], "traduites_sans_basculer": [],
      "temoins_divergents": ["p2"]}),
    ("corpus VIDE : aucune faute à nommer, et c'est pourquoi le test de corpus "
     "porte son propre plancher",
     frozenset(), frozenset(), frozenset(), _RIEN),
]


@pytest.mark.parametrize("nom, lecture, ecriture, traduites, attendu",
                         _CAS_FABRIQUES, ids=lambda v: str(v)[:60])
def test_le_verdict_de_langue_refuse_les_deux_sens(nom, lecture, ecriture,
                                                   traduites, attendu):
    """Les deux sens sont refusés, et l'état FUTUR du corpus reste vert.

    C'est ce dernier cas qui remplace la contre-vacuité retirée : il prouve que
    la garde ne se retournera pas contre la réussite. Le cas « corpus vide »
    montre l'autre face — la fonction pure ne peut pas nommer une faute dans le
    vide, donc le plancher contre la vacuité appartient au test de corpus, pas à
    elle.
    """
    assert ecarts_de_langue(lecture, ecriture, traduites) == attendu, nom


def test_la_langue_annoncee_est_celle_du_contenu():
    """La langue qu'une page ANNONCE doit être celle que son contenu LIVRE.

    Cette garde en remplace une qui disait : « toutes les pages de la nav doivent
    lire la langue mémorisée ». Elle était vraie dans un sens et fausse dans
    l'autre, et c'est la version fausse qui a été livrée le 2026-10-19 :
    `/projects/` et `/demos/` ont reçu la bascule, donc rendaient `lang="en"` et
    `data-lang="en"` sur un corps resté FRANÇAIS, titre compris. Un lecteur
    d'écran lisait du français avec une voix anglaise — WCAG 3.1.1 Language of
    Page, niveau A. Avant la bascule, `lang` restait `fr`, ce qui était juste :
    la garde exigeait donc une régression.

    L'invariant correct est une ÉQUIVALENCE, et les trois familles d'écart que
    `ecarts_de_langue` nomme doivent toutes être vides. Les deux sens de cette
    équivalence sont prouvés par les cas FABRIQUÉS ci-dessus, pas par l'état du
    corpus : ce test-ci ne juge que le corpus.

    Trois témoins indépendants le renseignent, aucun n'étant une liste écrite
    ici (même forme que
    `test_theme_clair.test_les_trois_temoins_du_theme_disent_la_meme_chose`) :

        pages_qui_basculent_la_langue()        lecture du choix mémorisé
        pages_qui_ecrivent_l_attribut_langue() écriture de `lang` sur le document
        pages_majoritairement_traduites()      plus de 50 % du texte traduisible

    Mesuré le 2026-10-19, texte visible hors nav, parseur HTML sur les artefacts
    publiés : /explorer/ 155 traduisibles contre 2 nues (98,7 %), /graph/ 90
    contre 2 (97,8 %), /highlights/ 69 contre 29 (70,4 %), l'accueil 186 contre
    90 (67,4 %) — et /projects/ 0 contre 174, /demos/ 0 contre 33, soit 0,0 %
    tout rond. Aucun seuil à régler entre 0 % et 67 %.

    Prouvée ROUGE par mutation : sur une copie vierge de l'état d'avant le
    correctif (`git archive 9d7d7e2 | tar -x`, les deux pages portant encore la
    bascule), cette garde nomme les deux pages et leurs comptes.

    PLANCHER, et pourquoi il n'est pas celui d'avant. L'ancienne contre-vacuité
    exigeait `nav - traduites`, c'est-à-dire qu'une page de la nav reste NON
    traduite : elle serait devenue rouge le jour où la dette est payée. Le
    plancher retenu va dans l'autre sens — au moins une page traduite — et la
    réussite le renforce au lieu de le casser. Il ferme la seule vacuité qui
    reste ici : si les trois témoins se vidaient ensemble (traduction retirée de
    tout le site, ou parseur cassé), les trois familles d'écart seraient vides et
    ce test passerait sur un site sans une ligne de traduction.
    """
    nav = set(corpus_publie.pages_de_la_nav_partagee())
    assert len(nav) >= 6, f"seules {len(nav)} page(s) de nav découvertes : {sorted(nav)}"
    compte = corpus_publie.traduction_par_page()
    lecture = frozenset(corpus_publie.pages_qui_basculent_la_langue()) & nav
    ecriture = frozenset(corpus_publie.pages_qui_ecrivent_l_attribut_langue()) & nav
    traduites = frozenset(corpus_publie.pages_majoritairement_traduites()) & nav

    assert traduites, (
        f"aucune page de nav n'est majoritairement traduite : les trois témoins "
        f"se sont vidés ensemble, et l'équivalence serait tenue par le vide "
        f"({compte})")

    ecarts = ecarts_de_langue(lecture, ecriture, traduites)
    assert ecarts == _RIEN, (
        "la langue annoncée n'est pas celle du contenu — "
        f"bascule(nt) sans être traduite(s) : "
        f"{({p: compte[p] for p in ecarts['annoncent_sans_livrer']})} ; "
        f"traduite(s) sans basculer : "
        f"{({p: compte[p] for p in ecarts['traduites_sans_basculer']})} ; "
        f"témoins de la bascule divergents (lisent le choix mémorisé "
        f"{sorted(lecture)}, écrivent l'attribut `lang` {sorted(ecriture)}) : "
        f"{ecarts['temoins_divergents']}")
