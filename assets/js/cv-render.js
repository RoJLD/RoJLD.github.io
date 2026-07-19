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
    "@page { size: A4; margin: 12mm 14mm; }\n" +
    "* { box-sizing: border-box; }\n" +
    "body { font-family: -apple-system, \"Segoe UI\", Roboto, sans-serif; color: #1a1a2e;\n" +
    "       font-size: 9.8pt; line-height: 1.3; margin: 0; }\n" +
    ".cv-header { border-bottom: 2px solid #4361ee; padding-bottom: 5px; margin-bottom: 9px; }\n" +
    ".cv-name { font-size: 17pt; font-weight: 700; margin: 0; }\n" +
    ".cv-title { font-size: 10.5pt; color: #4361ee; margin: 1px 0 0; }\n" +
    ".cv-contact { font-size: 8.5pt; color: #555; margin-top: 3px; }\n" +
    ".cv-section { margin-bottom: 7px; page-break-inside: avoid; }\n" +
    ".cv-exp-head { display: flex; justify-content: space-between; font-weight: 600; }\n" +
    ".cv-exp-company { color: #16213e; }\n" +
    ".cv-exp-dates { color: #777; font-size: 8.5pt; font-weight: 400; white-space: nowrap; }\n" +
    ".cv-exp-title { font-style: italic; color: #444; font-size: 9pt; margin-bottom: 2px; }\n" +
    "ul.cv-bullets { margin: 2px 0 0; padding-left: 15px; }\n" +
    "ul.cv-bullets li { margin-bottom: 1px; }\n" +
    ".cv-skills { margin-top: 4px; font-size: 9pt; }\n" +
    ".cv-skills strong { color: #4361ee; }\n" +
    ".cv-footer { margin-top: 8px; font-size: 8pt; color: #999; text-align: right; }\n" +
    ".cv-h2 { font-size: 10.5pt; color: #4361ee; margin: 0 0 4px; border-bottom: 1px solid #dde; padding-bottom: 2px; }\n" +
    ".cv-edu-head { display: flex; justify-content: space-between; font-weight: 600; }\n" +
    ".cv-edu-school { color: #16213e; }\n" +
    ".cv-edu-meta { font-size: 9pt; color: #444; margin-top: 1px; }\n" +
    ".cv-extra { margin-top: 3px; font-size: 9pt; }\n" +
    ".cv-extra strong { color: #4361ee; }\n";

  var LABELS = {
    fr: { skills: "Compétences", updated: "Mis à jour", education: "Formation",
          languages: "Langues", certifications: "Certifications",
          interests: "Centres d'intérêt" },
    en: { skills: "Skills", updated: "Updated", education: "Education",
          languages: "Languages", certifications: "Certifications",
          interests: "Interests" },
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
    // Ligne de contact : localisation • email • linkedin • github (jamais le tél).
    var contact = [idy.location || "", idy.email || "", idy.linkedin || "", idy.github || ""]
      .filter(function (x) { return x; }).join(" • ");
    if (contact) p.push('<p class="cv-contact">' + esc(contact) + "</p>");
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

    // Formation (miroir Python : après les expériences)
    var education = cv.education || [];
    if (education.length) {
      p.push('<section class="cv-section">');
      p.push('<h2 class="cv-h2">' + esc(lab.education) + "</h2>");
      education.forEach(function (e) {
        p.push('<div class="cv-edu-head">');
        p.push('<span class="cv-edu-school">' + esc(e.school || "") + "</span>");
        p.push('<span class="cv-exp-dates">' + esc(e.period || "") + "</span>");
        p.push("</div>");
        // Miroir Python : `title` recouvre souvent `school` → on l'omet pour ne
        // pas afficher deux fois le nom de l'école dans le PDF public.
        var titleTxt = e.title || "", schoolTxt = e.school || "";
        if (titleTxt && schoolTxt && titleTxt.indexOf(schoolTxt) === 0) titleTxt = "";
        var sub = [titleTxt, e.org || ""].filter(function (x) { return x; }).join(" — ");
        if (sub) p.push('<div class="cv-exp-title">' + esc(sub) + "</div>");
        if (e.degree) p.push('<div class="cv-edu-meta">' + esc(e.degree) + "</div>");
        var courses = e.courses || [];
        if (courses.length) {
          p.push('<div class="cv-edu-meta"><strong>' + esc(e.courses_label || "") + ":</strong> " +
                 esc(courses.map(function (c) { return String(c); }).join(" · ")) + "</div>");
        }
        var cap = e.capstone;
        if (cap) {
          var capTxt = [cap.label || "", cap.summary || ""]
            .filter(function (x) { return x; }).join(" — ");
          if (capTxt) p.push('<div class="cv-edu-meta">' + esc(capTxt) + "</div>");
        }
      });
      p.push("</section>");
    }

    // Compétences : une ligne LIBELLÉE par catégorie (miroir Python), repli sur
    // la liste plate si un structured_cv ancien (sans skills_groups) est rendu.
    var groups = cv.skills_groups;
    if (Array.isArray(groups) && groups.length) {
      groups.forEach(function (g) {
        var items = Array.isArray(g.items) ? g.items : [];
        if (!items.length) return;
        p.push('<p class="cv-skills"><strong>' + esc(g.label || "") + ":</strong> " +
               esc(items.map(function (i) { return String(i); }).join(" · ")) + "</p>");
      });
    } else {
      var skills = cv.skills_top || [];
      if (skills.length) {
        p.push('<p class="cv-skills"><strong>' + esc(lab.skills) + ":</strong> " +
               esc(skills.map(function (s) { return String(s); }).join(" · ")) + "</p>");
      }
    }

    // Compléments : certifications · langues · centres d'intérêt (ordre du CV ATS)
    var certs = cv.certifications || [];
    if (certs.length) {
      p.push('<p class="cv-extra"><strong>' + esc(lab.certifications) + ":</strong> " +
             esc(certs.map(function (c) { return String(c); }).join(" · ")) + "</p>");
    }

    var languages = cv.languages || [];
    if (languages.length) {
      var langItems = [];
      languages.forEach(function (lg) {
        var nm = lg.name || "", lvl = lg.level || "";
        var item = (nm && lvl) ? (nm + " — " + lvl) : (nm || lvl);
        if (item) langItems.push(item);
      });
      if (langItems.length) {
        p.push('<p class="cv-extra"><strong>' + esc(lab.languages) + ":</strong> " +
               esc(langItems.join(" · ")) + "</p>");
      }
    }

    var interests = cv.interests || [];
    if (interests.length) {
      p.push('<p class="cv-extra"><strong>' + esc(lab.interests) + ":</strong> " +
             esc(interests.map(function (i) { return String(i); }).join(" · ")) + "</p>");
    }

    var updated = (cv.footer || {}).updated || "";
    if (updated) p.push('<p class="cv-footer">' + esc(lab.updated) + " " + esc(updated) + "</p>");

    p.push("</body></html>");
    return p.join("");
  }

  return { renderHtml: renderHtml, CV_CSS: CV_CSS };
});
