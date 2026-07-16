#!/usr/bin/env python3
"""build_highlights.py — génère highlights/index.html depuis profile.json.

Vue pitch pondérée par lentille (?lens=<domaine>). Scoring 100% Python émis en
attributs data-lens-<id>/data-gen/data-idx ; le JS lit et trie, ne recalcule rien
(anti-parité Σ-CLIENT-SERVER-RENDER-PARITY).
"""
from __future__ import annotations

import collections
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "highlights" / "index.html"


class BuildError(Exception):
    pass


CAPS = {"skills": 10, "experiences": 3, "projects": 6, "demos": 2, "articles": 2}
REL_AXES = {"quant", "risk", "dev"}   # axes de experience.relevance (hors general)
LENS_MIN = 2                          # seuil domaine -> lentille (exp+projets)


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


def _pair(v):
    if isinstance(v, dict):
        return (v.get("fr", ""), v.get("en", ""))
    return (v or "", v or "")


def _truncate(s, n: int = 150) -> str:
    s = one_line(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _period(start, end, current):
    sy = str(start or "")[:4]
    if current:
        return (f"{sy} – présent", f"{sy} – present")
    ey = str(end or "")[:4]
    base = f"{sy} – {ey}" if ey else sy
    return (base, base)


def _abs_url(u):
    if not u:
        return ""
    if u.startswith(("http://", "https://", "/", "#")):
        return u
    return "/" + u


# ── Lentilles data-driven ──
def lens_domains(profile):
    t = collections.Counter()
    for x in profile.get("experiences", []):
        for d in x.get("domains", []) or []:
            t[d] += 1
    for p in profile.get("projects", []):
        for d in p.get("domains", []) or []:
            t[d] += 1
    order = [d.get("id") for d in profile.get("domains", [])]
    return [d for d in order if t.get(d, 0) >= LENS_MIN]


def domain_label(profile, did):
    for d in profile.get("domains", []):
        if d.get("id") == did:
            return _pair(d.get("label", did))
    return (did, did)


def flat_skills(profile):
    out = []
    for cat, lst in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in (lst or []):
            out.append(s)
    return out


def demo_domains(profile, demo):
    proj = demo.get("project")
    for p in profile.get("projects", []):
        if p.get("id") == proj:
            return p.get("domains", []) or []
    return []


# ── Scores par lentille (signature uniforme (profile, item, lens)) ──
def score_skill(profile, s, lens):
    return s.get("weight", 0) if lens in (s.get("contexts") or []) else None


def score_experience(profile, x, lens):
    rel = x.get("relevance") or {}
    in_dom = lens in (x.get("domains") or [])
    rel_l = rel.get(lens, 0) if lens in REL_AXES else 0
    if not in_dom and rel_l <= 0:
        return None
    return 3 * in_dom + rel_l + 0.5 * rel.get("general", 0)


def score_project(profile, p, lens):
    if lens not in (p.get("domains") or []):
        return None
    return 3 + 2 * (1 if p.get("featured") else 0)


def score_demo(profile, d, lens):
    return 3 if lens in demo_domains(profile, d) else None


def score_article(profile, a, lens):
    return 3 if lens in (a.get("domains") or []) else None


# ── Scores vue générale ──
def gen_skill(s):
    return s.get("weight", 0)


def gen_experience(x):
    return (x.get("relevance") or {}).get("general", 0.5)


def gen_project(p):
    return 1 + 2 * (1 if p.get("featured") else 0)


def gen_demo(d):
    return 1.0


def gen_article(a):
    return 1.0


def _fmt(n):
    return f"{n:g}"


def lens_attrs(profile, lenses, item, scorer):
    """-> ' data-lens-quant="3.6" ...' pour les lentilles où l'item est inclus (score>0)."""
    parts = []
    for L in lenses:
        sc = scorer(profile, item, L)
        if sc is not None and sc > 0:
            parts.append(f'data-lens-{L}="{_fmt(sc)}"')
    return (" " + " ".join(parts)) if parts else ""
