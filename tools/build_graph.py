#!/usr/bin/env python3
"""build_graph.py — génère graph/index.html : le profil comme réseau interactif.

Topologie réutilisée de profile_pipeline.build_profile_graph (source unique, SP6) ;
layout force-directed déterministe pur-Python ; labels bilingues re-dérivés de
profile.json ; SVG pré-rendu self-contained + données embarquées.
"""
from __future__ import annotations

import html
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "graph" / "index.html"


class BuildError(Exception):
    pass


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _load_topology(profile):
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "cv"))
    import profile_pipeline  # livré SP6, sous tools/cv/
    return profile_pipeline.build_profile_graph(profile)


def _pair(v, fallback):
    if isinstance(v, dict):
        fr = v.get("fr") or v.get("en") or fallback
        en = v.get("en") or v.get("fr") or fallback
        return {"fr": fr, "en": en}
    s = str(v) if v else fallback
    return {"fr": s, "en": s}


def _bi_label(node_id, profile):
    typ, _, rid = str(node_id).partition(":")
    if typ == "identity":
        idn = profile.get("identity", {}) or {}
        nm = f'{idn.get("first_name","")} {idn.get("last_name","")}'.strip() or rid
        return {"fr": nm, "en": nm}
    if typ == "domain":
        for d in profile.get("domains", []):
            if d.get("id") == rid:
                return _pair(d.get("label"), rid)
    if typ == "experience":
        for x in profile.get("experiences", []):
            if x.get("id") == rid:
                return _pair(x.get("title"), rid)
    if typ == "education":
        for ed in profile.get("education", []):
            if ed.get("id") == rid:
                return _pair(ed.get("title"), rid)
    if typ == "project":
        for p in profile.get("projects", []):
            if p.get("id") == rid:
                return _pair(p.get("name"), rid)
    if typ == "article":
        for a in profile.get("articles", []):
            if a.get("id") == rid:
                return _pair(a.get("title"), rid)
    if typ == "demo":
        for dm in profile.get("demos", []):
            if dm.get("id") == rid:
                return _pair(dm.get("title"), rid)
    if typ == "journey":
        try:
            j = (profile.get("journey", []) or [])[int(rid)]
            return _pair(j.get("label"), f"jalon {rid}")
        except (ValueError, IndexError):
            return {"fr": f"jalon {rid}", "en": f"milestone {rid}"}
    if typ == "skill":
        return {"fr": rid, "en": rid}
    return {"fr": rid, "en": rid}


def graph_edges(profile):
    return _load_topology(profile)["edges"]


def graph_nodes(profile):
    topo = _load_topology(profile)
    out = []
    for n in topo["nodes"]:
        lab = _bi_label(n["id"], profile)
        out.append({"id": n["id"], "type": n["type"], "fr": lab["fr"], "en": lab["en"]})
    return out
