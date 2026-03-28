# Career OS — Roadmap

> Transformer un portfolio statique en un système expert de gestion de carrière "End-to-End".
> Chaque version ajoute une couche d'intelligence. Chaque tier ajoute une couche d'infrastructure.

---

## Naming & Branding

| Couche | Nom | Positionnement | Modèle |
|--------|-----|---------------|--------|
| Tier 1-2 | **Career OS** | Outil open-source pour développeurs | MIT — code public |
| Tier 3-4 | **Life Architect** | Produit SaaS grand public | Propriétaire — payant |

**Stratégie open-core :** Career OS reste open-source et construit la crédibilité technique. Life Architect monétise les couches cloud/SaaS au-dessus du même moteur. Le `profile.json` est le contrat commun entre les deux.

**Signal de bascule :** quand un utilisateur externe dit "je veux ça pour moi" — c'est le moment de lancer Life Architect. Avant ce signal, construire pour soi.

---

## Tiers d'infrastructure

| Tier | Infrastructure | Prérequis |
|------|---------------|-----------|
| **Tier 1** | 100% statique — GitHub Pages uniquement | Aucun |
| **Tier 2** | Statique + serveur local (PC allumé) | Python, app locale |
| **Tier 3** | Serveur cloud 24/7 | VPS / PaaS |
| **Tier 4** | SaaS multi-tenant cloud | Clerk, Stripe, Postgres multi-tenant |

---

## Versions

### ✅ V1.0 — Portfolio Intelligent *(Tier 1)*
**Tag git :** `v1.0` (repo `RoJLD.github.io`)
**Repos :** `RoJLD/RoJLD.github.io`

- [x] Site statique bilingue FR/EN
- [x] Dark / Light mode
- [x] Timeline horizontale interactive
- [x] Radar chart compétences (Canvas)
- [x] Black-Scholes pricer interactif
- [x] Monte Carlo GBM simulation
- [x] Section témoignages + recommandations PDF
- [x] Blog (2 articles)
- [x] Bouton CV flottant
- [x] Meta OG / favicon / SEO
- [x] Déployé sur GitHub Pages

---

### ✅ V1.5 — Profile API + Fondation Career OS *(Tier 1)*
**Tag git :** `v1.5` (repo `RoJLD.github.io`)
**Repos :** `RoJLD/RoJLD.github.io`

- [x] `profile.json` — source de vérité machine-readable (20 skills pondérés, 3 expériences, ikigai, lifestyle, career goals)
- [x] `hidden_edge` — 3 combos de compétences rares avec market premium calculé
- [x] `/analyzer.html` — Skill Stack Analyzer (80/20, rare combos, radar, optionality, decay)
- [x] `/match.html` — Score de compatibilité fiche de poste (keyword matching JS, séniorité, secteur, recs LM)
- [x] `/simulator.html` — Path Simulator 10 ans (12 sliders, Canvas 2D devicePixelRatio, MRR compounding, fear-setting, crossover detection)
- [x] Analytics visiteurs (Plausible — script 1 ligne, zero cookies, RGPD-friendly)

---

### ✅ V2.0 — Admin Local FastAPI *(Tier 2)*
**Tag git :** `v1.0` (repo `portfolio-admin`)
**Repos :** `RoJLD/portfolio-admin` (privé)

- [x] Interface admin locale FastAPI (localhost:8000)
- [x] Éditeur de sections portfolio + publication GitHub via API
- [x] CRM contacts (CRUD SQLite, import/export CSV)
- [x] Bot de candidature SMTP (envoi, relances auto, prévisualisation)
- [x] Config live (profil, objets emails, délais de relance)
- [x] Wizard setup.py (GitHub token, SMTP, raccourci bureau)
- [x] Templates email (12 templates FR/EN par type × cible)

---

### ✅ V2.5 — Générateur CV/LM Sémantique *(Tier 2)*
**Tag git :** `v2.0` (repo `portfolio-admin`)
**Repos :** `RoJLD/portfolio-admin`

- [x] Parsing fiche de poste — extraction must-have vs nice-to-have, ton, séniorité
- [x] Matching sémantique fiche × `profile.json` (keyword + contexte, 300+ alias FR/EN)
- [x] Génération CV restructuré via API Claude (streaming SSE, balises `===CV_START===`)
- [x] Génération LM personnalisée (ton adapté : startup / banque / fintech)
- [x] Export PDF via `window.print()` + print stylesheet
- [x] Historique générations (SQLite generator.db, date, fiche, score, statut)
- [x] Bouton "→ Candidatures" — pré-remplit `/contacts/add` depuis la JD analysée (sector→type mapping)

---

### ✅ V2.6 — Content Flywheel *(Tier 2)*
**Tag git :** `v2.6` (repo `portfolio-admin`)
**Repos :** `RoJLD/portfolio-admin`

> Transformer automatiquement les articles de blog en contenu LinkedIn/X optimisé pour le personal brand.

- [x] Ingestion articles HTML blog (html.parser stdlib, extraction texte propre sans scripts/styles/nav)
- [x] Génération via Claude : 3 formats par article (post court ~300 car. / moyen ~800 / thread X 5 tweets)
- [x] Streaming SSE avec balises `===SHORT_START===` / `===MEDIUM_START===` / `===THREAD_START===`
- [x] Copy-to-clipboard par format (pas d'API LinkedIn — friction volontaire réduite)
- [x] Calendrier éditorial : historique SQLite (flywheel.db), statut draft/published
- [x] Sauvegarde + marquage publié par format, suppression

**Insight stratégique :** le même pipeline Claude que V2.5 (CV/LM) appliqué à la production de contenu. Coût marginal quasi nul. Un article = 5-10 posts LinkedIn sur 30 jours. Personal brand amplifie toutes les autres actions du Career OS.

---

### 📋 V3.0 — Extension Chrome *(Tier 2 → Tier 3)*
**Repos :** `RoJLD/career-os-extension` (à créer)

- [ ] Manifest V3 — content script sur LinkedIn Jobs, WTTJ, Indeed, Glassdoor
- [ ] Extraction DOM de la fiche de poste depuis la page active
- [ ] Score de compatibilité en badge sur chaque annonce (calcul temps réel vs `profile.json`)
- [ ] Envoi au backend (local ou cloud) pour génération CV/LM
- [ ] Popup avec preview email + CV/LM générés
- [ ] Historique des annonces scannées (sidebar)

---

### 📋 V3.5 — Analytics & Tracking *(Tier 1 + Tier 3)*
**Repos :** `RoJLD/RoJLD.github.io` + `RoJLD/portfolio-admin`

- [x] Tier 1 : Plausible Analytics (visites, sections, referrers) *(livré V1.5)*
- [ ] Tier 3 : Pixel tracking dans les PDFs envoyés (ping serveur à l'ouverture)
- [ ] Dashboard "qui a ouvert mon CV" (date, heure, nombre d'ouvertures)
- [ ] Tracking ouverture emails de candidature
- [ ] Notifications push à l'ouverture

---

### 📋 V4.0 — Modules Lifestyle Design *(Tier 1)*
**Repos :** `RoJLD/RoJLD.github.io`

#### V4.1 — Skill Stack Analyzer *(livré V1.5 ✅)*

#### V4.2 — DEAL Framework Self-Audit
- [ ] Questionnaire interactif (activités de la semaine → freedom / skill / trap)
- [ ] Camembert animé freedom ratio (temps libéré vs temps piégé)
- [ ] Stockage localStorage, historique mensuel
- [ ] Suggestions d'élimination / automatisation basées sur les patterns

#### V4.3 — Path Simulator *(livré V1.5 ✅)*

#### V4.4 — Freedom Roadmap
- [ ] Timeline verticale interactive 3 phases (Launch / Automation / Ownership)
- [ ] Milestones avec metrics (MRR cible, heures libérées, nb clients)
- [ ] "Single most important move — 90 jours"

---

### 📋 V4.5 — Freedom Number Tracker *(Tier 1 → Tier 2 → Tier 3)*
**Repos :** `RoJLD/RoJLD.github.io` + `RoJLD/portfolio-admin`

> Tracker en temps réel la progression vers l'indépendance financière. Réponse à la question : "dans combien de jours suis-je libre ?"

**Tier 1 — Version statique (sliders manuels)**
- [ ] Inputs : dépenses mensuelles, épargne mensuelle, MRR actuel side projects, objectif de runway
- [ ] Freedom Number = dépenses × mois de runway souhaités
- [ ] Gauge animée : progression vers le freedom number
- [ ] "Days to Freedom" countdown (calculé dynamiquement)
- [ ] Scenarios : salariat seul / salariat + side / side seul

**Tier 2 — Import CSV bancaire**
- [ ] Import export de compte bancaire (CSV format BNP/SG/CA/Revolut)
- [ ] Catégorisation automatique des dépenses (fixe / variable / investissement)
- [ ] Calcul automatique du burn rate mensuel réel
- [ ] Historique 12 mois, tendances

**Tier 3 — Open Banking**
- [ ] Connexion API (Bridge by Bankin / Powens / Plaid EU)
- [ ] Refresh automatique des soldes et transactions
- [ ] Alertes "burn rate en hausse" / "MRR milestone atteint"
- [ ] Dashboard unifié : salaire + side MRR + dépenses + progression freedom

**Métriques clés :**
- Freedom Ratio = MRR / dépenses mensuelles (1.0 = indépendant)
- Days to Freedom = (freedom_number − épargne_actuelle) / épargne_mensuelle
- Burn Multiple = total_dépenses / total_revenus
- Optionality Runway = mois de vie sans revenu avec épargne actuelle

---

### 📋 V5.0 — Coaching IA & Questionnaires *(Tier 2)*
**Repos :** `RoJLD/portfolio-admin`

- [ ] Interface chat locale (Coach IA) avec contexte `profile.json` + historique candidatures
- [ ] Questionnaires MBTI / Big Five / valeurs (résultats en SQLite)
- [ ] Pre-mortem wizard (analyse des risques avant grande décision)
- [ ] DEAL Framework alimenté par Google Calendar / Toggl (API)
- [ ] Veille sectorielle auto (arXiv quant-fin, SSRN) + résumés Claude

---

### 📋 V5.5 — Job Hunter Autonome *(Tier 3)*
**Repos :** `RoJLD/portfolio-admin` + infra cloud

- [ ] Scraper LinkedIn Jobs, WTTJ, Indeed, Glassdoor (Playwright)
- [ ] Sources spécialisées : Web3 Career, CryptoJobsList, pages carrières cibles
- [ ] Scoring multicritère (match technique, culturel, géographique, salarial estimé)
- [ ] Apprentissage des préférences (feedback loop sur rejets/intérêts)
- [ ] Digest quotidien email / Telegram à 7h
- [ ] Dashboard Kanban (à voir / intéressant / candidaté / refusé)
- [ ] Alertes push "perfect match" (>90% compatibilité)

---

### 📋 V6.0 — Weak Ties & Network CRM *(Tier 2 + Tier 3)*

- [ ] Import contacts LinkedIn → catégorisation (recruteurs, peers, mentors, décideurs)
- [ ] Tracker interactions + alertes "pas de contact depuis X semaines"
- [ ] Pretextes naturels de re-contact (changement de poste, article publié)
- [ ] Messages networking personnalisés générés via Claude
- [ ] Weak ties optimizer (score de potentiel par connexion)

---

### 📋 V7.0 — Life Architect SaaS *(Tier 4)*
**Stack :** Next.js, Clerk, Stripe, Neon Postgres (RLS multi-tenant), Vercel

> Le pivot commercial : transformer l'outil personnel en produit. Career OS devient Life Architect — même moteur, couche SaaS au-dessus.
> La moat = le schéma `profile.json` + les modules d'analyse devenus une plateforme.

**Produit particuliers (B2C)**
- [ ] Auth multi-utilisateurs (Clerk)
- [ ] Chaque utilisateur a son `profile.json`, historique, coach IA
- [ ] Freemium : Tier 1 gratuit (profil + analyzers statiques) / Premium 15-30€/mois (IA + tracker)
- [ ] Onboarding guidé : importer CV → générer `profile.json` automatiquement via Claude

**Produit entreprises (B2B)**
- [ ] Cabinets de recrutement : scoring automatique de candidats vs `profile.json` de la fiche
- [ ] Écoles / universités : bilan de compétences étudiant, hidden edge, optionality score
- [ ] Prix : 200-500€/mois par organisation, dégressif au volume
- [ ] API publique de profil (`/api/profile/:slug`) pour intégration ATS

**Infrastructure**
- [ ] Billing Stripe (freemium / pro / enterprise)
- [ ] Multi-tenant Neon Postgres (row-level security par tenant)
- [ ] Marketplace optionnelle (recruteurs × candidats — double-sided)
- [ ] OIDC / SSO entreprise (SAML pour les gros comptes)
- [ ] Déploiement Vercel (CI/CD natif, preview URLs, edge functions)

**Moat technique :** le `profile.json` devient un standard ouvert. Les utilisateurs exportent, importent, partagent leur profil. Network effects dès que recruteurs et candidats utilisent le même format.

---

## Matrice fonctionnalités × tiers

| Fonctionnalité | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|:---:|:---:|:---:|:---:|
| Portfolio bilingue, démos, blog | ✅ | ✅ | ✅ | ✅ |
| `profile.json` structuré | ✅ | ✅ | ✅ | ✅ |
| Skill Stack Analyzer | ✅ | ✅ | ✅ | ✅ |
| Score match fiche de poste (keywords) | ✅ | ✅ | ✅ | ✅ |
| Path Simulator 10 ans | ✅ | ✅ | ✅ | ✅ |
| DEAL Framework self-audit | ✅ | ✅ | ✅ | ✅ |
| Freedom Roadmap visuel | ✅ | ✅ | ✅ | ✅ |
| Freedom Number (sliders manuels) | ✅ | ✅ | ✅ | ✅ |
| Analytics visiteurs (Plausible) | ✅ | ✅ | ✅ | ✅ |
| Admin local (portfolio + CRM) | ❌ | ✅ | ✅ | ✅ |
| Générateur CV/LM Claude AI | ❌ | ✅ | ✅ | ✅ |
| Content Flywheel (blog → LinkedIn/X) | ❌ | ✅ | ✅ | ✅ |
| Extension Chrome | ❌ | ⚠️ tunnel | ✅ | ✅ |
| CRM candidatures (SQLite/Postgres) | ❌ | ✅ | ✅ | ✅ |
| Job scraper automatique | ❌ | ⚠️ PC on | ✅ | ✅ |
| Envoi email automatisé | ❌ | ✅ | ✅ | ✅ |
| Coach carrière IA | ❌ | ✅ | ✅ | ✅ |
| Freedom Number (import CSV) | ❌ | ✅ | ✅ | ✅ |
| Pixel tracking CV | ❌ | ⚠️ tunnel | ✅ | ✅ |
| Bot relance candidatures 24/7 | ❌ | ❌ | ✅ | ✅ |
| Job hunter autonome 24/7 | ❌ | ❌ | ✅ | ✅ |
| Freedom Number (Open Banking live) | ❌ | ❌ | ✅ | ✅ |
| Network CRM | ❌ | ❌ | ✅ | ✅ |
| Multi-user SaaS (Life Architect) | ❌ | ❌ | ❌ | ✅ |
| B2B recruteurs / écoles | ❌ | ❌ | ❌ | ✅ |
| API publique de profil | ❌ | ❌ | ❌ | ✅ |
| Marketplace recruteurs × candidats | ❌ | ❌ | ❌ | ✅ |

---

## Analyse stratégique

### Content Flywheel — Pourquoi c'est puissant
Le pipeline est identique à V2.5 (Claude + `profile.json`), mais le ROI est différent : au lieu d'optimiser pour un recruteur ponctuel, on optimise pour construire une audience durable. Un article de blog = 5-10 posts LinkedIn sur 30 jours. Le personal brand amplifie toutes les autres actions du Career OS (recruteurs inbound, opportunités réseau, crédibilité).

**Risque :** LinkedIn API restrictive pour le posting automatique. Stratégie : génération + clipboard (friction volontaire). L'IA propose, l'humain publie.

### Freedom Number Tracker — Le module le plus personnel
C'est le module qui transforme Career OS d'un outil de recherche d'emploi en un système de design de vie. La "Freedom Number" est le vrai objectif derrière tous les autres modules : le CV parfait, le job idéal, le réseau, le side business — tout pointe vers ce chiffre.

**MVP Tier 1 :** 3 sliders (dépenses, épargne, MRR cible) + une gauge animée = 100 lignes de JS. Peut être intégré à `/simulator.html` ou page dédiée `/freedom.html`.

**Piège à éviter :** l'Open Banking est complexe (GDPR, PSD2, gestion des tokens). Commencer Tier 1 manuel, puis Tier 2 CSV avant toute API.

### Life Architect SaaS — La question de timing
Le pivot SaaS est tentant mais risqué à lancer trop tôt. La vraie question : à quel moment Career OS est suffisamment différencié pour que quelqu'un paie ?

**Signal de maturité :** quand les Tier 1-2 sont complets et qu'un utilisateur externe dit "je veux ça pour moi". Avant ce signal, construire pour soi d'abord.

**Stack Tier 4 :** Next.js App Router + Clerk + Stripe + Neon Postgres (RLS) + Vercel. Le schéma `profile.json` devient le contrat d'API public.

### Open-Core — Pourquoi séparer Career OS et Life Architect
Career OS (Tier 1-2) reste MIT open-source : crédibilité technique, contributions communauté, portfolio visible. Life Architect (Tier 3-4) est propriétaire : monet­isation des couches infrastructure et SaaS. Les deux partagent le même moteur `profile.json`. Pas de conflit — c'est le modèle classique open-core (ex : GitLab, Sentry, Metabase).

---

## Tags git

| Tag | Repo | Description |
|-----|------|-------------|
| `v1.0` | `RoJLD.github.io` | Portfolio HTML statique |
| `v1.5` | `RoJLD.github.io` | Profile API + Skill Analyzer + Match + Simulator + Plausible |
| `v1.0` | `portfolio-admin` | Admin FastAPI local (portfolio + CRM + SMTP) |
| `v2.0` | `portfolio-admin` | Générateur CV/LM Claude API + lien → Candidatures |
| `v2.6` | `portfolio-admin` | Content Flywheel (blog → LinkedIn/X) |
| `v3.0` | `portfolio-admin` | *(prévu)* Extension Chrome + cloud |

---

*Dernière mise à jour : 2026-03-28*
