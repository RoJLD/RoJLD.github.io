# Atelier CV ciblé — human-test (SP7b)

Serveur **local privé** (jamais exposé par GitHub Pages) qui transforme une fiche de
poste en CV ciblé PDF. Le ciblage passe par le résolveur LLM souverain d'ELYSIUM
(`career/core/llm_client.py`, SIGIL-1714).

## Prérequis

1. **Checkout ELYSIUM sibling** : le repo `ELYSIUM` doit être cloné à côté du site,
   à `../ELYSIUM` (soit `VScode_Project/ELYSIUM/`). Le résolveur y cherche
   `satellites/anthropos/apps/career/core/llm_client.py`.
2. **Un backend LLM atteignable** (l'un des trois, essayés dans cet ordre) :
   - Gateway souverain ELYSIUM (`scripts.governance.sigma_llm_gateway`) — préféré,
     applique le budget cap SIGIL-529 + la télémétrie ;
   - `CAREER_LLM_BASE_URL` pointant un endpoint OpenAI-compat local (ex. ollama
     `http://127.0.0.1:11434/v1`) ;
   - `settings.anthropic_api_key` (dans `career/config.yaml`) — legacy, dernier recours.
3. Dépendances Python du site (`playwright` installé + `python -m playwright install chromium`
   pour le rendu PDF).

## Lancer

```bash
python tools/cv/atelier.py
```
→ ouvre `http://127.0.0.1:8010`. Colle une fiche de poste dans la zone de texte,
choisis la langue, clique **Générer le CV ciblé (PDF)**.

## Critère de succès (ce qui prouve que le ciblage a réellement eu lieu)

Après génération, la barre de statut affiche `Ciblage: <relevance_key>~<min_relevance>`
(header HTTP `X-CV-Target`).

- **[OK] Succès** : `X-CV-Target` **≠ `general~0.0`** — p. ex. `quant~0.7`. Le LLM a
  déduit un cfg spécifique (clé de pertinence adaptée et/ou seuil > 0), donc le CV est
  filtré vers les expériences pertinentes.
- **[DÉGRADÉ] Fallback (attendu si aucun backend)** : `general~0.0` — le résolveur
  n'a pas pu joindre de LLM et est retombé sur le cfg défaut (CV générique). C'est
  **bruyant** : un WARNING `cv_target: extraction cfg échouée (...) — cfg défaut`
  apparaît dans les logs. Ce n'est jamais silencieux.

## Troubleshooting

| Symptôme | Cause probable | Remède |
|---|---|---|
| `X-CV-Target: general~0.0` systématique | Sibling ELYSIUM absent, ou aucun backend LLM configuré | Vérifier `../ELYSIUM/satellites/anthropos/apps/career/core/llm_client.py` existe ; configurer un backend (cf. prérequis 2) |
| `RuntimeError: llm_client souverain introuvable` (logs) | Le sibling ELYSIUM n'est pas à `../ELYSIUM` | Cloner/placer ELYSIUM au bon endroit |
| `Erreur: HTTP 500` dans l'UI | Playwright/chromium absent | `python -m playwright install chromium` |
| Le tier gateway échoue en silence puis anthropic est appelé | Import `scripts.governance.sigma_llm_gateway` KO (racine ELYSIUM non sur `sys.path`) | Corrigé par SP7b (`_sovereign_complete` insère la racine ELYSIUM) ; vérifier les WARNING de downgrade dans les logs |

## Note d'architecture

Le pipeline (`extract_cfg` → `select_experiences` → `build_structured_cv` → PDF) est
**pur et testé** ; seule la frontière LLM (`_sovereign_complete`) touche le réseau.
Les tests unitaires injectent un `complete_fn` factice (aucun réseau) ; le test
d'intégration `test_extract_cfg_non_default_with_real_resolution` exerce le vrai
chemin de résolution (skip si le sibling est absent, p. ex. en CI GitHub Pages).
