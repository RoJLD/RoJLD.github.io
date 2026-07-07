"""Σ-CV-ATELIER sous-projet C — extracteur fiche-de-poste → cfg de ciblage.

Le « seul maillon manquant » du CV ciblé (roadmap Track 2b). Prend une fiche de
poste + le profil, demande à un LLM d'en déduire un `cfg` de sélection
(relevance_key / min_relevance / domains_in / keywords), puis le **valide et
clampe** contre les domaines/clés réellement présents (config-only reject-loud,
isomorphe S4). Le cfg alimente ensuite cv_select.select_experiences → render → PDF.

Seam `complete_fn` injectable (comme score_job_offer) : les tests passent une
fonction factice, la prod route via le résolveur souverain llm_client (SIGIL-1674,
tier local-precision). Aucun réseau dans les tests.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MIN_REL = 0.5
_MAX_KEYWORDS = 20


def known_relevance_keys(profile: dict) -> list[str]:
    keys = set()
    for exp in profile.get("experiences", []):
        keys.update((exp.get("relevance") or {}).keys())
    return sorted(keys) or ["general"]


def known_domains(profile: dict) -> list[str]:
    out = []
    for d in profile.get("domains", []):
        if isinstance(d, dict) and d.get("id"):
            out.append(d["id"])
    return out


def _default_cfg(keys: list[str]) -> dict[str, Any]:
    key = "general" if "general" in keys else keys[0]
    return {"relevance_key": key, "min_relevance": 0.0, "domains_in": [],
            "keywords": [], "label": {"fr": "Ciblé (défaut)", "en": "Targeted (default)"}}


def _build_prompt(job_posting: str, keys: list[str], domains: list[str]) -> str:
    return f"""Tu es un assistant de candidature. À partir de la FICHE DE POSTE ci-dessous,
déduis une configuration de ciblage de CV.

FICHE DE POSTE :
{job_posting[:4000]}

CLÉS DE PERTINENCE disponibles (choisis LA plus adaptée) : {", ".join(keys)}
DOMAINES disponibles (choisis un sous-ensemble pertinent) : {", ".join(domains)}

Retourne UNIQUEMENT un objet JSON valide (sans markdown, sans commentaire) :
{{
  "relevance_key": "<une des clés de pertinence>",
  "min_relevance": <flottant 0.0-1.0, seuil de pertinence>,
  "domains_in": [<sous-ensemble des domaines disponibles>],
  "keywords": [<3-10 mots-clés saillants de la fiche>]
}}"""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def extract_cfg(job_posting: str, profile: dict,
                complete_fn: Optional[Callable[[str], str]] = None) -> dict[str, Any]:
    """Déduit un cfg de ciblage depuis une fiche de poste, validé contre le profil.

    complete_fn : callable (prompt)->str injectable. Si None → llm_client.complete
    (tier local-precision). Sur échec (LLM absent, JSON invalide) → cfg défaut + WARNING.
    """
    keys = known_relevance_keys(profile)
    domains = known_domains(profile)

    if not job_posting or not job_posting.strip():
        return _default_cfg(keys)

    if complete_fn is None:
        complete_fn = _sovereign_complete

    prompt = _build_prompt(job_posting, keys, domains)
    try:
        raw = complete_fn(prompt).strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("réponse LLM non-dict")
    except Exception as exc:
        logger.warning("cv_target: extraction cfg échouée (%s) — cfg défaut", exc)
        return _default_cfg(keys)

    key = parsed.get("relevance_key")
    if key not in keys:
        key = "general" if "general" in keys else keys[0]

    try:
        min_rel = _clamp(float(parsed.get("min_relevance", _DEFAULT_MIN_REL)), 0.0, 1.0)
    except (TypeError, ValueError):
        min_rel = _DEFAULT_MIN_REL

    domains_in = [d for d in (parsed.get("domains_in") or []) if d in domains]
    keywords = [str(k) for k in (parsed.get("keywords") or [])][:_MAX_KEYWORDS]

    return {
        "relevance_key": key,
        "min_relevance": min_rel,
        "domains_in": domains_in,
        "keywords": keywords,
        "label": {"fr": "Ciblé (fiche de poste)", "en": "Targeted (job posting)"},
    }


def targeted_structured_cv(job_posting: str, profile: dict, lang: str = "fr",
                           complete_fn: Optional[Callable[[str], str]] = None):
    """Pipeline ciblé complet (pur, hors PDF) : fiche → cfg → select → structured_cv.

    Retourne (cfg, structured_cv). Le rendu HTML/PDF réutilise cv_render + Playwright
    (mêmes que la banque préfab). Testable sans réseau via complete_fn factice.
    """
    import cv_select  # sibling, import paresseux

    cfg = extract_cfg(job_posting, profile, complete_fn=complete_fn)
    exps = cv_select.select_experiences(profile, cfg)
    scv = cv_select.build_structured_cv(profile, exps, lang)
    return cfg, scv


def _sovereign_complete(prompt: str) -> str:
    """Route via le résolveur souverain llm_client du sibling ELYSIUM career.

    Import paresseux + sibling-path (comme profile_source trouve profile.json).
    Lève si indisponible → extract_cfg retombe sur le cfg défaut (loud).
    """
    import pathlib
    import sys

    # tools/cv -> repo site -> parent commun -> ELYSIUM/satellites/anthropos/apps/career
    here = pathlib.Path(__file__).resolve()
    candidates = [
        here.parents[2].parent / "ELYSIUM" / "satellites" / "anthropos" / "apps" / "career",
    ]
    for c in candidates:
        if (c / "core" / "llm_client.py").exists():
            sys.path.insert(0, str(c))
            from core.llm_client import complete  # type: ignore
            return complete(prompt, tier="local-precision", max_tokens=1024)
    raise RuntimeError("llm_client souverain introuvable (ELYSIUM career sibling absent)")
