import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_highlights as bh  # noqa: E402


def _p():
    import json
    return json.loads((bh.ROOT / "profile.json").read_text(encoding="utf-8"))


def test_lens_domains():
    lenses = bh.lens_domains(_p())
    assert lenses == ["quant", "risk", "finance", "data", "defi", "dev", "ai", "research", "product"]
    for excl in ("architecture", "infra", "knowledge-graph"):
        assert excl not in lenses


def test_flat_skills_excludes_radar():
    p = _p()
    names = [s.get("name") for s in bh.flat_skills(p)]
    assert "Python" in names
    assert all(isinstance(s, dict) and "name" in s for s in bh.flat_skills(p))


def test_demo_inherits_project_domains():
    p = _p()
    bs = next(d for d in p["demos"] if d["id"] == "bs")
    mc = next(d for d in p["demos"] if d["id"] == "mc")
    assert set(bh.demo_domains(p, bs)) == {"quant", "finance"}
    assert set(bh.demo_domains(p, mc)) == {"quant", "data"}


def test_score_experience():
    p = _p()
    alten = next(x for x in p["experiences"] if x["id"] == "alten_2026")
    s = bh.score_experience(p, alten, "quant")
    assert s == 3 + 0.95 + 0.5 * alten["relevance"]["general"]
    assert bh.score_experience(p, alten, "product") is None


def test_score_project_featured():
    p = _p()
    ely = next(pr for pr in p["projects"] if pr["id"] == "elysium")
    assert bh.score_project(p, ely, "ai") == 5
    assert bh.score_project(p, ely, "quant") is None


def test_score_skill_and_article_and_demo():
    p = _p()
    py = next(s for s in bh.flat_skills(p) if s["name"] == "Python")
    assert bh.score_skill(p, py, "quant") == py["weight"]
    assert bh.score_skill(p, py, "risk") is None
    art = next(a for a in p["articles"] if a["id"] == "couverture_dynamique")
    assert bh.score_article(p, art, "quant") == 3 and bh.score_article(p, art, "ai") is None
    bs = next(d for d in p["demos"] if d["id"] == "bs")
    assert bh.score_demo(p, bs, "finance") == 3 and bh.score_demo(p, bs, "risk") is None


def test_lens_attrs_only_included():
    p = _p()
    ely = next(pr for pr in p["projects"] if pr["id"] == "elysium")
    attrs = bh.lens_attrs(p, bh.lens_domains(p), ely, bh.score_project)
    assert 'data-lens-ai="5"' in attrs
    assert "data-lens-quant" not in attrs


# ── rendu / page (T3) ──
def test_render_project_card_attrs():
    p = _p()
    ely = next(pr for pr in p["projects"] if pr["id"] == "elysium")
    card = bh.render_project(p, bh.lens_domains(p), ely, 0)
    assert 'class="h-card"' in card and 'data-idx="0"' in card
    assert 'data-gen=' in card and 'data-lens-ai="5"' in card
    assert 'href="/projects/#elysium"' in card
    assert 'data-fr="' in card and 'data-en="' in card


def test_page_structure():
    out = bh.render_highlights_page(_p())
    assert out.count('<button class="h-chip') == 10    # Général + 9 lentilles (hors div conteneur h-chips)
    assert 'data-lens="quant"' in out and 'data-lens=""' in out
    assert 'id="copy"' in out and 'id="banner"' in out
    assert 'onclick="toggleLang()"' in out and 'onclick="tgTheme()"' in out
    for sec in ("skills", "experiences", "projects", "demos", "articles"):
        assert f'data-sec="{sec}"' in out
    assert 'LENS_LABELS' in out and 'LENS_IDS' in out
    assert 'class="on"' in out and '/highlights/' in out


def test_build_highlights_returns_html():
    out = bh.build_highlights(_p(), write=False)
    assert '<title>' in out and 'Highlights' in out


def test_page_idempotent():
    p = _p()
    assert bh.render_highlights_page(p) == bh.render_highlights_page(p)
