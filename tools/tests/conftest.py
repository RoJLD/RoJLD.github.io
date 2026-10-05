"""Fixtures partagées de la suite.

La porte des oracles de comportement (node) vit dans `oracle_node`, pas ici :
une fixture ne garde que les tests qui pensent à la demander, et l'oubli est
silencieux (mesuré : retirer `node_requis` de deux tests laissait la suite
verte). Les harnais appellent `oracle_node.porte()` eux-mêmes ; la fixture
ci-dessous n'est qu'un confort — elle fait décider la porte au SETUP, ce qui
donne un skip propre au lieu d'un skip au milieu d'un test.
"""
from __future__ import annotations

import pathlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import oracle_node  # noqa: E402


@pytest.fixture
def node_requis():
    """Porte des oracles de comportement — cf. `oracle_node.porte`."""
    return oracle_node.porte()


_SITE = Path(__file__).resolve().parents[2]
if str(_SITE) not in sys.path:
    sys.path.insert(0, str(_SITE))  # `from tools.cockpit import …` dans les tests
