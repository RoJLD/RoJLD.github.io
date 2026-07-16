import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_browse as bb  # noqa: E402


def _p():
    import json
    return json.loads((bb.ROOT / "profile.json").read_text(encoding="utf-8"))


# ── helpers ──
def test_sortkey():
    assert bb._sortkey("2026-03") == "2026-03"
    assert bb._sortkey("2021 – 2026") == "2026-00"
    assert bb._sortkey("2025") == "2025-00"
    assert bb._sortkey("") == "0000-00"
    assert bb._sortkey(None) == "0000-00"


def test_pair():
    assert bb._pair("x") == ("x", "x")
    assert bb._pair({"fr": "a", "en": "b"}) == ("a", "b")
    assert bb._pair(None) == ("", "")


def test_truncate():
    assert bb._truncate("court") == "court"
    long = "m" * 200
    out = bb._truncate(long)
    assert len(out) <= 160 and out.endswith("…")


def test_period():
    assert bb._period("2026-02", "2026-08", True) == ("2026 – présent", "2026 – present")
    assert bb._period("2021-09", "2026-09", False) == ("2021 – 2026", "2021 – 2026")


# ── normaliseurs ──
def test_norm_project():
    p = _p()["projects"][0]
    en = bb._norm_project(p)
    assert en["type"] == "project"
    assert en["href"] == f'/projects/#{p["id"]}'
    assert en["sort"] == bb._sortkey(p.get("date", ""))


def test_norm_demo_pinned():
    d = _p()["demos"][0]
    en = bb._norm_demo(d)
    assert en["type"] == "demo" and en["href"] == f'/demos/#{d["id"]}'
    assert en["sort"] == bb.DEMO_PIN
    assert en["date_display"] == ("", "")


def test_norm_article_soon_and_href():
    arts = _p()["articles"]
    soon = next(a for a in arts if a.get("status") == "soon")
    en = bb._norm_article(soon)
    assert en["soon"] is True
    assert en["href"] == "/#blog"  # pas d'url -> ancre blog
    published = next(a for a in arts if a.get("url"))
    assert bb._norm_article(published)["href"] == published["url"]


def test_norm_experience_composed_title():
    x = _p()["experiences"][0]
    en = bb._norm_experience(x)
    assert en["type"] == "experience" and en["href"] == "/#experience"
    assert x["company"] in en["title"][0] and x["company"] in en["title"][1]
    assert en["desc"][0] == bb.one_line(x["bullets"]["fr"][0])


def test_norm_education_and_reco():
    p = _p()
    ed = bb._norm_education(p["education"][0])
    assert ed["href"] == "/#education" and ed["date_display"][0] == p["education"][0]["period"]
    r = p["recommendations"][0]
    rn = bb._norm_recommendation(r)
    assert rn["href"] == "/#testimonials"
    assert r["author"] in rn["title"][0]
    assert len(rn["desc"][0]) <= 160


# ── aggregate ──
def test_aggregate_count():
    ents = bb.aggregate(_p())
    assert len(ents) == 28  # 17+2+2+3+2+2
    assert {e["type"] for e in ents} == set(bb.TYPE_ORDER)


def test_aggregate_sorted_desc_demos_first():
    ents = bb.aggregate(_p())
    keys = [e["sort"] for e in ents]
    assert keys == sorted(keys, reverse=True)
    assert ents[0]["type"] == "demo"  # pin 9999-99


# ── rendu carte ──
def test_render_card_attrs_and_bilingual():
    p = _p()
    en = bb._norm_experience(p["experiences"][0])
    card = bb.render_card(en)
    assert 'class="e-card"' in card and 'data-type="experience"' in card
    assert f'href="{bb.e(en["href"])}"' in card
    assert 'data-fr="' in card and 'data-en="' in card
    s = card.split('data-search="')[1].split('"')[0]
    assert en["title"][0].split()[0].lower() in s
    assert "voir →" in card.lower() and "view →" in card.lower()


def test_render_card_soon_pill():
    soon = next(a for a in _p()["articles"] if a.get("status") == "soon")
    card = bb.render_card(bb._norm_article(soon))
    assert 'e-soon' in card and 'à venir' in card


def test_render_card_no_date_for_demo():
    card = bb.render_card(bb._norm_demo(_p()["demos"][0]))
    assert 'class="e-date"' not in card  # démo sans date


# ── page ──
def test_page_controls_and_toggles():
    out = bb.render_browse_page(_p())
    assert out.count('class="f-btn') == 7            # Tous + 6 types
    assert 'id="q"' in out and 'id="count"' in out and 'id="empty"' in out
    assert 'onclick="toggleLang()"' in out and 'onclick="tgTheme()"' in out
    assert out.count('class="e-card"') == 28
    assert '/explorer/' in out and 'class="on"' in out  # nav Explorer actif


def test_chips_bilingual():
    chips = bb._chips()
    assert 'data-filter="all"' in chips and 'data-fr="Tous"' in chips
    for t in bb.TYPE_ORDER:
        assert f'data-filter="{t}"' in chips


def test_build_browse_returns_html():
    out = bb.build_browse(_p(), write=False)
    assert '<title>' in out and 'Explorer' in out


def test_page_idempotent():
    p = _p()
    assert bb.render_browse_page(p) == bb.render_browse_page(p)
