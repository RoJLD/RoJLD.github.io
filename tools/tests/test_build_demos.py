"""SP2 Task 2 — build_demos génère /demos/ (widgets + code du projet lié + filtre)."""
import html as _h
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_demos as bd  # noqa: E402


def _p():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def test_page_has_widgets_and_meta():
    p = _p()
    page = bd.render_demos_page(p)
    for d in p["demos"]:
        assert f'id="{d["id"]}"' in page, d["id"]
        assert d["title"] in page
    assert 'id="mcCanvas"' in page and 'oninput="bsCalc()"' in page  # widgets injectés
    assert "function mcRun" in page and "function bsCalc" in page      # JS widget injecté


def test_code_extract_from_linked_project():
    p = _p()
    page = bd.render_demos_page(p)
    bs = next(d for d in p["demos"] if d["id"] == "bs")
    code = (ROOT / f"snippets/{bs['project']}.py").read_text(encoding="utf-8")
    assert _h.escape(code.strip().splitlines()[0], quote=False) in page
    assert "/projects/#derivatives-pricer" in page  # cross-lien


def test_category_filter():
    p = _p()
    page = bd.render_demos_page(p)
    assert 'data-filter="all"' in page
    for c in {d["category"] for d in p["demos"]}:
        assert bd.e(c) in page


def test_idempotent():
    p = _p()
    assert bd.render_demos_page(p) == bd.render_demos_page(p)


def test_gist_link_conditional():
    p = _p()
    demo = next(d for d in p["demos"] if d["id"] == "bs")
    assert "Gist" not in bd.render_card(demo)  # pas de gist -> pas de lien
    withg = dict(demo); withg["gist"] = "https://gist.github.com/RoJLD/abc123"
    card = bd.render_card(withg)
    assert 'href="https://gist.github.com/RoJLD/abc123"' in card and "Gist" in card
