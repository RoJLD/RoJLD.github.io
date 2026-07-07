/* Σ-CV-ATELIER — miroir JS de cv_select.py (sélection pure depuis profile.json).
 * selectExperiences (auto), selectManual (cases à cocher), buildStructuredCv.
 * Doit produire le MÊME structured_cv que Python (parité pipeline testée node).
 * UMD : window.CVSelect (navigateur) + module.exports (node). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CVSelect = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function loc(value, lang) {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      return String(value[lang] || value.fr || value.en || "");
    }
    return value == null ? "" : String(value);
  }

  // Miroir de _neg_date : complément à 9 des chiffres → tri asc = date desc.
  function negDate(s) {
    s = s || "";
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      out += (c >= "0" && c <= "9") ? String(9 - Number(c)) : c;
    }
    return out;
  }

  function relOf(exp, key) {
    return Number((exp.relevance || {})[key] || 0);
  }

  function selectExperiences(profile, cfg) {
    cfg = cfg || {};
    var key = cfg.relevance_key || "general";
    var minRel = Number(cfg.min_relevance || 0);
    var domainsIn = new Set(cfg.domains_in || []);
    var maxExp = cfg.max_experiences;

    var matched = (profile.experiences || []).filter(function (exp) {
      if (relOf(exp, key) >= minRel) return true;
      return (exp.domains || []).some(function (d) { return domainsIn.has(d); });
    });

    matched.sort(function (a, b) {
      var ra = -relOf(a, key), rb = -relOf(b, key);
      if (ra !== rb) return ra < rb ? -1 : 1;
      var na = negDate(a.start || ""), nb = negDate(b.start || "");
      if (na !== nb) return na < nb ? -1 : 1;
      var ia = a.id || "", ib = b.id || "";
      return ia < ib ? -1 : ia > ib ? 1 : 0;
    });

    if (typeof maxExp === "number" && maxExp >= 0) matched = matched.slice(0, maxExp);
    return matched;
  }

  function selectManual(profile, bulletIds, lang) {
    var wanted = {};
    (bulletIds || []).forEach(function (bid) {
      var dot = bid.lastIndexOf(".");
      if (dot <= 0) return;
      var expId = bid.slice(0, dot), idx = bid.slice(dot + 1);
      if (!/^\d+$/.test(idx)) return;
      (wanted[expId] = wanted[expId] || new Set()).add(Number(idx));
    });

    var out = [];
    (profile.experiences || []).forEach(function (exp) {
      var eid = exp.id || "";
      if (!(eid in wanted)) return;
      var bullets = (exp.bullets || {})[lang] || [];
      var idxs = Array.from(wanted[eid]).sort(function (a, b) { return a - b; });
      var picked = idxs.filter(function (i) { return i >= 0 && i < bullets.length; })
                       .map(function (i) { return bullets[i]; });
      if (picked.length) {
        var copy = Object.assign({}, exp);
        copy.bullets = {};
        copy.bullets[lang] = picked;
        out.push(copy);
      }
    });
    return out;
  }

  function buildStructuredCv(profile, experiences, lang) {
    var identity = profile.identity || {};
    var present = lang === "fr" ? "présent" : "present";
    var sections = (experiences || []).map(function (exp) {
      return {
        kind: "experience",
        company: loc(exp.company, lang),
        title: loc(exp.title, lang),
        dates: (exp.start || "") + " → " + (exp.current ? present : (exp.end || "")),
        bullets: ((exp.bullets || {})[lang] || []).slice(),
      };
    });

    var skills = profile.skills || {};
    var skillsTop = [];
    ["programming", "finance", "data_ml"].forEach(function (cat) {
      (skills[cat] || []).slice(0, 3).forEach(function (s) {
        skillsTop.push(s && typeof s === "object" ? (s.name || s) : s);
      });
    });

    var name = ((identity.first_name || "") + " " + (identity.last_name || "")).trim()
               || loc(identity.name, lang);
    return {
      lang: lang,
      identity: { name: name, title: loc(identity.title, lang), email: loc(identity.email, lang) },
      sections: sections,
      skills_top: skillsTop,
      footer: { updated: profile.$updated || "" },
    };
  }

  // Liste plate des bullets sélectionnables (pour l'UI cases à cocher).
  function listBullets(profile, lang) {
    var items = [];
    (profile.experiences || []).forEach(function (exp) {
      var bullets = (exp.bullets || {})[lang] || [];
      bullets.forEach(function (b, i) {
        items.push({ id: (exp.id || "") + "." + i, company: loc(exp.company, lang), text: b });
      });
    });
    return items;
  }

  return {
    loc: loc, negDate: negDate,
    selectExperiences: selectExperiences, selectManual: selectManual,
    buildStructuredCv: buildStructuredCv, listBullets: listBullets,
  };
});
