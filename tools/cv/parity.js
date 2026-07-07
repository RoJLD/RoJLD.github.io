/* Parité JS↔Python : cv-render.js doit produire le MÊME HTML que cv_render.py. */
const fs = require("fs");
const { renderHtml } = require("../../assets/js/cv-render.js");

const cases = JSON.parse(fs.readFileSync("parity_cases.json", "utf-8"));
let ok = 0, fail = 0;
for (const c of cases) {
  const htmlJs = renderHtml(c.cv);
  if (htmlJs === c.html_py) {
    ok++;
    console.log(`  PASS ${c.name}`);
  } else {
    fail++;
    console.log(`  FAIL ${c.name}`);
    // premier point de divergence
    const a = c.html_py, b = htmlJs;
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    console.log(`    divergence @${i}: py=${JSON.stringify(a.slice(i, i + 40))} js=${JSON.stringify(b.slice(i, i + 40))}`);
  }
}
console.log(`\n${ok} PASS / ${fail} FAIL sur ${cases.length}`);
process.exit(fail === 0 ? 0 : 1);
