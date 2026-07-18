"""Tests de l'extracteur fiche-de-poste → cfg (Σ-CV-ATELIER sous-projet C)."""
from __future__ import annotations

import json
import logging
import pathlib

import pytest

import cv_select
import cv_target


@pytest.fixture
def profile():
    return {
        "domains": [{"id": "quant", "label": {"fr": "Quant", "en": "Quant"}},
                    {"id": "risk", "label": {"fr": "Risk", "en": "Risk"}},
                    {"id": "dev", "label": {"fr": "Dev", "en": "Dev"}},
                    {"id": "data", "label": {"fr": "Data", "en": "Data"}}],
        "experiences": [
            {"id": "a", "company": "A", "title": "T", "start": "2024", "current": True,
             "domains": ["quant"], "relevance": {"quant": 0.95, "risk": 0.5, "dev": 0.7, "general": 0.6},
             "bullets": {"fr": ["b1"], "en": ["b1"]}},
            {"id": "b", "company": "B", "title": "T", "start": "2021", "current": False,
             "domains": ["risk"], "relevance": {"quant": 0.2, "risk": 0.9, "dev": 0.1, "general": 0.4},
             "bullets": {"fr": ["b2"], "en": ["b2"]}},
        ],
    }


def _fn(payload):
    """Fabrique un complete_fn factice qui renvoie `payload` (str ou dict→json)."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda _prompt: text


# ── helpers ───────────────────────────────────────────────────────────────────

def test_known_keys_and_domains(profile):
    assert cv_target.known_relevance_keys(profile) == ["dev", "general", "quant", "risk"]
    assert cv_target.known_domains(profile) == ["quant", "risk", "dev", "data"]


# ── extraction nominale ─────────────────────────────────────────────────────────

def test_valid_extraction(profile):
    cfg = cv_target.extract_cfg("Quant developer, Python, risk models", profile,
                                complete_fn=_fn({"relevance_key": "quant", "min_relevance": 0.7,
                                                 "domains_in": ["quant", "risk"], "keywords": ["Python", "risk"]}))
    assert cfg["relevance_key"] == "quant"
    assert cfg["min_relevance"] == 0.7
    assert cfg["domains_in"] == ["quant", "risk"]
    assert cfg["keywords"] == ["Python", "risk"]


def test_unknown_domain_filtered(profile):
    cfg = cv_target.extract_cfg("x", profile,
                                complete_fn=_fn({"relevance_key": "dev", "min_relevance": 0.5,
                                                 "domains_in": ["dev", "blockchain", "banana"], "keywords": []}))
    assert cfg["domains_in"] == ["dev"]  # inconnus filtrés


def test_unknown_key_falls_back_to_general(profile):
    cfg = cv_target.extract_cfg("x", profile,
                                complete_fn=_fn({"relevance_key": "astrology", "min_relevance": 0.3, "domains_in": []}))
    assert cfg["relevance_key"] == "general"


def test_min_relevance_clamped(profile):
    hi = cv_target.extract_cfg("x", profile, complete_fn=_fn({"relevance_key": "quant", "min_relevance": 5.0}))
    lo = cv_target.extract_cfg("x", profile, complete_fn=_fn({"relevance_key": "quant", "min_relevance": -2}))
    assert hi["min_relevance"] == 1.0 and lo["min_relevance"] == 0.0


def test_keywords_capped(profile):
    cfg = cv_target.extract_cfg("x", profile,
                                complete_fn=_fn({"relevance_key": "quant", "keywords": list(range(50))}))
    assert len(cfg["keywords"]) == 20
    assert all(isinstance(k, str) for k in cfg["keywords"])


# ── robustesse reject-loud ──────────────────────────────────────────────────────

def test_non_json_returns_default_loud(profile, caplog):
    with caplog.at_level(logging.WARNING):
        cfg = cv_target.extract_cfg("x", profile, complete_fn=_fn("pas du json <think>bla</think>"))
    assert cfg["relevance_key"] == "general" and cfg["domains_in"] == []
    assert any("cfg défaut" in r.message for r in caplog.records)


def test_empty_job_posting_default(profile):
    cfg = cv_target.extract_cfg("   ", profile, complete_fn=_fn({"relevance_key": "quant"}))
    assert cfg["relevance_key"] == "general"  # pas d'appel LLM, défaut direct


def test_raising_complete_fn_returns_default(profile, caplog):
    def boom(_p):
        raise RuntimeError("LLM down")
    with caplog.at_level(logging.WARNING):
        cfg = cv_target.extract_cfg("x", profile, complete_fn=boom)
    assert cfg["relevance_key"] == "general"


# ── intégration : cfg → select_experiences ─────────────────────────────────────

def test_extracted_cfg_drives_selection(profile):
    cfg = cv_target.extract_cfg("Risk analyst", profile,
                                complete_fn=_fn({"relevance_key": "risk", "min_relevance": 0.8, "domains_in": []}))
    exps = cv_select.select_experiences(profile, cfg)
    assert [e["id"] for e in exps] == ["b"]  # seule 'b' a risk>=0.8


def test_targeted_structured_cv_pipeline(profile):
    cfg, scv = cv_target.targeted_structured_cv(
        "Quant developer Python", profile, lang="en",
        complete_fn=_fn({"relevance_key": "quant", "min_relevance": 0.9, "domains_in": ["quant"]}))
    assert cfg["relevance_key"] == "quant"
    assert scv["lang"] == "en"
    assert [s["company"] for s in scv["sections"]] == ["A"]  # seule 'a' a quant>=0.9
    assert scv["sections"][0]["bullets"] == ["b1"]


# ── SP7b : câblage réel du résolveur souverain (SIGIL-1714) ─────────────────────

def _fake_career_tree(tmp_path: pathlib.Path, with_llm: bool) -> pathlib.Path:
    """Construit <tmp>/ELYSIUM/satellites/anthropos/apps/career[/core/llm_client.py]
    et renvoie un `here` factice tel que here.parents[2].parent == tmp_path."""
    career = tmp_path / "ELYSIUM" / "satellites" / "anthropos" / "apps" / "career"
    (career / "core").mkdir(parents=True, exist_ok=True)
    if with_llm:
        (career / "core" / "llm_client.py").write_text("def complete(*a, **k): return '{}'\n", encoding="utf-8")
    return tmp_path / "repo" / "tools" / "cv" / "cv_target.py"


def test_resolve_career_returns_both_paths(tmp_path):
    here = _fake_career_tree(tmp_path, with_llm=True)
    resolved = cv_target._resolve_career(here)
    assert resolved is not None
    career, elysium_root = resolved
    # garde du bug EXACT : la racine ELYSIUM doit être renvoyée (tier-1 gateway en dépend)
    assert elysium_root == tmp_path / "ELYSIUM"
    assert career == tmp_path / "ELYSIUM" / "satellites" / "anthropos" / "apps" / "career"


def test_resolve_career_none_when_absent(tmp_path):
    here = _fake_career_tree(tmp_path, with_llm=False)
    assert cv_target._resolve_career(here) is None


def test_extract_cfg_non_default_with_real_resolution(profile, monkeypatch):
    """Exécute le VRAI _sovereign_complete (import réel de core.llm_client), en ne
    monkeypatchant QUE la frontière LLM. Prouve le câblage résolution+import+appel.
    Skip hors machine dev (sibling ELYSIUM/career/core/llm_client.py absent)."""
    resolved = cv_target._resolve_career(pathlib.Path(cv_target.__file__).resolve())
    if resolved is None:
        pytest.skip("sibling ELYSIUM/career/core/llm_client.py absent (attendu en CI site)")
    career, elysium_root = resolved
    import importlib
    monkeypatch.syspath_prepend(str(career))         # nettoyé en téardown
    monkeypatch.syspath_prepend(str(elysium_root))
    llm = importlib.import_module("core.llm_client")
    monkeypatch.setattr(llm, "complete", lambda prompt, **kw:
        '{"relevance_key": "quant", "min_relevance": 0.7, "domains_in": ["quant"], "keywords": ["pricing"]}')
    cfg = cv_target.extract_cfg("Quant developer, derivatives pricing", profile)  # complete_fn=None -> vrai chemin
    assert cfg["min_relevance"] == 0.7
    assert cfg["relevance_key"] == "quant"
    assert cfg["label"]["fr"] == "Ciblé (fiche de poste)"


def test_sovereign_complete_reinserts_elysium_root(monkeypatch):
    """Garde du bug EXACT (le cœur de SP7b) : _sovereign_complete DOIT (ré)insérer la
    RACINE ELYSIUM sur sys.path — le tier-1 `scripts.governance.sigma_llm_gateway`
    (importé lazy dans complete()) en dépend, pas seulement career/. On charge le vrai
    core.llm_client (complete stubbé = zéro réseau), on RETIRE elysium_root de sys.path,
    on appelle _sovereign_complete, et on vérifie qu'il l'a bien réinséré. Une régression
    vers « insère career seul » ferait échouer ce test."""
    import sys
    import importlib
    resolved = cv_target._resolve_career(pathlib.Path(cv_target.__file__).resolve())
    if resolved is None:
        pytest.skip("sibling ELYSIUM/career/core/llm_client.py absent (attendu en CI site)")
    career, elysium_root = resolved
    monkeypatch.syspath_prepend(str(career))         # career requis pour importer le module
    llm = importlib.import_module("core.llm_client")
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "{}")   # zéro réseau
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(elysium_root)])
    assert str(elysium_root) not in sys.path
    cv_target._sovereign_complete("job posting")
    assert str(elysium_root) in sys.path             # _sovereign_complete l'a (ré)inséré


def test_extract_cfg_falls_back_loud_when_resolver_absent(profile, monkeypatch, caplog):
    """Résolveur absent → _sovereign_complete lève → extract_cfg retombe sur le
    cfg défaut ET logge un WARNING (fallback bruyant, jamais muet)."""
    monkeypatch.setattr(cv_target, "_resolve_career", lambda here: None)
    with caplog.at_level(logging.WARNING):
        cfg = cv_target.extract_cfg("Quant developer", profile)  # complete_fn=None -> vrai chemin -> raise
    assert cfg["min_relevance"] == 0.0
    assert cfg["relevance_key"] == "general"
    assert any("cfg défaut" in r.message for r in caplog.records)
