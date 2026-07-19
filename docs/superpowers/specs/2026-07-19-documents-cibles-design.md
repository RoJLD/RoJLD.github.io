# Documents ciblés — conception commune (CV templates + lettre de motivation)

**Date** : 2026-07-19
**Statut** : approuvé (cadre)
**Portée** : une chaîne unique « fiche de poste → document ciblé », instanciée par le CV
(projection de faits) et la lettre de motivation (prose générée). Plus une banque de
templates, en donnée et non en code.

## 1. Ce qui existe déjà (mesuré, pas supposé)

| Brique | État | Fichier |
|---|---|---|
| Lecture de fiche de poste → `cfg` de ciblage | **existe** (LLM) | `tools/cv/cv_target.py` |
| Profils de contenu (quant / dev / risk / full) | **existe**, 4 profils | `tools/cv/cv_profiles.json` |
| Sélection + projection en `structured_cv` | **existe**, fonction pure | `tools/cv/cv_select.py` |
| Rendu HTML | **existe**, **un seul** template | `tools/cv/cv_render.py` |
| HTML → PDF | **existe** (Playwright/Chromium) | `tools/cv/cv_pdf.py` |
| Atelier local (`/generate`) | **existe** | `tools/cv/atelier.py` |
| Lettre de motivation | **rien** | — |

Le ciblage n'est donc pas à construire : il manque la **forme** (un seul template) et le
**second document** (la lettre).

### La contrainte structurante : la paire miroir

Le rendu du CV existe en deux implémentations qui doivent rester **identiques à l'octet** :

| | lignes | rôle |
|---|---|---|
| `tools/cv/cv_render.py` | 187 | autoritaire — produit les PDF |
| `assets/js/cv-render.js` | 176 | navigateur — aperçu dans l'atelier |

`CV_CSS` y est dupliqué : 1483 octets, 23 règles, 8 couleurs, 6 tailles de police. Un
harnais de 42 cas de parité vérifie l'identité, et il a déjà attrapé trois bugs dormants.

**Conséquence** : ajouter N templates *en tant que code* coûterait **2N** artefacts à
maintenir synchronisés, et autant de cas de parité. C'est le fait qui détermine
l'architecture.

## 2. Chaîne commune

```
                        fiche de poste
                              │
                              ▼
                     job_context  (cv_target étendu)
        { cfg de sélection · entreprise · poste · exigences · registre · marché }
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
        CV — projection                  LETTRE — prose
   select_experiences (pur)        select_evidence (pur)
   build_structured_cv (pur)       draft (LLM)
              │                          │
              │                    check_grounding (LLM) ──► BLOQUANT
              │                          │
              └──────► template ◄────────┘
                    (donnée partagée)
                          │
                          ▼
                    render_html → cv_pdf.html_to_pdf_bytes
```

**Commun** : `profile.json` comme unique source de faits, la lecture de fiche de poste, la
banque de templates, la chaîne rendu→PDF, l'atelier local.
**Distinct** : le CV réordonne des faits et ne peut structurellement rien inventer ; la
lettre en produit et le peut. Le vérificateur n'existe donc que du côté lettre.

## 3. Templates en donnée

### Modèle

Un fichier par template, `cv/templates/<id>.json` :

```json
{
  "id": "sobre",
  "label": { "fr": "Sobre", "en": "Plain" },
  "meta": {
    "pages": 1,
    "market": ["FR", "EU"],
    "tone": "corporate",
    "ats_safe": true,
    "sections": ["identity", "experience", "education", "skills", "languages"]
  },
  "style": {
    "page":    { "size": "A4", "margin": "12mm 14mm" },
    "palette": { "ink": "#1a1a2e", "accent": "#4361ee", "muted": "#555", "rule": "#dde" },
    "type":    { "base": "9.8pt", "h1": "17pt", "h2": "10.5pt", "small": "8pt" },
    "density": { "line": 1.3, "section_gap": "6pt", "bullet_gap": "2pt" }
  }
}
```

`meta` est la partie « connaître parfaitement les templates » : elle permet à l'étape de
ciblage de **choisir** le template à partir de la fiche de poste (marché visé, registre,
contrainte ATS, budget de pages), au lieu de laisser l'utilisateur deviner.

`style` est ce que le moteur consomme.

### Moteur

Une fonction `build_css(style) -> str` de chaque côté du miroir. Ajouter un template coûte
alors **un fichier de données**, pas deux implémentations.

**Garde-fou de non-régression, mécaniquement vérifiable** : le template par défaut
(`sobre`) doit produire un CSS **octet pour octet identique** à l'actuel `CV_CSS`. C'est
exactement le motif employé pour la migration de l'article — l'ancien artefact est figé en
fixture et la génération doit le reproduire.

### Le miroir navigateur

Les templates sont de la donnée ; le navigateur doit y accéder sans dépendance réseau ni
`fetch` (le site est statique et doit fonctionner hors ligne). Un builder
`tools/build_cv_templates.py` — huitième du même patron que les sept existants — génère
`assets/js/cv-templates.js` depuis les JSON. La donnée reste la source ; le bundle JS en
est un artefact généré, jamais édité à la main.

### Harnais de parité

Il teste aujourd'hui le rendu. Il testera :
1. le **moteur** `build_css` une fois (mêmes entrées → même CSS des deux côtés) ;
2. **un cas générique par template**, ajouté automatiquement en parcourant
   `cv/templates/*.json` — pas une liste écrite à la main, qui prendrait du retard.

### Phase 2 — mise en page libre (conçue, non construite)

La phase 2 fait varier la **structure** : colonne latérale, ordre des sections, encadrés,
photo. Le modèle ci-dessus ne l'interdit pas : `meta.sections` porte déjà la liste et son
ordre, et une clé `layout` viendra s'ajouter à côté de `style`. Rien de la phase 1 n'est à
défaire — c'est la condition qui rend l'étagement légitime plutôt que dilatoire.

## 4. Lettre de motivation

### Ce qu'est une lettre ici

Une fonction de (faits de `profile.json`) × (fiche de poste) × (squelette) → prose, dont
**chaque affirmation factuelle trace vers une entrée de `profile.json`**.

`letters/skeletons/<id>.<lang>.md` porte un squelette de **guidage**, pas des fentes
rigides : chaque section déclare son intention, son registre et un budget de longueur. Le
modèle rédige librement à l'intérieur.

### Pipeline

1. `job_context` — réutilise `cv_target`, étendu pour extraire aussi entreprise, intitulé,
   exigences saillantes et registre.
2. `select_evidence(profile, job_context)` — **pur** : les 2-3 expériences/projets les plus
   pertinents, via le même score de pertinence que le CV. La lettre parle donc des mêmes
   faits que le CV qui l'accompagne.
3. `draft(profile_facts, job_context, skeleton, lang)` — LLM. Ne reçoit **que** les faits
   sélectionnés, jamais `profile.json` entier : ce qu'on ne donne pas ne peut pas être
   déformé.
4. `check_grounding(letter, profile)` — LLM, **appel séparé**, la lettre passée en entrée
   *non fiable*. Le rédacteur ne juge pas sa propre copie dans le même contexte.
5. Export — **bloqué** tant qu'une affirmation ne trace pas.

### Le vérificateur d'ancrage

Sortie : une liste d'affirmations, chacune avec son support.

```
[
  { "affirmation": "j'ai modélisé des stratégies de couverture dynamique avec EY",
    "supporte": true,  "source": "education[ece].capstone" },
  { "affirmation": "j'ai dirigé une équipe de cinq personnes",
    "supporte": false, "source": null }
]
```

Toute entrée `supporte: false` bloque l'export et s'affiche avec son motif.

**Faiblesse à traiter, sinon la garantie est creuse** : un extracteur peut *sous-extraire*
— une affirmation jamais extraite n'est jamais examinée, et passe. La parade est une
**couverture par partition** : chaque phrase de la lettre doit être rattachée à exactement
une catégorie (affirmation factuelle · motivation · formule de politesse · liaison). Toute
phrase non rattachée bloque. La question invérifiable « a-t-on tout extrait ? » devient
ainsi la question vérifiable « la partition couvre-t-elle toutes les phrases ? ».

### Le sens du fail-safe s'inverse

C'est le point de conception le plus important, et il est contre-intuitif.

| Fonction | Échec du modèle | Valeur inerte |
|---|---|---|
| Classification Gmail (`classify_with_fallback`) | → `unknown` | ne déclenche rien |
| Vérificateur d'ancrage | → **export bloqué** | ne publie rien |

Le repli sûr n'est pas une propriété du mécanisme : il dépend de ce que coûte chaque
erreur. Une lettre fausse chez un recruteur coûte infiniment plus qu'une lettre non
générée. Si le vérificateur ne peut pas tourner, **rien ne sort**.

### Le vérificateur est une porte, pas un filtre

Il bloque et explique ; il ne corrige jamais en silence. L'arbitrage — corriger le profil
ou retirer la phrase — appartient à l'humain. Un filtre autonome qui réécrirait la prose
recréerait exactement le risque qu'il est censé supprimer.

## 4bis. Découpage en deux livraisons

Ce document est un **cadre commun** ; il ne se livre pas d'un bloc. L'auto-revue du spec
conclut à deux plans d'implémentation séquentiels, chacun produisant un logiciel
fonctionnel et testable :

| Plan | Contenu | Dépend de |
|---|---|---|
| **A — Templates (phase 1)** | extraction de `CV_CSS` en donnée, `build_css` des deux côtés du miroir, bundle navigateur généré, `meta` par template, choix dans l'atelier, 2-3 templates | rien |
| **B — Lettre** | `job_context` élargi, `select_evidence`, squelettes, brouillon, vérificateur d'ancrage + partition, export bloquant, onglet atelier | A (pour le rendu et le PDF) |

Les livrer ensemble diluerait les deux : A est une **extraction** à risque faible et à
garde-fou mécanique (identité octet du CSS par défaut) ; B est une **création** dont
l'essentiel du travail est la garantie d'ancrage. Ce ne sont ni les mêmes tests ni les
mêmes modes de défaillance.

## 5. Fichiers

**Créer**
- `cv/templates/sobre.json` — le template actuel, extrait en donnée
- `cv/templates/<autres>.json` — les nouveaux
- `tools/build_cv_templates.py` — génère le bundle navigateur
- `assets/js/cv-templates.js` — **généré**
- `tools/cv/cv_letter.py` — squelettes, brouillon, sélection de preuves
- `tools/cv/cv_grounding.py` — extraction d'affirmations, partition, verdict
- `letters/skeletons/standard.{fr,en}.md`
- tests : `test_cv_templates.py`, `test_cv_letter.py`, `test_cv_grounding.py`

**Modifier**
- `tools/cv/cv_render.py` + `assets/js/cv-render.js` — `build_css(style)` des deux côtés
- `tools/cv/cv_target.py` — `job_context` élargi
- `tools/cv/atelier.py` — choix du template, onglet lettre
- `tools/cv/gen_parity_cases.py` + `tools/cv/parity.js` — un cas par template

## 6. Non-régression

- Le CSS du template `sobre` est **identique à l'octet** à l'actuel `CV_CSS` (fixture figée).
- Les 8 PDF préfabriqués (`cv/prefab/*.pdf`) restent générés par le même chemin.
- Les 42 cas de parité existants restent verts, sans modification.
- L'atelier continue de fonctionner sans template choisi (défaut = `sobre`).

## 7. Hors périmètre

- La mise en page libre (phase 2 — conçue pour, non construite).
- L'envoi de la lettre (aucune intégration mail).
- Le contrôle fin de pagination multi-pages.
- La traduction automatique d'une lettre d'une langue à l'autre : chaque langue a son
  squelette et son brouillon, comme les articles ont leur `.md` par langue.
