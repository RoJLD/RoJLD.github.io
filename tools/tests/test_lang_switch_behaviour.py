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
