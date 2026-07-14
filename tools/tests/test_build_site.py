"""Tests SP0 keystone. Modèle réframé : PAS de parité byte (les copies avaient dérivé) —
on teste que le rendu vient de profile.json, que l'i18n contenu est bilingue, que le build
est idempotent et fail-loud, et que les clés-chrome i18n sont préservées."""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import build_site as bs  # noqa: E402


# ── Moteur ────────────────────────────────────────────────────────────────────
def test_inject_replaces_between_markers():
    t = "A<!-- BUILD:x -->OLD<!-- /BUILD:x -->B"
    assert bs.inject(t, "<!-- BUILD:x -->", "<!-- /BUILD:x -->", "NEW") == \
        "A<!-- BUILD:x -->NEW<!-- /BUILD:x -->B"

def test_inject_missing_marker_fails_loud():
    import pytest
    with pytest.raises(bs.BuildError):
        bs.inject("no markers", "<!-- BUILD:x -->", "<!-- /BUILD:x -->", "NEW")

def test_inject_idempotent():
    t = "A<!-- BUILD:x -->OLD<!-- /BUILD:x -->B"
    once = bs.inject(t, "<!-- BUILD:x -->", "<!-- /BUILD:x -->", "NEW")
    assert bs.inject(once, "<!-- BUILD:x -->", "<!-- /BUILD:x -->", "NEW") == once

def test_fmt_date_bilingual():
    assert bs.fmt_date("2026-03", "fr") == "Mars 2026"
    assert bs.fmt_date("2026-03", "en") == "March 2026"

def test_fmt_date_failloud():
    import pytest
    with pytest.raises(bs.BuildError):
        bs.fmt_date("mars", "fr")


# ── Rendu #blog depuis profile.json ───────────────────────────────────────────
def test_render_blog_from_profile():
    p = bs.load_profile()
    html = bs.render_blog(p)
    pub = [a for a in p["articles"] if a.get("status") != "soon"]
    soon = [a for a in p["articles"] if a.get("status") == "soon"]
    for a in pub:
        assert a["title"]["fr"] in html and f'href="{a["url"]}"' in html
    for a in soon:
        assert a["title"]["fr"] in html
        assert 'data-i18n="blog_soon"' in html  # badge « À venir »
    # une carte soon n'est PAS un lien <a> cliquable
    if soon:
        assert 'style="opacity:.55;cursor:default"' in html

def test_gen_i18n_blog_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_blog(p, "fr"), bs.gen_i18n_blog(p, "en")
    assert p["articles"][0]["title"]["fr"] in fr
    assert p["articles"][0]["title"]["en"] in en
    assert "blog1_title" in fr and "blog1_desc" in fr


# ── Rendu #interests depuis profile.json ──────────────────────────────────────
def test_render_interests_from_profile():
    p = bs.load_profile()
    html = bs.render_interests(p)
    for L in p["languages"]:
        assert bs.esc(L["name"]["fr"]) in html and L["flag"] in html
        assert f'data-i18n="lang_{L["code"]}"' in html
    for it in p["interests"]:
        assert bs.esc(it["fr"]) in html  # esc : & -> &amp; (HTML valide)

def test_gen_i18n_langs_ints_bilingual():
    p = bs.load_profile()
    assert p["languages"][0]["name"]["fr"] in bs.gen_i18n_langs(p, "fr")
    assert p["languages"][0]["name"]["en"] in bs.gen_i18n_langs(p, "en")
    assert p["interests"][0]["fr"] in bs.gen_i18n_ints(p, "fr")
    assert p["interests"][0]["en"] in bs.gen_i18n_ints(p, "en")


# ── Build intégré (index.html instrumenté réel) ───────────────────────────────
def _built():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    return bs.build_html(html, p), p

def test_build_fills_markers_and_content_present():
    out, p = _built()
    for name in ["blog", "interests"]:
        assert f"<!-- BUILD:{name} -->" in out and f"<!-- /BUILD:{name} -->" in out
    for a in p["articles"]:
        assert a["title"]["fr"] in out
    for L in p["languages"]:
        assert bs.esc(L["name"]["fr"]) in out
    for it in p["interests"]:
        assert bs.esc(it["fr"]) in out

def test_build_idempotent():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    once = bs.build_html(html, p)
    assert bs.build_html(once, p) == once

def test_chrome_i18n_preserved():
    out, _ = _built()
    # clés-chrome NON générées → toujours présentes, intactes
    assert 'sec_blog: "Articles & Notes"' in out
    assert "nav_exp:" in out
    assert 'blog_soon: "À venir"' in out  # badge label reste chrome
