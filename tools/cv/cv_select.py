"""Σ-CV-ATELIER sous-projet A — sélection pure depuis profile.json.

Cœur d'export natif profile.json (la source de vérité, Track 1). Fournit :
- select_experiences(profile, cfg)  → filtrage AUTO au niveau expérience (préfabs/ciblage)
- select_manual(profile, bullet_ids, lang) → sélection MANUELLE bullet-par-bullet (cases à cocher)
- build_structured_cv(profile, experiences, lang) → dict de rendu neutre-langue-résolue

Aucun tag par-bullet requis : le filtrage auto s'appuie sur `experience.relevance`
+ `experience.domains` (présents dans profile.json) ; les cases à cocher sont une
sélection humaine explicite. Fonctions PURES et déterministes (testables sans I/O).
"""
from __future__ import annotations

from typing import Any


def _bullet_id(exp_id: str, index: int) -> str:
    """Identifiant stable d'un bullet : '{exp.id}.{index}' (0-based, langue-agnostique)."""
    return f"{exp_id}.{index}"


def select_experiences(profile: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Filtre + ordonne les expériences selon un cfg de profil (filtrage AUTO).

    cfg :
      - relevance_key : clé de `experience.relevance` à comparer (ex "quant")
      - min_relevance : seuil (float, défaut 0.0)
      - domains_in    : liste de domaines visés
      - max_experiences : cap (int|None)

    Règle d'inclusion (permissive, OU) : garde une expérience si
      relevance[relevance_key] >= min_relevance  OU  set(domains) & set(domains_in).
    Tri : relevance[relevance_key] desc, puis `start` desc (récent d'abord), puis id.
    """
    key = cfg.get("relevance_key", "general")
    min_rel = float(cfg.get("min_relevance", 0.0))
    domains_in = set(cfg.get("domains_in", []))
    max_exp = cfg.get("max_experiences")

    def rel(exp: dict[str, Any]) -> float:
        return float((exp.get("relevance") or {}).get(key, 0.0))

    matched = [
        exp for exp in profile.get("experiences", [])
        if rel(exp) >= min_rel or (set(exp.get("domains", [])) & domains_in)
    ]
    matched.sort(key=lambda e: (-rel(e), _neg_date(e.get("start", "")), e.get("id", "")))
    if isinstance(max_exp, int) and max_exp >= 0:
        matched = matched[:max_exp]
    return matched


def _neg_date(date_str: str) -> str:
    """Clé de tri « récent d'abord » : inverse lexicographique d'une date ISO-ish.

    Les dates profile.json sont des chaînes (ex "2024-09", "2021"). On veut le plus
    récent en premier ; on renvoie une clé qui trie desc quand utilisée en asc.
    """
    # Complément à '9' de chaque chiffre → tri ascendant = date descendante.
    return "".join(str(9 - int(c)) if c.isdigit() else c for c in (date_str or ""))


def select_manual(profile: dict[str, Any], bullet_ids: list[str], lang: str) -> list[dict[str, Any]]:
    """Projette exactement les bullets cochés, groupés par expérience (ordre profil.json).

    bullet_ids : liste de '{exp.id}.{index}'. Silencieusement ignore les ids inconnus
    ou hors-plage (robustesse UI). Retourne une liste d'expériences allégées
    ne contenant que les bullets sélectionnés (dans l'ordre d'index croissant).
    """
    wanted: dict[str, set[int]] = {}
    for bid in bullet_ids:
        exp_id, _, idx = bid.rpartition(".")
        if exp_id and idx.isdigit():
            wanted.setdefault(exp_id, set()).add(int(idx))

    out: list[dict[str, Any]] = []
    for exp in profile.get("experiences", []):
        eid = exp.get("id", "")
        if eid not in wanted:
            continue
        bullets = (exp.get("bullets") or {}).get(lang, [])
        picked = [bullets[i] for i in sorted(wanted[eid]) if 0 <= i < len(bullets)]
        if picked:
            out.append({**exp, "bullets": {lang: picked}})
    return out


def _loc(value: Any, lang: str) -> str:
    """Résout un champ potentiellement bilingue.

    profile.json a des champs `{fr, en}` (ex `experience.title`, `identity.title`)
    ET des champs string plats (ex `company`). Ce helper renvoie la variante `lang`
    d'un dict bilingue, sinon la valeur telle quelle. Évite d'afficher un dict brut.
    """
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("fr") or value.get("en") or "")
    return str(value) if value is not None else ""


def build_structured_cv(profile: dict[str, Any], experiences: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    """Construit le dict de rendu neutre depuis profile + une sélection d'expériences.

    `experiences` = sortie de select_experiences OU select_manual. `lang` ∈ {fr,en}.
    Le résultat est consommé identiquement par le rendu Python (build) et JS (client).
    Les champs bilingues (`title`, etc.) sont résolus vers `lang` via `_loc`.
    """
    identity = profile.get("identity", {})
    present = "présent" if lang == "fr" else "present"
    sections = []
    for exp in experiences:
        sections.append({
            "kind": "experience",
            "company": _loc(exp.get("company"), lang),
            "title": _loc(exp.get("title"), lang),
            "dates": f"{exp.get('start', '')} → {present if exp.get('current') else exp.get('end', '')}",
            "bullets": list((exp.get("bullets") or {}).get(lang, [])),
        })

    skills = profile.get("skills", {})
    skills_top = [
        s.get("name", s) if isinstance(s, dict) else s
        for cat in ("programming", "finance", "data_ml")
        for s in (skills.get(cat, []) or [])[:3]
    ]

    return {
        "lang": lang,
        "identity": {
            "name": f"{identity.get('first_name', '')} {identity.get('last_name', '')}".strip()
                    or _loc(identity.get("name"), lang),
            "title": _loc(identity.get("title"), lang),
            "email": _loc(identity.get("email"), lang),
        },
        "sections": sections,
        "skills_top": skills_top,
        "footer": {"updated": profile.get("$updated", "")},
    }
