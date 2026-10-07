"""Fixtures du CV projeté (D8). Données inventées : aucune ne vient du vrai profil."""

PROFIL = {
    "$version": "1.1.0",
    "domains": [{"id": "calc", "label": {"fr": "Calcul", "en": "Computing"}}],
    "skills": {"radar_scores": {"Calcul": 0.9}},
    "identity": {"tagline": {"fr": "x", "en": "x"}, "status": {"fr": "x", "en": "x"},
                 "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.org", "phone": "",
                 "location": {"city": "Londres", "country": "Royaume-Uni"},
                 "links": {"portfolio": "https://ada.example.org/", "github": "https://github.com/ada",
                           "linkedin": "https://www.linkedin.com/in/ada/"}},
    "education": [{"id": "u1", "title": {"fr": "Université X, Cycle Ingénieur", "en": "University X, Engineering Cycle"},
                   "org": {"fr": "Majeure Calcul", "en": "Major in Computing"}, "location": "Londres, Royaume-Uni",
                   "start": "2019-09", "end": "2022-06",
                   "courses_label": {"fr": "Cours pertinents", "en": "Relevant coursework"},
                   "courses": [{"fr": "Analyse", "en": "Analysis"}, "Algèbre"]}],
    "experiences": [{"id": "x1", "company": "Machine Co", "location": "Londres, Royaume-Uni",
                     "title": {"fr": "Analyste (moteur)", "en": "Engine Analyst"}, "type": "stage", "domains": ["calc"],
                     "start": "2021-02", "end": "2021-08", "current": False,
                     "bullets": {"fr": ["Notes sur le moteur analytique."], "en": ["Wrote notes on the analytical engine."]}}],
    "projects": [
        {"id": "p1", "name": "Bernoulli", "type": "academic", "context": "u1", "domains": ["calc"],
         "cv": {"group": "academic", "start": "2020-09", "end": "2021-01",
                "title": {"fr": "Projet : nombres de Bernoulli", "en": "Project: Bernoulli numbers"},
                "role": {"fr": "Autrice", "en": "Author"},
                "bullets": {"fr": ["Premier programme publié."], "en": ["First published program."]}}},
        {"id": "p2", "name": {"fr": "Métier", "en": "Loom"}, "type": "personal", "context": "personal", "domains": ["calc"],
         "cv": {"group": "personal", "title": {"fr": "Métier à tisser", "en": "Loom"},
                "summary": {"fr": "cartes perforées.", "en": "punched cards."}}},
        {"id": "p3", "name": "Sans CV", "type": "personal", "context": "personal", "domains": ["calc"]},
        {"id": "p4", "name": "Notes", "type": "personal", "context": "personal", "domains": ["calc"], "cv": {"group": "other", "title": "Notes G"}},
    ],
    "languages": [{"code": "en", "name": {"fr": "Anglais", "en": "English"}, "level": {"fr": "natif", "en": "Native"}}],
    "certifications": ["Royal Society"],
    "interests": [{"fr": "♟️ Échecs", "en": "♟️ Chess"}],
    "cv": {"skills": [{"label": {"fr": "Langages", "en": "Programming"}, "items": ["Python", "C"]}]},
}

# Le complément tel qu'il est écrit sur disque (data/cv_private.json)…
COMPLEMENT_BRUT = {
    "phone": "+44 0",
    "location": "London W1, UK",
    "availability": {"fr": "", "en": ""},
    "experiences_cv": [{"company": "Poste Ancien", "location": "Lyon, France",
                        "title": {"fr": "Agente", "en": "Agent"}, "start": "2018-01", "end": "2018-08",
                        "bullets": {"fr": ["Appels."], "en": ["Calls."]}}],
}

# … et tel que complement.charger() le rend (forme consommée par cv_md et profile_yml).
COMPLEMENT = {
    "phone": "+44 0",
    "location": {"fr": "London W1, UK", "en": "London W1, UK"},
    "availability": {"fr": "", "en": ""},
    "experiences_cv": [{"company": "Poste Ancien", "location": {"fr": "Lyon, France", "en": "Lyon, France"},
                        "title": {"fr": "Agente", "en": "Agent"}, "type": None, "start": "2018-01", "end": "2018-08",
                        "current": False, "bullets": {"fr": ["Appels."], "en": ["Calls."]}}],
}

YML = (
    "# Career-Ops Profile Configuration\n"
    "candidate:\n"
    '  full_name: "Ada Lovelace"\n'
    '  email: "ada@example.org"\n'
    '  phone: "+44 0"\n'
    "  # Optional. WeChat.\n"
    '  wechat: ""\n'
    '  location: "London W1, UK"\n'
    '  linkedin: "linkedin.com/in/ada"\n'
    '  portfolio_url: "https://ada.example.org/"\n'
    '  github: "github.com/ada"\n'
    "\n"
    "target_roles:\n"
    "  primary:\n"
    '    - "Analyst"\n'
    "\n"
    "cover_letter:\n"
    "  # Your notice period in calendar days.\n"
    "  notice_period_days: 0  # disponible\n"
)
