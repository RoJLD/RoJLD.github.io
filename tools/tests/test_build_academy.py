import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_academy as ba  # noqa: E402


def _q(level, correct):
    return {"level": level, "correct": correct, "options": [{"fr": "a", "en": "a"}, {"fr": "b", "en": "b"}],
            "prompt": {"fr": "p", "en": "p"}, "concept": {"fr": "c", "en": "c"}, "explanation": {"fr": "e", "en": "e"}}


def test_score_quiz_counts_and_levels():
    qs = [_q("Recall", 0), _q("Apply", 1), _q("Analyze", 0)]
    r = ba.score_quiz(qs, [0, 0, None])   # Q1 juste, Q2 faux, Q3 non répondu
    assert r["total"] == 3 and r["correct"] == 1
    assert r["byLevel"]["Recall"] == {"correct": 1, "total": 1}
    assert r["byLevel"]["Apply"] == {"correct": 0, "total": 1}
    assert r["byLevel"]["Analyze"] == {"correct": 0, "total": 1}
    assert r["missedIndices"] == [1, 2]


def test_score_quiz_perfect():
    qs = [_q("Recall", 2), _q("Apply", 1)]
    r = ba.score_quiz(qs, [2, 1])
    assert r["correct"] == 2 and r["missedIndices"] == []


def test_validate_real_academy_passes():
    assert ba.validate_academy(ba.load_academy()) == []


def test_validate_catches_bad_correct_and_level():
    data = ba.load_academy()
    data["topics"][0]["questions"][0]["correct"] = 99
    data["topics"][0]["questions"][1]["level"] = "Nope"
    errs = ba.validate_academy(data)
    assert any("correct" in e for e in errs) and any("level" in e for e in errs)


def test_real_content_shape():
    data = ba.load_academy()
    ids = [t["id"] for t in data["topics"]]
    assert ids == ["bs-pricing", "monte-carlo", "hedging", "defi-onchain"]
    for t in data["topics"]:
        assert len(t["flashcards"]) >= 3 and len(t["questions"]) >= 3
