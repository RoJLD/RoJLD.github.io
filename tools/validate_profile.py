#!/usr/bin/env python3
"""Validate the canonical CV corpus (profile.json) — Sigma-CV-SPINE 1.1.

Pure function ``validate(profile: dict) -> list[str]`` returns human-readable
error strings (empty list = valid). CLI: ``python tools/validate_profile.py [path]``
exits non-zero and prints every violation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _skill_iter(profile):
    for cat, skills in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in skills or []:
            yield cat, s


def validate(profile: dict) -> list[str]:
    errors: list[str] = []

    if not profile.get("$version"):
        errors.append("missing $version")

    exp_ids = {e.get("id") for e in profile.get("experiences", [])}
    proj_ids = {p.get("id") for p in profile.get("projects", [])}
    edu_ids = {e.get("id") for e in profile.get("education", [])}
    domain_ids = {d.get("id") for d in profile.get("domains", [])}
    item_ids = exp_ids | proj_ids | edu_ids
    context_ids = exp_ids | edu_ids | {"personal"}

    if not domain_ids:
        errors.append("missing top-level domains taxonomy")

    # Taggable items must carry a non-empty, valid domains[].
    for kind, items in (("experience", profile.get("experiences", [])),
                        ("project", profile.get("projects", []))):
        for it in items:
            iid = it.get("id", "?")
            doms = it.get("domains") or []
            if not doms:
                errors.append(f"{kind} '{iid}': empty domains[]")
            for d in doms:
                if d not in domain_ids:
                    errors.append(f"{kind} '{iid}': unknown domain '{d}'")

    # Skill used_in references must resolve to a real experience/project/education id.
    for cat, s in _skill_iter(profile):
        for uid in s.get("used_in", []):
            if uid not in item_ids:
                errors.append(f"skill '{s.get('name')}' ({cat}): used_in '{uid}' unresolved")

    # project.context must be an experience, an education, or "personal".
    for p in profile.get("projects", []):
        ctx = p.get("context")
        if ctx not in context_ids:
            errors.append(f"project '{p.get('id')}': context '{ctx}' invalid")

    # Bilingual required fields must carry both 'fr' and 'en'.
    def _needs_bilingual(obj, label):
        if not isinstance(obj, dict) or "fr" not in obj or "en" not in obj:
            errors.append(f"{label}: must have both 'fr' and 'en'")

    identity = profile.get("identity", {})
    _needs_bilingual(identity.get("tagline", {}), "identity.tagline")
    _needs_bilingual(identity.get("status", {}), "identity.status")
    for e in profile.get("experiences", []):
        _needs_bilingual(e.get("title", {}), f"experience '{e.get('id')}'.title")
        _needs_bilingual(e.get("bullets", {}), f"experience '{e.get('id')}'.bullets")
    for e in profile.get("education", []):
        _needs_bilingual(e.get("title", {}), f"education '{e.get('id')}'.title")
        _needs_bilingual(e.get("org", {}), f"education '{e.get('id')}'.org")

    for pr in profile.get("projects", []):
        if not pr.get("name"):
            errors.append(f"project '{pr.get('id')}': name manquant")
        if pr.get("type") not in {"academic", "personal", "professional"}:
            errors.append(f"project '{pr.get('id')}': type invalide '{pr.get('type')}'")

    # radar_scores present & non-empty.
    if not (profile.get("skills", {}) or {}).get("radar_scores"):
        errors.append("skills.radar_scores empty or missing")

    return errors


def main(argv):
    default = Path(__file__).resolve().parent.parent / "profile.json"
    path = Path(argv[1]) if len(argv) > 1 else default
    profile = json.loads(path.read_text(encoding="utf-8"))
    errs = validate(profile)
    if errs:
        print(f"INVALID: {len(errs)} error(s) in {path}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"VALID: {path.name} — {len(profile.get('experiences', []))} experiences, "
          f"{len(profile.get('projects', []))} projects, "
          f"{len(profile.get('domains', []))} domains")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
