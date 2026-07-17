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


def test_render_flashcard_bilingual():
    fc = {"level": "Recall", "front": {"fr": "AvantFR", "en": "FrontEN"}, "back": {"fr": "ArriereFR", "en": "BackEN"}}
    h = ba.render_flashcard(fc)
    assert 'data-level="Recall"' in h
    assert 'data-front-fr="AvantFR"' in h and 'data-front-en="FrontEN"' in h
    assert 'data-back-fr="ArriereFR"' in h and 'data-back-en="BackEN"' in h


def test_render_question_attrs():
    q = {"level": "Apply", "correct": 1, "prompt": {"fr": "PromptFR", "en": "PromptEN"},
         "options": [{"fr": "o0", "en": "o0"}, {"fr": "o1", "en": "o1"}],
         "concept": {"fr": "conceptFR", "en": "conceptEN"}, "explanation": {"fr": "explFR", "en": "explEN"}}
    h = ba.render_question(q, 2)
    assert 'data-correct="1"' in h and 'data-level="Apply"' in h
    assert 'data-concept-fr="conceptFR"' in h and 'data-concept-en="conceptEN"' in h
    assert h.count('class="q-opt"') == 2
    assert 'data-fr="PromptFR"' in h and 'data-fr="explFR"' in h


def test_render_topic_has_link_flash_quiz():
    t = ba.load_academy()["topics"][0]
    h = ba.render_topic(t)
    assert f'href="{t["link"]}"' in h
    assert 'class="fc"' in h and 'class="q-card"' in h
    assert f'data-topic="{t["id"]}"' in h


def test_page_structure():
    out = ba.render_academy_page(ba.load_academy())
    assert out.count('class="topic"') == 4
    assert 'onclick="toggleLang()"' in out and 'onclick="tgTheme()"' in out
    assert 'function scoreQuiz' in out and "localStorage" in out
    assert 'academy-progress' in out
    assert 'class="on"' in out and '/academy/' in out


def test_build_academy_returns_html():
    out = ba.build_academy(ba.load_academy(), write=False)
    assert '<title>Academy' in out


def test_page_idempotent():
    d = ba.load_academy()
    assert ba.render_academy_page(d) == ba.render_academy_page(d)
