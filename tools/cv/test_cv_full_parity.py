"""Σ-CV-ATELIER — convergence full CV (parité complète avec le CV hand-made).

Projection étendue (build_structured_cv) + rendu des sections Formation / Langues
/ Certifications / Centres d'intérêt + tri reverse-chrono optionnel (sort_by).
Doctrine : fonction PURE de profile.json. Le téléphone est présent dans le profil
de test mais NE DOIT JAMAIS être rendu (les PDF préfab sont servis publiquement).
"""
from __future__ import annotations

import cv_render
import cv_select


def _profile():
    return {
        "$updated": "2026-07-19",
        "identity": {
            "first_name": "Robin", "last_name": "Denis", "email": "r@x.io",
            "phone": "+33 6 00 00 00 00",  # présent — NE DOIT PAS être rendu (privé)
            "location": {"city": "Paris", "country": "France", "remote": True},
            "links": {"portfolio": "https://rojld.github.io",
                      "linkedin": "https://www.linkedin.com/in/robin-x/",
                      "github": "https://github.com/RoJLD"},
            "tagline": {"fr": "Ingénierie Financière", "en": "Financial Engineering"},
        },
        "experiences": [
            {"id": "a", "company": "ALTEN", "title": {"fr": "Quant", "en": "Quant"},
             "start": "2026-02", "end": "2026-08", "current": True,
             "bullets": {"fr": ["b1"], "en": ["b1"]}, "relevance": {"general": 0.65}, "domains": ["quant"]},
            {"id": "b", "company": "Bouygues", "title": {"fr": "Trésorier", "en": "Treasurer"},
             "start": "2025-02", "end": "2025-08",
             "bullets": {"fr": ["b2"], "en": ["b2"]}, "relevance": {"general": 0.8}, "domains": ["finance"]},
            {"id": "c", "company": "ManCo", "title": {"fr": "Risk", "en": "Risk"},
             "start": "2024-06", "end": "2024-12",
             "bullets": {"fr": ["b3"], "en": ["b3"]}, "relevance": {"general": 0.75}, "domains": ["risk"]},
        ],
        "education": [
            {"school": "ECE Paris", "title": {"fr": "ECE Cycle Ingénieur", "en": "ECE Eng"},
             "org": {"fr": "Majeure IF&Q", "en": "Major"}, "period": "2021 – 2026",
             "degree": "Diplôme d'Ingénieur", "start": "2021-09", "end": "2026-09",
             "courses_label": {"fr": "Cours clés", "en": "Key courses"},
             "courses": [{"fr": "Calcul stochastique", "en": "Stochastic"}, {"fr": "ML appliqué", "en": "ML"}],
             "capstone": {"label": {"fr": "Projet de fin d'études (avec EY)", "en": "Capstone (EY)"},
                          "summary": {"fr": "Couverture dynamique", "en": "Dynamic hedging"}}},
            {"school": "Classes Prépas MPSI-MP", "title": {"fr": "MPSI-MP", "en": "MPSI-MP"},
             "org": {"fr": "Maths/Physique", "en": "Math/Physics"}, "period": "2019 – 2021",
             "start": "2019-09", "end": "2021-06", "courses": [], "capstone": None},
        ],
        "languages": [
            {"name": {"fr": "Français", "en": "French"}, "level": {"fr": "Langue maternelle", "en": "Native"}},
            {"name": {"fr": "Anglais", "en": "English"}, "level": {"fr": "Courant (C1)", "en": "Fluent (C1)"}},
        ],
        "certifications": ["Google Project Management", "TOEIC (925/990)"],
        "interests": [{"fr": "♟️ Échecs", "en": "♟️ Chess"}, {"fr": "🏍️ Moto", "en": "🏍️ Motorbike"}],
        "skills": {"programming": [{"name": "Python"}]},
    }


_FULL_CFG = {"id": "full", "relevance_key": "general", "min_relevance": 0.0, "domains_in": []}


# ── Projection : identity enrichie (title/location/links) sans téléphone ────────

def test_identity_title_from_tagline():
    scv = cv_select.build_structured_cv(_profile(), [], "fr")
    assert scv["identity"]["title"] == "Ingénierie Financière"  # tagline, pas identity.title (absent)


def test_identity_location_and_links_projected():
    idy = cv_select.build_structured_cv(_profile(), [], "fr")["identity"]
    assert idy["location"] == "Paris, France"
    assert idy["linkedin"] == "linkedin.com/in/robin-x/"   # scheme + www strippés
    assert idy["github"] == "github.com/RoJLD"


def test_phone_never_projected():
    """Le téléphone ne doit apparaître nulle part dans le structured_cv."""
    import json
    scv = cv_select.build_structured_cv(_profile(), [], "fr")
    assert "phone" not in scv["identity"]
    assert "+33" not in json.dumps(scv, ensure_ascii=False)


# ── Projection : nouvelles sections ────────────────────────────────────────────

def test_education_projected_bilingual_resolved():
    scv = cv_select.build_structured_cv(_profile(), [], "fr")
    edu = scv["education"]
    assert len(edu) == 2
    assert edu[0]["school"] == "ECE Paris"
    assert edu[0]["title"] == "ECE Cycle Ingénieur"      # résolu fr
    assert edu[0]["courses"] == ["Calcul stochastique", "ML appliqué"]  # liste de str résolus
    assert edu[0]["capstone"]["label"] == "Projet de fin d'études (avec EY)"
    assert edu[1]["capstone"] is None                    # prépa : pas de capstone


def test_languages_projected():
    scv = cv_select.build_structured_cv(_profile(), [], "en")
    langs = scv["languages"]
    assert {"name": "English", "level": "Fluent (C1)"} in langs
    assert langs[0]["name"] == "French"


def test_certifications_passthrough():
    scv = cv_select.build_structured_cv(_profile(), [], "fr")
    assert scv["certifications"] == ["Google Project Management", "TOEIC (925/990)"]


def test_interests_resolved():
    scv = cv_select.build_structured_cv(_profile(), [], "fr")
    assert scv["interests"] == ["♟️ Échecs", "🏍️ Moto"]


def test_new_sections_absent_gracefully():
    """profile sans education/languages/etc. → listes vides, pas de crash."""
    scv = cv_select.build_structured_cv({"identity": {}, "experiences": []}, [], "fr")
    assert scv["education"] == [] and scv["languages"] == []
    assert scv["certifications"] == [] and scv["interests"] == []
    assert scv["identity"]["location"] == "" and scv["identity"]["linkedin"] == ""


# ── Tri reverse-chrono optionnel (sort_by) pour le CV complet ───────────────────

def test_sort_by_date_reverse_chrono():
    cfg = {**_FULL_CFG, "sort_by": "date"}
    ids = [e["id"] for e in cv_select.select_experiences(_profile(), cfg)]
    assert ids == ["a", "b", "c"]  # 2026, 2025, 2024 — récent d'abord, IGNORE la relevance


def test_default_sort_unchanged_relevance():
    """Sans sort_by, l'ordre relevance historique est préservé (backward-compat)."""
    ids = [e["id"] for e in cv_select.select_experiences(_profile(), _FULL_CFG)]
    assert ids == ["b", "c", "a"]  # relevance 0.8, 0.75, 0.65


# ── Rendu : les nouvelles sections apparaissent, le téléphone jamais ────────────

def _full_scv(lang="fr"):
    prof = _profile()
    exps = cv_select.select_experiences(prof, {**_FULL_CFG, "sort_by": "date"})
    return cv_select.build_structured_cv(prof, exps, lang)


def test_render_contact_line_has_location_and_links_not_phone():
    out = cv_render.render_html(_full_scv())
    assert "Paris, France" in out
    assert "linkedin.com/in/robin-x/" in out
    assert "github.com/RoJLD" in out
    assert "+33" not in out  # téléphone jamais rendu


def test_render_education_section():
    out = cv_render.render_html(_full_scv())
    assert "Formation" in out          # heading FR
    assert "ECE Paris" in out
    assert "Calcul stochastique" in out
    # apostrophe échappée par _esc (html.escape quote=True) — comportement voulu
    assert "Projet de fin d&#x27;études (avec EY)" in out


def test_render_languages_certifications_interests():
    out = cv_render.render_html(_full_scv())
    assert "Langues" in out and "Courant (C1)" in out
    assert "Certifications" in out and "TOEIC (925/990)" in out
    assert "Centres d&#x27;intérêt" in out and "Échecs" in out  # apostrophe échappée


def test_render_english_headings():
    out = cv_render.render_html(_full_scv("en"))
    assert "Education" in out and "Languages" in out and "Interests" in out


def test_render_still_deterministic():
    scv = _full_scv()
    assert cv_render.render_html(scv) == cv_render.render_html(scv)


# ── Témoins des correctifs de revue adversariale ───────────────────────────────

def test_render_shows_title_from_tagline():
    """Témoin au niveau RENDU (la projection seule ne prouvait pas l'affichage)."""
    assert "Ingénierie Financière" in cv_render.render_html(_full_scv())


def test_title_precedence_tagline_over_identity_title():
    prof = _profile()
    prof["identity"]["title"] = {"fr": "NE DOIT PAS APPARAITRE"}
    assert cv_select.build_structured_cv(prof, [], "fr")["identity"]["title"] == "Ingénierie Financière"


def test_education_school_not_duplicated_when_title_repeats_it():
    """`title` recouvrant `school` est omis : pas deux fois « ECE Paris » au PDF."""
    prof = _profile()
    prof["education"][0]["school"] = "ECE Paris"
    prof["education"][0]["title"] = {"fr": "ECE Paris, Cycle Ingénieur"}
    exps = cv_select.select_experiences(prof, {**_FULL_CFG, "sort_by": "date"})
    out = cv_render.render_html(cv_select.build_structured_cv(prof, exps, "fr"))
    assert out.count("ECE Paris") == 1


def test_null_end_renders_empty_not_the_word_none():
    """`"end": null` produisait littéralement « 2025-02 → None » dans le PDF public."""
    prof = _profile()
    prof["experiences"][0]["end"] = None
    prof["experiences"][0]["current"] = False
    scv = cv_select.build_structured_cv(prof, prof["experiences"][:1], "fr")
    assert "None" not in scv["sections"][0]["dates"]


def test_skills_never_leak_internal_dict_fields():
    """Une entrée skills sans `name` exploitable ne doit JAMAIS exposer weight/level
    (champs internes) dans un PDF servi publiquement."""
    prof = _profile()
    prof["skills"]["programming"] = [{"weight": 0.9, "level": "expert", "used_in": ["x"]}]
    scv = cv_select.build_structured_cv(prof, [], "fr")
    assert scv["skills_top"] == []
    out = cv_render.render_html(scv)
    # NB: ne pas tester "weight" — le CSS contient légitimement `font-weight`.
    assert "used_in" not in out and "expert" not in out and "0.9" not in out
    assert 'class="cv-skills"' not in out  # aucune ligne Compétences émise


def test_null_cfg_values_do_not_crash():
    """`null` est l'idiome « pas de contrainte » : Python plantait là où JS passait."""
    cfg = {**_FULL_CFG, "min_relevance": None, "domains_in": None, "max_experiences": None}
    assert len(cv_select.select_experiences(_profile(), cfg)) == 3


def test_certifications_bilingual_resolved():
    """certifications passe par _loc comme le reste (entrée {fr,en} résolue)."""
    prof = _profile()
    prof["certifications"] = [{"fr": "Certif FR", "en": "Cert EN"}]
    assert cv_select.build_structured_cv(prof, [], "en")["certifications"] == ["Cert EN"]


def test_string_instead_of_list_is_not_iterated_char_by_char():
    """Une chaîne au lieu d'une liste ne doit pas être explosée en caractères."""
    prof = _profile()
    prof["certifications"] = "PAS UNE LISTE"
    prof["interests"] = "IDEM"
    scv = cv_select.build_structured_cv(prof, [], "fr")
    assert scv["certifications"] == [] and scv["interests"] == []
