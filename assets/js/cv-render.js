/* Σ-CV-ATELIER sous-projet A/B — miroir JS de cv_render.py::render_html.
 * DOIT produire un HTML identique à la version Python pour le même structured_cv
 * (garde-fou de parité testé via node). Utilisable en navigateur (window.CVRender)
 * ET en node (module.exports). CSS inline identique à cv_render.py (contrainte
 * GitHub Pages : aucune requête externe). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CVRender = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var CV_CSS = "" +
    "@page { size: A4; margin: 18mm 16mm; }\n" +
    "* { box-sizing: border-box; }\n" +
    "body { font-family: -apple-system, \"Segoe UI\", Roboto, sans-serif; color: #1a1a2e;\n" +
    "       font-size: 10.5pt; line-height: 1.45; margin: 0; }\n" +
    ".cv-header { border-bottom: 2px solid #4361ee; padding-bottom: 8px; margin-bottom: 14px; }\n" +
    ".cv-name { font-size: 20pt; font-weight: 700; margin: 0; }\n" +
    ".cv-title { font-size: 11pt; color: #4361ee; margin: 2px 0 0; }\n" +
    ".cv-contact { font-size: 9pt; color: #555; margin-top: 4px; }\n" +
    ".cv-section { margin-bottom: 12px; page-break-inside: avoid; }\n" +
    ".cv-exp-head { display: flex; justify-content: space-between; font-weight: 600; }\n" +
    ".cv-exp-company { color: #16213e; }\n" +
    ".cv-exp-dates { color: #777; font-size: 9pt; font-weight: 400; white-space: nowrap; }\n" +
    ".cv-exp-title { font-style: italic; color: #444; font-size: 9.5pt; margin-bottom: 3px; }\n" +
    "ul.cv-bullets { margin: 3px 0 0; padding-left: 16px; }\n" +
    "ul.cv-bullets li { margin-bottom: 2px; }\n" +
    ".cv-skills { margin-top: 10px; font-size: 9.5pt; }\n" +
    ".cv-skills strong { color: #4361ee; }\n" +
    ".cv-footer { margin-top: 16px; font-size: 8pt; color: #999; text-align: right; }\n";

  var LABELS = {
    fr: { skills: "Compétences", updated: "Mis à jour" },
    en: { skills: "Skills", updated: "Updated" },
  };

  // Miroir de html.escape(s, quote=True) : & < > " '  →  &amp; &lt; &gt; &quot; &#x27;
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  function renderHtml(cv) {
    cv = cv || {};
    var lang = cv.lang || "fr";
    var lab = LABELS[lang] || LABELS.fr;
    var idy = cv.identity || {};
    var p = [];
    p.push('<!doctype html><html lang="' + esc(lang) + '"><head><meta charset="utf-8">');
    p.push("<style>" + CV_CSS + "</style></head><body>");

    p.push('<header class="cv-header">');
    p.push('<h1 class="cv-name">' + esc(idy.name || "") + "</h1>");
    if (idy.title) p.push('<p class="cv-title">' + esc(idy.title) + "</p>");
    if (idy.email) p.push('<p class="cv-contact">' + esc(idy.email) + "</p>");
    p.push("</header>");

    (cv.sections || []).forEach(function (sec) {
      p.push('<section class="cv-section">');
      p.push('<div class="cv-exp-head">');
      p.push('<span class="cv-exp-company">' + esc(sec.company || "") + "</span>");
      p.push('<span class="cv-exp-dates">' + esc(sec.dates || "") + "</span>");
      p.push("</div>");
      if (sec.title) p.push('<div class="cv-exp-title">' + esc(sec.title) + "</div>");
      var bullets = sec.bullets || [];
      if (bullets.length) {
        p.push('<ul class="cv-bullets">');
        bullets.forEach(function (b) { p.push("<li>" + esc(b) + "</li>"); });
        p.push("</ul>");
      }
      p.push("</section>");
    });

    var skills = cv.skills_top || [];
    if (skills.length) {
      p.push('<p class="cv-skills"><strong>' + esc(lab.skills) + ":</strong> " +
             esc(skills.map(function (s) { return String(s); }).join(" · ")) + "</p>");
    }

    var updated = (cv.footer || {}).updated || "";
    if (updated) p.push('<p class="cv-footer">' + esc(lab.updated) + " " + esc(updated) + "</p>");

    p.push("</body></html>");
    return p.join("");
  }

  return { renderHtml: renderHtml, CV_CSS: CV_CSS };
});
