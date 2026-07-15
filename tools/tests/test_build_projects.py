"""Task 2 fusion projects — build_projects.py génère la page depuis profile.json
+ snippets fichiers. Design de page conservé ; seule la source change."""
import html as _h
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_projects as bp  # noqa: E402


def _profile():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def test_page_has_all_cards():
    p = _profile()
    page = bp.render_projects_page(p)
    for pr in p["projects"]:
        assert f'id="{pr["id"]}"' in page, pr["id"]
        assert bp.e(bp._fr(pr["name"])) in page, pr["id"]


def test_anchors_present():
    page = bp.render_projects_page(_profile())
    assert 'id="derivatives-pricer"' in page and 'id="monte-carlo-gbm"' in page


def test_filters_from_tag_labels():
    p = _profile()
    page = bp.render_projects_page(p)
    assert 'data-filter="all"' in page
    for tag in {t for pr in p["projects"] for t in pr["tags"]}:
        assert f'data-filter="{bp.e(tag)}"' in page, tag


def test_snippet_code_loaded_from_file():
    p = _profile()
    page = bp.render_projects_page(p)
    dp = next(pr for pr in p["projects"] if pr["id"] == "derivatives-pricer")
    code = (ROOT / dp["snippet"]["file"]).read_text(encoding="utf-8")
    first = _h.escape(code.strip().splitlines()[0], quote=False)
    assert first in page


def test_snippet_missing_file_fails_loud():
    import pytest
    pr = next(x for x in _profile()["projects"] if x.get("snippet"))
    pr = json.loads(json.dumps(pr))
    pr["snippet"]["file"] = "snippets/does-not-exist.py"
    with pytest.raises(bp.BuildError):
        bp.render_snippet(pr)


def test_build_idempotent():
    p = _profile()
    once = bp.render_projects_page(p)
    assert bp.render_projects_page(p) == once


def test_name_used_not_title():
    # le schéma unifié nomme 'name' ; render_card doit lire name
    p = _profile()
    pr = next(x for x in p["projects"] if x["id"] == "tms-bouygues")
    page = bp.render_projects_page(p)
    assert bp.e(pr["name"]) in page


def test_bilingual_project_renders_fr():
    p = _profile()
    page = bp.render_projects_page(p)
    pfe = next(x for x in p["projects"] if x["id"] == "pfe-hedging")
    assert bp.e(bp._fr(pfe["name"])) in page          # rend .fr
    assert pfe["name"]["fr"] in page and pfe["name"]["en"] not in page
