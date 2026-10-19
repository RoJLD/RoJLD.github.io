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

    L'invariant correct est une ÉQUIVALENCE, et il refuse les deux défauts :

      * une page traduite qui ne bascule pas -> le choix du visiteur meurt au
        premier saut de nav (le défaut mesuré le 2026-10-15) ;
      * une page qui bascule sans être traduite -> elle annonce une langue
        qu'elle ne livre pas (le défaut mesuré le 2026-10-19).

    Trois témoins indépendants doivent coïncider, aucun n'étant une liste écrite
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
    bascule), cette garde nomme les deux pages et leurs comptes —
    `1 failed, 4 passed`.
    """
    nav = set(corpus_publie.pages_de_la_nav_partagee())
    assert nav, "aucune page de nav découverte"
    compte = corpus_publie.traduction_par_page()
    lecture = set(corpus_publie.pages_qui_basculent_la_langue()) & nav
    ecriture = set(corpus_publie.pages_qui_ecrivent_l_attribut_langue()) & nav
    traduites = set(corpus_publie.pages_majoritairement_traduites()) & nav

    # Contre-vacuité : les deux familles doivent exister, sinon l'équivalence est
    # tenue par le vide et ne refuse plus rien.
    assert traduites, f"aucune page de nav traduite : {compte}"
    assert nav - traduites, (
        "toutes les pages de la nav sont traduites : le sens « annonce sans "
        f"livrer » de cette garde ne juge plus rien ({compte})")

    assert lecture == ecriture, (
        f"les deux témoins de la bascule divergent — lisent le choix mémorisé "
        f"{sorted(lecture)}, écrivent l'attribut `lang` {sorted(ecriture)}")
    assert lecture == traduites, (
        "la langue annoncée n'est pas celle du contenu — bascule(nt) sans être "
        f"traduite(s) : {({p: compte[p] for p in sorted(lecture - traduites)})} ; "
        f"traduite(s) sans basculer : "
        f"{({p: compte[p] for p in sorted(traduites - lecture)})}")
