#!/usr/bin/env python3
"""build_cv_templates.py — génère assets/js/cv-templates.js depuis cv/templates/*.json.

Huitième builder du même patron que les sept existants. Le bundle ne porte que de la
DONNÉE : la machinerie (`buildCss`) est du vrai JS écrit à la main dans
assets/js/cv-render.js, aux côtés de son jumeau `renderHtml`. Mettre le moteur ici
reviendrait à loger du JS dans un littéral Python — ce que ce dépôt a déjà corrigé une
fois en sortant les extraits de code de la donnée (Σ-CODE-LIVES-IN-FILES-NOT-JSON).

Les templates sont INLINÉS : le site est statique et doit rendre un CV hors ligne,
donc aucun `fetch`. Le bundle livre `style` ENTIER, jamais un CSS pré-rendu — sinon
`buildCss` côté JS ne serait plus exercé en production et le harnais de parité ne
garderait plus rien de réel.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "js" / "cv-templates.js"

sys.path.insert(0, str(ROOT / "tools" / "cv"))


class BuildError(Exception):
    pass


_ENTETE = """\
/* GÉNÉRÉ par tools/build_cv_templates.py — NE PAS ÉDITER À LA MAIN.
 * Banque de templates CV, inlinée : le site est statique et doit rendre un CV hors
 * ligne, donc aucune requête réseau. Rien que de la donnée — la machinerie buildCss
 * vit dans assets/js/cv-render.js, miroir de tools/cv/cv_templates.py.
 * Régénérer : python tools/build_cv_templates.py */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CVTemplates = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

"""

_PIED = """
  function get(id) {
    var t = ALL.filter(function (x) { return x.id === id; })[0];
    if (!t) throw new Error("template inconnu : " + id);
    return t;
  }

  return { DEFAUT: DEFAUT, all: ALL, get: get };
});
"""


def build_cv_templates(write: bool = True) -> str:
    import cv_templates

    templates = cv_templates.lister()
    if not templates:
        raise BuildError(f"aucun template dans {cv_templates.TEMPLATES}")

    corps = (
        f"  var DEFAUT = {json.dumps(cv_templates.DEFAUT)};\n"
        f"  var ALL = {json.dumps(templates, ensure_ascii=False, indent=2, sort_keys=True)};\n"
    )
    out = _ENTETE + corps + _PIED

    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    import cv_templates

    build_cv_templates()
    print(f"[build_cv_templates] OK - {len(cv_templates.lister())} templates -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
