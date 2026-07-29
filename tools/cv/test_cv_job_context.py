"""K1 — tests de `job_context` (cv_target élargi).

Décrivent l'ENTRÉE (fiche de poste + réponse LLM factice) et laissent le code
produire la SORTIE. Aucun réseau : `complete_fn` est toujours injecté.

Le point dur mesuré : les nouveaux champs (entreprise, intitulé, exigences,
registre, marché) n'ont AUCUN référentiel dans profile.json. Ces tests fixent le
régime de validation retenu, référentiel par référentiel :
  - clés/domaines  → référentiel = profile.json      → clamp reject-loud (inchangé)
  - registre/marché → référentiel = vocabulaire fermé → clamp sur l'énumération
  - entreprise/intitulé → référentiel = la fiche elle-même → ancrage VERBATIM
  - exigences → aucun référentiel → forme seule, et jamais un fait sur le candidat
"""
from __future__ import annotations

import json
import logging

import pytest

import cv_target


@pytest.fixture
def profile():
    return {
        "domains": [{"id": "quant"}, {"id": "risk"}, {"id": "dev"}, {"id": "data"}],
        "experiences": [
            {"id": "a", "relevance": {"quant": 0.9, "general": 0.6}, "domains": ["quant"]},
            {"id": "b", "relevance": {"risk": 0.9, "general": 0.4}, "domains": ["risk"]},
        ],
    }


def _fn(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return lambda _prompt: text


JOB = (
    "Nexora Capital recrute un Ingénieur Quantitatif (H/F) à Paris.\n"
    "Vous rejoindrez l'équipe de modélisation de produits dérivés.\n"
    "Exigences : Python, C++, calibration de modèles de volatilité stochastique."
)


# ── englobement : job_context CONTIENT le cfg, il ne le remplace pas ────────────

def test_job_context_is_a_superset_of_cfg(profile):
    """Contrainte cardinale K1 : atelier.generate_pdf consomme le cfg tel quel."""
    jc = cv_target.extract_job_context(
        JOB, profile,
        complete_fn=_fn({"relevance_key": "quant", "min_relevance": 0.7,
                         "domains_in": ["quant"], "keywords": ["Python"],
                         "company": "Nexora Capital", "job_title": "Ingénieur Quantitatif",
                         "requirements": ["Python", "C++"], "register": "formel", "market": "FR"}))
    for k in ("relevance_key", "min_relevance", "domains_in", "keywords", "label"):
        assert k in jc, f"clé cfg perdue : {k}"
    assert jc["relevance_key"] == "quant"
    assert jc["min_relevance"] == 0.7


def test_extract_cfg_still_exists_and_returns_the_same_object(profile):
    fn = _fn({"relevance_key": "risk", "min_relevance": 0.4, "domains_in": ["risk"]})
    assert cv_target.extract_cfg(JOB, profile, complete_fn=fn) == \
           cv_target.extract_job_context(JOB, profile, complete_fn=fn)


def test_cfg_extra_keys_do_not_disturb_selection(profile):
    """Le CV ciblé existant continue de fonctionner avec le cfg élargi."""
    import cv_select
    jc = cv_target.extract_job_context(
        JOB, profile,
        complete_fn=_fn({"relevance_key": "risk", "min_relevance": 0.8, "domains_in": [],
                         "company": "Nexora Capital", "register": "direct"}))
    assert [e["id"] for e in cv_select.select_experiences(profile, jc)] == ["b"]


# ── entreprise / intitulé : ancrage VERBATIM dans la fiche ──────────────────────

def test_company_and_title_accepted_when_verbatim(profile):
    jc = cv_target.extract_job_context(
        JOB, profile,
        complete_fn=_fn({"relevance_key": "quant", "company": "Nexora Capital",
                         "job_title": "Ingénieur Quantitatif"}))
    assert jc["company"] == "Nexora Capital"
    assert jc["job_title"] == "Ingénieur Quantitatif"
    assert jc["_field_provenance"]["company"] == "verbatim"


def test_hallucinated_company_is_rejected_loud(profile, caplog):
    """Un nom d'entreprise absent de la fiche finit en tête de la LETTRE :
    il ne peut pas être accepté sur la parole du modèle."""
    with caplog.at_level(logging.WARNING):
        jc = cv_target.extract_job_context(
            JOB, profile,
            complete_fn=_fn({"relevance_key": "quant", "company": "Goldman Sachs"}))
    assert jc["company"] is None
    assert jc["_field_provenance"]["company"] == "rejected"
    assert any("company" in r.message for r in caplog.records)


def test_verbatim_check_is_whitespace_and_case_insensitive(profile):
    jc = cv_target.extract_job_context(
        "Recrutement chez   NEXORA\nCAPITAL pour un poste quant.", profile,
        complete_fn=_fn({"relevance_key": "quant", "company": "Nexora Capital"}))
    assert jc["company"] == "Nexora Capital"


def test_company_beyond_prompt_window_is_rejected(profile):
    """Le modèle ne voit que la fenêtre envoyée : l'ancrage se mesure sur CETTE
    fenêtre, sinon on validerait contre un texte que le modèle n'a jamais lu."""
    posting = ("x" * cv_target._PROMPT_JOB_CHARS) + " Nexora Capital"
    jc = cv_target.extract_job_context(
        posting, profile, complete_fn=_fn({"relevance_key": "quant", "company": "Nexora Capital"}))
    assert jc["company"] is None


def test_company_non_string_is_rejected(profile):
    jc = cv_target.extract_job_context(
        JOB, profile, complete_fn=_fn({"relevance_key": "quant", "company": {"fr": "Nexora"}}))
    assert jc["company"] is None
    assert jc["_field_provenance"]["company"] == "absent"


# ── registre / marché : vocabulaire fermé ───────────────────────────────────────

def test_register_clamped_to_known_vocabulary(profile):
    ok = cv_target.extract_job_context(JOB, profile,
                                       complete_fn=_fn({"relevance_key": "quant", "register": "formel"}))
    ko = cv_target.extract_job_context(JOB, profile,
                                       complete_fn=_fn({"relevance_key": "quant", "register": "sarcastique"}))
    assert ok["register"] == "formel"
    assert ko["register"] == cv_target._DEFAULT_REGISTER
    assert ko["_field_provenance"]["register"] == "rejected"


def test_market_uppercased_and_clamped(profile):
    ok = cv_target.extract_job_context(JOB, profile,
                                       complete_fn=_fn({"relevance_key": "quant", "market": "fr"}))
    ko = cv_target.extract_job_context(JOB, profile,
                                       complete_fn=_fn({"relevance_key": "quant", "market": "Mars"}))
    assert ok["market"] == "FR"
    assert ko["market"] is None


# ── exigences : forme seule, bornée ─────────────────────────────────────────────

def test_requirements_capped_in_count_and_length(profile):
    jc = cv_target.extract_job_context(
        JOB, profile,
        complete_fn=_fn({"relevance_key": "quant",
                         "requirements": [f"exigence {i} " + "z" * 400 for i in range(30)]}))
    assert len(jc["requirements"]) == cv_target._MAX_REQUIREMENTS
    assert all(len(r) <= cv_target._MAX_REQ_CHARS for r in jc["requirements"])


def test_requirements_drop_non_strings(profile):
    jc = cv_target.extract_job_context(
        JOB, profile,
        complete_fn=_fn({"relevance_key": "quant", "requirements": ["Python", 42, None, {"a": 1}, "C++"]}))
    assert jc["requirements"] == ["Python", "C++"]


# ── défauts et robustesse (fail-loud, forme stable) ─────────────────────────────

def test_default_context_has_the_full_shape(profile):
    jc = cv_target.extract_job_context("   ", profile, complete_fn=_fn({"company": "X"}))
    for k in ("company", "job_title", "requirements", "register", "market", "_field_provenance"):
        assert k in jc
    assert jc["company"] is None and jc["requirements"] == []
    assert jc["register"] == cv_target._DEFAULT_REGISTER


def test_llm_failure_yields_default_shape(profile, caplog):
    with caplog.at_level(logging.WARNING):
        jc = cv_target.extract_job_context(JOB, profile, complete_fn=_fn("pas du json"))
    assert jc["company"] is None and jc["job_title"] is None
    assert jc["register"] == cv_target._DEFAULT_REGISTER
    assert any("cfg défaut" in r.message for r in caplog.records)


def test_prompt_asks_for_every_new_field(profile):
    """Garde de câblage : un champ ajouté au schéma mais pas au prompt serait
    toujours vide en production, et tous les tests ci-dessus resteraient verts."""
    seen = {}

    def spy(prompt):
        seen["p"] = prompt
        return "{}"

    cv_target.extract_job_context(JOB, profile, complete_fn=spy)
    for field in ("company", "job_title", "requirements", "register", "market"):
        assert f'"{field}"' in seen["p"], f"champ absent du prompt : {field}"
    for reg in cv_target._REGISTERS:
        assert reg in seen["p"]
