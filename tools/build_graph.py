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


def _abs_url(u):
    if not u:
        return ""
    if u.startswith(("http://", "https://", "/", "#")):
        return u
    return "/" + u


def _node_href(node_id, node_type, profile, lens_ids):
    _, _, rid = str(node_id).partition(":")
    if node_type == "project":
        return f"/projects/#{rid}"
    if node_type == "domain":
        return f"/highlights/?lens={rid}" if rid in lens_ids else "/explorer/"
    if node_type == "experience":
        return "/#experience"
    if node_type == "education":
        return "/#education"
    if node_type == "demo":
        return f"/demos/#{rid}"
    if node_type == "article":
        for a in profile.get("articles", []):
            if a.get("id") == rid:
                return _abs_url(a.get("url")) or "/explorer/"
        return "/explorer/"
    if node_type == "journey":
        return "/#parcours"
    if node_type == "skill":
        return "/explorer/"
    return ""


def graph_edges(profile):
    return _load_topology(profile)["edges"]


def graph_nodes(profile):
    topo = _load_topology(profile)
    out = []
    for n in topo["nodes"]:
        lab = _bi_label(n["id"], profile)
        out.append({"id": n["id"], "type": n["type"], "fr": lab["fr"], "en": lab["en"]})
    return out


def compute_layout(nodes, edges, width=1000, height=700, iterations=300):
    ids = [n["id"] for n in nodes]
    n = len(ids)
    if n == 0:
        return {}
    idx = {nid: i for i, nid in enumerate(ids)}
    cx, cy = width / 2.0, height / 2.0
    k = math.sqrt((width * height) / n) * 0.8            # distance idéale
    R = min(width, height) * 0.42
    pos = {}
    for i, nid in enumerate(ids):                        # init déterministe (cercle)
        if nid == "identity:self":
            pos[nid] = [cx, cy]
        else:
            ang = 2 * math.pi * i / n
            pos[nid] = [cx + R * math.cos(ang), cy + R * math.sin(ang)]
    adj = [(idx[ed["source"]], idx[ed["target"]])
           for ed in edges if ed["source"] in idx and ed["target"] in idx]
    t = width / 10.0
    dt = t / (iterations + 1)
    for _ in range(iterations):
        disp = {nid: [0.0, 0.0] for nid in ids}
        for i in range(n):                               # répulsion O(n²)
            for j in range(i + 1, n):
                a, b = ids[i], ids[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = math.hypot(dx, dy) or 0.01
                f = k * k / dist
                ux, uy = dx / dist, dy / dist
                disp[a][0] += ux * f; disp[a][1] += uy * f
                disp[b][0] -= ux * f; disp[b][1] -= uy * f
        for si, ti in adj:                               # attraction (arêtes)
            a, b = ids[si], ids[ti]
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = math.hypot(dx, dy) or 0.01
            f = dist * dist / k
            ux, uy = dx / dist, dy / dist
            disp[a][0] -= ux * f; disp[a][1] -= uy * f
            disp[b][0] += ux * f; disp[b][1] += uy * f
        for nid in ids:                                  # déplacement borné (identity figé)
            if nid == "identity:self":
                continue
            ddx, ddy = disp[nid]
            d = math.hypot(ddx, ddy) or 0.01
            step = min(d, t)
            pos[nid][0] = min(width - 10, max(10, pos[nid][0] + ddx / d * step))
            pos[nid][1] = min(height - 10, max(10, pos[nid][1] + ddy / d * step))
        t -= dt
    return {nid: (round(pos[nid][0], 2), round(pos[nid][1], 2)) for nid in ids}
