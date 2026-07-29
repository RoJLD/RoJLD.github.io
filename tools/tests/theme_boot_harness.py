"""Exécute le thème des pages publiées dans node : restauration et bascule.

Pourquoi ce harnais existe, mesuré et non supposé. Le fichier `test_theme_clair.py`
revendiquait la propriété « le thème est restauré au chargement » avec cette
assertion :

    assert "getItem('theme')" in html

Une revue par mutation a débranché la restauration de `/life-architect/` en
laissant la lecture en place — c'est-à-dire exactement le défaut que la
propriété prétend interdire :

    if(t)document.documentElement.setAttribute('data-theme',t)   ->   if(t){}

La suite est restée à 406 passed. La chaîne cherchée était toujours là ; la
valeur lue était jetée. Un test de présence répond à « le code est-il écrit ? »,
jamais à « la page s'affiche-t-elle dans le thème choisi ? ».

La page `/life-architect/` est le cas le plus coûteux du dépôt : aucun builder
ne la produit, donc `python tools/build_site.py` ne répare rien — une régression
y survit jusqu'à ce qu'un humain ouvre la page dans le bon thème.

Le harnais extrait le `<script>` réel de la page servie, l'exécute dans node
contre un DOM stubé, et rend l'état FINAL de `data-theme` sur la racine. C'est
un oracle de comportement : il attrape la suppression, mais aussi l'inversion et
la valeur en dur, qu'aucun test textuel ne distingue.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_node  # noqa: E402

# `src=` exclu : un script externe n'a pas de corps à exécuter ici.
_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)

# Les données embarquées (`<script type="application/json" id="…">`) ne sont pas
# du code : elles alimentent `getElementById(id).textContent`. `/graph/` fait
# `JSON.parse(document.getElementById('graph-data').textContent)` au chargement ;
# un stub qui rendrait `''` ferait échouer le boot pour une raison étrangère au
# thème, et la garde deviendrait un faux rouge permanent.
_JSON_PAYLOAD = re.compile(
    r'<script[^>]*\bid="([^"]+)"[^>]*\btype="application/json"[^>]*>(.*?)</script>',
    re.DOTALL)


class ScriptIntrouvable(AssertionError):
    """Aucun (ou plusieurs) script ne porte le motif — page restructurée."""


def extract_script(page: str, needle: str) -> str:
    """Corps du `<script>` qui contient `needle`.

    Fail-loud dans les deux sens : zéro script signalerait « rien à tester » en
    restant vert, et deux scripts rendraient le choix arbitraire donc l'oracle
    incertain. C'est précisément le silence que ce harnais existe pour supprimer.
    """
    bodies = [b for b in _SCRIPT.findall(page) if needle in b]
    if len(bodies) != 1:
        raise ScriptIntrouvable(
            f"{len(bodies)} script(s) portent {needle!r} — il en faut exactement un")
    return bodies[0]


def _payloads(page: str) -> dict[str, str]:
    return {i: t for i, t in _JSON_PAYLOAD.findall(page)}


def run_scenarios(page: str, scenarios: list[dict]) -> list[dict]:
    """Joue plusieurs scénarios sur la même page, dans UN seul processus node.

    Chaque scénario : `{needle, stored, initial, call}`. `stored` accepte la
    forme `{"__depuis__": i}` — « repartir du `localStorage` laissé par le
    scénario i » : c'est ainsi qu'on relie une bascule à un rechargement sans
    postuler la clé utilisée.

    Chaque scénario tourne dans un contexte `vm` NEUF : les scripts de page
    déclarent des `const` au niveau racine, les rejouer dans le même contexte
    lèverait, et les faire partager un état ferait dépendre chaque mesure de la
    précédente.

    Rend, par scénario, `{"theme": <data-theme final>, "store": <localStorage
    final>, "store_initial": <localStorage AVANT exécution>}`.

    `store_initial` est une copie profonde prise avant de lancer le script : elle
    permet à un test de vérifier de quoi il est réellement parti, plutôt que de
    le postuler depuis la description du scénario. C'est ce qui rend la chaîne
    BASCULE -> RECHARGE prouvable (mesuré : remplacer `{"__depuis__": BASCULE}`
    par un `{"theme": "light"}` écrit à la main laissait la suite verte, et le
    test du rechargement devenait une redite du test de restauration).

    Aucun `try/catch` n'enveloppe les scripts : une erreur d'exécution doit
    faire échouer le test, jamais se transformer en « thème non restauré ».
    """
    oracle_node.porte()   # le seul chemin vers node passe par la porte
    payloads = json.dumps(_payloads(page))
    prepares = [{
        "source": (_STUB.replace("__INITIAL__", json.dumps(sc.get("initial", "dark")))
                        .replace("__PAYLOADS__", payloads)
                   + "\n" + extract_script(page, sc.get("needle", "getItem('theme')"))
                   + (f"\n;{sc['call']};" if sc.get("call") else "")
                   + "\n;__rendre();\n"),
        "stored": sc.get("stored") or {},
    } for sc in scenarios]

    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "run.mjs"
        js.write_text(_PILOTE.replace("__SCENARIOS__", json.dumps(prepares)),
                      encoding="utf-8")
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120)
    if proc.returncode:
        raise AssertionError(f"node a échoué :\n{proc.stderr}")
    marque = [l for l in proc.stdout.splitlines() if l.startswith("__THEME__")]
    if not marque:
        raise AssertionError(f"le harnais n'a rien rendu :\n{proc.stdout}\n{proc.stderr}")
    return json.loads(marque[-1][len("__THEME__"):])


def run_theme(page: str, *, needle: str = "getItem('theme')",
              stored: dict | None = None, initial: str = "dark",
              call: str = "") -> dict:
    """Un seul scénario — voir `run_scenarios`."""
    return run_scenarios(page, [{"needle": needle, "stored": stored,
                                 "initial": initial, "call": call}])[0]


# Le pilote : il crée un contexte neuf par scénario et n'y expose que ce qu'un
# navigateur fournirait de toute façon (`console`, les minuteries,
# `URLSearchParams` — que `/highlights/` lit au chargement). Tout le reste du
# DOM vient du stub, donc reste sous le contrôle explicite de ce fichier.
_PILOTE = r"""
import vm from 'node:vm';

const SCENARIOS = __SCENARIOS__;
const resultats = [];

for (const sc of SCENARIOS) {
  const stored = (sc.stored && sc.stored.__depuis__ !== undefined)
    ? JSON.parse(JSON.stringify(resultats[sc.stored.__depuis__].store))
    : sc.stored;
  // Copie prise AVANT exécution : `localStorage._v` est cet objet même, le
  // script de la page va le muter. Sans cette copie, un test ne peut pas
  // vérifier de quoi il est parti.
  const store_initial = JSON.parse(JSON.stringify(stored));
  const bac = {
    console, setTimeout, clearTimeout, setInterval, clearInterval,
    queueMicrotask, URLSearchParams, TextEncoder, TextDecoder,
    __STORE_INITIAL__: stored,
    __resultat__: null,
  };
  vm.createContext(bac);
  vm.runInContext(sc.source, bac, {filename: 'page-script.js'});
  if (bac.__resultat__ === null)
    throw new Error('le script de la page n\'a pas atteint __rendre()');
  bac.__resultat__.store_initial = store_initial;
  resultats.push(bac.__resultat__);
}
console.log('__THEME__' + JSON.stringify(resultats));
"""


# ---------------------------------------------------------------------------
# Le stub DOM. Deux régimes délibérés :
#
#  * `documentElement` est FIDÈLE : c'est l'objet mesuré, ses attributs sont
#    réellement stockés et relus. Tout le test tient à lui.
#  * le reste est INERTE et permissif (boutons, canvas, fetch) : ces éléments ne
#    peuvent pas faire passer un thème faux pour juste, et les exiger obligerait
#    à mettre le stub à jour à chaque bouton ajouté — un coût sans contrepartie.
#
# `getElementById` rend cependant le VRAI contenu des blocs JSON de la page :
# sans cela `/graph/` lèverait au chargement.
# ---------------------------------------------------------------------------
_STUB = r"""
const __PAYLOADS = __PAYLOADS__;

function __ctx() {
  return new Proxy({}, {
    get: (t, k) => {
      if (k === 'canvas') return __el('CANVAS');
      if (k === 'measureText') return () => ({width: 0});
      if (k === 'createLinearGradient' || k === 'createRadialGradient')
        return () => ({addColorStop() {}});
      if (k === 'getImageData') return () => ({data: []});
      return () => {};
    },
    set: () => true,
  });
}

function __el(tag) {
  return {
    tagName: tag || 'DIV', attrs: {}, dataset: {}, textContent: '', innerHTML: '',
    value: '', hidden: false, checked: false, children: [],
    style: {setProperty() {}, removeProperty() {}},
    classList: {add() {}, remove() {}, toggle() {}, contains: () => false},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    removeAttribute(k) { delete this.attrs[k]; },
    hasAttribute(k) { return k in this.attrs; },
    addEventListener() {}, removeEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    append() {}, remove() {}, insertAdjacentHTML() {},
    querySelector: () => __el(), querySelectorAll: () => [], closest: () => null,
    focus() {}, blur() {}, click() {}, scrollIntoView() {},
    getBoundingClientRect: () => ({top: 0, left: 0, width: 0, height: 0, bottom: 0, right: 0}),
    getContext: () => __ctx(),
  };
}

const __root = __el('HTML');
__root.setAttribute('data-theme', __INITIAL__);

const document = {
  documentElement: __root, body: __el('BODY'), head: __el('HEAD'),
  getElementById: (id) => {
    const e = __el();
    if (Object.prototype.hasOwnProperty.call(__PAYLOADS, id)) e.textContent = __PAYLOADS[id];
    return e;
  },
  querySelector: () => __el(), querySelectorAll: () => [],
  createElement: (t) => __el(t), createElementNS: (ns, t) => __el(t),
  createTextNode: () => __el('#text'),
  addEventListener() {}, removeEventListener() {}, readyState: 'complete', title: '',
};

const localStorage = {
  _v: __STORE_INITIAL__,
  getItem(k) { return Object.prototype.hasOwnProperty.call(this._v, k) ? this._v[k] : null; },
  setItem(k, v) { this._v[k] = String(v); },
  removeItem(k) { delete this._v[k]; },
};

const location = {search: '', hash: '', pathname: '/', href: 'http://x/', origin: 'http://x'};
const navigator = {language: 'fr', userAgent: 'node', clipboard: {writeText: () => Promise.resolve()}};
const window = {
  matchMedia: () => ({matches: false, addEventListener() {}, addListener() {}}),
  addEventListener() {}, removeEventListener() {}, location, localStorage, navigator, document,
  innerWidth: 1280, innerHeight: 800, devicePixelRatio: 1,
  scrollTo() {}, requestAnimationFrame: () => 0,
  getComputedStyle: () => ({getPropertyValue: () => ''}), setTimeout, clearTimeout,
};
const requestAnimationFrame = () => 0;
const getComputedStyle = () => ({getPropertyValue: () => ''});
const fetch = () => Promise.resolve(
  {ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve('')});
const IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };
const ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
const alert = () => {};

// Rend l'état observé au pilote. Appelé APRÈS le script de la page.
function __rendre() {
  __resultat__ = {theme: __root.getAttribute('data-theme'), store: localStorage._v};
}
"""
