// Vérifie que la sélection de domaines depuis le graphe filtre réellement (min_relevance:2).
const assert = require('assert');
const CVSelect = require('../../assets/js/cv-select.js');

const profile = {
  experiences: [
    { id: 'a', title: 'A', domains: ['quant'], relevance: { general: 0.9, quant: 0.8 } },
    { id: 'b', title: 'B', domains: ['bio'],   relevance: { general: 0.9 } },
  ],
};

// min_relevance:2 (> échelle) => seule l'intersection de domaines compte
const picked = CVSelect.selectExperiences(profile, { domains_in: ['quant'], relevance_key: 'general', min_relevance: 2 });
assert.strictEqual(picked.length, 1, 'seule l\'exp du domaine quant');
assert.strictEqual(picked[0].id, 'a');

// contre-preuve : min_relevance:0 passerait TOUT (le bug qu'on évite)
const naive = CVSelect.selectExperiences(profile, { domains_in: ['quant'], relevance_key: 'general', min_relevance: 0 });
assert.strictEqual(naive.length, 2, 'min_relevance:0 = sélection inerte (toutes passent)');

console.log('OK test_graph_cv');
