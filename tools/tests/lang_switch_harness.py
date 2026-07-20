"""Exécute la bascule de langue des pages générées dans node.

Pourquoi ce harnais existe : les bascules FR/EN sont du JavaScript embarqué dans
du HTML généré, et pytest ne sait lire ce JS que comme du texte. Un test textuel
répond à « cette chaîne est-elle là ? », jamais à « le lien pointe-t-il vers la
bonne langue ? ». Il attrape la suppression du code, jamais son inversion.

Mesuré le 2026-07-20 : intervertir les deux branches de la bascule laissait la
suite à 309 verts sur les trois pages (accueil, explorer, highlights).

Le harnais extrait le <script> de la page générée, l'exécute dans node contre un
DOM stubé, puis rend l'état final des liens — un oracle de comportement, pas de
présence.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

# Le bloc de script porteur de la bascule est reconnu par la fonction qu'il
# définit ; les pages en contiennent plusieurs (analytics, thème, filtres).
_SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


def extract_script(page: str, needle: str) -> str:
    """Rend le contenu du <script> qui définit `needle`.

    Fail-loud : une page dont on n'extrait rien signalerait « aucune bascule à
    tester » en restant verte, exactement le silence qu'on cherche à supprimer.
    """
    for body in _SCRIPT.findall(page):
        if needle in body:
            return body
    raise AssertionError(f"aucun <script> ne definit {needle!r} — page restructuree ?")


def run_lang_switch(page: str, *, entry: str, lang: str, cards: list[dict]) -> list[dict]:
    """Applique `entry(lang)` au DOM stubé et rend l'état final des cartes.

    `cards` décrit les liens présents avant bascule, p.ex. :
        [{"dataset": {"hrefFr": "/a.html", "hrefEn": "/a.en.html"},
          "attrs": {"href": "/a.html"}}]

    Rend la même liste, `attrs` mis à jour par le JS réel.
    """
    program = _DOM_STUB + "\n" + extract_script(page, entry) + f"""
;(function () {{
  {entry}({json.dumps(lang)});
  console.log(JSON.stringify(__cards.map(c => ({{dataset: c.dataset, attrs: c.attrs}}))));
}})();
"""
    with tempfile.TemporaryDirectory() as tmp:
        js = Path(tmp) / "run.mjs"
        js.write_text(
            program.replace("__CARDS_JSON__", json.dumps(cards)), encoding="utf-8"
        )
        proc = subprocess.run(
            ["node", str(js)], capture_output=True, text=True, timeout=30
        )
    if proc.returncode:
        raise AssertionError(f"node a echoue :\n{proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# Le stub applique deux régimes différents, et l'asymétrie est délibérée.
#
# `querySelectorAll` est STRICT : un sélecteur non déclaré lève. C'est là que
# vit le mode de panne qu'on traque — une liste vide ne lève pas, ne modifie
# rien et laisse le test vert en n'ayant rien exercé. Déclarer `.f-btn` comme
# vide est une décision consignée ; y répondre `[]` par défaut serait le même
# silence, non consigné.
#
# `getElementById` est INERTE et permissif : un bouton manquant ne peut pas
# faire passer une bascule fausse pour juste, donc la rigidité n'y achète rien
# et coûterait une mise à jour du stub à chaque élément ajouté.
# ---------------------------------------------------------------------------
_DOM_STUB = """
function __el(init) {
  return {
    dataset: {...(init && init.dataset)},
    attrs: {...(init && init.attrs)},
    textContent: '',
    hidden: false,
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; },
    querySelectorAll: __qsa,
    addEventListener() {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
  };
}

const __cards = __CARDS_JSON__.map(__el);

// Les éléments traduits : non vides, sinon la boucle de traduction tournerait
// à vide et l'oracle perdrait la moitié de ce qu'il prétend couvrir.
const __texts = [__el({dataset: {fr: 'Explorer', en: 'Explore'}})];

// Les cartes portent les deux rôles, comme dans la vraie page : ce sont les
// mêmes noeuds .e-card qui portent data-href-fr/en.
const __SELECTORS = {
  '[data-href-fr][data-href-en]': () => __cards,
  '[data-fr][data-en]':           () => __texts,
  '.e-card':                      () => __cards,
  '.f-btn':                       () => [],   // filtres : hors bascule
  '.h-chip':                      () => [],   // lentilles : hors bascule
  '.h-sec':                       () => [],   // sections : hors bascule
};

function __qsa(sel) {
  if (!Object.prototype.hasOwnProperty.call(__SELECTORS, sel)) {
    throw new Error(
      'selecteur non declare dans le stub : ' + sel +
      ' — la bascule a change, mettre a jour __SELECTORS plutot que de rendre []'
    );
  }
  return __SELECTORS[sel]();
}

const __root = __el({attrs: {'data-lang': 'fr'}});

const document = {
  querySelectorAll: __qsa,
  getElementById: () => __el(),
  documentElement: __root,
  addEventListener() {},
};
const localStorage = {
  _v: {lang: 'fr'},
  getItem(k) { return k in this._v ? this._v[k] : null; },
  setItem(k, v) { this._v[k] = v; },
};
const window = {matchMedia: () => ({matches: false})};
// highlights lit la lentille active dans la query string au chargement.
const location = {search: '', hash: '', pathname: '/'};
"""
