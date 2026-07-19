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
    for name in ["blog", "interests", "testimonials", "experience", "education", "journey", "demos"]:
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
        assert f'<div class="{bs._HT_CLS[j["kind"]]}"' in html
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

def test_render_demos_teaser():
    p = bs.load_profile()
    html = bs.render_demos(p)
    for d in p["demos"]:
        assert f'href="/demos/#{d["id"]}"' in html          # teaser -> /demos/
        assert bs.esc(d["title"]) in html and bs.esc(d["category"]) in html
        assert f'data-i18n="{d["id"]}_desc"' in html

def test_gen_i18n_demos_bilingual():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_demos(p, "fr"), bs.gen_i18n_demos(p, "en")
    assert p["demos"][0]["desc"]["fr"] in fr and p["demos"][0]["desc"]["en"] in en
    assert "bs_desc" in fr and "mc_desc" in en

def test_homepage_demos_is_teaser_no_widgets():
    p = bs.load_profile()
    out = bs.build_html((bs.ROOT / "index.html").read_text(encoding="utf-8"), p)
    for d in p["demos"]:
        assert f'/demos/#{d["id"]}' in out                  # teaser cliquable
    assert 'id="mcCanvas"' not in out and 'oninput="bsCalc()"' not in out  # widgets partis

def test_index_html_no_demo_js():
    src = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    for fn in ("function bsCalc", "function mcRun", "function normCdf", "let currentMC"):
        assert fn not in src, fn


def test_build_also_generates_projects_page():
    import build_projects as bp
    p = bs.load_profile()
    out = bp.build_projects(p, write=False)
    assert 'id="derivatives-pricer"' in out and 'id="monte-carlo-gbm"' in out
    import build_site, inspect
    assert "build_projects" in inspect.getsource(build_site.build)


# ── SP1 modals + frise cliquable ──────────────────────────────────────────────
def test_modals_generated_for_each_ref():
    p = bs.load_profile()
    html = bs.render_modals(p)
    refs = {j["ref"] for j in p["journey"]}
    for r in refs:
        assert f'id="{bs._ref_slug(r)}"' in html, r
    assert html.count('class="modal-ov"') == len(refs)  # 7 uniques
    assert html.count("modal-x") == len(refs)

def test_experience_and_education_modals_reuse_section_keys():
    html = bs.render_modals(bs.load_profile())
    assert 'data-i18n="exp3_title"' in html   # manco = experiences[2] -> exp3
    assert 'data-i18n="edu1_title"' in html    # ece = education[0] -> edu1

def test_project_modal_bilingual_keys():
    p = bs.load_profile()
    fr, en = bs.gen_i18n_modals(p, "fr"), bs.gen_i18n_modals(p, "en")
    assert "mproj_pfe_hedging_summary" in fr and "mproj_pfe_hedging_summary" in en
    assert "mproj_elysium_name" in fr

def test_journey_items_clickable():
    html = bs.render_journey(bs.load_profile())
    assert html.count('onclick="openModal(') == 8
    assert 'data-ref="experience:manco_2024"' in html

def test_build_injects_modals_and_ui():
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    out = bs.build_html(html, p)
    assert "<!-- BUILD:modals -->" in out and "<!-- /BUILD:modals -->" in out
    assert 'id="modal-experience-manco_2024"' in out
    assert "function openModal" in out and "function closeModal" in out
    assert ".modal-ov{" in out
    assert "mproj_pfe_hedging_summary:" in out

def test_saved_en_reapplies_lang_after_dom_ready():
    # régression SP1 : modals (fin de body) traduits au chargement EN initial
    p = bs.load_profile()
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    out = bs.build_html(html, p)
    assert "DOMContentLoaded" in out
    assert out.count("applyLang('en')") >= 2  # immédiat + re-apply DCL


def test_build_also_generates_explorer_page():
    import build_browse as bbr
    p = bs.load_profile()
    out = bbr.build_browse(p, write=False)
    assert out.count('class="e-card"') == 28 and '<title>Explorer' in out
    import build_site, inspect
    assert "build_browse" in inspect.getsource(build_site.build)


def test_nav_explorer_link_everywhere():
    import build_projects as bp, build_demos as bd
    p = bs.load_profile()
    assert 'href="/explorer/"' in bp.build_projects(p, write=False)
    assert 'href="/explorer/"' in bd.build_demos(p, write=False)
    assert 'href="/explorer/"' in (bs.ROOT / "index.html").read_text(encoding="utf-8")


def test_build_also_generates_highlights_page():
    import build_highlights as bhl
    p = bs.load_profile()
    out = bhl.build_highlights(p, write=False)
    assert '<title>Highlights' in out and out.count('class="h-card"') > 0
    import build_site, inspect
    assert "build_highlights" in inspect.getsource(build_site.build)


def test_nav_highlights_link_everywhere():
    import build_projects as bp, build_demos as bd, build_browse as bb
    p = bs.load_profile()
    assert 'href="/highlights/"' in bp.build_projects(p, write=False)
    assert 'href="/highlights/"' in bd.build_demos(p, write=False)
    assert 'href="/highlights/"' in bb.render_browse_page(p)
    assert 'href="/highlights/"' in (bs.ROOT / "index.html").read_text(encoding="utf-8")


def test_build_also_generates_academy_page():
    import build_academy as bac
    out = bac.build_academy(bac.load_academy(), write=False)
    assert '<title>Academy' in out and out.count('class="topic"') == 4
    import build_site, inspect
    assert "build_academy" in inspect.getsource(build_site.build)


def test_nav_academy_link_everywhere():
    import build_projects as bp, build_demos as bd, build_browse as bb, build_highlights as bh
    p = bs.load_profile()
    assert 'href="/academy/"' in bp.build_projects(p, write=False)
    assert 'href="/academy/"' in bd.build_demos(p, write=False)
    assert 'href="/academy/"' in bb.render_browse_page(p)
    assert 'href="/academy/"' in bh.render_highlights_page(p)
    assert 'href="/academy/"' in (bs.ROOT / "index.html").read_text(encoding="utf-8")


def test_build_also_generates_graph_page():
    import build_graph as bg
    p = bs.load_profile()
    out = bg.build_graph(p, write=False)
    assert '<title>Graphe du profil' in out and out.count('class="gnode"') > 0
    import build_site, inspect
    assert "build_graph" in inspect.getsource(build_site.build)


def test_nav_has_graph_link():
    import build_projects as bp, build_demos as bd, build_browse as bb, build_highlights as bh, build_academy as bac
    p = bs.load_profile()
    assert 'href="/graph/"' in bp.build_projects(p, write=False)
    assert 'href="/graph/"' in bd.build_demos(p, write=False)
    assert 'href="/graph/"' in bb.render_browse_page(p)
    assert 'href="/graph/"' in bh.render_highlights_page(p)
    assert 'href="/graph/"' in bac.render_academy_page(bac.load_academy())
    assert 'href="/graph/"' in (bs.ROOT / "index.html").read_text(encoding="utf-8")


# ── Articles : cartes bilingues + ordre de génération ─────────────────────────

def test_carte_article_porte_les_deux_langues():
    import build_site
    markup = build_site.render_blog(build_site.load_profile())
    assert 'data-article-fr="articles/couverture-dynamique.html"' in markup
    assert 'data-article-en="articles/couverture-dynamique.en.html"' in markup


def test_carte_replie_sur_le_fr_si_traduction_absente(monkeypatch):
    """Quand la page anglaise n'existe pas, les deux attributs pointent le FR.
    Promettre une page absente produirait un 404 sur un lien public."""
    import build_site, pathlib
    vrai_exists = pathlib.Path.exists
    monkeypatch.setattr(pathlib.Path, "exists",
                        lambda self: False if self.name.endswith(".en.html") else vrai_exists(self))
    markup = build_site.render_blog(build_site.load_profile())
    assert 'data-article-en="articles/couverture-dynamique.html"' in markup
    assert ".en.html" not in markup


def test_articles_generes_avant_index():
    """`render_blog` teste l'existence de la page EN sur disque : si les articles
    étaient générés APRÈS index.html (comme les six autres builders), une
    construction sur clone frais figerait des liens FR que seule une seconde
    construction corrigerait. L'ordre est donc une contrainte, pas un détail."""
    import inspect, build_site
    src = inspect.getsource(build_site.build)
    assert src.index("import build_articles") < src.index("out = build_html("), \
        "build_articles doit précéder build_html"


def test_carte_soon_reste_non_cliquable():
    """L'article `soon` n'a pas d'URL : il ne doit porter aucun attribut de lien."""
    import build_site
    markup = build_site.render_blog(build_site.load_profile())
    soon = [c for c in markup.split("<") if "opacity:.55" in c]
    assert soon, "la carte `soon` a disparu"
    assert markup.count("data-article-fr") == 1


def test_echec_du_builder_articles_remonte(monkeypatch):
    """Zero Masking : si la génération des articles échoue, build() doit s'arrêter.

    Un mutant remplaçant le `raise BuildError` par `pass` survivait à toute la
    suite : la construction se serait poursuivie en vert avec des pages d'articles
    périmées ou absentes, et rien ne l'aurait dit."""
    import pytest
    import build_articles

    def _boum(*a, **k):
        raise RuntimeError("boum")

    monkeypatch.setattr(build_articles, "build_articles", _boum)
    with pytest.raises(bs.BuildError, match="articles"):
        bs.build(write=False)


def test_sources_manquantes_signalees_en_production(capsys):
    """I1. `build_articles` retourne les manques, une docstring l'exige et un test
    le vérifie — mais le SEUL appelant de production jetait le retour. La garantie
    Zero Masking n'existait que dans le test. Émettre n'est pas garder."""
    bs.build(write=False)
    sortie = capsys.readouterr().out
    assert "source d'article absente" in sortie
    assert "onchain_analytics" in sortie


def test_les_trois_surfaces_portent_le_href_bilingue():
    """I5. index #blog, explorer et highlights annoncent tous l'article et ont tous
    une bascule FR/EN. N'en câbler qu'une laisse les deux autres traduire le titre
    puis envoyer l'anglophone sur la page française."""
    import build_browse, build_highlights
    profile = bs.load_profile()

    idx = bs.render_blog(profile)
    assert 'data-article-en="articles/couverture-dynamique.en.html"' in idx

    browse = build_browse.build_browse(profile, write=False)
    assert 'data-href-en="/articles/couverture-dynamique.en.html"' in browse
    assert "data-href-fr" in browse

    hl = build_highlights.build_highlights(profile, write=False)
    assert 'data-href-en="/articles/couverture-dynamique.en.html"' in hl


def test_les_trois_bascules_reecrivent_le_href():
    """Le marquage ne sert à rien sans le JS qui le consomme — la carte resterait
    sur le FR. Vérifié sur les trois pages générées."""
    import build_browse, build_highlights
    profile = bs.load_profile()
    idx = bs.build_html((bs.ROOT / "index.html").read_text(encoding="utf-8"), profile)
    assert "querySelectorAll('[data-article-fr]')" in idx
    for page in (build_browse.build_browse(profile, write=False),
                 build_highlights.build_highlights(profile, write=False)):
        assert "querySelectorAll('[data-href-fr][data-href-en]')" in page
