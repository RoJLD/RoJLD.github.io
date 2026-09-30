"""Exécute le JS de statut de sauvegarde (/edit, /cms) dans node : `stages.prefab`
s'affiche-t-il vraiment, ou seulement dans `res.stages` avant d'être jeté ?

Pourquoi ce harnais existe (finding I1, revue finale opus du 2026-09-29) : `_EDIT`
et `_CMS` (tools/cockpit/pages/cv.py) bâtissent leur barre de statut depuis
`res.stages` (history, review, graph, rebuild) sans jamais lire `stages.prefab` —
si le gate daté de `build_cv_bank` refuse ou si Chromium échoue à mi-chemin,
Robin lisait un « Enregistré ✓ — … rebuild ok » vert pendant que les 8 PDF
publics restaient périmés ou mélangés. Un test textuel (« la chaîne existe dans
la page ») ne distingue pas « le statut est calculé » de « le statut est calculé
puis jeté » — exactement le défaut mesuré ici. Ce harnais exécute le VRAI script
de la page contre un `fetch('/save', …)` stubé et lit l'état FINAL de `#status` /
`#errs`, comme `theme_boot_harness` pour le thème ou `radar_boot_harness` pour
les axes du radar.
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

# `src=` exclu : un script externe (cms-model.js) n'a pas de corps à exécuter ici —
# son contenu réel est injecté via `prelude`, comme le ferait le navigateur.
_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)


class ScriptIntrouvable(AssertionError):
    """Aucun (ou plusieurs) script ne porte le motif — page restructurée."""


def extract_script(page: str, needle: str) -> str:
    """Corps du `<script>` qui contient `needle`.

    Fail-loud dans les deux sens : zéro script signalerait « rien à tester » en
    restant vert, et deux scripts rendraient le choix arbitraire.
    """
    bodies = [b for b in _SCRIPT.findall(page) if needle in b]
    if len(bodies) != 1:
        raise ScriptIntrouvable(
            f"{len(bodies)} script(s) portent {needle!r} — il en faut exactement un")
    return bodies[0]


def run_save_status(page: str, *, needle: str, trigger: str, report: dict,
                     prelude: str = "") -> dict:
    """Exécute le script réel de `page` contre un `fetch` stubé qui rend
    toujours `report`, déclenche `trigger` (l'expression JS qui lance la
    sauvegarde), laisse la chaîne de promesses se dérouler, et rend l'état
    final de `#status` / `#errs`.

    `prelude` : JS additionnel injecté APRÈS le stub et AVANT le script
    extrait — le contenu réel de `cms-model.js`, comme le ferait le
    `<script src=...>` qui précède l'inline sur la page servie.
    """
    oracle_node.porte()   # le seul chemin vers node passe par la porte
    script = extract_script(page, needle)
    programme = (_STUB.replace("__REPORT__", json.dumps(report))
                 + "\n" + prelude + "\n" + script + f"""
;(function () {{
  {trigger};
  // La chaîne réelle est `fetch(...).then(r => r.json()).then(res => {{...}})`
  // (et parfois `.catch().then()` derrière) : quelques ticks de microtâche
  // suffisent largement, on en pose beaucoup pour ne jamais lire trop tôt.
  var __t = Promise.resolve();
  for (var __i = 0; __i < 60; __i++) {{ __t = __t.then(function () {{}}); }}
  __t.then(function () {{
    console.log('__STATUT__' + JSON.stringify({{
      status_text: document.getElementById('status').textContent,
      status_class: document.getElementById('status').className,
      errs_text: document.getElementById('errs').textContent,
    }}));
  }});
}})();
""")
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "run.mjs"
        js.write_text(programme, encoding="utf-8")
        proc = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=30)
    if proc.returncode:
        raise AssertionError(f"node a échoué :\n{proc.stderr}")
    marque = [l for l in proc.stdout.splitlines() if l.startswith("__STATUT__")]
    if not marque:
        raise AssertionError(f"le harnais n'a rien rendu :\n{proc.stdout}\n{proc.stderr}")
    return json.loads(marque[-1][len("__STATUT__"):])


# ---------------------------------------------------------------------------
# Stub minimal. Deux régimes délibérés :
#
#  * `getElementById` est MÉMOÏSÉ (même objet à chaque appel pour le même id) —
#    condition nécessaire pour que le gestionnaire posé par le script de la
#    page (`$("save").onclick = function () {...}` côté CMS) reste atteignable
#    depuis notre `trigger`, qui relit l'élément après coup.
#  * `fetch` rend systématiquement `__REPORT__`, quel que soit `url`/`opts` :
#    ce harnais ne mesure pas la requête, seulement ce que la page FAIT de la
#    réponse.
# ---------------------------------------------------------------------------
_STUB = r"""
const __ELS = new Map();
function __el(id) {
  if (!__ELS.has(id)) {
    __ELS.set(id, {
      id: id, _text: '', _html: '', className: '', value: '', checked: false,
      disabled: false, onclick: null, oninput: null, onchange: null,
      dataset: {}, style: { setProperty() {}, removeProperty() {} },
      get textContent() { return this._text; },
      set textContent(v) { this._text = String(v); },
      get innerHTML() { return this._html; },
      set innerHTML(v) { this._html = String(v); },
      classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
      querySelectorAll: () => [], querySelector: () => null,
      appendChild(c) { return c; }, append() {}, remove() {},
      addEventListener() {}, removeEventListener() {}, focus() {}, blur() {},
      click() { if (this.onclick) this.onclick(); },
      getAttribute() { return null; }, setAttribute() {}, removeAttribute() {},
    });
  }
  return __ELS.get(id);
}
const document = {
  getElementById: __el,
  querySelector: () => null, querySelectorAll: () => [],
  createElement: (t) => __el(Symbol(t)), createElementNS: (ns, t) => __el(Symbol(t)),
  createTextNode: () => __el(Symbol('text')),
  addEventListener() {}, removeEventListener() {}, readyState: 'complete',
};
const window = { document };
const self = window;
function confirm() { return true; }
function alert() {}
const __REPORT = __REPORT__;
function fetch(url, opts) {
  return Promise.resolve({
    ok: true, status: 200,
    json: () => Promise.resolve(__REPORT),
    text: () => Promise.resolve(JSON.stringify(__REPORT)),
  });
}
"""
