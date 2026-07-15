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


# ── Rendu #testimonials depuis profile.json ───────────────────────────────────
def test_render_testimonials_from_profile():
    p = bs.load_profile()
    html = bs.render_testimonials(p)
    for i, r in enumerate(p["recommendations"], start=1):
        assert bs.esc(r["text"]["fr"]) in html
        assert r["author"] in html and r["initials"] in html
        assert f'data-i18n="testi{i}"' in html
        for m, d in enumerate(r["docs"], start=1):
            assert d["path"] in html and f'data-i18n="testi{i}_doc{m}"' in html

def test_gen_i18n_testi_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_testi(p, "fr"), bs.gen_i18n_testi(p, "en")
    assert p["recommendations"][0]["text"]["fr"] in fr
    assert p["recommendations"][0]["text"]["en"] in en
    assert "testi1_doc1" in fr


# ── Rendu #experience depuis profile.json (bilingue déjà, CV-consommé) ────────
def test_fmt_range_bilingual():
    assert bs.fmt_range("2026-02", "2026-08", "fr") == "Février – Août 2026"
    assert bs.fmt_range("2026-02", "2026-08", "en") == "February – August 2026"

def test_render_experience_from_profile():
    p = bs.load_profile()
    html = bs.render_experience(p)
    for i, e in enumerate(p["experiences"], start=1):
        assert bs.esc(e["title"]["fr"]) in html
        assert f'data-i18n="exp{i}_title"' in html and f'data-i18n="exp{i}_per"' in html
        assert e["company"] in html
        for j in range(1, len(e["bullets"]["fr"]) + 1):
            assert f'data-i18n="exp{i}_b{j}"' in html

def test_gen_i18n_exp_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_exp(p, "fr"), bs.gen_i18n_exp(p, "en")
    assert p["experiences"][0]["title"]["fr"] in fr
    assert p["experiences"][0]["title"]["en"] in en
    assert "Février" in fr and "February" in en  # dates résolues par langue


# ── Build intégré (index.html instrumenté réel) ───────────────────────────────
def _built():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    return bs.build_html(html, p), p

def test_build_fills_markers_and_content_present():
    out, p = _built()
    for name in ["blog", "interests", "testimonials", "experience", "education", "journey", "demo_bs", "demo_mc"]:
        assert f"<!-- BUILD:{name} -->" in out and f"<!-- /BUILD:{name} -->" in out
    for r in p["recommendations"]:
        assert r["author"] in out
    for e in p["experiences"]:
        assert e["company"] in out
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


# ── Rendu #education depuis profile.json (restructuré, bilingue, NON CV-lu) ────
def test_education_has_prepa_entry():
    p = bs.load_profile()
    ids = [e["id"] for e in p["education"]]
    assert ids == ["ece", "prepa"]  # Prépa remontée dans la donnée (était affichage-only)

def test_render_education_from_profile():
    p = bs.load_profile()
    html = bs.render_education(p)
    for i, e in enumerate(p["education"], start=1):
        assert bs.esc(bs._bi(e["title"], "fr")) in html
        assert f'data-i18n="edu{i}_title"' in html and f'data-i18n="edu{i}_org"' in html
        assert f'<span class="per">{bs.esc(e["period"])}</span>' in html
    # ECE a des cours (dont le 1er désormais traduisible) + un capstone
    assert 'data-i18n="edu1_courses_label"' in html
    assert 'data-i18n="edu1_c1"' in html  # bug latent corrigé : 1er cours a une clé
    assert 'data-i18n="edu1_pfe_role"' in html and 'data-i18n="edu1_pfe_desc"' in html
    assert 'onclick="sub(this,event)"' in html  # handler collapsible préservé
    # Prépa n'a NI cours NI capstone
    assert 'data-i18n="edu2_courses_label"' not in html
    assert 'data-i18n="edu2_pfe_label"' not in html

def test_render_education_pfe_shows_summary_not_long_desc():
    p = bs.load_profile()
    html = bs.render_education(p)
    cap = p["education"][0]["capstone"]
    assert bs.esc(bs._bi(cap["summary"], "fr")) in html          # texte live (court)
    assert bs.esc(bs._bi(cap["description"], "fr")) not in html  # desc longue réservée SP1

def test_gen_i18n_edu_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_edu(p, "fr"), bs.gen_i18n_edu(p, "en")
    assert p["education"][0]["title"]["fr"] in fr
    assert p["education"][0]["title"]["en"] in en
    # 1er cours traduit dans les deux langues (était FR-only avant le fix)
    assert p["education"][0]["courses"][0]["fr"] in fr
    assert p["education"][0]["courses"][0]["en"] in en
    assert "edu1_c1" in fr and "edu2_title" in en

def test_build_education_integrated():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    out = bs.build_html(html, p)
    assert "<!-- BUILD:education -->" in out and "<!-- /BUILD:education -->" in out
    for e in p["education"]:
        assert bs.esc(bs._bi(e["title"], "fr")) in out
    assert 'sec_edu: "Formation"' in out   # label de section reste chrome
    assert "edu1_courses_label:" in out    # ancien cours_cles migré en contenu généré


# ── Rendu #parcours (frise journey ; champs statiques OU bilingues) ───────────
def test_journey_present_and_shaped():
    p = bs.load_profile()
    assert len(p["journey"]) == 8
    for j in p["journey"]:
        assert j["kind"] in ("edu", "proj", "exp")
        assert set(j.keys()) >= {"year", "kind", "label", "sub"}

def test_render_journey_from_profile():
    p = bs.load_profile()
    html = bs.render_journey(p)
    for i, j in enumerate(p["journey"], start=1):
        assert f'<div class="{bs._HT_CLS[j["kind"]]}">' in html
        for name, val in (("year", j["year"]), ("label", j["label"]), ("sub", j["sub"])):
            if isinstance(val, dict):
                assert f'data-i18n="ht_j{i}_{name}"' in html
                assert bs.esc(bs._bi(val, "fr")) in html
            else:
                assert bs.esc(val) in html
    # champ statique = PAS de data-i18n (année, lieu)
    assert '<span class="ht-year">2019</span>' in html
    assert '<div class="ht-sub">Bouygues Telecom</div>' in html

def test_gen_i18n_journey_only_bilingual_keys():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_journey(p, "fr"), bs.gen_i18n_journey(p, "en")
    # ELYSIUM (item 7) : year + label + sub tous bilingues
    assert "ht_j7_year" in fr and "ht_j7_label" in fr and "ht_j7_sub" in fr
    # item 1 : year statique → PAS de clé year ; label bilingue → clé label
    assert "ht_j1_label" in fr and "ht_j1_year" not in fr
    assert p["journey"][3]["label"]["en"] in en  # "Treasurer & Dev"

def test_build_journey_integrated():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    out = bs.build_html(html, p)
    assert "<!-- BUILD:journey -->" in out and "<!-- /BUILD:journey -->" in out
    assert "sec_parcours:" in out    # titre de section reste chrome
    assert "journey_hint:" in out    # hint reste chrome
    assert 'data-i18n="ht_j1_label"' in out


# ── Rendu #demos (méta data-driven ; widgets JS-bound préservés) ──────────────
def test_demos_present():
    p = bs.load_profile()
    assert [d["id"] for d in p["demos"]] == ["bs", "mc"]

def test_render_demo_info():
    p = bs.load_profile()
    for did, render in (("bs", bs.render_demo_bs), ("mc", bs.render_demo_mc)):
        d = next(x for x in p["demos"] if x["id"] == did)
        html = render(p)
        assert f'<h4>{bs.esc(d["title"])}</h4>' in html
        assert f'data-i18n="{did}_desc"' in html
        assert bs.esc(bs._bi(d["desc"], "fr")) in html
        assert f'href="{bs.esc(d["link"])}"' in html
        assert 'data-i18n="code_src"' in html  # label lien reste chrome

def test_gen_i18n_demos_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_demos(p, "fr"), bs.gen_i18n_demos(p, "en")
    assert p["demos"][0]["desc"]["fr"] in fr and p["demos"][0]["desc"]["en"] in en
    assert "bs_desc" in fr and "mc_desc" in en

def test_build_demos_preserves_widgets():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    out = bs.build_html(html, p)
    assert "<!-- BUILD:demo_bs -->" in out and "<!-- BUILD:demo_mc -->" in out
    # widgets JS-bound INTOUCHÉS (hors marqueurs)
    for wid in ('id="slS"', 'id="mcCanvas"', 'oninput="bsCalc()"', 'onclick="mcRun(50)"', 'id="callP"'):
        assert wid in out
    # méta data-driven présente
    assert "Black-Scholes Pricer" in out and "Simulation Monte Carlo (GBM)" in out
