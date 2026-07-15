"""SP1 Task 1 — journey[].ref résolus + 2 projets bilingues."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _p():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


REFS = {"education:prepa", "education:ece", "experience:manco_2024", "experience:bouygues_2025",
        "experience:alten_2026", "project:pfe-hedging", "project:elysium"}


def test_every_journey_has_resolvable_ref():
    p = _p()
    exp = {e["id"] for e in p["experiences"]}
    edu = {e["id"] for e in p["education"]}
    proj = {x["id"] for x in p["projects"]}
    for j in p["journey"]:
        assert j.get("ref"), j
        t, _, i = j["ref"].partition(":")
        assert ((t == "experience" and i in exp) or (t == "education" and i in edu)
                or (t == "project" and i in proj)), j["ref"]
    assert {j["ref"] for j in p["journey"]} == REFS


def test_two_projects_bilingual():
    p = _p()
    byid = {x["id"]: x for x in p["projects"]}
    for pid in ("pfe-hedging", "elysium"):
        for f in ("name", "summary", "impact"):
            v = byid[pid][f]
            assert isinstance(v, dict) and set(v) == {"fr", "en"}, (pid, f)
    others = [x for x in p["projects"] if x["id"] not in ("pfe-hedging", "elysium")]
    assert all(isinstance(x["name"], str) for x in others)
