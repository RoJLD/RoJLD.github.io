"""SP2 Task 1 — demos[] += category/project + widgets extraits en fichiers."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _p():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def test_demos_have_category_and_project():
    p = _p()
    proj = {x["id"] for x in p["projects"]}
    assert p["demos"], "demos vide"
    for d in p["demos"]:
        assert d.get("category"), d["id"]
        assert d.get("project") in proj, d["id"]
        assert "link" not in d


def test_widget_files_extracted():
    for wid in ("bs", "mc"):
        for ext in ("html", "js"):
            f = ROOT / f"demos/widgets/{wid}.{ext}"
            assert f.exists() and f.read_text(encoding="utf-8").strip(), f"{wid}.{ext}"
    assert "normCdf" in (ROOT / "demos/widgets/bs.js").read_text(encoding="utf-8")
    assert "function bsCalc" in (ROOT / "demos/widgets/bs.js").read_text(encoding="utf-8")
    assert "mcCanvas" in (ROOT / "demos/widgets/mc.html").read_text(encoding="utf-8")
    assert "function mcRun" in (ROOT / "demos/widgets/mc.js").read_text(encoding="utf-8")
