"""K2 + K3 — sélection de preuves (pure) et brouillon (LLM, seam injectable).

Aucun réseau : `complete_fn` est toujours injecté. Les tests décrivent l'ENTRÉE
(profil, job_context, squelette) et laissent le code produire la SORTIE.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

import cv_letter
import cv_select


REPO = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def profile():
    """Profil miniature de forme IDENTIQUE au vrai : les expériences ont un dict
    `relevance`, les projets n'ont que `domains` — c'est le bloqueur de donnée
    mesuré (17 projets sur 17 sans `relevance`).

    **QUATRE expériences, et pas trois.** Un test d'ordre sur une liste que le
    filtre réduit à un seul élément est vacuement vrai : c'est exactement ce qui
    laissait passer la mutation `list(reversed(select_experiences(...)))`
    (M22, 124 passed). Quatre entrées permettent de retenir un PRÉFIXE STRICT de
    trois, donc de distinguer l'ordre, la troncature et une rotation. Rejeu de la
    leçon Σ-A-TWO-ITEM-FIXTURE-CANNOT-TEST-A-BOUNDARY.
    """
    return {
        "identity": {"first_name": "Ada", "last_name": "Lovelace",
                     "email": "ada@example.org", "phone": "+33 6 00 00 00 00",
                     "location": {"city": "Paris", "country": "France"},
                     "links": {"linkedin": "https://linkedin.com/in/ada"}},
        "domains": [{"id": "quant"}, {"id": "risk"}, {"id": "dev"}, {"id": "ai"}],
        "experiences": [
            # `current: True` AVEC une date de fin renseignée : c'est la forme du
            # profil de production (un CDD en cours), et c'est elle qui a fait
            # fuiter `.end` dans l'index clampé alors que le rédacteur lit
            # « présent ». Une fixture avec `end: ""` ne l'exerce pas.
            {"id": "exp_quant", "company": "Nexora", "title": {"fr": "Quant", "en": "Quant"},
             "start": "2024-01", "end": "2026-12", "current": True, "domains": ["quant"],
             "relevance": {"quant": 0.95, "risk": 0.4, "general": 0.7},
             "bullets": {"fr": ["Calibré des modèles", "Écrit un pricer"],
                         "en": ["Calibrated models", "Wrote a pricer"]}},
            {"id": "exp_risk", "company": "Manco", "title": {"fr": "Risk", "en": "Risk"},
             "start": "2021-01", "end": "2023-12", "current": False, "domains": ["risk"],
             "relevance": {"quant": 0.3, "risk": 0.95, "general": 0.5},
             "bullets": {"fr": ["Suivi le risque"], "en": ["Monitored risk"]}},
            {"id": "exp_dev", "company": "Bouygues", "title": {"fr": "Dev", "en": "Dev"},
             "start": "2020-01", "end": "2020-12", "current": False, "domains": ["dev"],
             "relevance": {"quant": 0.2, "risk": 0.2, "general": 0.4},
             "bullets": {"fr": ["Livré un outil"], "en": ["Shipped a tool"]}},
            {"id": "exp_stage", "company": "Sopra", "title": {"fr": "Stage", "en": "Intern"},
             "start": "2019-01", "end": "2019-06", "current": False, "domains": ["ai"],
             "relevance": {"quant": 0.1, "risk": 0.1, "general": 0.2},
             "bullets": {"fr": ["Annoté un jeu de données"], "en": ["Labelled a dataset"]}},
        ],
        "projects": [
            # `date` : montrée au rédacteur en guise de période, et absente de
            # tout index jusqu'à cette vague (divergence inverse mesurée).
            {"id": "pricer", "name": "Pricer", "domains": ["quant", "dev"], "featured": True,
             "date": "2023 — 2024",
             "summary": {"fr": "Un pricer Monte-Carlo.", "en": "A Monte-Carlo pricer."}},
            {"id": "hmm", "name": "HMM", "domains": ["quant", "ai"],
             "summary": {"fr": "Régimes de marché.", "en": "Market regimes."}},
            {"id": "robot", "name": "Robot", "domains": ["dev"],
             "summary": {"fr": "Un bras robot.", "en": "A robot arm."}},
        ],
        "lifestyle": {"freedom_number": "MARQUEUR-PRIVE-42"},
        "career_goals": {"compensation": 0.75},
    }


def _fn(payload):
    """complete_fn factice : renvoie `payload` (str, ou dict/list sérialisé)."""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return lambda _prompt: text


def _jc(**over):
    base = {"relevance_key": "quant", "min_relevance": 0.9, "domains_in": [], "keywords": [],
            "company": None, "job_title": None, "requirements": [],
            "register": "neutre", "market": None}
    base.update(over)
    return base


# ── K2 : select_evidence, pur ───────────────────────────────────────────────────

def test_experiences_are_exactly_the_cv_selection(profile):
    """LA garantie tenable : les expériences de la lettre sont un PRÉFIXE de la
    sélection du CV — même appel, même score, même ordre.

    Le SEUIL fait le test. Avec `min_relevance=0.9` (version précédente),
    `select_experiences` ne rend qu'UNE expérience et « même ordre » est
    trivialement vrai : la mutation `list(reversed(...))` laissait 124 tests
    verts. Le seuil est donc à 0.0 — quatre expériences retenues, trois
    conservées — et les gardes ci-dessous refusent que le test redevienne vide.
    """
    jc = _jc(relevance_key="quant", min_relevance=0.0, domains_in=[])
    cv_ids = [e["id"] for e in cv_select.select_experiences(profile, jc)]
    ev = cv_letter.select_evidence(profile, jc)
    letter_ids = [e["id"] for e in ev if e["kind"] == "experience"]

    # GARDES DU GARDE — sans eux l'égalité finale peut être vraie sans rien dire.
    assert len(cv_ids) >= 4, f"fixture trop petite ({cv_ids}) : la troncature ne s'exerce pas"
    assert len(letter_ids) >= 3, f"ordre indécidable sur {letter_ids}"
    assert len(set(letter_ids)) == len(letter_ids)
    assert letter_ids != list(reversed(letter_ids)), "fixture palindrome : l'ordre est indécidable"

    assert letter_ids == cv_ids[:len(letter_ids)]


def test_the_letter_truncates_the_cv_selection_it_never_permutes_it(profile):
    """Les trois permutations qu'un tri « inoffensif » produirait : inversion,
    rotation, et queue de liste. Chacune doit être discernable."""
    jc = _jc(relevance_key="quant", min_relevance=0.0, domains_in=[])
    cv_ids = [e["id"] for e in cv_select.select_experiences(profile, jc)]
    letter_ids = [e["id"] for e in cv_letter.select_evidence(profile, jc)
                  if e["kind"] == "experience"]
    n = len(letter_ids)
    assert n >= 3 and len(cv_ids) > n, "préfixe STRICT requis pour discriminer"

    assert letter_ids == cv_ids[:n]                       # préfixe, dans l'ordre
    assert letter_ids != list(reversed(cv_ids))[:n]       # inversion
    assert letter_ids != cv_ids[1:n + 1]                  # rotation d'un cran
    assert letter_ids != cv_ids[-n:]                      # queue de liste


def test_projects_scored_on_domain_overlap_not_relevance(profile):
    """Aucun projet n'a de `relevance` : un score fondé dessus rendrait 0.0 pour
    les 17. Le score des projets est donc un recouvrement de domaines, et il est
    ÉTIQUETÉ comme tel."""
    jc = _jc(relevance_key="quant", min_relevance=0.99, domains_in=["quant", "ai"])
    ev = cv_letter.select_evidence(profile, jc)
    projs = [e for e in ev if e["kind"] == "project"]
    assert projs, "aucun projet retenu alors que domains_in recouvre"
    assert all(p["score_basis"] == "domains" for p in projs)
    assert all(e["score_basis"] == "relevance" for e in ev if e["kind"] == "experience")


def test_project_without_domain_overlap_is_never_invented(profile):
    """domains_in vide → aucun projet ne peut être justifié → aucun n'est retenu.
    On ne fabrique pas de pertinence pour remplir un quota."""
    ev = cv_letter.select_evidence(profile, _jc(domains_in=[]))
    assert [e["kind"] for e in ev] == ["experience"] * len(ev)


def test_project_scores_are_ordered_by_overlap(profile):
    jc = _jc(relevance_key="quant", min_relevance=0.99, domains_in=["quant", "dev"])
    ev = cv_letter.select_evidence(profile, jc, max_items=3)
    projs = [(e["id"], e["score"]) for e in ev if e["kind"] == "project"]
    assert projs == sorted(projs, key=lambda t: -t[1])
    assert projs[0][0] == "pricer"        # quant+dev = 2/2, seul à recouvrir les deux


def test_at_most_max_items_and_deterministic(profile):
    jc = _jc(min_relevance=0.0, domains_in=["quant", "dev", "ai"])
    a = cv_letter.select_evidence(profile, jc, max_items=3)
    b = cv_letter.select_evidence(profile, jc, max_items=3)
    assert len(a) <= 3 and a == b


def test_a_project_can_displace_a_third_experience(profile):
    """Avec des projets qualifiés, on garde au plus max_items-1 expériences :
    sinon la lettre ne parlerait jamais d'un projet."""
    jc = _jc(min_relevance=0.0, domains_in=["quant"])
    ev = cv_letter.select_evidence(profile, jc, max_items=3)
    assert sum(1 for e in ev if e["kind"] == "experience") == 2
    assert sum(1 for e in ev if e["kind"] == "project") == 1


def test_evidence_sources_resolve_in_the_profile(profile):
    import cv_grounding
    ev = cv_letter.select_evidence(profile, _jc(min_relevance=0.0, domains_in=["quant"]))
    for e in ev:
        assert cv_grounding.resolve_source(profile, e["source"]) is not cv_grounding.MISSING


def test_select_evidence_does_not_mutate_the_profile(profile):
    before = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    cv_letter.select_evidence(profile, _jc(min_relevance=0.0, domains_in=["quant"]))
    assert json.dumps(profile, sort_keys=True, ensure_ascii=False) == before


# ── K3 : faits transmis — ce qu'on ne donne pas ne peut pas être déformé ────────

def test_facts_exclude_everything_not_selected(profile):
    ev = cv_letter.select_evidence(profile, _jc(relevance_key="quant", min_relevance=0.9))
    facts = cv_letter.build_profile_facts(profile, ev, "fr")
    blob = json.dumps(facts, ensure_ascii=False)
    assert "MARQUEUR-PRIVE-42" not in blob     # lifestyle jamais transmis
    assert "compensation" not in blob          # career_goals jamais transmis
    assert "Manco" not in blob                 # expérience non retenue
    assert "Nexora" in blob                    # expérience retenue


def test_facts_never_carry_the_phone(profile):
    ev = cv_letter.select_evidence(profile, _jc(min_relevance=0.0))
    facts = cv_letter.build_profile_facts(profile, ev, "fr")
    assert "+33" not in json.dumps(facts, ensure_ascii=False)


def test_bullets_per_evidence_are_capped():
    """Borne jamais exercée jusqu'ici — la fixture n'avait que 2 puces, la coupe
    ne s'appliquait donc à rien. Neutralisée, la suite restait verte. L'attendu
    est celui qu'on a ÉCRIT EN ENTRÉE (cinq puces nommées), pas la borne du code :
    déplacer la borne se voit ici."""
    prof = {"identity": {}, "projects": [],
            "experiences": [{"id": "e", "company": "C", "title": "T",
                             "relevance": {"general": 1.0},
                             "bullets": {"fr": ["b0", "b1", "b2", "b3", "b4"]}}]}
    ev = [{"kind": "experience", "id": "e", "source": "experiences[e]",
           "score": 1.0, "score_basis": "relevance"}]
    points = cv_letter.build_profile_facts(prof, ev, "fr")["evidence"][0]["points"]
    assert points == ["b0", "b1", "b2"]          # les PREMIÈRES, dans l'ordre


def test_the_writer_bullet_cap_and_the_verifier_clamp_cut_at_the_same_place():
    """Cross-cutting, et c'est là que ça casse en silence : la coupe du rédacteur
    (`build_profile_facts`) et le clamp du vérificateur
    (`cv_grounding.build_fact_index(..., evidence=)`) doivent tomber au MÊME
    index. Une puce montrée mais hors index bloquerait une affirmation vraie ;
    une puce hors prompt mais dans l'index rouvrirait le trou de la garantie."""
    import cv_grounding
    prof = {"identity": {"first_name": "Ada", "last_name": "L"}, "projects": [],
            "experiences": [{"id": "e", "company": "C", "title": "T",
                             "relevance": {"general": 1.0},
                             "bullets": {"fr": ["b0", "b1", "b2", "b3", "b4"]}}]}
    ev = [{"kind": "experience", "id": "e", "source": "experiences[e]",
           "score": 1.0, "score_basis": "relevance"}]
    shown = cv_letter.build_profile_facts(prof, ev, "fr")["evidence"][0]["points"]
    indexed = [r["text"] for r in cv_grounding.build_fact_index(prof, "fr", evidence=ev)
               if r["source"].startswith("experiences[e].bullets.")]
    assert shown == indexed


def test_facts_resolve_the_requested_language(profile):
    ev = cv_letter.select_evidence(profile, _jc(relevance_key="quant", min_relevance=0.9))
    fr = json.dumps(cv_letter.build_profile_facts(profile, ev, "fr"), ensure_ascii=False)
    en = json.dumps(cv_letter.build_profile_facts(profile, ev, "en"), ensure_ascii=False)
    assert "Calibré des modèles" in fr and "Calibrated models" not in fr
    assert "Calibrated models" in en and "Calibré des modèles" not in en


# ── K3 : squelettes ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", ["fr", "en"])
def test_shipped_skeletons_parse(lang):
    sk = cv_letter.load_skeleton("standard", lang)
    assert sk["lang"] == lang and sk["id"] == "standard"
    assert sk["sections"], "squelette sans section"
    for s in sk["sections"]:
        assert s["intention"] and isinstance(s["budget_mots"], int)


def test_skeletons_are_not_translations_of_each_other():
    """Contrainte du spec §7 : chaque langue a SA lettre. Des budgets et des
    identifiants de section identiques trahiraient une traduction mécanique."""
    fr = cv_letter.load_skeleton("standard", "fr")
    en = cv_letter.load_skeleton("standard", "en")
    assert [s["id"] for s in fr["sections"]] != [s["id"] for s in en["sections"]]
    assert fr["budget_mots"] != en["budget_mots"]


def test_skeleton_missing_intention_is_rejected_loud():
    text = "---\nid: x\nlang: fr\nbudget_mots: 100\n---\n\n## accroche\n- budget_mots: 40\n"
    with pytest.raises(cv_letter.LetterError):
        cv_letter.parse_skeleton(text)


def test_skeleton_without_frontmatter_is_rejected_loud():
    with pytest.raises(cv_letter.LetterError):
        cv_letter.parse_skeleton("## accroche\n- intention: x\n- budget_mots: 10\n")


def test_unknown_skeleton_raises(tmp_path):
    with pytest.raises(cv_letter.LetterError):
        cv_letter.load_skeleton("inexistant", "fr", root=tmp_path)


# ── K3 : draft ──────────────────────────────────────────────────────────────────

def _facts(profile, **jc_over):
    jc = _jc(**jc_over)
    ev = cv_letter.select_evidence(profile, jc)
    return cv_letter.build_profile_facts(profile, ev, "fr"), jc


def test_draft_prompt_carries_only_selected_facts(profile):
    seen = {}
    facts, jc = _facts(profile, relevance_key="quant", min_relevance=0.9)
    sk = cv_letter.load_skeleton("standard", "fr")
    cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda p: (seen.setdefault("p", p), "Texte.")[1])
    assert "MARQUEUR-PRIVE-42" not in seen["p"]
    assert "+33" not in seen["p"]
    assert "Manco" not in seen["p"]
    assert "Nexora" in seen["p"]
    for s in sk["sections"]:                      # le squelette guide réellement
        assert s["id"] in seen["p"]


def test_draft_returns_the_model_text_untouched(profile):
    facts, jc = _facts(profile, min_relevance=0.0)
    sk = cv_letter.load_skeleton("standard", "fr")
    out = cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda _p: "  Une lettre.  ")
    assert out == "Une lettre."


def test_draft_refuses_a_language_mismatch(profile):
    facts, jc = _facts(profile, min_relevance=0.0)
    sk = cv_letter.load_skeleton("standard", "en")
    with pytest.raises(cv_letter.LetterError):
        cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda _p: "text")


def test_draft_refuses_without_evidence(profile):
    jc = _jc(relevance_key="quant", min_relevance=1.01, domains_in=[])
    ev = cv_letter.select_evidence(profile, jc)
    assert ev == []
    facts = cv_letter.build_profile_facts(profile, ev, "fr")
    sk = cv_letter.load_skeleton("standard", "fr")
    with pytest.raises(cv_letter.LetterError):
        cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda _p: "text")


def test_draft_raises_instead_of_inventing_when_llm_fails(profile):
    """Aucun repli en prose : un brouillon de secours serait de la fabrication."""
    facts, jc = _facts(profile, min_relevance=0.0)
    sk = cv_letter.load_skeleton("standard", "fr")

    def boom(_p):
        raise RuntimeError("LLM down")

    with pytest.raises(cv_letter.LetterError):
        cv_letter.draft(facts, jc, sk, "fr", complete_fn=boom)


def test_draft_refuses_an_empty_completion(profile):
    facts, jc = _facts(profile, min_relevance=0.0)
    sk = cv_letter.load_skeleton("standard", "fr")
    with pytest.raises(cv_letter.LetterError):
        cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda _p: "   ")


def test_draft_routes_through_the_sovereign_resolver_by_default(profile, monkeypatch):
    """Le défaut ne doit JAMAIS être anthropic.Anthropic : ADR-003 impose le
    passage par cv_target._sovereign_complete (budget cap SIGIL-529)."""
    called = {}

    def fake_sovereign(prompt):
        called["p"] = prompt
        return "Lettre."

    monkeypatch.setattr(cv_letter.cv_target, "_sovereign_complete", fake_sovereign)
    facts, jc = _facts(profile, min_relevance=0.0)
    sk = cv_letter.load_skeleton("standard", "fr")
    assert cv_letter.draft(facts, jc, sk, "fr") == "Lettre."
    assert "p" in called


# ── K5 : document de lettre (structure rendue) ─────────────────────────────────

def test_letter_document_never_carries_the_phone(profile):
    facts, jc = _facts(profile, min_relevance=0.0)
    doc = cv_letter.build_letter_document(profile, facts, jc, "Corps.\n\nSuite.", "fr")
    assert "+33" not in json.dumps(doc, ensure_ascii=False)


def test_letter_document_splits_paragraphs_and_keeps_company(profile):
    facts, jc = _facts(profile, min_relevance=0.0, company="Nexora Capital",
                       job_title="Ingénieur Quantitatif")
    doc = cv_letter.build_letter_document(profile, facts, jc, "Un.\n\nDeux.\n\n\nTrois.", "fr")
    assert doc["paragraphs"] == ["Un.", "Deux.", "Trois."]
    assert doc["recipient"]["company"] == "Nexora Capital"
    assert "Ingénieur Quantitatif" in doc["subject"]


@pytest.mark.parametrize("url", ["https://linkedin.com/in/ada", "http://linkedin.com/in/ada",
                                 "https://www.linkedin.com/in/ada", "www.linkedin.com/in/ada",
                                 "linkedin.com/in/ada"])
def test_letter_document_strips_the_url_scheme_like_the_cv_header(profile, url):
    """Les cinq formes qu'une URL prend dans un profil édité à la main rendent la
    MÊME chaîne affichable. Une seule d'entre elles (celle qui était testée) ne
    distingue ni le retrait de `www.` ni celui de `http://`."""
    profile["identity"]["links"]["linkedin"] = url
    facts, jc = _facts(profile, min_relevance=0.0)
    doc = cv_letter.build_letter_document(profile, facts, jc, "Corps.", "fr")
    assert doc["identity"]["linkedin"] == "linkedin.com/in/ada"


def test_letter_document_without_company_has_no_placeholder(profile):
    """Pas d'entreprise ancrée → pas d'entreprise du tout. Jamais « [Entreprise] »."""
    facts, jc = _facts(profile, min_relevance=0.0)
    doc = cv_letter.build_letter_document(profile, facts, jc, "Corps.", "fr")
    assert doc["recipient"]["company"] is None
    blob = json.dumps(doc, ensure_ascii=False)
    # Un gabarit non rempli (« [Entreprise] », « XXX », « TODO ») serait pire que
    # l'absence : il partirait tel quel chez le recruteur.
    assert not re.search(r"\[[A-Za-zÀ-ÿ]", blob)
    assert "XXX" not in blob and "TODO" not in blob


def test_paragraph_count_is_capped(profile):
    """`_MAX_PARAGRAPHS` : mesuré, 20 paragraphes en entrée → 12 conservés. La
    borne n'était pas testée ; neutralisée, la suite restait verte."""
    facts, jc = _facts(profile, min_relevance=0.0)
    body = "\n\n".join(f"Paragraphe {i}." for i in range(1, 21))
    doc = cv_letter.build_letter_document(profile, facts, jc, body, "fr")
    assert len(doc["paragraphs"]) == 12 == cv_letter._MAX_PARAGRAPHS
    assert doc["paragraphs"][0] == "Paragraphe 1."       # les PREMIERS, dans l'ordre
    assert doc["paragraphs"][-1] == "Paragraphe 12."
    assert "Paragraphe 13." not in doc["paragraphs"]


def test_paragraph_cap_does_not_bite_below_the_bound(profile):
    """L'autre côté du bord : une lettre normale n'est pas amputée. Un seuil
    déplacé vers le bas se verrait ici, pas dans le test précédent."""
    facts, jc = _facts(profile, min_relevance=0.0)
    n = cv_letter._MAX_PARAGRAPHS - 1
    body = "\n\n".join(f"P{i}." for i in range(n))
    doc = cv_letter.build_letter_document(profile, facts, jc, body, "fr")
    assert len(doc["paragraphs"]) == n == 11


@pytest.mark.parametrize("lang", ["fr", "en", "de", "", "zz"])
def test_the_letter_document_is_total_over_languages(profile, lang):
    """Une langue inconnue ne doit pas faire SORTIR une exception d'une fonction
    de rendu : le document se construit, avec un objet non vide. Mesuré : sans
    défaut, `_SUBJECT[lang]` lève un KeyError — chez l'appelant, un 500."""
    facts, jc = _facts(profile, min_relevance=0.0, job_title="Quant")
    doc = cv_letter.build_letter_document(profile, facts, jc, "Corps.", lang)
    assert doc["subject"].strip() and doc["lang"] == lang
    assert "Quant" in doc["subject"]


def test_project_ties_are_broken_by_featured_then_id_never_by_file_order(profile):
    """Le tri se déclare « déterministe » : score, puis `featured`, puis id. À
    score ÉGAL — le seul cas où le départage existe — l'ordre du fichier ne doit
    pas décider. La fixture est écrite à rebours de l'attendu (ordre du fichier
    zeta, alpha, mid) pour que les deux se distinguent."""
    prof = {"identity": profile["identity"], "experiences": [], "projects": [
        {"id": "zeta", "name": "Zeta", "domains": ["quant"], "summary": "Z."},
        {"id": "alpha", "name": "Alpha", "domains": ["quant"], "summary": "A."},
        {"id": "mid", "name": "Mid", "domains": ["quant"], "featured": True, "summary": "M."},
    ]}
    jc = _jc(relevance_key="quant", min_relevance=0.0, domains_in=["quant"])
    ev = cv_letter.select_evidence(prof, jc, max_items=3)
    assert len(ev) == 3 and len({e["score"] for e in ev}) == 1, \
        f"scores non ex æquo : le départage ne s'exerce pas ({ev})"
    assert [e["id"] for e in ev] == ["mid", "alpha", "zeta"]


def test_letter_document_date_is_injected_never_read_from_the_clock(profile):
    facts, jc = _facts(profile, min_relevance=0.0)
    assert cv_letter.build_letter_document(profile, facts, jc, "C.", "fr")["date"] is None
    doc = cv_letter.build_letter_document(profile, facts, jc, "C.", "fr", today="2026-07-28")
    assert doc["date"] == "2026-07-28"


# ── bout en bout sur le VRAI profile.json (aucun réseau) ───────────────────────

REAL_JOB = (
    "Nexora Capital recherche un Ingénieur Quantitatif à Paris.\n"
    "Modélisation de produits dérivés, calibration, Python et C++.\n"
)


@pytest.fixture
def real_profile():
    return json.loads((REPO / "profile.json").read_text(encoding="utf-8"))


def test_end_to_end_on_the_real_profile(real_profile):
    """Le vrai profil : 3 expériences avec `relevance`, 17 projets sans. La chaîne
    complète doit tourner, et chaque preuve doit tracer dans le fichier réel."""
    import cv_grounding
    import cv_letter_render
    import cv_target

    jc = cv_target.extract_job_context(
        REAL_JOB, real_profile,
        complete_fn=_fn({"relevance_key": "quant", "min_relevance": 0.7,
                         "domains_in": ["quant", "dev"], "keywords": ["calibration"],
                         "company": "Nexora Capital", "job_title": "Ingénieur Quantitatif",
                         "requirements": ["Python", "C++"], "register": "formel",
                         "market": "FR"}))
    assert jc["company"] == "Nexora Capital"          # ancré verbatim dans la fiche

    ev = cv_letter.select_evidence(real_profile, jc)
    assert 2 <= len(ev) <= 3
    for e in ev:
        assert cv_grounding.resolve_source(real_profile, e["source"]) is not cv_grounding.MISSING
    assert {e["score_basis"] for e in ev} <= {"relevance", "domains"}

    facts = cv_letter.build_profile_facts(real_profile, ev, "fr")
    sk = cv_letter.load_skeleton("standard", "fr")
    seen = {}

    def fake_writer(prompt):
        seen["p"] = prompt
        return "Je candidate.\n\nJ'ai travaillé sur des modèles.\n\nCordialement."

    body = cv_letter.draft(facts, jc, sk, "fr", complete_fn=fake_writer)

    # Mesuré le 2026-07-28 : `identity.phone` vaut "" dans le profil PUBLIC (le
    # numéro vit dans profile_private.json, cf. meta.note). Le garde utile porte
    # donc sur les champs réellement sensibles qui, eux, SONT dans le fichier.
    assert (real_profile.get("identity") or {}).get("phone") == ""
    for private in ("freedom_number_eur_month", "deal_framework", "optionality_score",
                    "company_type_preference"):
        assert private not in seen["p"], f"champ privé transmis au rédacteur : {private}"
    assert str(real_profile["career_goals"]["short_term"]["target"]) not in seen["p"]

    doc = cv_letter.build_letter_document(real_profile, facts, jc, body, "fr",
                                          today="2026-07-28")

    # Vérificateur factice : une affirmation non supportée → export refusé.
    sents = cv_grounding.split_sentences(body)
    rows = [{"phrase": i, "categorie": "factuelle" if i == 2 else "motivation",
             "affirmation": s, "supporte": False if i == 2 else None, "source": None}
            for i, s in enumerate(sents, 1)]
    verdict = cv_grounding.check_grounding(body, real_profile, "fr",
                                           complete_fn=_fn(rows), evidence=ev)
    assert verdict["ok"] is False
    with pytest.raises(cv_grounding.GroundingBlocked):
        cv_letter_render.render_letter_html_gated(doc, verdict)

    # Le maillon que le chantier existait pour poser : `evidence` clampe les
    # sources recevables sur les faits RÉELLEMENT montrés au rédacteur. Une source
    # qui résout dans le vrai profil mais qu'il n'a jamais vue ne l'ancre pas.
    full = [r["source"] for r in cv_grounding.build_fact_index(real_profile, "fr")]
    clamped = {r["source"] for r in
               cv_grounding.build_fact_index(real_profile, "fr", evidence=ev)}
    assert clamped and clamped < set(full), "le clamp ne retire rien : il ne clampe rien"
    unshown = next(s for s in full if s not in clamped)
    assert cv_grounding.resolve_source(real_profile, unshown) is not cv_grounding.MISSING
    rows[1].update({"supporte": True, "source": unshown})
    blocked = cv_grounding.check_grounding(body, real_profile, "fr",
                                           complete_fn=_fn(rows), evidence=ev)
    assert blocked["ok"] is False
    assert [b["reason"] for b in blocked["blocking"]] == ["source_hors_index"]

    # Même lettre, affirmation ancrée sur un fait MONTRÉ au rédacteur → export permis.
    rows[1].update({"supporte": True, "source": sorted(clamped)[0]})
    verdict2 = cv_grounding.check_grounding(body, real_profile, "fr",
                                            complete_fn=_fn(rows), evidence=ev)
    assert verdict2["ok"] is True, verdict2["blocking"]
    html = cv_letter_render.render_letter_html_gated(doc, verdict2)
    assert "Nexora Capital" in html
    assert "freedom_number_eur_month" not in html


# ══════════════════════════════════════════════════════════════════════════════
# LE COUPLAGE — « les sources recevables = les faits montrés au RÉDACTEUR »
#
# C'est l'invariant qui justifie tout le clamp, et rien ne le surveillait :
# `cv_grounding` était validé contre l'idée qu'on se faisait de `_fact_block`,
# jamais contre ce que `_fact_block` écrit. Deux contre-exemples MESURÉS sur
# `profile.json` de production :
#
#  (1) FUITE — `experiences[alten_2026].end = '2026-08'` était dans l'index
#      clampé, alors que `current: True` fait rendre au rédacteur
#      « 2026-02 → présent » : la valeur brute ne lui est JAMAIS montrée. Une
#      affirmation ancrée dessus obtenait ok=True.
#  (2) DIVERGENCE INVERSE — `projects[trading-algo-csharp].date` EST montré au
#      rédacteur et n'existait dans AUCUN index : une affirmation vraie bloquée.
#
# Le test ci-dessous lit les DEUX SENS, sur le profil réel, contre l'ARTEFACT
# RENDU (le bloc de faits du prompt) et non contre l'implémentation du clamp.
# ══════════════════════════════════════════════════════════════════════════════

def _leaves(node):
    """Aplatissement GÉNÉRIQUE de `profile.json` : il ne connaît ni les sections
    ni les chemins de `build_fact_index`. C'est l'oracle indépendant du sens 2 —
    il voit tout ce que le fichier contient, y compris ce que l'index oublie."""
    if isinstance(node, dict):
        for v in node.values():
            yield from _leaves(v)
    elif isinstance(node, list):
        for v in node:
            yield from _leaves(v)
    elif isinstance(node, str):
        yield node


def _assert_prompt_and_clamp_agree(profile, jc, lang, min_facts=6):
    import cv_grounding
    ev = cv_letter.select_evidence(profile, jc)
    # GARDES DU GARDE : les deux branches du clamp et le cas « poste en cours »
    # doivent être exercés, sinon l'accord est vrai sans rien dire.
    kinds = {e["kind"] for e in ev}
    assert kinds == {"experience", "project"}, f"branches non exercées : {kinds}"
    exps = {e.get("id"): e for e in profile.get("experiences") or []}
    prjs = {p.get("id"): p for p in profile.get("projects") or []}
    assert any(exps[e["id"]].get("current") and exps[e["id"]].get("end")
               for e in ev if e["kind"] == "experience"), \
        "aucune expérience EN COURS avec date de fin : la fuite `.end` ne s'exerce pas"
    assert any(prjs[e["id"]].get("date") for e in ev if e["kind"] == "project"), \
        "aucun projet daté retenu : la divergence `projects[x].date` ne s'exerce pas"

    facts = cv_letter.build_profile_facts(profile, ev, lang)
    block = cv_letter._fact_block(facts)
    idx = cv_grounding.build_fact_index(profile, lang, evidence=ev)
    assert len(idx) >= min_facts, f"index clampé trop pauvre ({len(idx)})"

    # le bloc de faits est bien CE QUE LE RÉDACTEUR LIT
    sk = cv_letter.load_skeleton("standard", lang)
    assert block in cv_letter.build_draft_prompt(facts, jc, sk, lang)

    shown = " ".join(block.split())
    texts = [r["text"] for r in idx]
    paths = [r["source"] for r in idx]

    # SENS 1 — rien n'est ACCEPTÉ qui n'ait été MONTRÉ.
    assert [r["source"] for r in idx if r["text"] not in shown] == []

    # SENS 2 — rien n'est MONTRÉ qui ne soit ANCRABLE. Toute valeur du profil qui
    # apparaît dans le bloc doit être couverte par un fait de l'index (ou n'être
    # que l'étiquette de chemin que nous y écrivons nous-mêmes).
    ungrounded = sorted({v for v in _leaves(profile)
                         if len(v) >= 4 and " ".join(v.split()) in shown
                         and not any(" ".join(v.split()) in t for t in texts)
                         and not any(v in p for p in paths)})
    assert ungrounded == []


def test_the_writers_prompt_and_the_verifiers_clamp_carry_the_same_facts(real_profile):
    """Sur la DONNÉE DE PRODUCTION, dans les deux sens. Ce test unique rougit sur
    la fuite `.end`, sur la divergence `projects[x].date`, et sur toute
    modification de `_fact_block` qui cesse de montrer un fait indexé (les puces,
    le nom du candidat) ou se met à en montrer un qui ne l'est pas (l'e-mail)."""
    _assert_prompt_and_clamp_agree(
        real_profile,
        _jc(relevance_key="quant", min_relevance=0.7, domains_in=["quant", "dev"],
            company="Nexora Capital", job_title="Ingénieur Quantitatif",
            requirements=["Python", "C++"], register="formel", market="FR"),
        "fr", min_facts=12)


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_prompt_and_clamp_agree_on_the_fixture_too(profile, lang):
    """La fixture porte ce que le profil réel n'a pas : un `summary` de projet
    BILINGUE (donc un chemin suffixé par la langue) et une expérience `current`
    avec `end` non nul. Deux formes de plus sur le même invariant."""
    _assert_prompt_and_clamp_agree(
        profile, _jc(relevance_key="quant", min_relevance=0.0, domains_in=["quant"]),
        lang)


def test_the_guarantee_does_not_rest_on_what_the_writer_was_told(real_profile):
    """ADR-003 le dit : une consigne de prompt n'est pas une garantie. On le
    mesure — un rédacteur qui IGNORE entièrement son prompt et fabrique une
    carrière chez Goldman Sachs est arrêté par K4, avec un vérificateur pourtant
    complaisant, parce que la source qu'il cite n'a jamais été montrée."""
    import cv_grounding
    jc = _jc(relevance_key="quant", min_relevance=0.7, domains_in=["quant", "dev"])
    ev = cv_letter.select_evidence(real_profile, jc)
    facts = cv_letter.build_profile_facts(real_profile, ev, "fr")
    sk = cv_letter.load_skeleton("standard", "fr")

    invented = ("J'ai dirigé une équipe de cinquante personnes chez Goldman Sachs "
                "pendant huit ans.")
    body = cv_letter.draft(facts, jc, sk, "fr", complete_fn=lambda _p: invented)
    assert body == invented, "le rédacteur voyou n'a pas produit sa lettre"

    sents = cv_grounding.split_sentences(body)
    complaisant = [{"phrase": i, "categorie": "factuelle", "affirmation": s,
                    "supporte": True, "source": "identity"} for i, s in enumerate(sents, 1)]
    v = cv_grounding.check_grounding(body, real_profile, "fr",
                                     complete_fn=_fn(complaisant), evidence=ev)
    assert v["ok"] is False
    assert [b["reason"] for b in v["blocking"]] == ["source_hors_index"]
