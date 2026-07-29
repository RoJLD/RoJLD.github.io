"""Exécute le boot de `/radar.html` dans node : les axes viennent-ils du corpus ?

Pourquoi ce harnais existe, mesuré et non supposé. La tâche H13 demandait que
`radar.html` cesse de porter ses compétences en dur et lise `profile.json`. La
garde posée était :

    assert 'fetch("profile.json")' in txt

Une revue par mutation a gardé l'appel et JETÉ son résultat — c'est-à-dire
exactement le défaut que H13 corrigeait :

    DEFAULT_SKILLS = skillsFromProfile(await res.json());
 -> await res.json();
    DEFAULT_SKILLS = [{id:"js", name:"JavaScript", yourLevel:3, marketLevel:3}];

La suite entière est restée à **506 passed**. La chaîne cherchée était toujours
là ; la page affichait un profil inventé. C'est le même mécanisme que
`getItem('theme')` pour le thème (cf. `theme_boot_harness`) : un test de
présence répond à « le code est-il écrit ? », jamais à « la page montre-t-elle
le corpus ? ».

Le harnais sert le VRAI `profile.json` à un `fetch` stubé, exécute le script réel
de la page, et rend les axes que le radar a effectivement construits. Il attrape
donc aussi bien la copie en dur que la lecture d'une autre source.

`renderSliders`/`drawRadar` sont neutralisés : ce qui est mesuré ici est le
chemin de DONNÉES (le corpus atteint-il les axes ?), pas le dessin. Les laisser
tourner ferait dépendre la garde de la fidélité du stub canvas — un faux rouge
possible, sans contrepartie.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_node  # noqa: E402
from theme_boot_harness import _STUB, extract_script

# Le `fetch` inerte du stub partagé, remplacé ici par un `fetch` qui SERT le
# corpus. Écrit en clair et vérifié : si le stub change de forme, ce harnais doit
# crier, pas servir silencieusement un profil vide (ce qui rendrait la garde
# rouge pour une raison étrangère à ce qu'elle défend).
_FETCH_INERTE = """const fetch = () => Promise.resolve(
  {ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve('')});"""


class StubIncompatible(AssertionError):
    """Le stub DOM partagé a changé : le harnais ne peut plus servir le corpus."""


def _stub_servant(profil: dict, url_servie: str) -> str:
    if _FETCH_INERTE not in _STUB:
        raise StubIncompatible(
            "`fetch` n'a plus la forme attendue dans theme_boot_harness._STUB")
    # L'URL est vérifiée : lire une AUTRE source doit échouer, pas être servie.
    fetch = (
        "const __PROFIL = " + json.dumps(profil) + ";\n"
        "const __URL_SERVIE = " + json.dumps(url_servie) + ";\n"
        "const fetch = (u) => Promise.resolve(String(u) === __URL_SERVIE\n"
        "  ? {ok: true, json: () => Promise.resolve(__PROFIL),\n"
        "     text: () => Promise.resolve(JSON.stringify(__PROFIL))}\n"
        "  : {ok: false, status: 404,\n"
        "     json: () => Promise.reject(new Error('404 ' + u)),\n"
        "     text: () => Promise.resolve('')});")
    return (_STUB.replace(_FETCH_INERTE, fetch)
                 .replace("__INITIAL__", '"dark"')
                 .replace("__PAYLOADS__", "{}"))


_PILOTE = r"""
import vm from 'node:vm';
const bac = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, queueMicrotask,
  URLSearchParams, TextEncoder, TextDecoder, __STORE_INITIAL__: {}, __resultat__: null,
};
vm.createContext(bac);
vm.runInContext(SOURCE, bac, {filename: 'radar-script.js'});
"""


def axes_du_radar(page_html: str, profil: dict, *,
                  url_servie: str = "profile.json") -> list[str]:
    """Étiquettes des axes construits par le boot réel de la page.

    Liste vide = le radar n'a rien construit (source injoignable, boot en échec) :
    c'est une observation, pas une erreur — le test décide de son sens.
    """
    oracle_node.porte()   # le seul chemin vers node passe par la porte
    corps = extract_script(page_html, "async function init")
    source = (_stub_servant(profil, url_servie) + "\n" + corps + "\n"
              ";renderSliders = function () {};\n"
              ";drawRadar = function () {};\n"
              ";init().then(() => {\n"
              "  console.log('__RADAR__' + JSON.stringify(skills.map(s => s.label)));\n"
              "});\n")
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "radar.mjs"
        js.write_text(_PILOTE.replace("SOURCE", json.dumps(source)), encoding="utf-8")
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode:
        raise AssertionError(f"node a échoué :\n{proc.stderr}")
    marque = [l for l in proc.stdout.splitlines() if l.startswith("__RADAR__")]
    if not marque:
        raise AssertionError(
            f"le harnais n'a rien rendu — le boot du radar n'a pas abouti :\n"
            f"{proc.stdout}\n{proc.stderr}")
    return json.loads(marque[-1][len("__RADAR__"):])
