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
