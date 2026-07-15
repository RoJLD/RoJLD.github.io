"""Task 1 fusion projects — état cible de profile.json après migration.
17 projets schéma unifié (ids yaml canoniques, summary seul, domains/context, tags),
snippets extraits en fichiers, project_tag_labels + projects_meta remontés."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _profile():
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


DOMAINS = {"quant", "risk", "finance", "data", "defi", "dev", "ai", "architecture",
           "infra", "knowledge-graph", "research", "product"}
EXP_EDU_CTX = {"bouygues_2025", "alten_2026", "manco_2024", "ece", "personal"}
EXPECTED_IDS = {
    "tms-bouygues", "crypto-exploration", "pfe-hedging", "elysium", "portfolio-site",
    "anthropos", "hmm-studio", "derivatives-pricer", "monte-carlo-gbm", "sudoku-cnn",
    "trading-algo-csharp", "vba-index-tool", "vhdl-calculator", "atc-simulation",
    "gripper-robot", "octoprint-bed-leveller", "ppe-politique-monetaire",
}


def test_seventeen_projects_with_canonical_ids():
    p = _profile()
    ids = {pr["id"] for pr in p["projects"]}
    assert ids == EXPECTED_IDS
    assert len(p["projects"]) == 17


def test_every_project_schema_valid():
    p = _profile()
    for pr in p["projects"]:
        assert pr.get("name"), f"{pr['id']} sans name"
        assert pr.get("type") in {"academic", "personal", "professional"}, pr["id"]
        assert pr.get("summary"), f"{pr['id']} sans summary"
        assert "description" not in pr, f"{pr['id']} a un description résiduel"
        assert pr.get("domains"), f"{pr['id']} sans domains"
        assert set(pr["domains"]) <= DOMAINS, pr["id"]
        assert pr.get("context") in EXP_EDU_CTX, f"{pr['id']} context {pr.get('context')!r}"
        assert isinstance(pr.get("tags"), list) and pr["tags"], f"{pr['id']} sans tags"


def test_anchors_preserved():
    ids = {pr["id"] for pr in _profile()["projects"]}
    assert {"derivatives-pricer", "monte-carlo-gbm", "elysium"} <= ids


def test_snippets_extracted_to_files():
    p = _profile()
    with_snip = {pr["id"] for pr in p["projects"] if pr.get("snippet")}
    assert with_snip == {"elysium", "derivatives-pricer", "monte-carlo-gbm"}
    for pr in p["projects"]:
        sn = pr.get("snippet")
        if not sn:
            continue
        assert "code" not in sn, f"{pr['id']} snippet.code inline résiduel"
        f = ROOT / sn["file"]
        assert f.exists() and f.read_text(encoding="utf-8").strip(), f"{sn['file']} vide/absent"
        assert sn.get("lang") and sn.get("label")


def test_tag_labels_and_meta_promoted():
    p = _profile()
    assert isinstance(p.get("project_tag_labels"), dict) and p["project_tag_labels"]
    assert p.get("projects_meta", {}).get("updated")
    used = {t for pr in p["projects"] for t in pr["tags"]}
    assert used <= set(p["project_tag_labels"]), used - set(p["project_tag_labels"])
