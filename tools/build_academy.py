#!/usr/bin/env python3
"""build_academy.py — génère academy/index.html depuis academy.json.

Academy = flashcards + quiz auto-évalué (moteur porté de HMMstudio en vanilla).
score_quiz est PUR et indiciel (langue-agnostique) ; le gap report bilingue vit
côté JS (data-concept-<lang>). LECTURE de academy.json (profile.json non touché).
"""
from __future__ import annotations

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "academy" / "index.html"
LEVELS = ["Recall", "Apply", "Analyze"]


class BuildError(Exception):
    pass


def load_academy(path=None):
    p = pathlib.Path(path) if path else ROOT / "academy.json"
    return json.loads(p.read_text(encoding="utf-8"))


def score_quiz(questions, answers):
    """PUR. answers[i] = index choisi ou None. Indiciel, langue-agnostique."""
    by = {lv: {"correct": 0, "total": 0} for lv in LEVELS}
    missed = []
    correct = 0
    for i, q in enumerate(questions):
        lv = q["level"]
        by[lv]["total"] += 1
        if answers[i] is not None and answers[i] == q["correct"]:
            correct += 1
            by[lv]["correct"] += 1
        else:
            missed.append(i)
    return {"total": len(questions), "correct": correct, "byLevel": by, "missedIndices": missed}


def _bi_ok(v):
    return isinstance(v, dict) and "fr" in v and "en" in v


def validate_academy(data):
    errors = []
    if not data.get("$version"):
        errors.append("academy: missing $version")
    seen = set()
    for t in data.get("topics", []):
        tid = t.get("id", "?")
        if tid in seen:
            errors.append(f"topic '{tid}': id dupliqué")
        seen.add(tid)
        for f in ("title", "subtitle", "link_label"):
            if not _bi_ok(t.get(f)):
                errors.append(f"topic '{tid}': {f} non bilingue")
        if not t.get("link"):
            errors.append(f"topic '{tid}': link manquant")
        for fc in t.get("flashcards", []):
            if fc.get("level") not in LEVELS:
                errors.append(f"topic '{tid}': flashcard level invalide '{fc.get('level')}'")
            if not _bi_ok(fc.get("front")) or not _bi_ok(fc.get("back")):
                errors.append(f"topic '{tid}': flashcard non bilingue")
        for qi, q in enumerate(t.get("questions", [])):
            if q.get("level") not in LEVELS:
                errors.append(f"topic '{tid}' q{qi}: level invalide '{q.get('level')}'")
            opts = q.get("options") or []
            if len(opts) < 2:
                errors.append(f"topic '{tid}' q{qi}: <2 options")
            if not isinstance(q.get("correct"), int) or not (0 <= q.get("correct", -1) < len(opts)):
                errors.append(f"topic '{tid}' q{qi}: correct hors range")
            for f in ("prompt", "concept", "explanation"):
                if not _bi_ok(q.get(f)):
                    errors.append(f"topic '{tid}' q{qi}: {f} non bilingue")
            for oi, o in enumerate(opts):
                if not _bi_ok(o):
                    errors.append(f"topic '{tid}' q{qi} opt{oi}: non bilingue")
    return errors


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


# ══════════════════ Rendu ══════════════════

def _pill(level):
    return f'<span class="lv lv-{e(level.lower())}">{e(level)}</span>'


def render_flashcard(fc):
    ffr, fen = fc["front"]["fr"], fc["front"]["en"]
    bfr, ben = fc["back"]["fr"], fc["back"]["en"]
    return (
        f'<button type="button" class="fc" data-level="{e(fc["level"])}" '
        f'data-front-fr="{e(ffr)}" data-front-en="{e(fen)}" '
        f'data-back-fr="{e(bfr)}" data-back-en="{e(ben)}">'
        f'{_pill(fc["level"])}'
        f'<span class="fc-face" data-fr="{e(ffr)}" data-en="{e(fen)}">{e(ffr)}</span>'
        f'<span class="fc-hint" data-fr="Cliquer pour révéler" data-en="Click to reveal">Cliquer pour révéler</span>'
        f'</button>'
    )


def render_question(q, idx):
    pfr, pen = q["prompt"]["fr"], q["prompt"]["en"]
    cfr, cen = q["concept"]["fr"], q["concept"]["en"]
    xfr, xen = q["explanation"]["fr"], q["explanation"]["en"]
    opts = "".join(
        f'<button type="button" class="q-opt" data-oi="{oi}" '
        f'data-fr="{e(o["fr"])}" data-en="{e(o["en"])}">{e(o["fr"])}</button>'
        for oi, o in enumerate(q["options"])
    )
    return (
        f'<div class="q-card" data-qi="{idx}" data-correct="{q["correct"]}" data-level="{e(q["level"])}" '
        f'data-concept-fr="{e(cfr)}" data-concept-en="{e(cen)}">'
        f'<p class="q-prompt"><span class="q-num">{idx + 1}.</span> '
        f'<span data-fr="{e(pfr)}" data-en="{e(pen)}">{e(pfr)}</span></p>'
        f'<div class="q-opts">{opts}</div>'
        f'<p class="q-expl" hidden data-fr="{e(xfr)}" data-en="{e(xen)}">{e(xfr)}</p>'
        f'</div>'
    )


def render_topic(t):
    tid = t["id"]
    tfr, ten = t["title"]["fr"], t["title"]["en"]
    sfr, sen = t["subtitle"]["fr"], t["subtitle"]["en"]
    lfr, len_ = t["link_label"]["fr"], t["link_label"]["en"]
    flash = "\n".join(render_flashcard(fc) for fc in t["flashcards"])
    ques = "\n".join(render_question(q, i) for i, q in enumerate(t["questions"]))
    return (
        f'<section class="topic" data-topic="{e(tid)}">'
        f'<button type="button" class="topic-h" aria-expanded="false">'
        f'<span class="topic-tt"><span class="topic-title" data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</span>'
        f'<span class="topic-sub" data-fr="{e(sfr)}" data-en="{e(sen)}">{e(sfr)}</span></span>'
        f'<span class="topic-badge" data-topic-badge="{e(tid)}"></span>'
        f'<span class="topic-caret">▾</span></button>'
        f'<div class="topic-body">'
        f'<a class="topic-link" href="{e(t["link"])}" data-fr="{e(lfr)}" data-en="{e(len_)}">{e(lfr)}</a>'
        f'<h3 class="blk" data-fr="Flashcards" data-en="Flashcards">Flashcards</h3>'
        f'<div class="fc-grid">{flash}</div>'
        f'<h3 class="blk" data-fr="Quiz" data-en="Quiz">Quiz</h3>'
        f'<div class="quiz" data-topic="{e(tid)}">{ques}'
        f'<button type="button" class="q-submit" disabled data-fr="Valider le quiz" data-en="Submit quiz">Valider le quiz</button>'
        f'<div class="q-result" hidden></div></div>'
        f'</div></section>'
    )
