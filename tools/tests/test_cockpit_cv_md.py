"""Rendu de cv.md : la structure que career-ops lit aujourd'hui (mesurée le 2026-10-07), en
anglais puis en français, depuis profile.json + complément privé."""
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures_cv import COMPLEMENT, PROFIL  # noqa: E402
from tools.cockpit import cv_md  # noqa: E402

ATTENDU = "\n".join([
    "# Ada Lovelace — CV",
    "",
    "London W1, UK · +44 0 · ada@example.org · ada.example.org · github.com/ada · linkedin.com/in/ada",
    "",
    "---",
    "",
    "## English",
    "",
    "### Education",
    "- **2019–2022 — University X, Engineering Cycle** — Londres, Royaume-Uni. Major in Computing.",
    "  Relevant coursework: Analysis, Algèbre.",
    "",
    "### Professional Experience",
    "- **Feb – Aug 2021 — Machine Co, Londres, Royaume-Uni — Engine Analyst (Internship)**",
    "  - Wrote notes on the analytical engine.",
    "- **Jan – Aug 2018 — Poste Ancien, Lyon, France — Agent**",
    "  - Calls.",
    "",
    "### Academic Projects",
    "- **Sep 2020 – Jan 2021 — Project: Bernoulli numbers — Author**",
    "  - First published program.",
    "",
    "### Personal Projects",
    "- **Loom** — punched cards.",
    "",
    "### Other Projects (to be detailed later)",
    "- Notes G",
    "",
    "### Languages & Skills",
    "- **Languages:** English (Native)",
    "- **Certifications:** Royal Society",
    "- **Programming:** Python, C",
    "",
    "### Activities & Interests",
    "- Chess",
    "",
    "---",
    "",
    "## Français",
    "",
    "### Formation",
    "- **2019–2022 — Université X, Cycle Ingénieur** — Londres, Royaume-Uni. Majeure Calcul.",
    "  Cours pertinents : Analyse, Algèbre.",
    "",
    "### Expérience professionnelle",
    "- **Févr. – Août 2021 — Machine Co, Londres, Royaume-Uni — Analyste (moteur) (Stage)**",
    "  - Notes sur le moteur analytique.",
    "- **Janv. – Août 2018 — Poste Ancien, Lyon, France — Agente**",
    "  - Appels.",
    "",
    "### Projets académiques",
    "- **Sept. 2020 – Janv. 2021 — Projet : nombres de Bernoulli — Autrice**",
    "  - Premier programme publié.",
    "",
    "### Projets personnels",
    "- **Métier à tisser** — cartes perforées.",
    "",
    "### Autres projets (à détailler ultérieurement)",
    "- Notes G",
    "",
    "### Langues & Compétences",
    "- **Langues :** Anglais (natif)",
    "- **Certifications :** Royal Society",
    "- **Langages :** Python, C",
    "",
    "### Centres d'intérêt",
    "- Échecs",
]) + "\n"


def test_golden_octet_pour_octet():
    assert cv_md.rendre(PROFIL, COMPLEMENT) == ATTENDU


def test_le_rendu_est_deterministe():
    assert cv_md.rendre(PROFIL, COMPLEMENT) == cv_md.rendre(PROFIL, COMPLEMENT)


@pytest.mark.parametrize("start, end, lang, attendu", [
    ("2026-02", "2026-08", "en", "Feb – Aug 2026"),
    ("2025-09", "2026-02", "en", "Sep 2025 – Feb 2026"),
    ("2026-02", None, "en", "Feb 2026 – Present"),
    ("2026-02", "2026-08", "fr", "Févr. – Août 2026"),
    ("2025-09", "2026-02", "fr", "Sept. 2025 – Févr. 2026"),
    ("2026-02", None, "fr", "Févr. 2026 – Aujourd'hui"),
    ("2022", "2023", "en", "2022 – 2023"),
])
def test_periode(start, end, lang, attendu):
    assert cv_md.periode(start, end, lang) == attendu


def test_annees():
    assert cv_md.annees("2021-09", "2026-09") == "2021–2026"
    assert cv_md.annees("2022", "2023") == "2022–2023"
    assert cv_md.annees("2024", "2024-12") == "2024"


def test_t_accepte_texte_et_bilingue():
    assert cv_md.t({"fr": "a", "en": "b"}, "fr") == "a"
    assert cv_md.t({"fr": "a"}, "en") == "a"          # repli sur l'autre langue, jamais vide si une existe
    assert cv_md.t("x", "en") == "x" and cv_md.t(None, "fr") == ""


def test_lien_court():
    assert cv_md.lien_court("https://www.linkedin.com/in/ada/") == "linkedin.com/in/ada"
    assert cv_md.lien_court("https://ada.example.org") == "ada.example.org"


def test_sans_complement_location_l_adresse_vient_du_profil():
    sans = dict(COMPLEMENT, location=None)
    assert "\nLondres, Royaume-Uni · +44 0 · " in cv_md.rendre(PROFIL, sans)


def test_un_poste_en_cours_dit_present():
    p = {**PROFIL, "experiences": [dict(PROFIL["experiences"][0], current=True, end="2021-08")]}
    assert "- **Feb 2021 – Present — Machine Co" in cv_md.rendre(p, dict(COMPLEMENT, experiences_cv=[]))


def test_les_interets_du_bloc_cv_priment():
    p = {**PROFIL, "cv": {**PROFIL["cv"], "interests": [{"fr": "Sports : course", "en": "Sports: running"}]}}
    rendu = cv_md.rendre(p, COMPLEMENT)
    assert "- Sports: running" in rendu and "- Chess" not in rendu


def test_une_section_vide_est_omise():
    p = {**PROFIL, "projects": []}
    rendu = cv_md.rendre(p, COMPLEMENT)
    assert "### Academic Projects" not in rendu and "### Projets personnels" not in rendu
