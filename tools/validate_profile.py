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


# Schémas non résolvables sur le disque -> hors périmètre du validateur.
_EXTERNAL = ("http://", "https://", "//", "mailto:", "tel:")


def _local_urls(profile):
    """(label, url) de chaque URL déclarée dans profile.json.

    Convention du corpus : une URL locale est un chemin **relatif à la racine du
    site** (les gabarits lui appliquent `_abs_url`), jamais relatif à la page.
    """
    for p in profile.get("projects", []):
        for key, url in (p.get("links") or {}).items():
            yield f"project '{p.get('id','?')}'.links.{key}", url
    for a in profile.get("articles", []):
        if a.get("url"):
            yield f"article '{a.get('id','?')}'.url", a["url"]
    for key, url in ((profile.get("identity") or {}).get("links") or {}).items():
        yield f"identity.links.{key}", url


def _has_anchor(text: str, frag: str) -> bool:
    return any(pat in text for pat in (f'id="{frag}"', f"id='{frag}'", f'name="{frag}"'))


def _validate_links(profile, root, errors):
    """Liens locaux : forme non ambiguë, puis cible réelle si `root` est fourni."""
    for label, url in _local_urls(profile):
        if not url or url.startswith(_EXTERNAL):
            continue
        path, _, frag = url.partition("#")
        # `index.html#x` se lit comme relatif à la PAGE qui le rend : servi
        # depuis /projects/, il pointe sur /projects/ lui-même, pas sur l'accueil.
        if path.split("/")[0] == "index.html":
            cible = "/#" + frag if frag else "/"
            errors.append(f"{label}: {url!r} est relatif à la page — "
                          f"écrire {cible!r} pour viser l'accueil")
            continue
        if not path:
            errors.append(f"{label}: {url!r} est une ancre nue — cible dépendante de la page")
            continue
        if root is None:
            continue
        target = Path(root) / path.lstrip("/")
        if path.endswith("/") or target.is_dir():
            target = target / "index.html"
        if not target.exists():
            errors.append(f"{label}: cible inexistante {url!r} ({target})")
        elif frag and target.suffix == ".html":
            if not _has_anchor(target.read_text(encoding="utf-8", errors="replace"), frag):
                errors.append(f"{label}: ancre #{frag} absente de {path}")


def _skill_iter(profile):
    for cat, skills in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in skills or []:
            yield cat, s


def validate(profile: dict, root=None) -> list[str]:
    """Règles du corpus. `root` = racine du site : si fourni, les liens locaux
    (`projects[].links`, `articles[].url`, `identity.links`) sont résolus sur le
    disque — c'est ce qui manquait quand /projects/ a été publié avec un 404."""
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

    # Articles carry an optional domains[] (used by /highlights/) — valid ids only.
    for a in profile.get("articles", []):
        for d in a.get("domains") or []:
            if d not in domain_ids:
                errors.append(f"article '{a.get('id','?')}': unknown domain '{d}'")

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

    for j in profile.get("journey", []):
        ref = j.get("ref", "")
        t, _, iid = ref.partition(":")
        ok = ((t == "experience" and iid in exp_ids) or (t == "education" and iid in edu_ids)
              or (t == "project" and iid in proj_ids))
        if not ok:
            errors.append(f"journey ref non résolu : {ref!r}")

    for pr in profile.get("projects", []):
        if not pr.get("name"):
            errors.append(f"project '{pr.get('id')}': name manquant")
        if pr.get("type") not in {"academic", "personal", "professional"}:
            errors.append(f"project '{pr.get('id')}': type invalide '{pr.get('type')}'")

    # radar_scores present & non-empty.
    if not (profile.get("skills", {}) or {}).get("radar_scores"):
        errors.append("skills.radar_scores empty or missing")

    _validate_links(profile, root, errors)

    return errors


def main(argv):
    site_root = Path(__file__).resolve().parent.parent
    default = site_root / "profile.json"
    path = Path(argv[1]) if len(argv) > 1 else default
    profile = json.loads(path.read_text(encoding="utf-8"))
    errs = validate(profile, root=site_root)
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
