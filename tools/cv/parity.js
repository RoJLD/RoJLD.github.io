/* Parité JS↔Python (garde-fou anti-divergence des deux miroirs) :
 *  - RENDU    : cv-render.js doit produire le MÊME HTML que cv_render.py
 *  - PIPELINE : cv-select.js doit produire le MÊME ordre d'expériences et le MÊME
 *               structured_cv que cv_select.py, puis le même HTML.
 * Sans le volet PIPELINE, une divergence de PROJECTION (ex: la branche
 * sort_by:"date" du profil `full`) passait totalement sous le radar.
 */
const fs = require("fs");
const path = require("path");
const { renderHtml } = require("../../assets/js/cv-render.js");
const CVSelect = require("../../assets/js/cv-select.js");

const data = JSON.parse(fs.readFileSync(path.join(__dirname, "parity_cases.json"), "utf-8"));
let ok = 0, fail = 0;

function firstDiff(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  return `    divergence @${i}: py=${JSON.stringify(a.slice(i, i + 40))} js=${JSON.stringify(b.slice(i, i + 40))}`;
}

function check(name, expected, actual) {
  if (expected === actual) {
    ok++;
    console.log(`  PASS ${name}`);
  } else {
    fail++;
    console.log(`  FAIL ${name}`);
    console.log(firstDiff(String(expected), String(actual)));
  }
}

/* Sérialisation déterministe (clés triées) : compare des OBJETS sans dépendre de
   l'ordre d'insertion, qui diffère légitimement entre Python et JS. */
function ss(o) {
  if (Array.isArray(o)) return "[" + o.map(ss).join(",") + "]";
  if (o && typeof o === "object") {
    return "{" + Object.keys(o).sort()
      .map((k) => JSON.stringify(k) + ":" + ss(o[k])).join(",") + "}";
  }
  return JSON.stringify(o === undefined ? null : o);
}

for (const c of data.render) {
  check(`render:${c.name}`, c.html_py, renderHtml(c.cv));
}

for (const c of data.pipeline.cases) {
  // un cas peut porter son PROPRE profil (variantes adversariales) ; build_cfg
  // peut être null — c'est le chemin du navigateur (appel sans cfg).
  const prof = c.profile || data.pipeline.profile;
  const exps = CVSelect.selectExperiences(prof, c.sel_cfg);
  check(`order:${c.name}`, ss(c.order_py), ss(exps.map((e) => (e.id === undefined ? null : e.id))));
  const scv = CVSelect.buildStructuredCv(prof, exps, c.lang, c.build_cfg);
  check(`scv:${c.name}`, ss(c.scv_py), ss(scv));
  check(`html:${c.name}`, c.html_py, renderHtml(scv));
}

console.log(`\n${ok} PASS / ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
