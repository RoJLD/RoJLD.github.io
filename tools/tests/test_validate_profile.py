"""Tests for the CV corpus validator (Sigma-CV-SPINE 1.1)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/ importable

from validate_profile import validate  # noqa: E402

REPO = Path(__file__).resolve().parents[2]  # tools/tests/ -> repo root


def _valid_profile():
    return {
        "$version": "1.1.0",
        "identity": {
            "tagline": {"fr": "x", "en": "x"},
            "status": {"fr": "x", "en": "x"},
        },
        "domains": [
            {"id": "quant", "label": {"fr": "Q", "en": "Q"}},
            {"id": "dev", "label": {"fr": "D", "en": "D"}},
        ],
        "education": [{"id": "ece", "title": {"fr": "t", "en": "t"}, "org": {"fr": "o", "en": "o"}}],
        "experiences": [{
            "id": "job1",
            "title": {"fr": "t", "en": "t"},
            "bullets": {"fr": ["a"], "en": ["a"]},
            "domains": ["quant"],
        }],
        "projects": [
            {"id": "proj1", "name": "P1", "type": "personal", "context": "job1", "domains": ["dev"]},
            {"id": "elysium", "name": "Ely", "type": "personal", "context": "personal", "domains": ["dev"]},
        ],
        "skills": {
            "programming": [{"name": "Python", "used_in": ["job1", "proj1"]}],
            "radar_scores": {"Quant": 0.9},
        },
    }


def test_valid_profile_passes():
    assert validate(_valid_profile()) == []


def test_missing_version():
    p = _valid_profile(); del p["$version"]
    assert any("$version" in e for e in validate(p))


def test_unknown_domain():
    p = _valid_profile(); p["experiences"][0]["domains"] = ["nope"]
    assert any("unknown domain 'nope'" in e for e in validate(p))


def test_empty_domains():
    p = _valid_profile(); p["projects"][0]["domains"] = []
    assert any("empty domains" in e for e in validate(p))


def test_unresolved_used_in():
    p = _valid_profile(); p["skills"]["programming"][0]["used_in"] = ["ghost"]
    assert any("used_in 'ghost'" in e for e in validate(p))


def test_bad_context():
    p = _valid_profile(); p["projects"][0]["context"] = "proj1"  # a project can't be a context
    assert any("context 'proj1'" in e for e in validate(p))


def test_missing_bilingual():
    p = _valid_profile(); p["experiences"][0]["title"] = {"fr": "only"}
    assert any("title: must have both" in e for e in validate(p))


def test_empty_radar():
    p = _valid_profile(); p["skills"]["radar_scores"] = {}
    assert any("radar_scores" in e for e in validate(p))


def test_real_profile_json_valid():
    """The actual site profile.json must validate (RED before 1.1 enrichment)."""
    profile = json.loads((REPO / "profile.json").read_text(encoding="utf-8"))
    errs = validate(profile)
    assert errs == [], f"{len(errs)} error(s): {errs}"


def test_project_requires_type_and_name():
    p = _valid_profile()
    p["projects"][0].pop("name", None)
    p["projects"][0]["type"] = "bogus"
    errs = validate(p)
    assert any("name" in e for e in errs)
    assert any("type" in e for e in errs)
