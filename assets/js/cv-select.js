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

  // Miroir de _as_list : liste STRICTE (une chaîne ne doit pas être itérée).
  function asList(v) { return Array.isArray(v) ? v : []; }

  // Miroir de _DEFAULT_SKILL_CATS : ordre EXPLICITE (jamais Object.keys, dont
  // l'ordre déciderait du CV et embarquerait radar_scores).
  var DEFAULT_SKILL_CATS = ["finance", "programming", "data_ml", "domain", "engineering"];

  // Miroir de _skills_groups
  function skillsGroups(profile, lang, cfg) {
    cfg = cfg || {};
    var cats = Array.isArray(cfg.skills_categories) && cfg.skills_categories.length
      ? cfg.skills_categories : DEFAULT_SKILL_CATS;
    var cap = cfg.skills_per_category;
    cap = (Number.isInteger(cap) && cap >= 0) ? cap : null;
    var labels = profile.skills_labels || {};
    var skills = profile.skills || {};
    // own() : une catégorie nommée comme une propriété d'Object.prototype
    // ("constructor", "toString") renverrait sinon la fonction native — le
    // libellé du CV deviendrait « function Object() { [native code] } ».
    function own(o, k) {
      return Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined;
    }
    var groups = [];
    cats.forEach(function (cat) {
      var items = [];
      asList(own(skills, cat)).forEach(function (s) {
        var n = (s && typeof s === "object" && !Array.isArray(s)) ? s.name : s;
        if (typeof n === "string" && n) items.push(n);
      });
      if (cap !== null) items = items.slice(0, cap);
      if (items.length) groups.push({ label: loc(own(labels, cat), lang) || String(cat), items: items });
    });
    return groups;
  }

  // Miroir de _neg_date : complément à 9 des chiffres → tri asc = date desc.
  // Non-chaîne → "" (miroir explicite du garde isinstance côté Python).
  function negDate(v) {
    var s = (typeof v === "string") ? v : "";
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

  // Miroir de _link_display : retire le schéma http(s):// puis un préfixe www.
  // Chaînes UNIQUEMENT (une URL non-str ne doit pas être stringifiée ici).
  function linkDisplay(url) {
    var s = (typeof url === "string") ? url.trim() : "";
    if (s.indexOf("https://") === 0) s = s.slice(8);
    else if (s.indexOf("http://") === 0) s = s.slice(7);
    if (s.indexOf("www.") === 0) s = s.slice(4);
    return s;
  }

  // Miroir de _location_str : 'City, Country'. Le téléphone n'est JAMAIS projeté.
  function locationStr(identity) {
    var l = identity.location;
    if (!l || typeof l !== "object" || Array.isArray(l)) return "";
    return [(typeof l.city === "string" ? l.city : "").trim(),
            (typeof l.country === "string" ? l.country : "").trim()]
      .filter(function (p) { return p; }).join(", ");
  }

  // Miroir de _education
  function educationOf(profile, lang) {
    return asList(profile.education).map(function (e) {
      var cap = e.capstone;
      return {
        school: loc(e.school, lang),
        title: loc(e.title, lang),
        org: loc(e.org, lang),
        period: loc(e.period, lang),
        degree: loc(e.degree, lang),
        courses_label: loc(e.courses_label, lang),
        courses: asList(e.courses).map(function (c) { return loc(c, lang); }),
        capstone: (cap && typeof cap === "object" && !Array.isArray(cap))
          ? { label: loc(cap.label, lang), summary: loc(cap.summary, lang) }
          : null,
      };
    });
  }

  // Miroir de _languages
  function languagesOf(profile, lang) {
    return asList(profile.languages).map(function (lg) {
      return { name: loc(lg.name, lang), level: loc(lg.level, lang) };
    });
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

    if (cfg.sort_by === "date") {
      // Miroir Python : CV complet = reverse-chrono, IGNORE la relevance.
      matched.sort(function (a, b) {
        var na = negDate(a.start || ""), nb = negDate(b.start || "");
        if (na !== nb) return na < nb ? -1 : 1;
        var ia = a.id || "", ib = b.id || "";
        return ia < ib ? -1 : ia > ib ? 1 : 0;
      });
    } else {
      matched.sort(function (a, b) {
        var ra = -relOf(a, key), rb = -relOf(b, key);
        if (ra !== rb) return ra < rb ? -1 : 1;
        var na = negDate(a.start || ""), nb = negDate(b.start || "");
        if (na !== nb) return na < nb ? -1 : 1;
        var ia = a.id || "", ib = b.id || "";
        return ia < ib ? -1 : ia > ib ? 1 : 0;
      });
    }

    // Prédicat ENTIER STRICT (miroir Python) : exclut bool, float, NaN, Infinity.
    if (Number.isInteger(maxExp) && maxExp >= 0) matched = matched.slice(0, maxExp);
    return matched;
  }

  function selectManual(profile, bulletIds, lang) {
    // Object.create(null) : un exp.id valant une clé d'Object.prototype
    // ("constructor", "toString"...) casserait l'accumulation avec un {} nu.
    var wanted = Object.create(null);
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

  function buildStructuredCv(profile, experiences, lang, cfg) {
    var identity = profile.identity || {};
    var present = lang === "fr" ? "présent" : "present";
    var sections = (experiences || []).map(function (exp) {
      return {
        kind: "experience",
        company: loc(exp.company, lang),
        title: loc(exp.title, lang),
        dates: (exp.start || "") + " → " + (exp.current ? present : (exp.end || "")),
        bullets: asList((exp.bullets || {})[lang]).slice(),
      };
    });

    // Compétences groupées par catégorie (pilotées par cfg) ; skills_top reste la
    // liste PLATE dérivée, pour les consommateurs historiques du schéma.
    var groups = skillsGroups(profile, lang, cfg);
    var skillsTop = [];
    groups.forEach(function (g) { g.items.forEach(function (n) { skillsTop.push(n); }); });

    var name = ((identity.first_name || "") + " " + (identity.last_name || "")).trim()
               || loc(identity.name, lang);
    var links = identity.links || {};
    return {
      lang: lang,
      identity: {
        name: name,
        // tagline = sous-titre du profil (identity.title absent de profile.json)
        title: loc(identity.tagline || identity.title, lang),
        email: loc(identity.email, lang),
        location: locationStr(identity),      // tél JAMAIS projeté (public)
        linkedin: linkDisplay(links.linkedin),
        github: linkDisplay(links.github),
      },
      sections: sections,
      skills_groups: groups,
      skills_top: skillsTop,
      education: educationOf(profile, lang),
      languages: languagesOf(profile, lang),
      // certifications passe par loc() comme interests (miroir Python) : une
      // entrée bilingue {fr,en} doit être résolue, pas stringifiée.
      certifications: asList(profile.certifications).map(function (c) { return loc(c, lang); }),
      interests: asList(profile.interests).map(function (i) { return loc(i, lang); }),
      footer: { updated: loc(profile.$updated, lang) },
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
