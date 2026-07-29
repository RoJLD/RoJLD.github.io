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

  var DEFAUT = "sobre";
  var ALL = [
  {
    "id": "ats",
    "label": {
      "en": "ATS",
      "fr": "ATS"
    },
    "meta": {
      "ats_safe": true,
      "market": [
        "FR",
        "EU",
        "US"
      ],
      "pages": 1,
      "sections": [
        "identity",
        "experience",
        "education",
        "skills",
        "languages",
        "certifications",
        "interests"
      ],
      "tone": "neutral"
    },
    "style": {
      "density": {
        "bullet_gap": "2px",
        "line": 1.35,
        "section_gap": "8px"
      },
      "page": {
        "margin": "15mm 15mm",
        "size": "A4"
      },
      "palette": {
        "accent": "#000000",
        "body": "#000000",
        "faint": "#333333",
        "faint_2": "#333333",
        "ink": "#000000",
        "ink_2": "#000000",
        "muted": "#333333",
        "rule": "#000000"
      },
      "type": {
        "base": "10pt",
        "h1": "16pt",
        "h2": "11pt",
        "micro": "8.5pt",
        "small": "9.5pt",
        "tiny": "9pt"
      }
    }
  },
  {
    "id": "dense",
    "label": {
      "en": "Compact",
      "fr": "Dense"
    },
    "meta": {
      "ats_safe": true,
      "market": [
        "FR",
        "EU"
      ],
      "pages": 1,
      "sections": [
        "identity",
        "experience",
        "education",
        "skills",
        "languages",
        "certifications",
        "interests"
      ],
      "tone": "corporate"
    },
    "style": {
      "density": {
        "bullet_gap": "0px",
        "line": 1.2,
        "section_gap": "5px"
      },
      "page": {
        "margin": "10mm 12mm",
        "size": "A4"
      },
      "palette": {
        "accent": "#4361ee",
        "body": "#444",
        "faint": "#777",
        "faint_2": "#999",
        "ink": "#1a1a2e",
        "ink_2": "#16213e",
        "muted": "#555",
        "rule": "#dde"
      },
      "type": {
        "base": "9pt",
        "h1": "16pt",
        "h2": "10pt",
        "micro": "7.5pt",
        "small": "8.5pt",
        "tiny": "8pt"
      }
    }
  },
  {
    "id": "sobre",
    "label": {
      "en": "Plain",
      "fr": "Sobre"
    },
    "meta": {
      "ats_safe": true,
      "market": [
        "FR",
        "EU"
      ],
      "pages": 1,
      "sections": [
        "identity",
        "experience",
        "education",
        "skills",
        "languages",
        "certifications",
        "interests"
      ],
      "tone": "corporate"
    },
    "style": {
      "density": {
        "bullet_gap": "1px",
        "line": 1.3,
        "section_gap": "7px"
      },
      "page": {
        "margin": "12mm 14mm",
        "size": "A4"
      },
      "palette": {
        "accent": "#4361ee",
        "body": "#444",
        "faint": "#777",
        "faint_2": "#999",
        "ink": "#1a1a2e",
        "ink_2": "#16213e",
        "muted": "#555",
        "rule": "#dde"
      },
      "type": {
        "base": "9.8pt",
        "h1": "17pt",
        "h2": "10.5pt",
        "micro": "8pt",
        "small": "9pt",
        "tiny": "8.5pt"
      }
    }
  }
];

  function get(id) {
    var t = ALL.filter(function (x) { return x.id === id; })[0];
    if (!t) throw new Error("template inconnu : " + id);
    return t;
  }

  return { DEFAUT: DEFAUT, all: ALL, get: get };
});
