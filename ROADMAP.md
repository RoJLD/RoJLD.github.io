# Career OS — Roadmap

> Transformer un portfolio statique en un système intelligent de gestion de carrière end-to-end.
> Chaque version ajoute une couche d'intelligence. Chaque tier ajoute une couche d'infrastructure.

---

## Tiers d'infrastructure

| Tier | Infrastructure | Prérequis |
|------|---------------|-----------|
| **Tier 1** | 100% statique — GitHub Pages uniquement | Aucun |
| **Tier 2** | Statique + serveur local (PC allumé) | Python, app locale |
| **Tier 3** | Serveur cloud 24/7 | VPS / PaaS |

---

## Versions

### ✅ V1.0 — Portfolio Intelligent *(Tier 1)*
**Tag git :** `v1.0`
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
**Tag git :** `v1.5` *(en cours)*
**Repos :** `RoJLD/RoJLD.github.io`

- [x] `profile.json` — source de vérité machine-readable (20 skills pondérés, 3 expériences, ikigai, lifestyle, career goals)
- [x] `hidden_edge` — 3 combos de compétences rares avec market premium calculé
- [ ] `/analyzer.html` — Skill Stack Analyzer (80/20, rare combos, radar)
- [ ] `/match.html` — Score de compatibilité fiche de poste (keyword matching JS)
- [ ] `/simulator.html` — Path Simulator 5-10 ans (sliders Canvas)
- [ ] Analytics visiteurs (Plausible, script 1 ligne)

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

### 📋 V2.5 — Générateur CV/LM Sémantique *(Tier 2)*
**Repos :** `RoJLD/portfolio-admin`

- [ ] Parsing fiche de poste — extraction must-have vs nice-to-have, ton, séniorité
- [ ] Matching sémantique fiche × `profile.json` (keyword + contexte)
- [ ] Génération CV restructuré via API Claude (bullets réordonnés, vocabulaire adapté)
- [ ] Génération LM personnalisée (ton adapté : startup / banque / fintech)
- [ ] Export PDF (WeasyPrint ou puppeteer)
- [ ] Historique candidatures générées (date, fiche source, statut)

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

- [ ] Tier 1 : Plausible Analytics (visites, sections, referrers)
- [ ] Tier 3 : Pixel tracking dans les PDFs envoyés (ping serveur à l'ouverture)
- [ ] Dashboard "qui a ouvert mon CV" (date, heure, nombre d'ouvertures)
- [ ] Tracking ouverture emails de candidature
- [ ] Notifications push à l'ouverture

---

### 📋 V4.0 — Modules Lifestyle Design *(Tier 1)*
**Repos :** `RoJLD/RoJLD.github.io`

#### V4.1 — Skill Stack Analyzer (déplacé en V1.5)
#### V4.2 — DEAL Framework Self-Audit
- [ ] Questionnaire interactif (activités de la semaine → freedom / skill / trap)
- [ ] Camembert animé freedom ratio
- [ ] Stockage localStorage, historique mensuel
- [ ] Suggestions d'élimination / automatisation

#### V4.3 — Path Simulator
- [ ] Sliders : salaire, heures/semaine, taux augmentation, revenus side business
- [ ] Deux courbes Canvas : current path vs redesigned path sur 5-10 ans
- [ ] Fear-setting intégré (runway calculator, time-to-equivalent-job)
- [ ] Optionality score par trajectoire

#### V4.4 — Freedom Roadmap
- [ ] Timeline verticale interactive 3 phases (Launch / Automation / Ownership)
- [ ] Milestones avec metrics (MRR cible, heures libérées, nb clients)
- [ ] "Single most important move — 90 jours"

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

### 📋 V7.0 — Career OS SaaS *(Tier 3)*

- [ ] Auth multi-utilisateurs (Clerk)
- [ ] Billing (Stripe — freemium / 15-30€/mois particuliers / 200-500€/mois enterprise)
- [ ] Chaque utilisateur a son `profile.json`, historique, coach
- [ ] Version B2B (cabinets de recrutement, écoles)
- [ ] API publique de profil (`/api/profile`)
- [ ] Marketplace optionnelle (recruteurs × candidats)

---

## Matrice fonctionnalités × tiers

| Fonctionnalité | Tier 1 | Tier 2 | Tier 3 |
|---|:---:|:---:|:---:|
| Portfolio bilingue, démos, blog | ✅ | ✅ | ✅ |
| `profile.json` structuré | ✅ | ✅ | ✅ |
| Skill Stack Analyzer | ✅ | ✅ | ✅ |
| Score match fiche de poste (keywords) | ✅ | ✅ | ✅ |
| Path Simulator 5-10 ans | ✅ | ✅ | ✅ |
| DEAL Framework self-audit | ✅ | ✅ | ✅ |
| Freedom Roadmap visuel | ✅ | ✅ | ✅ |
| Analytics visiteurs (Plausible) | ✅ | ✅ | ✅ |
| Admin local (portfolio + CRM) | ❌ | ✅ | ✅ |
| Générateur CV/LM Claude AI | ❌ | ✅ | ✅ |
| Extension Chrome | ❌ | ⚠️ tunnel | ✅ |
| CRM candidatures (SQLite/Postgres) | ❌ | ✅ | ✅ |
| Job scraper automatique | ❌ | ⚠️ PC on | ✅ |
| Envoi email automatisé | ❌ | ✅ | ✅ |
| Coach carrière IA | ❌ | ✅ | ✅ |
| Pixel tracking CV | ❌ | ⚠️ tunnel | ✅ |
| Bot relance candidatures 24/7 | ❌ | ❌ | ✅ |
| Job hunter autonome 24/7 | ❌ | ❌ | ✅ |
| Network CRM | ❌ | ❌ | ✅ |
| Multi-user SaaS | ❌ | ❌ | ✅ |

---

## Tags git

| Tag | Repo | Description |
|-----|------|-------------|
| `v1.0` | `RoJLD.github.io` | Portfolio HTML statique |
| `v1.5` | `RoJLD.github.io` | Profile API + modules Tier 1 |
| `v1.0` | `portfolio-admin` | Admin FastAPI local |
| `v2.0` | `portfolio-admin` | *(prévu)* Générateur CV/LM Claude |
| `v3.0` | `portfolio-admin` | *(prévu)* Extension Chrome + cloud |

---

*Dernière mise à jour : 2026-03-27*
