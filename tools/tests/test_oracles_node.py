"""La porte des oracles de comportement est-elle tenue, et personne ne la contourne-t-il ?

Trente-cinq gardes de ce dépôt ne mesurent quelque chose qu'en exécutant du JS
dans node. Mesuré sur une machine sans node, avec `radar.html` muté pour lire le
corpus puis le JETER — le défaut exact que H13 corrigeait :

    avec node : 505 passed, 1 failed, 2 skipped
    sans node : 472 passed, 37 skipped        <- VERT

D'où `ELYSIUM_REQUIRE_NODE=1`, qui transforme chaque skip en échec (cf.
`oracle_node`). Mesuré, suite entière, machine sans node, drapeau posé :
`498 passed, 2 skipped, 36 errors` — les gardes disparues se voient, et les deux
skips restants ne parlent pas de node.

Ce fichier tient DEUX propriétés que rien d'autre ne tient.

1. **La porte décide ce qu'elle annonce.** Piège mesuré en l'écrivant : un
   `pytest.raises(pytest.fail.Exception)` autour d'un appel qui SKIPPE ne rougit
   pas — l'exception `Skipped` traverse le `raises`, et pytest marque le test
   comme sauté. Le test censé prouver que la porte échoue se saute lui-même, en
   silence (mesuré : `540 passed, 3 skipped`, aucun rouge). L'exception est donc
   attrapée puis TYPÉE ici, jamais laissée remonter.

2. **Personne ne la contourne.** Le `skipif` local est le geste naturel de qui
   ajoute un oracle : `test_lang_switch_behaviour.py` portait le sien, et ses
   quatre gardes continuaient de skipper pendant que les trente-deux autres
   échouaient. Corollaire mesuré : faire porter la garde par une fixture ne
   suffit pas non plus — retirer `node_requis` de deux tests laissait la suite à
   541 passed. La porte est donc appelée par les HARNAIS, seul chemin vers node,
   et c'est cela que ce fichier vérifie.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ICI = pathlib.Path(__file__).resolve().parent
ROOT = ICI.parents[1]
sys.path.insert(0, str(ICI))
import oracle_node  # noqa: E402


def _verdict(node, exige):
    """Ce que la porte FAIT, sous forme comparable : le nom de son issue.

    L'exception est attrapée ici et jamais relayée : un `Skipped` qui remonterait
    ferait sauter le test au lieu de le faire rougir — le défaut même qu'on
    mesure.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(oracle_node, "NODE", node)
        mp.setattr(oracle_node, "EXIGE_NODE", exige)
        try:
            return f"passe:{oracle_node.porte()}"
        except pytest.skip.Exception:
            return "saute"
        except pytest.fail.Exception:
            return "echoue"


def test_avec_node_la_porte_laisse_passer():
    """Contre-épreuve des deux suivants : une porte toujours fermée les
    passerait tous les deux sans rien garder."""
    assert _verdict("/usr/bin/node", True) == "passe:/usr/bin/node"
    assert _verdict("/usr/bin/node", False) == "passe:/usr/bin/node"


def test_sans_node_et_sans_drapeau_la_porte_saute():
    """Régime « poste local » : l'absence d'outil ne doit pas fabriquer un rouge."""
    assert _verdict(None, False) == "saute"


def test_sans_node_avec_le_drapeau_la_porte_echoue():
    """LA propriété. Sans elle, une chaîne d'intégration sur un conteneur sans
    node rend un vert franc pendant que 35 gardes ne mesurent plus rien.

    « echoue » et « saute » sont deux issues distinctes, et toute la garde tient
    à leur différence : c'est celle entre « la garde a parlé » et « la garde
    s'est tue ».
    """
    assert _verdict(None, True) == "echoue"


@pytest.mark.parametrize("env, attendu", [
    ({"ELYSIUM_REQUIRE_NODE": "1"}, True),
    ({"ELYSIUM_REQUIRE_NODE": "0"}, False),
    ({"ELYSIUM_REQUIRE_NODE": "true"}, False),
    ({}, False),
])
def test_seul_le_drapeau_explicite_interdit_de_sauter(env, attendu):
    """`ELYSIUM_REQUIRE_NODE=1`, et rien d'autre : une lecture laxiste
    (« variable définie » plutôt que « valeur 1 ») ferait échouer toute suite
    posant un `ELYSIUM_REQUIRE_NODE=0` explicite pour dire l'inverse."""
    assert oracle_node.lit_le_drapeau(env) is attendu


def test_le_drapeau_effectif_est_celui_de_l_environnement_courant():
    """`EXIGE_NODE` doit venir de la lecture, pas d'une valeur figée.

    Rouge exactement là où c'est décisif : sur une chaîne qui pose le drapeau, un
    `EXIGE_NODE = False` en dur diverge immédiatement. Sur un poste sans le
    drapeau, les deux valent False et ce test ne prouve rien — il ne prétend pas
    le contraire. La preuve du câblage complet est empirique : suite entière,
    machine sans node, drapeau posé -> 36 errors, et non 36 skips.
    """
    assert oracle_node.EXIGE_NODE is oracle_node.lit_le_drapeau()


# --- Personne ne contourne la porte ------------------------------------------

_LANCE_NODE = re.compile(r'subprocess\.run\(\s*\[\s*["\']node["\']')
_APPELLE_LA_PORTE = re.compile(r"\bporte\(\)")


def _modules_de_test() -> list[pathlib.Path]:
    return sorted(p for p in ROOT.rglob("test_*.py")
                  if ".git" not in p.parts and "node_modules" not in p.parts)


def _decisions_de_saut(source: str) -> list[str]:
    """Extraits où un module décide LUI-MÊME de sauter à cause de node."""
    trouves = []
    for m in re.finditer(r"skipif\s*\(|pytest\.skip\s*\(", source):
        fenetre = source[m.start():m.start() + 220]
        if re.search(r"\bnode\b", fenetre, re.I):
            trouves.append(" ".join(fenetre.split())[:120])
    return trouves


def test_tout_ce_qui_lance_node_passe_par_la_porte():
    """Le champ est dérivé des SOURCES : qui lance node doit d'abord demander.

    C'est la seule formulation qui résiste à l'oubli. Une garde portée par une
    fixture ne protège que les tests qui l'écrivent dans leur signature ; portée
    par le harnais, elle protège tout ce qui atteint l'interpréteur, y compris le
    prochain oracle que personne n'a encore écrit.
    """
    lanceurs = {p.name: p.read_text(encoding="utf-8", errors="replace")
                for p in ICI.glob("*.py")}
    lanceurs = {n: s for n, s in lanceurs.items() if _LANCE_NODE.search(s)}
    assert lanceurs, "aucun module ne lance node — ce test ne mesure plus rien"
    sans_porte = sorted(n for n, s in lanceurs.items() if not _APPELLE_LA_PORTE.search(s))
    assert not sans_porte, (
        f"modules qui lancent node sans passer par `oracle_node.porte()` : "
        f"{sans_porte} — leurs gardes s'évaporeraient en silence sur une machine "
        "sans node, drapeau ou pas")


def test_aucun_module_ne_decide_seul_de_sauter_quand_node_manque():
    """La détection de node vit à un seul endroit : là où le drapeau est lu."""
    coupables = {p.relative_to(ROOT).as_posix(): d
                 for p in _modules_de_test()
                 if (d := _decisions_de_saut(p.read_text(encoding="utf-8", errors="replace")))}
    assert not coupables, (
        f"modules qui décident seuls de sauter quand node manque : {coupables} — "
        "ils échappent à ELYSIUM_REQUIRE_NODE ; passer par `oracle_node.porte()`")
    assert _decisions_de_saut((ICI / "oracle_node.py").read_text(encoding="utf-8")), (
        "oracle_node.py ne décide plus rien à propos de node — la détection "
        "ci-dessus ne mesure plus rien")
