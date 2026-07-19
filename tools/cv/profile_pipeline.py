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


# ══════════════════ Revue LLM + orchestration ══════════════════

def _sovereign_complete(prompt):
    """Réutilise le résolveur LLM souverain de cv_target (ELYSIUM sibling)."""
    import cv_target  # type: ignore
    return cv_target._sovereign_complete(prompt)


def _review_prompt(new, changed_keys):
    sections = {k: new.get(k) for k in changed_keys}
    body = json.dumps(sections, ensure_ascii=False)[:6000]
    return ("Tu es un relecteur qualité d'un profil professionnel bilingue (fr/en). "
            "Relève UNIQUEMENT des problèmes concrets dans ces sections modifiées : "
            "champ bilingue incomplet (fr sans en, ou l'inverse), incohérence factuelle, "
            "faute de frappe. Une ligne par problème, ou 'RAS' si tout va bien.\n\n" + body)


def review_edit(old, new, complete_fn=None):
    """Revue LLM consultative (non bloquante). Gracieux si LLM indisponible."""
    changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    if not changed:
        return {"available": True, "changed_keys": [], "notes": []}
    fn = complete_fn or _sovereign_complete
    try:
        raw = fn(_review_prompt(new, changed)).strip()
    except Exception as exc:
        return {"available": False, "changed_keys": changed, "notes": [], "error": str(exc)}
    if not raw or raw.upper().startswith("RAS"):
        notes = []
    else:
        notes = [ln.strip("-•* ").strip() for ln in raw.splitlines()
                 if ln.strip() and ln.strip().upper() != "RAS"]
    return {"available": True, "changed_keys": changed, "notes": notes}


def _read_json(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _rebuild():
    if str(_TOOLS) not in sys.path:
        sys.path.insert(0, str(_TOOLS))
    import build_site  # type: ignore
    build_site.build(write=True)


def govern_save(raw_json, profile_path, history_dir, graph_path, ts_str,
                complete_fn=None, do_rebuild=True, validate_fn=None):
    """Pipeline gouverné -> rapport {ok, errors, stages}. Reject-loud sans effet de bord."""
    parsed, errors = parse_and_validate(raw_json, validate_fn)
    if errors:
        return {"ok": False, "errors": errors, "stages": {}}
    old = _read_json(profile_path)
    stages = {"review": review_edit(old, parsed, complete_fn=complete_fn)}
    snap = snapshot_profile(profile_path, history_dir, ts_str)
    stages["history"] = {"snapshot": (pathlib.Path(snap).name if snap else None)}
    atomic_write_profile(parsed, profile_path)
    stages["write"] = {"ok": True}
    graph = build_profile_graph(parsed)
    write_profile_graph(graph, graph_path)
    stages["graph"] = graph["summary"]
    if do_rebuild:
        # Le rebuild est POST-écriture : s'il échoue, le profil est DÉJÀ sur disque.
        # Laisser l'exception remonter ferait afficher « Refusé » à l'appelant alors
        # que le fichier a changé — l'exact inverse du contrat reject-loud, et le
        # pire message possible (l'utilisateur croit son édition annulée). On rapporte
        # donc un échec d'étape explicite, sans mentir sur l'écriture qui, elle, a eu lieu.
        try:
            _rebuild()
            stages["rebuild"] = {"ok": True}
        except Exception as exc:
            stages["rebuild"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        stages["rebuild"] = {"skipped": True}
    return {"ok": True, "errors": [], "stages": stages}


def main():
    """Régénère le graphe depuis profile.json (standalone)."""
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    graph = build_profile_graph(profile)
    write_profile_graph(graph, GRAPH_PATH)
    s = graph["summary"]
    print(f"[profile_pipeline] graphe: {s['nodes']} noeuds, {s['edges']} aretes -> {GRAPH_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
