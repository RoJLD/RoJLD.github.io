/* Tests du modèle CMS (assets/js/cms-model.js) — exécuter : node cms_model_test.js
 *
 * INVARIANT 1 : toute mutation préserve À L'IDENTIQUE les clés non modélisées.
 *   Le risque n°1 d'un CMS sur 23 clés est la perte PAR OMISSION.
 * INVARIANT 2 : la FORME d'un champ est lue, jamais supposée.
 *   profile.json est hétérogène (`projects.name` bilingue sur 2 entrées, chaîne
 *   simple sur 15 ; `education.courses` liste de chaînes OU d'objets bilingues ;
 *   `skills.weight` NOMBRE). Un formulaire qui suppose la forme rend un champ vide
 *   puis écrase la vraie valeur à la première frappe.
 *
 * Fixtures à ≥3 éléments par liste : avec 2, les mutations de bornes de moveItem
 * sont des no-ops et le test « borné » ne peut structurellement pas échouer.
 */
const M = require("../../assets/js/cms-model.js");

let ok = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { ok++; console.log(`  PASS ${name}`); }
  else { fail++; console.log(`  FAIL ${name}${detail ? " — " + detail : ""}`); }
}
function eq(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

function profile() {
  return {
    $schema: "s", $version: "1.1.0", $updated: "2026-07-19",
    domains: [{ id: "quant" }, { id: "dev" }],
    identity: { first_name: "Robin", links: { github: "g" } },
    experiences: [
      { id: "a", company: "ALTEN", title: { fr: "Quant", en: "Quant" }, start: "2026-02",
        current: true, domains: ["quant"], bullets: { fr: ["b1", "b2"], en: ["b1"] } },
      { id: "b", company: "Bouygues", title: { fr: "Trésorier" }, start: "2025-02",
        end: "2025-08", domains: ["dev"], bullets: { fr: ["b3"] } },
      { id: "c", company: "ManCo", title: { fr: "Risk" }, start: "2024-06",
        domains: ["quant"], bullets: { fr: ["b4"] } },
    ],
    projects: [
      // forme RÉELLE majoritaire : name/summary en CHAÎNE SIMPLE (15/17 du vrai profil)
      { id: "p1", name: "hmm-studio", summary: "Modèles de Markov", type: "personal",
        context: "personal", domains: ["quant"], tags: ["ml"] },
      // forme minoritaire : bilingue (2/17)
      { id: "p2", name: { fr: "Projet FR", en: "Project EN" },
        summary: { fr: "Résumé", en: "Summary" }, type: "academic",
        context: "personal", domains: ["dev"], tags: [] },
      { id: "p3", name: "Troisième", type: "personal", context: "personal", domains: ["dev"] },
    ],
    education: [
      // courses = liste d'OBJETS bilingues (cas ECE du vrai profil)
      { id: "ece", school: "ECE Paris", title: { fr: "Cycle Ing", en: "Eng" },
        courses: [{ fr: "Stochastique", en: "Stochastic" }, { fr: "ML", en: "ML" }] },
      // courses = liste de chaînes (cas prépa)
      { id: "prepa", school: "Prépa", courses: [] },
      { id: "autre", school: "Autre", courses: ["c1", "c2"] },
    ],
    skills: {
      programming: [{ name: "Python", weight: 0.95 }, { name: "SQL", weight: 0.88 },
                    { name: "VBA", weight: 0.82 }],
      finance: [{ name: "Pricing", weight: 0.9 }],
      radar_scores: { Quant: 0.9 },          // dict de scores, PAS une catégorie
    },
    // ── clés NON modélisées : doivent survivre à toute mutation ──
    hidden_edge: { description: "combinaisons rares", pairs: [["a", "b"]] },
    ikigai: { mission: "m" }, journey: [{ y: 2019 }, { y: 2021 }],
    projects_meta: { featured: ["p1"] }, lifestyle: { freedom: 1.0 },
  };
}

function otherKeysIntact(before, after, mutatedKey) {
  const ks = new Set([...Object.keys(before), ...Object.keys(after)]);
  for (const k of ks) {
    if (k === mutatedKey) continue;
    if (!eq(before[k], after[k])) return `clé « ${k} » altérée`;
  }
  return null;
}
const F = (t, n) => M.TYPES[t].fields.find((f) => f.name === n);

// ── INVARIANT 1 : préservation ────────────────────────────────────────────────

for (const [label, run, key] of [
  ["update", (p) => M.updateItem(p, "experiences", 0, { company: "X" }), "experiences"],
  ["add", (p) => M.addItem(p, "projects"), "projects"],
  ["remove", (p) => M.removeItem(p, "education", 0), "education"],
  ["move", (p) => M.moveItem(p, "experiences", 0, 1), "experiences"],
  ["skills", (p) => M.updateItem(p, "skills", 0, { name: "Rust" }, "programming"), "skills"],
]) {
  const before = profile(), after = run(profile());
  const bad = otherKeysIntact(before, after, key);
  check(`cardinal:${label} préserve les clés non modélisées`, bad === null, bad);
}

check("cardinal:aucune clé ne disparaît après une séquence d'opérations", (() => {
  const before = profile();
  let p = profile();
  p = M.updateItem(p, "experiences", 0, { company: "X" });
  p = M.addItem(p, "projects");
  p = M.removeItem(p, "education", 0);
  p = M.moveItem(p, "experiences", 0, 1);
  p = M.addItem(p, "skills", "finance");
  return eq(Object.keys(before).sort(), Object.keys(p).sort());
})());

check("cardinal:skills.radar_scores (non-liste) survit aux mutations de catégorie", (() => {
  const p = M.addItem(M.updateItem(profile(), "skills", 0, { name: "R" }, "programming"), "skills", "finance");
  return eq(p.skills.radar_scores, { Quant: 0.9 });
})());

// ── IMMUTABILITÉ (les 3 opérations mutantes, pas seulement update) ────────────

for (const [label, run] of [
  ["updateItem", (p) => M.updateItem(p, "experiences", 0, { company: "MUTE" })],
  ["removeItem", (p) => M.removeItem(p, "projects", 0)],
  ["addItem", (p) => M.addItem(p, "projects")],
  ["moveItem", (p) => M.moveItem(p, "projects", 0, 2)],
]) {
  const p = profile(), snap = JSON.stringify(p);
  run(p);
  check(`immutable:${label} ne mute pas l'entrée`, JSON.stringify(p) === snap);
}

// ── INVARIANT 2 : formes hétérogènes ──────────────────────────────────────────

check("shape:une chaîne simple est détectée scalar (pas bilingue)",
      M.fieldShape(profile().projects[0], F("projects", "name")) === "scalar");
check("shape:un objet {fr,en} est détecté bi",
      M.fieldShape(profile().projects[1], F("projects", "name")) === "bi");
check("shape:une liste d'objets est détectée biList",
      M.fieldShape(profile().education[0], F("education", "courses")) === "biList");
check("shape:une liste de chaînes est détectée list",
      M.fieldShape(profile().education[2], F("education", "courses")) === "list");

// bullets = {fr:[…], en:[…]} : forme bilingue-de-LISTES, distincte de biList
check("shape:un dict de listes est détecté biLines (≠ bi)",
      M.fieldShape(profile().experiences[0], F("experiences", "bullets")) === "biLines");

check("read:biLines s'affiche une ligne par point, dans la langue",
      M.readField(profile().experiences[0], F("experiences", "bullets"), "fr") === "b1\nb2");

check("write:biLines écrit une LISTE (pas une chaîne) et garde l'autre langue", (() => {
  const item = profile().experiences[0];
  const patch = M.writeField(item, F("experiences", "bullets"), "fr", "n1\nn2\nn3");
  return Array.isArray(patch.bullets.fr) && patch.bullets.fr.length === 3
      && eq(patch.bullets.en, ["b1"]);
})());

check("emptyItem:bullets porte les DEUX langues (exigé par validate_profile)", (() => {
  const it = M.emptyItem("experiences", profile());
  return Array.isArray(it.bullets.fr) && Array.isArray(it.bullets.en);
})());

check("read:une chaîne simple s'affiche (le champ n'est PAS vide)",
      M.readField(profile().projects[0], F("projects", "name"), null) === "hmm-studio");
check("read:un bilingue s'affiche par langue",
      M.readField(profile().projects[1], F("projects", "name"), "en") === "Project EN");
check("read:biList s'affiche une entrée par ligne, dans la langue",
      M.readField(profile().education[0], F("education", "courses"), "en") === "Stochastic\nML");

check("write:éditer un name-chaîne le garde CHAÎNE (pas de {fr:…})", (() => {
  const p = profile(), item = p.projects[0];
  const patch = M.writeField(item, F("projects", "name"), null, "nouveau-nom");
  return patch.name === "nouveau-nom";
})());

check("write:éditer un name-bilingue préserve l'AUTRE langue", (() => {
  const p = profile(), item = p.projects[1];
  const patch = M.writeField(item, F("projects", "name"), "fr", "FR modifié");
  return patch.name.fr === "FR modifié" && patch.name.en === "Project EN";
})());

check("write:éditer un biList préserve l'autre langue de chaque entrée", (() => {
  const item = profile().education[0];
  const patch = M.writeField(item, F("education", "courses"), "fr", "Stochastique 2\nML 2");
  return patch.courses.length === 2 && patch.courses[0].fr === "Stochastique 2"
      && patch.courses[0].en === "Stochastic" && patch.courses[1].en === "ML";
})());

// ── Nombres : jamais de chaîne là où le site attend un nombre ─────────────────

check("number:une saisie numérique est écrite comme NOMBRE", (() => {
  const item = profile().skills.programming[0];
  const patch = M.writeField(item, F("skills", "weight"), null, "0.42");
  return patch.weight === 0.42 && typeof patch.weight === "number";
})());

check("number:une saisie non numérique est REFUSÉE (patch null)", (() => {
  const item = profile().skills.programming[0];
  return M.writeField(item, F("skills", "weight"), null, "beaucoup") === null;
})());

check("number:updateItem ignore un patch null (valeur précédente conservée)", (() => {
  const p = M.updateItem(profile(), "skills", 0, null, "programming");
  return p.skills.programming[0].weight === 0.95;
})());

check("read:un poids 0 s'affiche « 0 », pas vide (falsy)", (() => {
  const item = { name: "X", weight: 0 };
  return M.readField(item, F("skills", "weight"), null) === 0;
})());

// ── emptyItem VALIDE par construction (sinon toute sauvegarde est bloquée) ────

check("emptyItem:projects porte domains/context/type valides", (() => {
  const it = M.emptyItem("projects", profile());
  return it.domains.length === 1 && it.domains[0] === "quant"
      && it.context === "personal" && it.type === "personal" && it.name;
})());

check("emptyItem:experiences porte un domains non vide", (() => {
  const it = M.emptyItem("experiences", profile());
  return Array.isArray(it.domains) && it.domains.length === 1;
})());

check("emptyItem:skills porte un poids NUMÉRIQUE", (() => {
  const it = M.emptyItem("skills", profile());
  return typeof it.weight === "number";
})());

// ── Opérations : sémantique et bornes (fixtures à 3 éléments) ─────────────────

check("update fusionne sans écraser les champs absents du patch", (() => {
  const p = M.updateItem(profile(), "experiences", 0, { company: "NEW" });
  return eq(p.experiences[0].bullets, { fr: ["b1", "b2"], en: ["b1"] }) && p.experiences[0].id === "a";
})());

check("remove retire le bon index", (() => {
  const p = M.removeItem(profile(), "projects", 1);
  return eq(p.projects.map((x) => x.id), ["p1", "p3"]);
})());

check("move descend d'un cran", (() => {
  const p = M.moveItem(profile(), "projects", 0, 1);
  return eq(p.projects.map((x) => x.id), ["p2", "p1", "p3"]);
})());

check("move borné en HAUT (3 éléments : une mutation ferait 'bac')", (() => {
  const p = M.moveItem(profile(), "projects", 0, -1);
  return eq(p.projects.map((x) => x.id), ["p1", "p2", "p3"]);
})());

check("move borné en BAS", (() => {
  const p = M.moveItem(profile(), "projects", 2, 1);
  return eq(p.projects.map((x) => x.id), ["p1", "p2", "p3"]);
})());

check("move index source négatif → inchangé (pas de téléportation)", (() => {
  const p = M.moveItem(profile(), "projects", -1, 1);
  return eq(p.projects.map((x) => x.id), ["p1", "p2", "p3"]);
})());

// ── groups : seules les LISTES sont des catégories ───────────────────────────

check("groupsOf n'expose que les catégories-listes (radar_scores exclu)",
      eq(M.groupsOf(profile(), "skills"), ["programming", "finance"]));

check("skills:update dans une catégorie préserve les autres catégories", (() => {
  const p = M.updateItem(profile(), "skills", 0, { name: "Rust" }, "programming");
  return p.skills.programming[0].name === "Rust" && p.skills.finance.length === 1;
})());

// ── Robustesse ───────────────────────────────────────────────────────────────

check("type inconnu → profil inchangé", (() => {
  const p = profile();
  return eq(M.updateItem(p, "inconnu", 0, { x: 1 }), p);
})());

check("index hors bornes → profil inchangé", (() => {
  const p = profile();
  return eq(M.updateItem(p, "experiences", 99, { company: "X" }), p)
      && eq(M.removeItem(p, "experiences", -1), p);
})());

check("clé absente → création propre, rien d'autre touché", (() => {
  const p = profile();
  delete p.projects;
  const after = M.addItem(p, "projects");
  return after.projects.length === 1 && otherKeysIntact(p, after, "projects") === null;
})());

check("listItems sur clé absente → tableau vide", (() => {
  const p = profile();
  delete p.education;
  return eq(M.listItems(p, "education"), []);
})());

check("TYPES couvre les 4 types et chaque champ est exploitable", (() => {
  return ["experiences", "projects", "education", "skills"].every((t) => M.TYPES[t])
    && Object.values(M.TYPES).every((t) => Array.isArray(t.fields) && t.fields.length
      && t.fields.every((f) => f.name && f.type));
})());

console.log(`\n${ok} PASS / ${fail} FAIL`);
process.exit(fail === 0 ? 0 : 1);
