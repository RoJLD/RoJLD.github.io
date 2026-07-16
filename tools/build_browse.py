#!/usr/bin/env python3
"""build_browse.py — génère explorer/index.html depuis profile.json.

Flux unifié de TOUT le contenu (projets, démos, articles, expériences, formations,
recommandations) en cartes normalisées, filtrables par type + recherche live + bilingue.
Page autonome au design-system de robin-denis.com. LECTURE SEULE de profile.json.

Usage : python tools/build_browse.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "explorer" / "index.html"


class BuildError(Exception):
    pass


# type -> (badge_fr, badge_en, classe couleur)
TYPE_META = {
    "project":        ("Projet", "Project", "b-project"),
    "demo":           ("Démo", "Demo", "b-demo"),
    "article":        ("Article", "Article", "b-article"),
    "experience":     ("Expérience", "Experience", "b-experience"),
    "education":      ("Formation", "Education", "b-education"),
    "recommendation": ("Recommandation", "Reference", "b-recommendation"),
}
# type -> (chip_fr, chip_en)  (libellés pluriels pour les filtres)
CHIP_LABEL = {
    "project":        ("Projets", "Projects"),
    "demo":           ("Démos", "Demos"),
    "article":        ("Articles", "Articles"),
    "experience":     ("Expériences", "Experience"),
    "education":      ("Formations", "Education"),
    "recommendation": ("Recommandations", "References"),
}
TYPE_ORDER = ["project", "demo", "article", "experience", "education", "recommendation"]
DEMO_PIN = "9999-99"   # les démos flottent en tête


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


def _pair(v):
    """str neutre -> (v, v) ; {fr,en} -> (fr, en) ; None -> ('', '')."""
    if isinstance(v, dict):
        return (v.get("fr", ""), v.get("en", ""))
    return (v or "", v or "")


def _sortkey(s) -> str:
    """Token AAAA(-MM) le plus récent d'une chaîne date-ish. '' -> '0000-00'."""
    toks = re.findall(r"\d{4}(?:-\d{2})?", str(s or ""))
    if not toks:
        return "0000-00"
    return max(t if len(t) == 7 else t + "-00" for t in toks)


def _truncate(s, n: int = 160) -> str:
    s = one_line(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _period(start, end, current):
    sy = str(start or "")[:4]
    if current:
        return (f"{sy} – présent", f"{sy} – present")
    ey = str(end or "")[:4]
    base = f"{sy} – {ey}" if ey else sy
    return (base, base)


def _entry(type_, id_, title, desc, date_display, sort, tags, href, soon=False):
    return {
        "type": type_, "id": id_, "title": title, "desc": desc,
        "date_display": date_display, "sort": sort, "tags": list(tags or []),
        "href": href, "soon": soon,
    }


def _norm_project(p):
    tfr, ten = _pair(p.get("name", ""))
    dfr, den = _pair(p.get("summary", ""))
    return _entry("project", p.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)),
                  (p.get("date", ""), p.get("date", "")),
                  _sortkey(p.get("date", "")), p.get("tags", []),
                  f'/projects/#{p.get("id", "")}')


def _norm_demo(d):
    tfr, ten = _pair(d.get("title", ""))
    dfr, den = _pair(d.get("desc", ""))
    cat = d.get("category", "")
    return _entry("demo", d.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)), ("", ""), DEMO_PIN,
                  [cat] if cat else [], f'/demos/#{d.get("id", "")}')


def _norm_article(a):
    tfr, ten = _pair(a.get("title", ""))
    dfr, den = _pair(a.get("desc", ""))
    return _entry("article", a.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)),
                  (a.get("date", ""), a.get("date", "")),
                  _sortkey(a.get("date", "")), a.get("tags", []),
                  a.get("url") or "/#blog", soon=(a.get("status") == "soon"))


def _norm_experience(x):
    company = x.get("company", "")
    tfr, ten = _pair(x.get("title", ""))
    if company:
        tfr, ten = f"{tfr} · {company}", f"{ten} · {company}"
    bullets = x.get("bullets", {}) or {}
    bfr = (bullets.get("fr") or [""])[0]
    ben = (bullets.get("en") or [""])[0]
    typ = x.get("type", "")
    return _entry("experience", x.get("id", ""), (tfr, ten),
                  (one_line(bfr), one_line(ben)),
                  _period(x.get("start"), x.get("end"), x.get("current")),
                  _sortkey(x.get("end") or x.get("start")),
                  [typ] if typ else [], "/#experience")


def _norm_education(ed):
    tfr, ten = _pair(ed.get("title", ""))
    dfr, den = _pair(ed.get("org", ""))
    period = ed.get("period", "")
    return _entry("education", ed.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)), (period, period),
                  _sortkey(ed.get("end") or ed.get("period")),
                  [ed.get("degree", "")] if ed.get("degree") else [], "/#education")


def _norm_recommendation(r):
    author = r.get("author", "")
    rfr, ren = _pair(r.get("role", ""))
    tfr = f"{author} · {rfr}" if rfr else author
    ten = f"{author} · {ren}" if ren else author
    xfr, xen = _pair(r.get("text", ""))
    date = r.get("date", "")
    return _entry("recommendation", r.get("id", ""), (tfr, ten),
                  (_truncate(xfr), _truncate(xen)), (date, date),
                  _sortkey(date), [], "/#testimonials")


def aggregate(profile):
    entries = []
    entries += [_norm_project(p) for p in profile.get("projects", [])]
    entries += [_norm_demo(d) for d in profile.get("demos", [])]
    entries += [_norm_article(a) for a in profile.get("articles", [])]
    entries += [_norm_experience(x) for x in profile.get("experiences", [])]
    entries += [_norm_education(ed) for ed in profile.get("education", [])]
    entries += [_norm_recommendation(r) for r in profile.get("recommendations", [])]
    entries.sort(key=lambda en: (en["sort"], en["type"], en["title"][0]), reverse=True)
    return entries
