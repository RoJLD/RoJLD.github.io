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

import math
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
    # `.get(k) or défaut` — PAS `.get(k, défaut)` : profile.json/cv_profiles.json
    # utilisent `null` comme idiome « pas de contrainte » ; `.get(k, défaut)` rend
    # alors None et fait planter float()/set(), là où le miroir JS (`|| défaut`)
    # produit un CV normal. Cette asymétrie cassait build_cv_bank en silence.
    key = cfg.get("relevance_key") or "general"
    min_rel = float(cfg.get("min_relevance") or 0.0)
    domains_in = set(cfg.get("domains_in") or [])
    max_exp = cfg.get("max_experiences")

    def rel(exp: dict[str, Any]) -> float:
        return float((exp.get("relevance") or {}).get(key) or 0.0)

    matched = [
        exp for exp in (profile.get("experiences") or [])
        if rel(exp) >= min_rel or (set(exp.get("domains") or []) & domains_in)
    ]
    if cfg.get("sort_by") == "date":
        # CV complet : ordre reverse-chronologique (récent d'abord), IGNORE la
        # relevance (le tri par relevance mettrait ALTEN, plus récent mais moins
        # « general », en dernier — non conventionnel pour un CV complet).
        matched.sort(key=lambda e: (_neg_date(e.get("start")), e.get("id") or ""))
    else:
        matched.sort(key=lambda e: (-rel(e), _neg_date(e.get("start")), e.get("id") or ""))
    # Prédicat ENTIER STRICT, identique des deux côtés (JS: Number.isInteger).
    # bool exclu (isinstance(True, int) est vrai en Python) ; float/NaN/Infinity
    # exclus aussi — `matched[:int(inf)]` lèverait OverflowError côté Python
    # alors que `slice(0, Infinity)` passe côté JS.
    if isinstance(max_exp, int) and not isinstance(max_exp, bool) and max_exp >= 0:
        matched = matched[:max_exp]
    return matched


def _neg_date(date_str: str) -> str:
    """Clé de tri « récent d'abord » : inverse lexicographique d'une date ISO-ish.

    Les dates profile.json sont des chaînes (ex "2024-09", "2021"). On veut le plus
    récent en premier ; on renvoie une clé qui trie desc quand utilisée en asc.
    """
    # Complément à '9' de chaque chiffre → tri ascendant = date descendante.
    # Test ASCII explicite (miroir de negDate JS) : str.isdigit() accepte des
    # chiffres Unicode ('²', '½') que int() refuse → crash. Non-str → "" comme JS.
    s = date_str if isinstance(date_str, str) else ""
    return "".join(str(9 - int(c)) if "0" <= c <= "9" else c for c in s)


def select_manual(profile: dict[str, Any], bullet_ids: list[str], lang: str) -> list[dict[str, Any]]:
    """Projette exactement les bullets cochés, groupés par expérience (ordre profil.json).

    bullet_ids : liste de '{exp.id}.{index}'. Silencieusement ignore les ids inconnus
    ou hors-plage (robustesse UI). Retourne une liste d'expériences allégées
    ne contenant que les bullets sélectionnés (dans l'ordre d'index croissant).
    """
    wanted: dict[str, set[int]] = {}
    for bid in bullet_ids:
        exp_id, _, idx = bid.rpartition(".")
        # isascii() en plus : str.isdigit() accepte des chiffres Unicode ('²')
        # que int() refuse (crash), là où le miroir JS /^\d+$/ est ASCII-only.
        if exp_id and idx.isascii() and idx.isdigit():
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


# Ordre de rendu par DÉFAUT des catégories de compétences (cfg absent). Liste
# EXPLICITE — et non « toutes les clés de profile.skills » — pour trois raisons :
# rester déterministe et identique côté JS (l'ordre des clés d'un dict ne doit pas
# décider du contenu d'un CV), exclure `radar_scores` qui n'est pas une liste de
# compétences, et garder le contrôle éditorial de l'ordre.
_DEFAULT_SKILL_CATS = ("finance", "programming", "data_ml", "domain", "engineering")


def _as_list(value: Any) -> list:
    """Liste STRICTE. Sans ce garde, une chaîne au lieu d'une liste serait itérée
    caractère par caractère côté Python (corruption silencieuse) alors que le
    miroir JS lèverait une TypeError. Miroir de `Array.isArray(v) ? v : []`."""
    return value if isinstance(value, list) else []


def _link_display(url: Any) -> str:
    """URL affichable : retire le schéma http(s):// et un préfixe `www.`
    (ex 'https://www.linkedin.com/in/x/' → 'linkedin.com/in/x/'). '' si absent."""
    # Chaînes UNIQUEMENT (miroir JS strict) : une URL non-str ne doit être ni
    # stringifiée ni dépouillée de son schéma des deux côtés différemment.
    s = url.strip() if isinstance(url, str) else ""
    for pfx in ("https://", "http://"):
        if s.startswith(pfx):
            s = s[len(pfx):]
            break
    if s.startswith("www."):
        s = s[4:]
    return s


def _location_str(identity: dict[str, Any]) -> str:
    """'City, Country' depuis identity.location (dict), '' si absent. Le téléphone
    n'est JAMAIS projeté (les préfabriqués sont servis publiquement)."""
    loc = identity.get("location")
    if not isinstance(loc, dict):
        return ""
    parts = [(loc.get("city") if isinstance(loc.get("city"), str) else "").strip(),
             (loc.get("country") if isinstance(loc.get("country"), str) else "").strip()]
    return ", ".join(p for p in parts if p)


def _education(profile: dict[str, Any], lang: str) -> list[dict[str, Any]]:
    """Projette profile.education → entrées neutres-langue (bilingue résolu)."""
    out: list[dict[str, Any]] = []
    for e in _as_list(profile.get("education")):
        cap = e.get("capstone")
        out.append({
            "school": _loc(e.get("school"), lang),
            "title": _loc(e.get("title"), lang),
            "org": _loc(e.get("org"), lang),
            "period": _loc(e.get("period"), lang),
            "degree": _loc(e.get("degree"), lang),
            "courses_label": _loc(e.get("courses_label"), lang),
            "courses": [_loc(c, lang) for c in _as_list(e.get("courses"))],
            "capstone": {
                "label": _loc(cap.get("label"), lang),
                "summary": _loc(cap.get("summary"), lang),
            } if isinstance(cap, dict) else None,
        })
    return out


def _skills_groups(profile: dict[str, Any], lang: str,
                   cfg: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Compétences GROUPÉES par catégorie : [{label, items}], ordre = cfg.

    `cfg.skills_categories` fixe les catégories retenues ET leur ordre de rendu
    (un CV quant n'affiche pas Kubernetes) ; `cfg.skills_per_category` plafonne
    (absent = illimité). Sans cfg : toutes les catégories connues.
    Seules des chaînes non vides entrent — jamais un dict (fuite des champs
    internes weight/level/used_in dans un PDF public).
    """
    cfg = cfg or {}
    cats = cfg.get("skills_categories")
    cats = cats if isinstance(cats, list) and cats else list(_DEFAULT_SKILL_CATS)
    # Miroir de Number.isInteger : JSON `2.0` devient un float côté Python mais
    # l'entier 2 côté JS — un prédicat `isinstance(int)` rendait donc le cap
    # illimité d'un côté et actif de l'autre. On accepte tout nombre INTÉGRAL.
    cap = cfg.get("skills_per_category")
    if (isinstance(cap, (int, float)) and not isinstance(cap, bool)
            and math.isfinite(cap) and cap == int(cap) and cap >= 0):
        cap = int(cap)   # math.isfinite : NaN/Infinity feraient lever int()
    else:
        cap = None
    labels = profile.get("skills_labels") or {}
    skills = profile.get("skills") or {}

    groups: list[dict[str, Any]] = []
    for cat in cats:
        items = []
        for s in _as_list(skills.get(cat)):
            n = s.get("name") if isinstance(s, dict) else s
            if isinstance(n, str) and n:
                items.append(n)
        if cap is not None:
            items = items[:cap]
        if items:
            groups.append({"label": _loc(labels.get(cat), lang) or str(cat), "items": items})
    return groups


def _languages(profile: dict[str, Any], lang: str) -> list[dict[str, str]]:
    return [
        {"name": _loc(lg.get("name"), lang), "level": _loc(lg.get("level"), lang)}
        for lg in _as_list(profile.get("languages"))
    ]


def build_structured_cv(profile: dict[str, Any], experiences: list[dict[str, Any]],
                        lang: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construit le dict de rendu neutre depuis profile + une sélection d'expériences.

    `experiences` = sortie de select_experiences OU select_manual. `lang` ∈ {fr,en}.
    Le résultat est consommé identiquement par le rendu Python (build) et JS (client).
    Les champs bilingues (`title`, etc.) sont résolus vers `lang` via `_loc`.
    """
    identity = profile.get("identity") or {}
    present = "présent" if lang == "fr" else "present"
    sections = []
    for exp in experiences:
        sections.append({
            "kind": "experience",
            "company": _loc(exp.get("company"), lang),
            "title": _loc(exp.get("title"), lang),
            # `or ''` et non `.get(k, '')` : `"end": null` (idiome JSON courant)
            # rendait littéralement « 2025-02 → None » dans le PDF PUBLIC, là où
            # le miroir JS (`exp.end || ""`) rendait « 2025-02 → ».
            "dates": f"{exp.get('start') or ''} → "
                     f"{present if exp.get('current') else (exp.get('end') or '')}",
            "bullets": _as_list((exp.get("bullets") or {}).get(lang)),
        })

    # Compétences groupées par catégorie (pilotées par cfg) ; `skills_top` reste
    # la liste PLATE dérivée, pour les consommateurs historiques du schéma.
    skills_groups = _skills_groups(profile, lang, cfg)
    skills_top = [n for g in skills_groups for n in g["items"]]

    links = identity.get("links") or {}
    return {
        "lang": lang,
        "identity": {
            "name": f"{identity.get('first_name') or ''} {identity.get('last_name') or ''}".strip()
                    or _loc(identity.get("name"), lang),
            # tagline = « sous-titre » du profil (identity.title est absent de
            # profile.json) — d'où le title vide avant convergence.
            "title": _loc(identity.get("tagline") or identity.get("title"), lang),
            "email": _loc(identity.get("email"), lang),
            "location": _location_str(identity),          # tél JAMAIS projeté (public)
            "linkedin": _link_display(links.get("linkedin")),
            "github": _link_display(links.get("github")),
        },
        "sections": sections,
        "skills_groups": skills_groups,
        "skills_top": skills_top,
        "education": _education(profile, lang),
        "languages": _languages(profile, lang),
        # certifications passe par _loc comme interests : une entrée bilingue
        # {fr,en} (la convention du reste de profile.json) doit être résolue, pas
        # stringifiée différemment de chaque côté du miroir.
        "certifications": [_loc(c, lang) for c in _as_list(profile.get("certifications"))],
        "interests": [_loc(i, lang) for i in _as_list(profile.get("interests"))],
        "footer": {"updated": _loc(profile.get("$updated"), lang)},
    }
