/* Σ-CV-ATELIER sous-projet D — modèle du CMS (édition structurée de profile.json).
 *
 * Fonctions PURES et IMMUABLES : chaque opération retourne un NOUVEAU profil et ne
 * mute jamais l'entrée. Testable en node (tools/cv/cms_model_test.js), utilisable
 * dans le navigateur via window.CMSModel.
 *
 * ── INVARIANT 1 : préservation par CONSTRUCTION ──────────────────────────────
 * Une mutation ne remplace qu'UNE clé de premier niveau (`{...profile, [k]: neuf}`) ;
 * tout le reste est reporté tel quel. Le CMS ne « reconstruit » jamais le document
 * depuis le formulaire : il charge le profil entier, mute un sous-arbre, resoumet
 * l'entier. C'est ce qui empêche la perte PAR OMISSION des clés non modélisées
 * (hidden_edge, ikigai, journey…) — invisible en démo, fatale en production.
 *
 * ── INVARIANT 2 : la FORME est lue, jamais supposée ──────────────────────────
 * profile.json est hétérogène : `projects.name` est bilingue {fr,en} sur 2 entrées
 * et une chaîne simple sur 15 ; `education.courses` est tantôt une liste de chaînes,
 * tantôt une liste d'objets bilingues ; `skills.weight` est un NOMBRE. Un schéma qui
 * DÉCLARE la forme rendrait un champ vide sur les entrées non conformes et
 * remplacerait la vraie valeur à la première frappe. `fieldShape` lit donc la forme
 * réelle de la valeur courante, et `writeField` réécrit DANS LA MÊME FORME.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CMSModel = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* Schéma déclaratif : engendre les formulaires. `i18n` n'est qu'un DÉFAUT, utilisé
     seulement quand la valeur est absente — la forme réelle prime toujours.
     types : text | textarea | lines | bool | number */
  var TYPES = {
    experiences: {
      key: "experiences", container: "list",
      label: { fr: "Expériences", en: "Experience" }, titleField: "company",
      fields: [
        { name: "id", type: "text", label: { fr: "Identifiant", en: "Id" } },
        { name: "company", type: "text", label: { fr: "Entreprise", en: "Company" } },
        { name: "title", type: "text", i18n: true, label: { fr: "Poste", en: "Role" } },
        { name: "division", type: "text", i18n: true, label: { fr: "Division", en: "Division" } },
        { name: "location", type: "text", label: { fr: "Lieu", en: "Location" } },
        { name: "type", type: "text", label: { fr: "Type (stage, cdi…)", en: "Type" } },
        { name: "start", type: "text", label: { fr: "Début (AAAA-MM)", en: "Start" } },
        { name: "end", type: "text", label: { fr: "Fin (AAAA-MM)", en: "End" } },
        { name: "current", type: "bool", label: { fr: "En cours", en: "Current" } },
        { name: "domains", type: "lines", label: { fr: "Domaines (1/ligne, requis)", en: "Domains (required)" } },
        { name: "bullets", type: "lines", i18n: true, label: { fr: "Points (1/ligne)", en: "Bullets (1/line)" } },
      ],
    },
    projects: {
      key: "projects", container: "list",
      label: { fr: "Projets", en: "Projects" }, titleField: "name",
      fields: [
        { name: "id", type: "text", label: { fr: "Identifiant", en: "Id" } },
        { name: "name", type: "text", i18n: true, label: { fr: "Nom", en: "Name" } },
        { name: "summary", type: "textarea", i18n: true, label: { fr: "Résumé", en: "Summary" } },
        { name: "date", type: "text", label: { fr: "Date", en: "Date" } },
        { name: "type", type: "text", label: { fr: "Type (academic|personal|professional)", en: "Type" } },
        { name: "context", type: "text", label: { fr: "Contexte (id exp/formation ou personal)", en: "Context" } },
        { name: "domains", type: "lines", label: { fr: "Domaines (1/ligne, requis)", en: "Domains (required)" } },
        { name: "tags", type: "lines", label: { fr: "Tags (1/ligne)", en: "Tags (1/line)" } },
        { name: "stack", type: "lines", label: { fr: "Stack (1/ligne)", en: "Stack (1/line)" } },
        { name: "featured", type: "bool", label: { fr: "Mis en avant", en: "Featured" } },
      ],
    },
    education: {
      key: "education", container: "list",
      label: { fr: "Formation", en: "Education" }, titleField: "school",
      fields: [
        { name: "id", type: "text", label: { fr: "Identifiant", en: "Id" } },
        { name: "school", type: "text", label: { fr: "École", en: "School" } },
        { name: "title", type: "text", i18n: true, label: { fr: "Intitulé", en: "Title" } },
        { name: "org", type: "text", i18n: true, label: { fr: "Spécialité", en: "Major" } },
        { name: "period", type: "text", label: { fr: "Période", en: "Period" } },
        { name: "degree", type: "text", label: { fr: "Diplôme", en: "Degree" } },
        { name: "courses", type: "lines", i18n: true, label: { fr: "Cours (1/ligne)", en: "Courses (1/line)" } },
      ],
    },
    skills: {
      key: "skills", container: "groups",   // dict de listes : une liste par catégorie
      label: { fr: "Compétences", en: "Skills" }, titleField: "name",
      fields: [
        { name: "name", type: "text", label: { fr: "Nom", en: "Name" } },
        { name: "level", type: "text", label: { fr: "Niveau", en: "Level" } },
        { name: "weight", type: "number", label: { fr: "Poids (0-1)", en: "Weight (0-1)" } },
        { name: "last_used", type: "text", label: { fr: "Dernier usage (AAAA-MM)", en: "Last used" } },
      ],
    },
  };

  function isObj(v) { return v && typeof v === "object" && !Array.isArray(v); }
  function asList(v) { return Array.isArray(v) ? v : []; }
  function own(o, k) { return isObj(o) && Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined; }
  function copy(o) { var out = {}; for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) out[k] = o[k]; return out; }

  /* ── Formes ────────────────────────────────────────────────────────────────
     "scalar"  valeur simple (str/num/bool)
     "bi"      objet bilingue de scalaires        {fr:"…", en:"…"}
     "biLines" objet bilingue de LISTES           {fr:[…], en:[…]}  ← experiences.bullets
     "list"    liste de chaînes                   […]               ← projects.tags
     "biList"  liste d'objets bilingues           [{fr,en}, …]      ← education.courses (ECE)
     Les DEUX formes bilingues-de-liste coexistent réellement dans profile.json :
     les confondre écrirait une chaîne là où le site attend une liste.             */
  function fieldShape(item, f) {
    var v = item ? item[f.name] : undefined;
    if (Array.isArray(v)) return v.some(isObj) ? "biList" : "list";
    if (isObj(v)) {
      for (var k in v) if (Object.prototype.hasOwnProperty.call(v, k) && Array.isArray(v[k])) return "biLines";
      return "bi";
    }
    if (v === undefined || v === null || v === "") {   // absent → forme DÉCLARÉE
      if (f.type === "lines") return f.i18n ? "biLines" : "list";
      return f.i18n ? "bi" : "scalar";
    }
    return "scalar";
  }

  /* Valeur à afficher pour (champ, langue). `lang` ignoré pour les formes non bilingues. */
  function readField(item, f, lang) {
    var v = item ? item[f.name] : undefined;
    switch (fieldShape(item, f)) {
      case "bi": return (own(v, lang) === undefined) ? "" : own(v, lang);
      case "biLines": return asList(own(v, lang)).join("\n");
      case "list": return asList(v).join("\n");
      case "biList": return asList(v).map(function (o) {
        var x = isObj(o) ? own(o, lang) : o;
        return x === undefined || x === null ? "" : String(x);
      }).join("\n");
      default: return (v === undefined || v === null) ? "" : v;
    }
  }

  function splitLines(raw) {
    return String(raw).split("\n").map(function (s) { return s.trim(); })
      .filter(function (s) { return s; });
  }

  /* Patch réécrivant le champ DANS SA FORME COURANTE. Retourne null si l'entrée est
     invalide (nombre non numérique) : l'appelant garde alors la valeur précédente
     plutôt que d'écrire une chaîne là où le site attend un nombre (ce qui validerait
     puis ferait planter le rebuild). */
  function writeField(item, f, lang, raw) {
    var patch = {}, cur = item ? item[f.name] : undefined;
    switch (fieldShape(item, f)) {
      case "bi":
        var o = isObj(cur) ? copy(cur) : {};
        o[lang] = String(raw);
        patch[f.name] = o;
        break;
      case "biLines":                       // {fr:[…], en:[…]} — l'autre langue survit
        var ol = isObj(cur) ? copy(cur) : {};
        ol[lang] = splitLines(raw);
        patch[f.name] = ol;
        break;
      case "list":
        patch[f.name] = splitLines(raw);
        break;
      case "biList":
        var lines = splitLines(raw), prev = asList(cur);
        patch[f.name] = lines.map(function (line, i) {
          var base = isObj(prev[i]) ? copy(prev[i]) : {};
          base[lang] = line;
          return base;                       // l'AUTRE langue de la même entrée survit
        });
        break;
      default:
        if (f.type === "bool") { patch[f.name] = !!raw; break; }
        if (f.type === "number") {
          var s = String(raw).trim();
          if (s === "") { patch[f.name] = null; break; }   // vidé explicitement
          var n = Number(s);
          if (!isFinite(n)) return null;                   // refus : on ne écrit pas de texte
          patch[f.name] = n;
          break;
        }
        patch[f.name] = raw;
    }
    return patch;
  }

  function groupsOf(profile, type) {
    var t = TYPES[type];
    if (!t || t.container !== "groups") return [];
    var d = (profile || {})[t.key];
    if (!isObj(d)) return [];
    // SEULES les entrées qui sont des LISTES sont des catégories : profile.skills
    // contient aussi `radar_scores`, un dict de scores qu'un « + Ajouter »
    // transformerait en liste et corromprait.
    return Object.keys(d).filter(function (k) { return Array.isArray(d[k]); });
  }

  function listItems(profile, type, group) {
    var t = TYPES[type];
    if (!t) return [];
    var v = (profile || {})[t.key];
    if (t.container === "groups") return isObj(v) ? asList(own(v, group)) : [];
    return asList(v);
  }

  /* Cœur de la préservation : remplace UNE clé de premier niveau, reporte le reste.
     Pour un type « groups », remplace UNE catégorie et reporte les autres (y compris
     les entrées non-listes comme radar_scores). */
  function withList(profile, type, group, newList) {
    var t = TYPES[type], out = copy(profile);
    if (t.container === "groups") {
      var nd = copy(isObj(profile[t.key]) ? profile[t.key] : {});
      nd[group] = newList;
      out[t.key] = nd;
    } else {
      out[t.key] = newList;
    }
    return out;
  }

  /* Élément neuf VALIDE par construction : `validate_profile` exige un `domains[]`
     non vide (et pour un projet un `context`/`type` reconnus). Un élément invalide
     bloquerait TOUTE sauvegarde ultérieure, y compris des éditions légitimes sans
     rapport — d'où les valeurs par défaut plutôt qu'un formulaire vide. */
  function emptyItem(type, profile) {
    var t = TYPES[type], item = {};
    t.fields.forEach(function (f) {
      if (f.type === "bool") item[f.name] = false;
      else if (f.type === "number") item[f.name] = 0.5;
      // lines+i18n → {fr:[],en:[]} : `validate_profile` exige les DEUX langues sur
      // experiences.bullets ; un `[]` nu rendait toute nouvelle entrée invalide.
      else if (f.type === "lines") item[f.name] = f.i18n ? { fr: [], en: [] } : [];
      else item[f.name] = f.i18n ? { fr: "", en: "" } : "";
    });
    var doms = asList((profile || {}).domains)
      .map(function (d) { return isObj(d) ? d.id : d; })
      .filter(function (d) { return typeof d === "string" && d; });
    if (type === "experiences") {
      item.id = "nouvelle-experience";
      if (doms.length) item.domains = [doms[0]];
    } else if (type === "projects") {
      item.id = "nouveau-projet";
      item.name = "Nouveau projet";
      item.type = "personal";
      item.context = "personal";
      if (doms.length) item.domains = [doms[0]];
    } else if (type === "education") {
      item.id = "nouvelle-formation";
    }
    return item;
  }

  function updateItem(profile, type, index, patch, group) {
    var t = TYPES[type];
    if (!t || !patch) return profile;
    var items = listItems(profile, type, group);
    if (!(index >= 0 && index < items.length)) return profile;
    var merged = copy(isObj(items[index]) ? items[index] : {});
    for (var pk in patch) if (Object.prototype.hasOwnProperty.call(patch, pk)) merged[pk] = patch[pk];
    var next = items.slice();
    next[index] = merged;
    return withList(profile, type, group, next);
  }

  function addItem(profile, type, group) {
    var t = TYPES[type];
    if (!t) return profile;
    var next = listItems(profile, type, group).slice();   // slice : jamais en place
    next.push(emptyItem(type, profile));
    return withList(profile, type, group, next);
  }

  function removeItem(profile, type, index, group) {
    var t = TYPES[type];
    if (!t) return profile;
    var items = listItems(profile, type, group);
    if (!(index >= 0 && index < items.length)) return profile;
    var next = items.slice();
    next.splice(index, 1);
    return withList(profile, type, group, next);
  }

  function moveItem(profile, type, index, delta, group) {
    var t = TYPES[type];
    if (!t) return profile;
    var items = listItems(profile, type, group), target = index + delta;
    if (!(index >= 0 && index < items.length)) return profile;     // source bornée
    if (!(target >= 0 && target < items.length)) return profile;   // cible bornée
    var next = items.slice();
    next.splice(target, 0, next.splice(index, 1)[0]);
    return withList(profile, type, group, next);
  }

  return {
    TYPES: TYPES,
    groupsOf: groupsOf, listItems: listItems, emptyItem: emptyItem,
    fieldShape: fieldShape, readField: readField, writeField: writeField,
    updateItem: updateItem, addItem: addItem, removeItem: removeItem, moveItem: moveItem,
  };
});
