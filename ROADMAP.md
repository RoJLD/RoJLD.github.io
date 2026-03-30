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

### 📋 V2.7 — Quick Wins Admin *(Tier 2)* — Vague 1
**Repos :** `RoJLD/portfolio-admin`

> Améliorations à fort impact quotidien, zéro nouvelle infrastructure. Tous les modules en silo deviennent un système cohérent.

**Dashboard unifié**
- [ ] Page d'accueil `/` avec stats globales : candidatures actives, générations récentes, posts en draft, contacts sans relance
- [ ] Graphique mini-pipeline : nb candidatures par statut (sparkline)
- [ ] Quick actions : bouton "Nouvelle candidature", "Générer CV", "Nouveau post"

**Networking Email Generator**
- [ ] Bouton "Générer message" dans `/contacts` à côté de chaque contact
- [ ] Input : nom + banque/entreprise + poste + contexte (cold / warm intro / post-article / après entretien)
- [ ] Output Claude : message LinkedIn 5-6 lignes personnalisé, ton professionnel non-servile
- [ ] Même pattern SSE que generator.py — zéro nouvelle infrastructure

**Recherche globale FTS5**
- [ ] Barre de recherche dans le header de l'admin
- [ ] SQLite FTS5 (`CREATE VIRTUAL TABLE fts USING fts5`) sur contacts + candidatures + historique générations
- [ ] Résultats typés avec icône et lien direct vers la ressource

**profile.json V2**
- [ ] Ajouter `projects[]` (projets perso avec stack + impact chiffré)
- [ ] Ajouter `certifications[]`
- [ ] Ajouter `availability` (date dispo, préférence remote/hybrid/présentiel)
- [ ] Ajouter `target_roles[]` (remplace le type générique — ex: ["Quant Researcher", "Risk Analyst"])
- [ ] Backward-compatible — tous les champs optionnels

---

### 📋 V2.8 — match.html V2 + Simulator V2 *(Tier 1)* — Vague 1
**Repos :** `RoJLD/RoJLD.github.io`

> Précision et richesse des outils d'analyse Tier 1. Zéro changement d'infrastructure.

**match.html — précision**
- [ ] Détection de bigrams — "machine learning", "interest rate" pèsent plus que les mots isolés
- [ ] Signal négatif — pénalité si JD contient "junior/débutant/0-2 ans" et profil senior (évite les faux espoirs)
- [ ] Score percentile — "top 20% de tes JDs analysées" au lieu d'un pourcentage brut (nécessite localStorage des scores)
- [ ] Stemming léger JS — "financier→finance", "modéliser→modèle", "développer→développement"

**simulator.html — scénarios**
- [ ] Sauvegarde de 3 scénarios nommés (localStorage) — comparer "CDI banque" vs "freelance+side" sur le même canvas
- [ ] Toggle inflation — courbes en euros constants (déflateur 2% annuel)
- [ ] Intégration Freedom Number — annotation visuelle quand MRR > dépenses mensuelles sur la courbe redesigned

---

### 📋 V2.9 — Generator V2 *(Tier 2)* — Vague 1
**Repos :** `RoJLD/portfolio-admin`

> Le générateur CV/LM devient itératif et apprend de tes préférences.

- [ ] **Multi-turn refinement** — input "feedback" qui relance le stream avec le draft précédent en contexte (ex: "rends la LM 30% plus courte", "ton plus assertif", "retire les bullet points")
- [ ] **Variants A/B** — générer 2 accroches LM différentes côte à côte, choisir la meilleure
- [ ] **Feedback loop** — boutons "bonne génération ✓ / mauvaise ✗" qui logguent en SQLite ; dans 3 mois : analyse des patterns de tes meilleures LM
- [ ] **Email templates scoring** — tracker les relances qui ont obtenu des réponses (taux de réponse par template, A/B sujet)

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

### 📋 V3.1 — Interview Prep Module *(Tier 2)* — Vague 2
**Repos :** `RoJLD/portfolio-admin`

> Suite logique du generator : tu envoies le CV, maintenant tu te prépares à l'entretien. Mêmes inputs (JD + `profile.json`), output différent.

- [ ] Input : JD + sélection du type d'entretien (technique / comportemental / case study / fit)
- [ ] Génération de 10-15 questions probables avec réponses STAR structurées basées sur TES vraies expériences
- [ ] Mode practice : Claude pose la question en streaming, tu réponds en textarea, il critique (structure STAR, précision, impact chiffré)
- [ ] Scoring de la réponse : clarté / structure / pertinence / conviction
- [ ] Historique sessions SQLite (questions, tes réponses, scores)
- [ ] Export PDF "fiche de préparation" avant entretien

---

### 📋 V3.2 — Kanban Candidatures + Funnel *(Tier 2)* — Vague 2
**Repos :** `RoJLD/portfolio-admin`

> La vue liste est fonctionnelle mais pas motivante. Vue Kanban + analytics du pipeline.

- [ ] Vue Kanban drag-and-drop — colonnes : À envoyer / Envoyé / Relancé / Répondu / Entretien / Refusé / Accepté
- [ ] Modèle SQLite inchangé — nouvelle vue côté frontend uniquement
- [ ] Funnel analytics : taux de conversion à chaque étape (envoyé→réponse, réponse→entretien)
- [ ] "Expected value" du pipeline : nb entretiens prévus × taux historique de conversion
- [ ] Alertes visuelles : candidatures sans mouvement depuis X jours (highlight orange)
- [ ] Toggle vue liste / vue kanban persisté en localStorage

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
- [ ] Intégration `/simulator.html` — annotation quand MRR atteint dépenses sur la courbe redesigned

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

### 📋 V4.6 — Skill Gap Radar *(Tier 1)* — Vague 2
**Repos :** `RoJLD/RoJLD.github.io`

> Visualiser l'écart entre son profil actuel et le profil idéal pour un rôle cible. Zéro Claude — pure logique JS.

- [ ] JSON de 5-6 profils-types (Quant Researcher / Risk Analyst / Quant Dev / Fintech PM / AM / IBD)
- [ ] Canvas radar overlay : profil actuel (bleu) vs profil idéal (rouge) — même composant que l'analyzer
- [ ] Gap analysis : "il te manque C++ proficiency, exchange connectivity — +2 formation estimée"
- [ ] Action plan auto-généré : ressources suggérées par gap (livres, certifications, projets)
- [ ] Intégration `profile.json` — mise à jour automatique au fil du temps

---

### 📋 V5.0 — Coaching IA & Questionnaires *(Tier 2)*
**Repos :** `RoJLD/portfolio-admin`

- [ ] Interface chat locale (Coach IA) avec contexte `profile.json` + historique candidatures
- [ ] Questionnaires MBTI / Big Five / valeurs (résultats en SQLite)
- [ ] Pre-mortem wizard (analyse des risques avant grande décision)
- [ ] Decision Journal — table SQLite (décision, contexte, outcome attendu, outcome réel), patterns Claude
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

### 📋 V5.7 — Telegram Bot Digest *(Tier 3)* — Vague 3
**Repos :** `RoJLD/portfolio-admin` + infra cloud

> Point d'entrée Tier 3 le plus simple et le plus utile au quotidien. Aucune UI à construire — l'interface, c'est Telegram.

- [ ] Daily digest à 7h : "X candidatures en cours, Y relances dues, Z entretiens cette semaine"
- [ ] `/status` → résumé pipeline (nb par statut)
- [ ] `/match <texte ou url>` → score de compatibilité immédiat vs `profile.json`
- [ ] `/generate <poste>` → déclenche une génération CV/LM, résultat en DM
- [ ] Notifications "CV ouvert" (pixel tracking) + "réponse reçue" (email parsing)
- [ ] Alerte "Freedom Ratio milestone" : notification quand MRR dépasse 25% / 50% / 100% des dépenses
- [ ] Stack : python-telegram-bot + webhook FastAPI existant + SQLite existant — zéro nouvelle infrastructure

---

### 📋 V6.0 — Weak Ties & Network CRM *(Tier 2 + Tier 3)*

- [ ] Import contacts LinkedIn → catégorisation (recruteurs, peers, mentors, décideurs)
- [ ] Tracker interactions + alertes "pas de contact depuis X semaines"
- [ ] Pretextes naturels de re-contact (changement de poste, article publié)
- [ ] Messages networking personnalisés générés via Claude
- [ ] Weak ties optimizer (score de potentiel par connexion)

---

### 📋 V6.5 — MCP Server Career OS *(Tier 2 → Tier 3)* — Vague 3
**Repos :** `RoJLD/portfolio-admin`

> L'API-first de Career OS. Expose toutes les données et actions comme outils MCP — n'importe quel agent IA peut interroger ton pipeline de carrière. C'est la fondation qui rend tout le reste composable.

**Outils MCP exposés**
- [ ] `get_profile()` — retourne `profile.json` structuré
- [ ] `get_pipeline_status()` — nb candidatures par statut, dernières activités
- [ ] `search_contacts(query)` — FTS5 sur les contacts
- [ ] `generate_cv_for_jd(text)` — déclenche une génération, retourne le résultat
- [ ] `get_freedom_number()` — Freedom Ratio actuel + Days to Freedom
- [ ] `add_candidature(poste, entreprise, jd)` — ajoute au CRM depuis n'importe quel agent
- [ ] `get_calendar()` — posts flywheel planifiés + candidatures dues

**Infrastructure**
- [ ] MCP Server local (Tier 2) : stdio transport, consommable par Claude Code, Cursor
- [ ] MCP Server cloud (Tier 3) : HTTP transport, OAuth, accessible depuis Telegram bot / extension Chrome
- [ ] `profile.json` devient le "contrat API" public — standard ouvert, JSON Schema publié

**Moat :** si d'autres personnes adoptent le schéma `profile.json`, Career OS devient un écosystème. C'est le network effect qui précède Life Architect.

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

## Backlog — Optimisations techniques transversales

*Items sans version assignée. À intégrer au fil des versions selon pertinence.*

| Problème | Fix proposé | Effort | Priorité |
|----------|-------------|--------|----------|
| Zéro tests | pytest sur `_analyze_jd()`, `_build_prompt()`, parsing SSE | S | Haute |
| Claude timeout mi-stream | Retry automatique + UI "reconnexion..." | S | Haute |
| profile.json non validé | JSON Schema validation à l'import/édition dans admin | S | Haute |
| Rate limiting Claude | Token bucket simple, max 3 appels simultanés | S | Moyenne |
| Logs inexistants | `logging.basicConfig` + rotation dans admin.py | XS | Moyenne |
| Design system fragmenté | match/simulator ont leur propre CSS, admin a le sien | M | Basse |
| Career Snapshot PDF | Rapport trimestriel (skills, candidatures, Freedom Ratio) généré via Claude | M | Basse |
| CV Audit Tool | Coller un CV existant → analyse ATS + verbes d'action + quantification | M | Basse |

---

## Matrice fonctionnalités × tiers

| Fonctionnalité | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|:---:|:---:|:---:|:---:|
| Portfolio bilingue, démos, blog | ✅ | ✅ | ✅ | ✅ |
| `profile.json` structuré (V2) | ✅ | ✅ | ✅ | ✅ |
| Skill Stack Analyzer | ✅ | ✅ | ✅ | ✅ |
| Score match fiche de poste V2 (bigrams, signal négatif) | ✅ | ✅ | ✅ | ✅ |
| Path Simulator 10 ans + scénarios | ✅ | ✅ | ✅ | ✅ |
| Skill Gap Radar (profil vs rôle cible) | ✅ | ✅ | ✅ | ✅ |
| DEAL Framework self-audit | ✅ | ✅ | ✅ | ✅ |
| Freedom Roadmap visuel | ✅ | ✅ | ✅ | ✅ |
| Freedom Number (sliders manuels) | ✅ | ✅ | ✅ | ✅ |
| Analytics visiteurs (Plausible) | ✅ | ✅ | ✅ | ✅ |
| Admin local + dashboard unifié | ❌ | ✅ | ✅ | ✅ |
| Recherche globale FTS5 | ❌ | ✅ | ✅ | ✅ |
| Générateur CV/LM Claude AI (V2 multi-turn) | ❌ | ✅ | ✅ | ✅ |
| Interview Prep Module | ❌ | ✅ | ✅ | ✅ |
| Networking Email Generator | ❌ | ✅ | ✅ | ✅ |
| Content Flywheel (blog → LinkedIn/X) | ❌ | ✅ | ✅ | ✅ |
| Kanban candidatures + funnel analytics | ❌ | ✅ | ✅ | ✅ |
| CRM candidatures (SQLite/Postgres) | ❌ | ✅ | ✅ | ✅ |
| Envoi email automatisé + scoring templates | ❌ | ✅ | ✅ | ✅ |
| Coach carrière IA + Decision Journal | ❌ | ✅ | ✅ | ✅ |
| Freedom Number (import CSV) | ❌ | ✅ | ✅ | ✅ |
| Extension Chrome | ❌ | ⚠️ tunnel | ✅ | ✅ |
| Job scraper automatique | ❌ | ⚠️ PC on | ✅ | ✅ |
| Pixel tracking CV | ❌ | ⚠️ tunnel | ✅ | ✅ |
| Telegram Bot Digest | ❌ | ❌ | ✅ | ✅ |
| MCP Server Career OS | ❌ | ✅ local | ✅ cloud | ✅ |
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

### Interview Prep — Le chainon manquant
Le generator produit le CV/LM, mais le vrai goulot c'est l'entretien. Interview Prep ferme la boucle : JD → CV → LM → Préparation → Entretien. Même inputs, output différent. Le mode practice (Claude critique tes réponses) est le différenciateur — aucun concurrent ne fait ça avec le contexte de TES propres expériences.

### MCP Server — L'API-first avant le SaaS
Le MCP Server local (Tier 2) est le meilleur investissement avant V7.0 : il force une discipline d'API claire sur toutes les données Career OS, il est consommable par Claude Code et Cursor dès maintenant, et il devient le contrat public pour Life Architect. Construire le MCP Server *avant* le SaaS évite de devoir réarchitecturer.

### Freedom Number Tracker — Le module le plus personnel
C'est le module qui transforme Career OS d'un outil de recherche d'emploi en un système de design de vie. La "Freedom Number" est le vrai objectif derrière tous les autres modules : le CV parfait, le job idéal, le réseau, le side business — tout pointe vers ce chiffre.

**Piège à éviter :** l'Open Banking est complexe (GDPR, PSD2, gestion des tokens). Commencer Tier 1 manuel, puis Tier 2 CSV avant toute API.

### Life Architect SaaS — La question de timing
Le pivot SaaS est tentant mais risqué à lancer trop tôt. La vraie question : à quel moment Career OS est suffisamment différencié pour que quelqu'un paie ?

**Signal de maturité :** quand les Tier 1-2 sont complets et qu'un utilisateur externe dit "je veux ça pour moi". Avant ce signal, construire pour soi d'abord.

**Stack Tier 4 :** Next.js App Router + Clerk + Stripe + Neon Postgres (RLS) + Vercel. Le schéma `profile.json` devient le contrat d'API public.

### Open-Core — Pourquoi séparer Career OS et Life Architect
Career OS (Tier 1-2) reste MIT open-source : crédibilité technique, contributions communauté, portfolio visible. Life Architect (Tier 3-4) est propriétaire : monétisation des couches infrastructure et SaaS. Les deux partagent le même moteur `profile.json`. Pas de conflit — c'est le modèle classique open-core (ex : GitLab, Sentry, Metabase).

---

## Tags git

| Tag | Repo | Description |
|-----|------|-------------|
| `v1.0` | `RoJLD.github.io` | Portfolio HTML statique |
| `v1.5` | `RoJLD.github.io` | Profile API + Skill Analyzer + Match + Simulator + Plausible |
| `v1.0` | `portfolio-admin` | Admin FastAPI local (portfolio + CRM + SMTP) |
| `v2.0` | `portfolio-admin` | Générateur CV/LM Claude API + lien → Candidatures |
| `v2.6` | `portfolio-admin` | Content Flywheel (blog → LinkedIn/X) |
| `v2.7` | `portfolio-admin` | *(prévu)* Quick Wins — dashboard + networking email + search |
| `v3.0` | `portfolio-admin` | *(prévu)* Extension Chrome + cloud |

---

*Dernière mise à jour : 2026-03-30*
