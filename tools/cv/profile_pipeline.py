#!/usr/bin/env python3
"""profile_pipeline.py — pipeline d'édition gouvernée de profile.json (atelier local).

historise -> valide -> revue LLM (advisory) -> écrit -> réindexe graphe -> rebuild.
Fonctions pures/seams testables. Graphe = artefact local data/profile_graph.json.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Callable

_HERE = pathlib.Path(__file__).resolve().parent   # tools/cv
_TOOLS = _HERE.parent                             # tools
_ROOT = _TOOLS.parent                             # repo site
PROFILE_PATH = _ROOT / "profile.json"
HISTORY_DIR = _ROOT / "data" / "profile_history"
GRAPH_PATH = _ROOT / "data" / "profile_graph.json"


class BuildError(Exception):
    pass


def _load_validate() -> Callable[[dict], list]:
    if str(_TOOLS) not in sys.path:
        sys.path.insert(0, str(_TOOLS))
    import validate_profile  # type: ignore
    return validate_profile.validate


def parse_and_validate(raw_json, validate_fn=None):
    """-> (parsed|None, errors). Reject-loud (JSON, non-dict, règles validate)."""
    if validate_fn is None:
        validate_fn = _load_validate()
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return None, [f"JSON invalide : {e}"]
    if not isinstance(parsed, dict):
        return None, ["Le profil doit être un objet JSON."]
    errs = list(validate_fn(parsed))
    if errs:
        return None, errs
    return parsed, []


def atomic_write_profile(parsed, profile_path):
    profile_path = pathlib.Path(profile_path)
    tmp = profile_path.parent / (profile_path.name + ".tmp")
    tmp.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(profile_path)


def snapshot_profile(profile_path, history_dir, ts_str):
    """Copie le profile courant AVANT écrasement + ligne log.jsonl. None si profile absent."""
    profile_path = pathlib.Path(profile_path)
    if not profile_path.exists():
        return None
    history_dir = pathlib.Path(history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    content = profile_path.read_text(encoding="utf-8")
    snap = history_dir / f"profile-{ts_str}.json"
    snap.write_text(content, encoding="utf-8")
    line = json.dumps({"ts": ts_str, "bytes": len(content.encode("utf-8")), "file": snap.name}, ensure_ascii=False)
    with (history_dir / "log.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return snap


def _label(v):
    if isinstance(v, dict):
        return v.get("fr") or v.get("en") or ""
    return str(v or "")


def build_profile_graph(profile):
    """PUR. profile -> {nodes, edges, summary}. Arête vers cible absente ignorée."""
    nodes, ids, edges = [], set(), []

    def add_node(nid, ntype, label):
        if nid not in ids:
            ids.add(nid)
            nodes.append({"id": nid, "type": ntype, "label": label})

    def add_edge(src, tgt, rel):
        if src in ids and tgt in ids:
            edges.append({"source": src, "target": tgt, "rel": rel})

    ident = profile.get("identity", {}) or {}
    add_node("identity:self", "identity",
             (f'{ident.get("first_name", "")} {ident.get("last_name", "")}'.strip() or "self"))
    for d in profile.get("domains", []):
        add_node(f'domain:{d.get("id")}', "domain", _label(d.get("label")))
    for x in profile.get("experiences", []):
        add_node(f'experience:{x.get("id")}', "experience", _label(x.get("title")))
    for ed in profile.get("education", []):
        add_node(f'education:{ed.get("id")}', "education", _label(ed.get("title")))
    for p in profile.get("projects", []):
        add_node(f'project:{p.get("id")}', "project", _label(p.get("name")))
    for a in profile.get("articles", []):
        add_node(f'article:{a.get("id")}', "article", _label(a.get("title")))
    for dm in profile.get("demos", []):
        add_node(f'demo:{dm.get("id")}', "demo", _label(dm.get("title")))
    for i, j in enumerate(profile.get("journey", [])):
        add_node(f'journey:{i}', "journey", _label(j.get("label")) or f"jalon {i}")
    for cat, lst in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in (lst or []):
            add_node(f'skill:{s.get("name")}', "skill", s.get("name", ""))

    for x in profile.get("experiences", []):
        for d in x.get("domains", []) or []:
            add_edge(f'experience:{x.get("id")}', f'domain:{d}', "has_domain")
    for p in profile.get("projects", []):
        for d in p.get("domains", []) or []:
            add_edge(f'project:{p.get("id")}', f'domain:{d}', "has_domain")
        ctx = p.get("context")
        if ctx and ctx != "personal":
            add_edge(f'project:{p.get("id")}', f'experience:{ctx}', "context")
            add_edge(f'project:{p.get("id")}', f'education:{ctx}', "context")
    for a in profile.get("articles", []):
        for d in a.get("domains", []) or []:
            add_edge(f'article:{a.get("id")}', f'domain:{d}', "has_domain")
    for cat, lst in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in (lst or []):
            sid = f'skill:{s.get("name")}'
            for uid in s.get("used_in", []) or []:
                add_edge(sid, f'experience:{uid}', "used_in")
                add_edge(sid, f'project:{uid}', "used_in")
                add_edge(sid, f'education:{uid}', "used_in")
            for ctx in s.get("contexts", []) or []:
                add_edge(sid, f'domain:{ctx}', "context")
    for dm in profile.get("demos", []):
        if dm.get("project"):
            add_edge(f'demo:{dm.get("id")}', f'project:{dm.get("project")}', "demo_of")
    for i, j in enumerate(profile.get("journey", [])):
        t, _, iid = str(j.get("ref", "")).partition(":")
        if t and iid:
            add_edge(f'journey:{i}', f'{t}:{iid}', "refs")

    by_type = {}
    for n in nodes:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
    return {"nodes": nodes, "edges": edges,
            "summary": {"nodes": len(nodes), "edges": len(edges), "by_type": by_type}}


def write_profile_graph(graph, graph_path):
    graph_path = pathlib.Path(graph_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
