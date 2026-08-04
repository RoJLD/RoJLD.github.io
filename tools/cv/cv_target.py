"""Σ-CV-ATELIER sous-projet C — extracteur fiche-de-poste → `job_context`.

Le « seul maillon manquant » du CV ciblé (roadmap Track 2b). Prend une fiche de
poste + le profil, demande à un LLM d'en déduire un `cfg` de sélection
(relevance_key / min_relevance / domains_in / keywords), puis le **valide et
clampe** contre les domaines/clés réellement présents (config-only reject-loud,
isomorphe S4). Le cfg alimente ensuite cv_select.select_experiences → render → PDF.

K1 (plan B lettre, ADR-003) élargit ce cfg en **`job_context`** : entreprise,
intitulé, exigences saillantes, registre, marché. `job_context` **englobe** le
cfg — même dict, clés en plus — parce que `atelier.generate_pdf` le consomme tel
quel ; `extract_cfg` reste donc un alias exact de `extract_job_context`.

### Régime de validation, référentiel par référentiel

La validation historique est *reject-loud contre le profil*. Les nouveaux champs
n'ont **aucun référentiel dans `profile.json`** — ils décrivent le POSTE, pas la
personne. Les clamper contre le profil serait un contresens ; les accepter sur
parole serait le mode de défaillance que tout le plan B existe pour supprimer.
On choisit donc le référentiel de chaque champ, et le régime en découle :

| champ | référentiel | régime |
|---|---|---|
| `relevance_key`, `domains_in` | `profile.json` | clamp reject-loud (inchangé) |
| `register`, `market` | vocabulaire fermé, à nous | clamp sur l'énumération |
| `company`, `job_title` | **la fiche de poste elle-même** | ancrage **verbatim** |
| `requirements` | aucun | forme et bornes seules |

`company` et `job_title` sont rendus **littéralement** en tête de la lettre : une
entreprise inventée arriverait telle quelle chez un recruteur. Ils ne sont donc
retenus que s'ils apparaissent dans la fenêtre de fiche réellement envoyée au
modèle (`_PROMPT_JOB_CHARS`), à la casse et aux espaces près — sinon `None` +
WARNING. Valider contre le texte complet validerait contre ce que le modèle n'a
pas lu.

`requirements` est paraphrasable par nature : aucun ancrage n'est possible. Le
risque résiduel (une exigence qui pousse le modèle à prêter une compétence au
candidat) n'est pas traité ici mais **en aval**, par le vérificateur d'ancrage
`cv_grounding` — c'est lui qui juge toute affirmation portant sur le candidat.

Seam `complete_fn` injectable (comme score_job_offer) : les tests passent une
fonction factice, la prod route via le résolveur souverain llm_client (SIGIL-1714,
tier local-precision). Aucun réseau dans les tests.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MIN_REL = 0.5
_MAX_KEYWORDS = 20

# Fenêtre de fiche envoyée au modèle. L'ancrage verbatim se mesure sur CETTE
# tranche : c'est la seule que le modèle a pu lire.
_PROMPT_JOB_CHARS = 4000

_MAX_SHORT_CHARS = 120      # entreprise, intitulé
_MAX_REQ_CHARS = 200        # une exigence
_MAX_REQUIREMENTS = 8

# Vocabulaires FERMÉS (référentiel = nous). Ce ne sont pas des données du profil :
# ils pilotent la rédaction, pas la sélection des faits.
_REGISTERS = ("formel", "neutre", "direct")
_DEFAULT_REGISTER = "neutre"
_MARKETS = ("FR", "EU", "UK", "US", "CH", "CA", "INTL")

# Provenance de chaque champ sans référentiel-profil, pour que l'aval sache ce
# qu'il manipule : "verbatim" (ancré dans la fiche), "model" (sortie du modèle,
# bornée mais non ancrable), "default" (notre défaut), "rejected" (sortie du
# modèle écartée), "absent" (le modèle n'a rien fourni d'exploitable).
_CONTEXT_FIELDS = ("company", "job_title", "requirements", "register", "market")


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
            "keywords": [], "label": {"fr": "Ciblé (défaut)", "en": "Targeted (default)"},
            "company": None, "job_title": None, "requirements": [],
            "register": _DEFAULT_REGISTER, "market": None,
            "_field_provenance": {"company": "absent", "job_title": "absent",
                                  "requirements": "absent", "register": "default",
                                  "market": "absent"}}


def _build_prompt(job_posting: str, keys: list[str], domains: list[str]) -> str:
    return f"""Tu es un assistant de candidature. À partir de la FICHE DE POSTE ci-dessous,
déduis une configuration de ciblage de CV et le contexte du poste.

FICHE DE POSTE :
{job_posting[:_PROMPT_JOB_CHARS]}

CLÉS DE PERTINENCE disponibles (choisis LA plus adaptée) : {", ".join(keys)}
DOMAINES disponibles (choisis un sous-ensemble pertinent) : {", ".join(domains)}
REGISTRES possibles : {", ".join(_REGISTERS)}
MARCHÉS possibles : {", ".join(_MARKETS)}

"company" et "job_title" doivent être RECOPIÉS MOT POUR MOT depuis la fiche
ci-dessus. N'invente rien, ne complète pas une abréviation, ne traduis pas : si
la fiche ne les nomme pas explicitement, mets null. Toute valeur absente de la
fiche sera rejetée.

Retourne UNIQUEMENT un objet JSON valide (sans markdown, sans commentaire) :
{{
  "relevance_key": "<une des clés de pertinence>",
  "min_relevance": <flottant 0.0-1.0, seuil de pertinence>,
  "domains_in": [<sous-ensemble des domaines disponibles>],
  "keywords": [<3-10 mots-clés saillants de la fiche>],
  "company": "<nom de l'entreprise, mot pour mot, ou null>",
  "job_title": "<intitulé du poste, mot pour mot, ou null>",
  "requirements": [<3-8 exigences saillantes de la fiche, courtes>],
  "register": "<un des registres>",
  "market": "<un des marchés, ou null>"
}}"""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _norm(s: str) -> str:
    """Forme de comparaison : espaces (y compris sauts de ligne) écrasés, casse pliée."""
    return " ".join(s.split()).casefold()


def _clean_str(value: Any, cap: int) -> Optional[str]:
    """Chaîne bornée, espaces écrasés, caractères de contrôle retirés. None sinon.

    Non-str → None (jamais `str(value)` : un dict bilingue stringifié atterrirait
    tel quel dans l'en-tête d'une lettre).
    """
    if not isinstance(value, str):
        return None
    s = " ".join(value.split())
    s = "".join(ch for ch in s if ch.isprintable())
    s = s.strip()
    return s[:cap] if s else None


def _verbatim_field(name: str, value: Any, window: str, cap: int) -> tuple[Optional[str], str]:
    """(valeur, provenance) — retenue seulement si littéralement dans `window`."""
    s = _clean_str(value, cap)
    if s is None:
        return None, "absent"
    if _norm(s) in _norm(window):
        return s, "verbatim"
    logger.warning("cv_target: champ %s=%r absent de la fiche — rejeté (non ancré)", name, s)
    return None, "rejected"


def _enum_field(name: str, value: Any, allowed: tuple[str, ...],
                default: Optional[str], upper: bool) -> tuple[Optional[str], str]:
    """(valeur, provenance) — clamp sur un vocabulaire fermé."""
    s = _clean_str(value, _MAX_SHORT_CHARS)
    if s is None:
        return default, "default" if default is not None else "absent"
    s = s.upper() if upper else s.lower()
    if s in allowed:
        return s, "model"
    logger.warning("cv_target: champ %s=%r hors vocabulaire %s — rejeté", name, s, allowed)
    return default, "rejected"


def _requirements_field(value: Any) -> tuple[list[str], str]:
    if not isinstance(value, list):
        return [], "absent"
    out = [c for c in (_clean_str(v, _MAX_REQ_CHARS) for v in value) if c]
    return out[:_MAX_REQUIREMENTS], ("model" if out else "absent")


def extract_job_context(job_posting: str, profile: dict,
                        complete_fn: Optional[Callable[[str], str]] = None) -> dict[str, Any]:
    """Déduit un `job_context` depuis une fiche de poste (K1).

    Le résultat **englobe** le cfg de ciblage historique (mêmes clés, mêmes
    valeurs) : il reste directement consommable par `cv_select.select_experiences`
    et `atelier.generate_pdf`. S'y ajoutent `company`, `job_title`,
    `requirements`, `register`, `market` et `_field_provenance`.

    complete_fn : callable (prompt)->str injectable. Si None → llm_client.complete
    (tier local-precision). Sur échec (LLM absent, JSON invalide) → contexte défaut
    + WARNING.
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

    # Champs sans référentiel-profil : chacun selon SON référentiel (cf. docstring).
    window = job_posting[:_PROMPT_JOB_CHARS]
    company, prov_company = _verbatim_field("company", parsed.get("company"),
                                            window, _MAX_SHORT_CHARS)
    job_title, prov_title = _verbatim_field("job_title", parsed.get("job_title"),
                                            window, _MAX_SHORT_CHARS)
    requirements, prov_req = _requirements_field(parsed.get("requirements"))
    register, prov_reg = _enum_field("register", parsed.get("register"), _REGISTERS,
                                     _DEFAULT_REGISTER, upper=False)
    market, prov_mkt = _enum_field("market", parsed.get("market"), _MARKETS, None, upper=True)

    return {
        "relevance_key": key,
        "min_relevance": min_rel,
        "domains_in": domains_in,
        "keywords": keywords,
        "label": {"fr": "Ciblé (fiche de poste)", "en": "Targeted (job posting)"},
        "company": company,
        "job_title": job_title,
        "requirements": requirements,
        "register": register,
        "market": market,
        "_field_provenance": {"company": prov_company, "job_title": prov_title,
                              "requirements": prov_req, "register": prov_reg,
                              "market": prov_mkt},
    }


def extract_cfg(job_posting: str, profile: dict,
                complete_fn: Optional[Callable[[str], str]] = None) -> dict[str, Any]:
    """Alias historique de `extract_job_context` — MÊME objet, pas une projection.

    Le cfg n'est pas « extrait » du job_context : c'est le job_context lui-même,
    dont `select_experiences` / `build_structured_cv` ne lisent qu'un sous-ensemble
    de clés (`.get`). Renvoyer une projection réduite ici recréerait deux vérités.
    """
    return extract_job_context(job_posting, profile, complete_fn=complete_fn)


def targeted_structured_cv(job_posting: str, profile: dict, lang: str = "fr",
                           complete_fn: Optional[Callable[[str], str]] = None):
    """Pipeline ciblé complet (pur, hors PDF) : fiche → cfg → select → structured_cv.

    Retourne (cfg, structured_cv). Le rendu HTML/PDF réutilise cv_render + Playwright
    (mêmes que la banque préfab). Testable sans réseau via complete_fn factice.
    """
    import cv_select  # sibling, import paresseux

    cfg = extract_cfg(job_posting, profile, complete_fn=complete_fn)
    exps = cv_select.select_experiences(profile, cfg)
    scv = cv_select.build_structured_cv(profile, exps, lang, cfg)
    return cfg, scv


def _resolve_career(here: "pathlib.Path"):
    """(career_dir, elysium_root) si career/core/llm_client.py existe, sinon None.

    Pur : aucune insertion sys.path, aucun import — testable avec un faux arbre tmp.
    tools/cv/x.py -> parents[2]=racine repo site -> .parent -> ELYSIUM sibling.
    """
    elysium_root = here.parents[2].parent / "ELYSIUM"
    career = elysium_root / "satellites" / "anthropos" / "apps" / "career"
    if (career / "core" / "llm_client.py").exists():
        return career, elysium_root
    return None


#: Tiers essayés dans l'ordre, surchargeables par `CV_LLM_TIERS` (séparés par des
#: virgules). Le défaut n'est PAS un seul tier, et c'est une correction mesurée :
#: lors du premier usage réel (fiche Amundi, 4908 caractères) `local-precision`
#: — ollama/deepseek-r1:32b — a échoué **3 fois sur 3** sur
#: `litellm.Timeout after 120.0s`. Ce n'est pas un backend absent : c'est un modèle
#: de raisonnement, qui dépense son budget en `<think>` avant de répondre, et qui
#: dépasse le timeout du gateway. Or `core.llm_client.complete` n'expose aucun
#: paramètre de timeout : depuis ce module on ne peut pas augmenter le budget, on
#: ne peut que choisir un tier qui tienne dedans. `local-qwen` (ollama/qwen2.5:14b)
#: a rendu la même extraction correctement.
_TIERS_DEFAUT = ("local-precision", "local-qwen")


def _tiers() -> tuple[str, ...]:
    import os
    brut = os.environ.get("CV_LLM_TIERS", "")
    choisis = tuple(t.strip() for t in brut.split(",") if t.strip())
    return choisis or _TIERS_DEFAUT


def _complete_http(prompt: str) -> str:
    """Appel OpenAI-compat DIRECT. Chemin du CONTENEUR, où le sibling n'existe pas.

    Déployé sur le cluster, l'atelier n'a pas de checkout ELYSIUM à côté de lui :
    `_resolve_career` rend None et le résolveur souverain est hors d'atteinte. Plutôt
    que d'empaqueter une copie de `career/core/` dans l'image — qui divergerait en
    silence de son original — on parle directement à l'endpoint compatible OpenAI
    du cluster (`forge-ollama.elysium-ml.svc:11434/v1`).

    Ce chemin **contourne le gateway souverain**, donc le budget cap SIGIL-529 : il
    est réservé aux backends LOCAUX (ollama, vllm), dont le coût marginal est nul.
    Il n'est jamais choisi tant que le sibling est là, et `CV_LLM_BASE_URL` doit
    être posé explicitement — aucune bascule automatique vers un backend payant.

    Contrepartie utile : ici le **timeout est réglable** (`CV_LLM_TIMEOUT`, 600 s par
    défaut), ce que `core.llm_client.complete` n'expose pas — c'est précisément la
    limite qui a fait échouer `local-precision` trois fois sur trois.
    """
    import json as _json
    import os
    import urllib.request

    base = os.environ["CV_LLM_BASE_URL"].rstrip("/")
    modele = os.environ.get("CV_LLM_MODEL", "qwen2.5:14b")
    corps = _json.dumps({"model": modele, "temperature": 0, "stream": False,
                         "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(f"{base}/chat/completions", data=corps,
                                 headers={"Content-Type": "application/json"})
    delai = int(os.environ.get("CV_LLM_TIMEOUT", "600"))
    logger.warning("cv_target: résolveur souverain absent — appel direct %s (%s), "
                   "hors gateway et hors budget cap", base, modele)
    with urllib.request.urlopen(req, timeout=delai) as rep:
        charge = _json.loads(rep.read().decode("utf-8"))
    return charge["choices"][0]["message"]["content"]


def _sovereign_complete(prompt: str) -> str:
    """Route via le résolveur souverain llm_client du sibling ELYSIUM career (SIGIL-1714).

    Insère la **racine ELYSIUM** (pour que le tier-1 sigma_llm_gateway — importé en
    `scripts.governance.sigma_llm_gateway` — soit atteignable) ET le dossier career
    (pour `core.llm_client` / `core.config`) sur sys.path, puis importe `complete`.

    Sibling absent : bascule sur `_complete_http` **si et seulement si**
    `CV_LLM_BASE_URL` est posé (cas du conteneur). Sinon lève, comme avant →
    extract_cfg retombe sur le cfg défaut (loud).

    Essaie les tiers de `_tiers()` **dans l'ordre**. Chaque échec est journalisé en
    WARNING **en nommant le tier et l'erreur** : la descente en gamme est un fait
    consigné, jamais un repli muet. Si tous échouent, la dernière exception est
    relancée — aucune prose de repli n'est fabriquée.
    """
    import pathlib
    import sys

    resolved = _resolve_career(pathlib.Path(__file__).resolve())
    if resolved is None:
        import os
        if os.environ.get("CV_LLM_BASE_URL"):
            return _complete_http(prompt)
        raise RuntimeError("llm_client souverain introuvable (ELYSIUM career sibling absent)")
    career, elysium_root = resolved
    for p in (str(elysium_root), str(career)):   # racine ELYSIUM (tier-1) ET career (core.*)
        if p not in sys.path:
            sys.path.insert(0, p)
    from core.llm_client import complete  # type: ignore

    tiers = _tiers()
    derniere: Optional[Exception] = None
    for i, tier in enumerate(tiers):
        try:
            return complete(prompt, tier=tier, max_tokens=1024)
        except Exception as exc:
            derniere = exc
            reste = tiers[i + 1:]
            logger.warning("cv_target: tier %s indisponible (%s) — %s", tier, exc,
                           f"essai de {reste[0]}" if reste else "plus aucun tier")
    raise derniere if derniere is not None else RuntimeError("aucun tier LLM configuré")
