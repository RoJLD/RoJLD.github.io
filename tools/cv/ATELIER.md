# Kleos — atelier CV, `.docx` ATS et lettre ancrée

Serveur **privé** (jamais exposé par GitHub Pages) qui transforme une fiche de poste
en dossier de candidature. Le ciblage et la rédaction passent par le résolveur LLM
souverain d'ELYSIUM (`career/core/llm_client.py`, SIGIL-1714).

> **Kleos** (κλέος) : chez Homère, le renom qui circule par la parole d'autrui et
> survit à celui qui l'a gagné. Un CV et une lettre ne sont rien d'autre — une
> réputation confiée à un tiers pour qu'il la répète.

## Ce que l'atelier produit

| Bouton | Route | Sortie | Porte |
|---|---|---|---|
| CV ciblé | `POST /generate` | PDF | verdict de ciblage |
| CV ATS | `POST /generate-docx` | `.docx` (texte réel, 0 tableau) | verdict de ciblage |
| Lettre ancrée | `POST /generate-letter` | PDF | ciblage **puis** ancrage |

Trois pages : `/` atelier · `/cms` édition structurée du profil · `/edit` JSON brut.

### Les deux refus, à ne pas confondre

- **`409` texte brut — le CIBLAGE a échoué.** Aucun champ n'a pu être lu de la fiche
  (`_field_provenance` entièrement `absent`/`default`). Rien n'a été rédigé. Le bouton
  *« Générer quand même »* réarme explicitement en mode générique — et le fichier
  s'appelle alors `cv_GENERIQUE.pdf`, jamais `cv_cible.pdf`.
- **`409` JSON `{blocking, sentences}` — l'ANCRAGE a bloqué.** La lettre existe, mais
  une ou plusieurs affirmations ne tracent pas jusqu'au profil. L'UI affiche quelles
  phrases et pourquoi. Rien ne sort : `render_letter_html_gated` est le seul chemin
  vers des octets, et il exige `verdict["ok"] is True`.

**Politique du ciblage dégradé : refus par défaut, réarmement explicite.** Livrer
en avertissant ferait du générique le chemin par défaut — celui qu'on prend distrait,
un soir de candidature à la chaîne. En inversant la charge, l'accident devient
impossible sans que la capacité disparaisse.

## Exposition réseau

Par défaut l'atelier écoute sur **127.0.0.1 seul** et n'accepte que les `Host`
loopback. C'est délibéré : ses pages servent le **profil entier** et ses routes POST
**écrivent** `profile.json`.

| Variable | Défaut | Effet |
|---|---|---|
| `ATELIER_BIND` | `127.0.0.1` | adresse d'écoute (`0.0.0.0` en conteneur) |
| `ATELIER_HOSTS` | *(vide)* | hôtes `Host` **ajoutés** au loopback, jamais substitués |

Quitter le loopback journalise un AVERTISSEMENT au démarrage : deux gardes tombent
d'un coup et ce qui les remplace est hors du processus. Déploiement cluster (privé,
`kleos.elysium.local`, basicAuth + tailnet-only) :
`gitops/manifests/elysium-anthropos/11-kleos-atelier.yaml` dans ELYSIUM.

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
- **[DÉGRADÉ] Fallback** : le résolveur n'a pas pu joindre de LLM et est retombé
  sur le cfg défaut (CV générique). Le PDF **change de nom** (`cv_GENERIQUE.pdf`),
  l'en-tête `X-CV-Degrade: 1` accompagne la réponse et la barre de statut passe au
  rouge avec le motif.

  > **Correction du 2026-08-03 (premier usage réel).** Ce paragraphe affirmait que
  > le repli « est bruyant […] jamais silencieux » parce qu'un WARNING
  > `cv_target: extraction cfg échouée (...) — cfg défaut` part dans les logs.
  > C'était vrai du **journal** et faux du **produit** : lors de la génération sur
  > la fiche Amundi, un CV générique a été livré sous le nom `cv_cible.pdf` avec le
  > statut « Ciblage: general~0.0 » — indiscernable d'un succès pour qui ne connaît
  > pas le code. Le WARNING parlait à la console pendant que le PDF partait chez le
  > recruteur. **Un garde qui ne parle qu'à la console ne garde rien.**
  >
  > Le signal n'est plus l'étiquette `general~0.0` (une fiche peut légitimement la
  > produire) mais `_field_provenance` : un cfg de repli a TOUS ses champs en
  > `absent`/`default`. Cf. `atelier.ciblage_degrade` / `atelier.verdict_ciblage`.

## Troubleshooting

| Symptôme | Cause probable | Remède |
|---|---|---|
| `X-CV-Target: general~0.0` systématique | Sibling ELYSIUM absent, ou aucun backend LLM configuré | Vérifier `../ELYSIUM/satellites/anthropos/apps/career/core/llm_client.py` existe ; configurer un backend (cf. prérequis 2) |
| `litellm.Timeout after 120.0s` sur `local-precision` | `deepseek-r1:32b` est un modèle de **raisonnement** : il dépense son budget en `<think>` et dépasse le timeout du gateway sur une fiche longue (mesuré : 3 échecs sur 3 pour 4908 caractères). `core.llm_client.complete` n'expose aucun paramètre de timeout | Aucune action : `_sovereign_complete` bascule désormais sur `local-qwen` et journalise la descente. Forcer l'ordre avec `CV_LLM_TIERS=local-qwen,local-precision` |
| `RuntimeError: llm_client souverain introuvable` (logs) | Le sibling ELYSIUM n'est pas à `../ELYSIUM` | Cloner/placer ELYSIUM au bon endroit |
| `Erreur: HTTP 500` dans l'UI | Playwright/chromium absent | `python -m playwright install chromium` |
| Le tier gateway échoue en silence puis anthropic est appelé | Import `scripts.governance.sigma_llm_gateway` KO (racine ELYSIUM non sur `sys.path`) | Corrigé par SP7b (`_sovereign_complete` insère la racine ELYSIUM) ; vérifier les WARNING de downgrade dans les logs |

## Note d'architecture

Le pipeline (`extract_cfg` → `select_experiences` → `build_structured_cv` → PDF) est
**pur et testé** ; seule la frontière LLM (`_sovereign_complete`) touche le réseau.
Les tests unitaires injectent un `complete_fn` factice (aucun réseau) ; le test
d'intégration `test_extract_cfg_non_default_with_real_resolution` exerce le vrai
chemin de résolution (skip si le sibling est absent, p. ex. en CI GitHub Pages).
