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
import shutil
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import build_site as bs  # noqa: E402
import build_browse  # noqa: E402
import build_highlights  # noqa: E402
from lang_switch_harness import run_lang_switch  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node absent — harnais comportemental non exécutable"
)

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
def test_la_bascule_en_envoie_vers_la_page_anglaise(nom):
    out = run_lang_switch(_page(nom), entry="applyBrowseLang", lang="en", cards=CARDS)
    assert out[0]["attrs"]["href"] == "/articles/x.en.html", (
        f"{nom} : en anglais le lien doit pointer vers la version .en"
    )


@pytest.mark.parametrize("nom", sorted(BUILDERS))
def test_la_bascule_fr_ramene_vers_la_page_francaise(nom):
    out = run_lang_switch(_page(nom), entry="applyBrowseLang", lang="fr", cards=CARDS)
    assert out[0]["attrs"]["href"] == "/articles/x.html", (
        f"{nom} : en français le lien doit revenir sur la version FR"
    )
