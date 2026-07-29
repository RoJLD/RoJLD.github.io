"""La porte des oracles de comportement : node est-il là, et a-t-on le droit de s'en passer ?

Pourquoi ce module existe, mesuré et non supposé. Trente-cinq gardes de ce dépôt
ne mesurent quelque chose qu'en exécutant du JS dans node : elles lancent le
script réel d'une page servie et regardent ce qu'il FAIT (le thème mémorisé
atteint-il `data-theme` ? les axes du radar viennent-ils de `profile.json` ?).

Mesuré sur une machine sans node, avec `radar.html` muté pour lire le corpus puis
le JETER — le défaut exact que H13 corrigeait :

    avec node : 505 passed, 1 failed, 2 skipped
    sans node : 472 passed, 37 skipped        <-  VERT

Le défaut est intact ; la garde s'est évaporée avec son interpréteur. Un `skip`
est une garde qui a le droit de ne rien dire : acceptable sur le poste d'un
développeur sans node, inacceptable dans une chaîne d'intégration, où « vert »
veut dire « livrable ». D'où `ELYSIUM_REQUIRE_NODE=1`, qui transforme chaque skip
en ÉCHEC (mesuré, suite entière, machine sans node : `498 passed, 2 skipped,
36 errors` — les gardes disparues se voient).

**La porte vit ici, et pas dans la fixture**, parce qu'une fixture ne garde que
les tests qui pensent à la demander. Mesuré : retirer `node_requis` des deux
tests de `test_lang_switch_behaviour.py` laissait la suite à 541 passed. Les
harnais appellent donc `porte()` eux-mêmes, juste avant de lancer node : le seul
chemin qui mène à l'interpréteur passe par elle, et on ne peut plus l'oublier.
"""
from __future__ import annotations

import os
import shutil

import pytest


def lit_le_drapeau(env=None) -> bool:
    """`ELYSIUM_REQUIRE_NODE=1` -> interdiction de sauter. Rien d'autre ne l'active.

    Une lecture laxiste (« la variable est définie ») ferait échouer toute suite
    posant un `ELYSIUM_REQUIRE_NODE=0` explicite pour dire l'inverse.
    """
    return (os.environ if env is None else env).get("ELYSIUM_REQUIRE_NODE") == "1"


NODE = shutil.which("node")
EXIGE_NODE = lit_le_drapeau()


def porte():
    """Décision de la porte.

    * node présent            -> rend son chemin, l'oracle s'exécute ;
    * node absent             -> `skip` (poste sans interpréteur) ;
    * node absent + REQUIRE=1 -> `fail`, jamais un skip silencieux.
    """
    if NODE:
        return NODE
    if EXIGE_NODE:
        pytest.fail(
            "node est introuvable alors que ELYSIUM_REQUIRE_NODE=1 : les gardes "
            "de comportement (thème appliqué, axes du radar, bascule de langue) "
            "ne peuvent pas s'exécuter. Un skip ici rendrait un vert qui ne "
            "garde rien.")
    pytest.skip("node absent — oracle de comportement non exécutable")
