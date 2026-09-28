"""Tests for the CV corpus validator (Sigma-CV-SPINE 1.1)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/ importable

from validate_profile import validate  # noqa: E402

REPO = Path(__file__).resolve().parents[2]  # tools/tests/ -> repo root


def _valid_profile():
    return {
        "$version": "1.1.0",
        "identity": {
            "tagline": {"fr": "x", "en": "x"},
            "status": {"fr": "x", "en": "x"},
        },
        "domains": [
            {"id": "quant", "label": {"fr": "Q", "en": "Q"}},
            {"id": "dev", "label": {"fr": "D", "en": "D"}},
        ],
        "education": [{"id": "ece", "title": {"fr": "t", "en": "t"}, "org": {"fr": "o", "en": "o"}}],
        "experiences": [{
            "id": "job1",
            "title": {"fr": "t", "en": "t"},
            "bullets": {"fr": ["a"], "en": ["a"]},
            "domains": ["quant"],
        }],
        "projects": [
            {"id": "proj1", "name": "P1", "type": "personal", "context": "job1", "domains": ["dev"]},
            {"id": "elysium", "name": "Ely", "type": "personal", "context": "personal", "domains": ["dev"]},
        ],
        "skills": {
            "programming": [{"name": "Python", "used_in": ["job1", "proj1"]}],
            "radar_scores": {"Quant": 0.9},
        },
    }


def test_valid_profile_passes():
    assert validate(_valid_profile()) == []


def test_missing_version():
    p = _valid_profile(); del p["$version"]
    assert any("$version" in e for e in validate(p))


def test_unknown_domain():
    p = _valid_profile(); p["experiences"][0]["domains"] = ["nope"]
    assert any("unknown domain 'nope'" in e for e in validate(p))


def test_empty_domains():
    p = _valid_profile(); p["projects"][0]["domains"] = []
    assert any("empty domains" in e for e in validate(p))


def test_unresolved_used_in():
    p = _valid_profile(); p["skills"]["programming"][0]["used_in"] = ["ghost"]
    assert any("used_in 'ghost'" in e for e in validate(p))


def test_bad_context():
    p = _valid_profile(); p["projects"][0]["context"] = "proj1"  # a project can't be a context
    assert any("context 'proj1'" in e for e in validate(p))


def test_missing_bilingual():
    p = _valid_profile(); p["experiences"][0]["title"] = {"fr": "only"}
    assert any("title: must have both" in e for e in validate(p))


def test_empty_radar():
    p = _valid_profile(); p["skills"]["radar_scores"] = {}
    assert any("radar_scores" in e for e in validate(p))


def test_real_profile_json_valid():
    """The actual site profile.json must validate (RED before 1.1 enrichment)."""
    profile = json.loads((REPO / "profile.json").read_text(encoding="utf-8"))
    errs = validate(profile)
    assert errs == [], f"{len(errs)} error(s): {errs}"


def test_project_requires_type_and_name():
    p = _valid_profile()
    p["projects"][0].pop("name", None)
    p["projects"][0]["type"] = "bogus"
    errs = validate(p)
    assert any("name" in e for e in errs)
    assert any("type" in e for e in errs)


def _alten_en_cours(p):
    """L'état exact de l'incident sur origin/main (2026-08-04 → 2026-09-28)."""
    p["$updated"] = "2026-07-07"
    p["experiences"][0].update({"company": "ALTEN", "start": "2026-02",
                                "end": "2026-08", "current": True})
    return p


def test_le_temps_qui_passe_suffit_a_perimer_un_poste_en_cours():
    """ALTEN portait `current: true` ET `end: "2026-08"` : le rendu CV imprime
    « présent » dès que `current` est vrai, sans regarder `end`. Les 8 PDF publiés
    ont affirmé « 2026-02 → présent » un mois après la fin du stage.

    Personne n'avait retouché le profil : `$updated` était resté au 2026-07-07.
    Une règle adossée à `$updated` seul se taisait donc sur l'incident même. La
    date de référence est la plus récente entre la relecture et le build."""
    p = _alten_en_cours(_valid_profile())
    assert validate(p) == []                       # sans date de build : muet, comme avant
    errs = validate(p, today="2026-09-05")         # un build le 5 septembre
    assert any("current" in e and "job1" in e for e in errs), errs


def test_une_relecture_posterieure_a_la_fin_suffit_aussi():
    p = _alten_en_cours(_valid_profile())
    p["$updated"] = "2026-09-28"
    assert any("current" in e and "job1" in e for e in validate(p))


def test_une_fin_prevue_non_depassee_reste_valide():
    """Un stage en cours a souvent une fin connue d'avance. Le mois de fin lui-même
    est encore « en cours » : la borne est stricte."""
    p = _alten_en_cours(_valid_profile())
    assert validate(p, today="2026-07-15") == []
    assert validate(p, today="2026-08-31") == []    # dernier mois du stage


def test_la_date_de_fin_doit_etre_lisible_par_le_build():
    """`fmt_range` exige 'YYYY-MM' ; une autre forme passait la validation puis
    faisait échouer la reconstruction (ou, pire, la règle d'échéance à tort)."""
    for mauvaise in ("2026", "Août 2026", "2026-8", "2026-08-31"):
        p = _valid_profile()
        p["experiences"][0]["end"] = mauvaise
        assert any("end" in e and "job1" in e for e in validate(p)), mauvaise


def test_le_statut_ne_peut_pas_citer_une_entreprise_quittee():
    """C'est le texte libre du statut qui a menti sur la page d'accueil, pas le
    drapeau : « Actuellement : Quant Researcher DeFi @ ALTEN » avec current=false."""
    p = _valid_profile()
    p["experiences"][0].update({"company": "ALTEN", "start": "2026-02",
                                "end": "2026-08", "current": False})
    p["identity"]["status"] = {"fr": "Actuellement : Quant Researcher DeFi @ ALTEN",
                               "en": "Currently: DeFi Quant Researcher @ ALTEN"}
    assert any("identity.status" in e and "ALTEN" in e for e in validate(p))
    # …alors qu'un poste réellement en cours peut être cité.
    p["experiences"][0].update({"end": "2026-12", "current": True})
    assert validate(p, today="2026-09-28") == []


def test_article_domains_must_be_valid_ids():
    real = json.loads((REPO / "profile.json").read_text(encoding="utf-8"))
    assert validate(real) == []  # profil réel : articles portent des domaines valides
    bad = json.loads((REPO / "profile.json").read_text(encoding="utf-8"))
    bad["articles"][0]["domains"] = ["not_a_domain"]
    assert any("unknown domain" in e and "article" in e for e in validate(bad))
