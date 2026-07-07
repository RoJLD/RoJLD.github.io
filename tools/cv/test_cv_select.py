"""Tests du cœur de sélection Σ-CV-ATELIER (sous-projet A)."""
from __future__ import annotations

import json
import pathlib

import pytest

import cv_select


@pytest.fixture
def profile():
    return {
        "$updated": "2026-07-07",
        "identity": {"first_name": "Robin", "last_name": "Denis", "title": "Quant", "email": "r@x.io"},
        "skills": {"programming": [{"name": "Python"}, {"name": "C++"}], "finance": [{"name": "Vasicek"}], "data_ml": []},
        "experiences": [
            {"id": "alten", "company": "ALTEN", "title": "Quant Dev", "start": "2024-09", "end": "2025-06",
             "current": False, "domains": ["quant", "dev"], "relevance": {"quant": 0.95, "risk": 0.5, "dev": 0.7, "general": 0.65},
             "bullets": {"fr": ["Pilotage CryptoExploration", "Modèles Vasicek/CIR"], "en": ["Led CryptoExploration", "Vasicek/CIR models"]}},
            {"id": "manco", "company": "ManCo", "title": "Risk Analyst", "start": "2021-01", "end": "2021-12",
             "current": False, "domains": ["risk", "finance"], "relevance": {"quant": 0.3, "risk": 0.9, "dev": 0.1, "general": 0.5},
             "bullets": {"fr": ["Reporting risque", "Stress tests"], "en": ["Risk reporting", "Stress tests"]}},
            {"id": "bouygues", "company": "Bouygues", "title": "Data Intern", "start": "2020-06", "end": "2020-09",
             "current": False, "domains": ["data"], "relevance": {"quant": 0.1, "risk": 0.1, "dev": 0.4, "general": 0.4},
             "bullets": {"fr": ["Pipeline data"], "en": ["Data pipeline"]}},
        ],
    }


# ── select_experiences ────────────────────────────────────────────────────────

def test_relevance_threshold_selects_above(profile):
    cfg = {"relevance_key": "quant", "min_relevance": 0.9, "domains_in": []}
    got = cv_select.select_experiences(profile, cfg)
    assert [e["id"] for e in got] == ["alten"]  # seul quant>=0.9


def test_domains_or_relevance_is_permissive(profile):
    # min_relevance haut MAIS domaine 'risk' visé → manco entre via le OU domaine
    cfg = {"relevance_key": "quant", "min_relevance": 0.9, "domains_in": ["risk"]}
    got = {e["id"] for e in cv_select.select_experiences(profile, cfg)}
    assert got == {"alten", "manco"}


def test_sorted_by_relevance_desc(profile):
    cfg = {"relevance_key": "quant", "min_relevance": 0.0, "domains_in": []}
    got = [e["id"] for e in cv_select.select_experiences(profile, cfg)]
    assert got == ["alten", "manco", "bouygues"]  # 0.95 > 0.3 > 0.1


def test_max_experiences_caps(profile):
    cfg = {"relevance_key": "quant", "min_relevance": 0.0, "max_experiences": 2}
    got = cv_select.select_experiences(profile, cfg)
    assert len(got) == 2
    assert got[0]["id"] == "alten"


def test_tie_break_recent_first(profile):
    # relevance.risk : manco 0.9, alten 0.5, bouygues 0.1 → tri par relevance suffit ici ;
    # on force une égalité en filtrant sur 'general' où alten(0.65)>manco(0.5)>bouygues(0.4)
    cfg = {"relevance_key": "general", "min_relevance": 0.0}
    got = [e["id"] for e in cv_select.select_experiences(profile, cfg)]
    assert got == ["alten", "manco", "bouygues"]


# ── select_manual ─────────────────────────────────────────────────────────────

def test_manual_projects_exact_bullets(profile):
    got = cv_select.select_manual(profile, ["alten.0", "manco.1"], "fr")
    assert [e["id"] for e in got] == ["alten", "manco"]
    assert got[0]["bullets"]["fr"] == ["Pilotage CryptoExploration"]
    assert got[1]["bullets"]["fr"] == ["Stress tests"]


def test_manual_ignores_unknown_and_out_of_range(profile):
    got = cv_select.select_manual(profile, ["alten.99", "ghost.0", "bouygues.0"], "en")
    assert [e["id"] for e in got] == ["bouygues"]  # alten.99 hors-plage, ghost inexistant
    assert got[0]["bullets"]["en"] == ["Data pipeline"]


def test_manual_preserves_index_order(profile):
    got = cv_select.select_manual(profile, ["alten.1", "alten.0"], "fr")
    assert got[0]["bullets"]["fr"] == ["Pilotage CryptoExploration", "Modèles Vasicek/CIR"]


# ── build_structured_cv ───────────────────────────────────────────────────────

def test_structured_cv_shape_and_lang(profile):
    exps = cv_select.select_experiences(profile, {"relevance_key": "quant", "min_relevance": 0.9})
    cv = cv_select.build_structured_cv(profile, exps, "en")
    assert cv["lang"] == "en"
    assert cv["identity"]["name"] == "Robin Denis"
    assert len(cv["sections"]) == 1
    assert cv["sections"][0]["company"] == "ALTEN"
    assert cv["sections"][0]["bullets"] == ["Led CryptoExploration", "Vasicek/CIR models"]
    assert "Python" in cv["skills_top"]
    assert cv["footer"]["updated"] == "2026-07-07"


def test_localizes_bilingual_title_fields():
    # profile.json réel : title est un dict {fr,en} → NE doit PAS afficher le dict brut
    prof = {"identity": {"first_name": "R", "last_name": "D",
                         "title": {"fr": "Chercheur", "en": "Researcher"}},
            "skills": {},
            "experiences": [{"id": "x", "company": "ALTEN",
                             "title": {"fr": "Quant FR", "en": "Quant EN"},
                             "start": "2024", "current": True, "domains": ["quant"],
                             "relevance": {"general": 0.9},
                             "bullets": {"fr": ["b"], "en": ["b"]}}]}
    cv_en = cv_select.build_structured_cv(prof, prof["experiences"], "en")
    assert cv_en["sections"][0]["title"] == "Quant EN"
    assert cv_en["identity"]["title"] == "Researcher"
    cv_fr = cv_select.build_structured_cv(prof, prof["experiences"], "fr")
    assert cv_fr["sections"][0]["title"] == "Quant FR"
    # jamais de repr de dict
    assert "{" not in cv_en["sections"][0]["title"]


def test_loc_helper_handles_string_and_dict():
    assert cv_select._loc("plain", "en") == "plain"
    assert cv_select._loc({"fr": "a", "en": "b"}, "en") == "b"
    assert cv_select._loc({"fr": "a"}, "en") == "a"  # fallback fr
    assert cv_select._loc(None, "en") == ""


def test_structured_cv_current_experience_shows_present():
    prof = {"identity": {}, "skills": {}, "experiences": [
        {"id": "now", "company": "X", "title": "T", "start": "2026-01", "current": True,
         "domains": ["ai"], "relevance": {"general": 0.9}, "bullets": {"fr": ["b"], "en": ["b"]}}]}
    cv = cv_select.build_structured_cv(prof, prof["experiences"], "fr")
    assert "présent" in cv["sections"][0]["dates"]


# ── Smoke sur le VRAI profile.json ────────────────────────────────────────────

def _find_real_profile() -> pathlib.Path | None:
    """Cherche profile.json en remontant (marche depuis scratchpad OU tools/cv/)."""
    here = pathlib.Path(__file__).resolve()
    for anc in here.parents:
        cand = anc / "profile.json"
        if cand.exists():
            return cand
    hard = pathlib.Path(r"C:/Users/robla/VScode_Project/RoJLD.github.io/profile.json")
    return hard if hard.exists() else None


_REAL = _find_real_profile()


@pytest.mark.skipif(_REAL is None, reason="profile.json réel absent")
def test_real_profile_quant_selection_nonempty():
    prof = json.loads(_REAL.read_text(encoding="utf-8"))
    exps = cv_select.select_experiences(prof, {"relevance_key": "quant", "min_relevance": 0.6})
    assert exps, "au moins une expérience quant-pertinente attendue"
    cv = cv_select.build_structured_cv(prof, exps, "fr")
    assert cv["identity"]["name"]
    assert all(s["bullets"] for s in cv["sections"])  # chaque section a des bullets FR
