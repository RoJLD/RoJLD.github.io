import json
import profile_pipeline as pp


def _profile():
    return {
        "$version": "1.0.0",
        "identity": {"first_name": "Robin", "last_name": "Denis"},
        "domains": [{"id": "quant", "label": {"fr": "Quant", "en": "Quant"}},
                    {"id": "risk", "label": {"fr": "Risk", "en": "Risk"}}],
        "experiences": [{"id": "alten", "title": {"fr": "Q", "en": "Q"}, "domains": ["quant"]}],
        "education": [{"id": "ece", "title": {"fr": "E", "en": "E"}}],
        "projects": [{"id": "p1", "name": "P1", "type": "personal", "context": "alten", "domains": ["quant", "risk"]}],
        "articles": [{"id": "a1", "title": {"fr": "A", "en": "A"}, "domains": ["risk"]}],
        "demos": [{"id": "d1", "title": "D1", "project": "p1"}],
        "skills": {"programming": [{"name": "Python", "used_in": ["alten", "p1"], "contexts": ["quant"]}],
                   "radar_scores": {"quant": 0.9}},
        "journey": [{"ref": "experience:alten"}],
    }


def test_parse_and_validate_ok_and_reject():
    parsed, errs = pp.parse_and_validate(json.dumps(_profile()), validate_fn=lambda p: [])
    assert parsed is not None and errs == []
    _, e2 = pp.parse_and_validate("{bad json", validate_fn=lambda p: [])
    assert e2 and "JSON" in e2[0]
    _, e3 = pp.parse_and_validate(json.dumps({"x": 1}), validate_fn=lambda p: ["boom"])
    assert e3 == ["boom"]
    _, e4 = pp.parse_and_validate(json.dumps([1, 2]), validate_fn=lambda p: [])
    assert e4 and "objet" in e4[0]


def test_snapshot(tmp_path):
    prof = tmp_path / "profile.json"; prof.write_text('{"a":1}', encoding="utf-8")
    hist = tmp_path / "hist"
    snap = pp.snapshot_profile(prof, hist, "20260717T101010")
    assert snap.exists() and snap.name == "profile-20260717T101010.json"
    lines = (hist / "log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 and "20260717T101010" in lines[0]
    assert pp.snapshot_profile(tmp_path / "nope.json", hist, "x") is None


def test_atomic_write(tmp_path):
    prof = tmp_path / "profile.json"
    pp.atomic_write_profile({"a": 1, "é": "à"}, prof)
    assert json.loads(prof.read_text(encoding="utf-8")) == {"a": 1, "é": "à"}


def test_build_profile_graph():
    g = pp.build_profile_graph(_profile())
    types = g["summary"]["by_type"]
    assert types["domain"] == 2 and types["experience"] == 1 and types["project"] == 1
    assert types["skill"] == 1 and types["demo"] == 1 and types["article"] == 1
    rels = {(e["source"], e["target"], e["rel"]) for e in g["edges"]}
    assert ("experience:alten", "domain:quant", "has_domain") in rels
    assert ("skill:Python", "experience:alten", "used_in") in rels
    assert ("skill:Python", "domain:quant", "context") in rels
    assert ("demo:d1", "project:p1", "demo_of") in rels
    assert ("project:p1", "experience:alten", "context") in rels
    assert ("article:a1", "domain:risk", "has_domain") in rels
    assert g["summary"]["edges"] == len(g["edges"])


def test_graph_no_phantom_edge():
    prof = _profile()
    prof["demos"][0]["project"] = "ghost"
    g = pp.build_profile_graph(prof)
    assert not any(e["target"] == "project:ghost" for e in g["edges"])


def test_write_profile_graph(tmp_path):
    g = pp.build_profile_graph(_profile())
    out = tmp_path / "data" / "profile_graph.json"
    pp.write_profile_graph(g, out)
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["nodes"] == g["summary"]["nodes"]
