"""Plan B (ADR-003) — lettre de motivation : sélection de preuves, squelettes, brouillon.

Chaîne : `job_context` (cv_target, K1) → `select_evidence` (pur, K2) →
`build_profile_facts` → `draft` (LLM, K3) → `cv_grounding.check_grounding` (K4,
BLOQUANT) → `cv_letter_render.render_letter_html` (K5).

### Ce que la lettre promet, honnêtement (correction K2)

Le spec §4 promettait : « les 2-3 expériences/projets les plus pertinents, via le
**même score de pertinence que le CV**. La lettre parle donc des mêmes faits que
le CV qui l'accompagne. »

**Mesuré le 2026-07-28** : les 3 expériences de `profile.json` portent un dict
`relevance` ; **aucun des 17 projets** n'en porte — ils n'ont que `domains`. Un
score fondé sur `relevance` rendrait 0.0 pour les 17 projets, et la promesse
serait tenue en n'ayant jamais rien à dire d'un projet.

Deux voies existaient : taguer éditorialement les 17 projets (travail humain, et
inventer des poids serait un placeholder), ou scorer les projets sur le
recouvrement `domains ∩ job_context.domains_in`. **On prend la seconde**, et la
promesse est donc réécrite :

> Les **expériences** citées par la lettre sont exactement celles que le CV
> retient, dans le même ordre : `select_evidence` appelle
> `cv_select.select_experiences(profile, job_context)`, le même appel avec le
> même cfg. Les **projets** sont retenus sur un score **distinct** — le
> recouvrement de domaines — parce qu'aucun ne porte de pertience chiffrée. La
> lettre peut donc citer un projet que le CV ne montre pas ; chaque preuve
> déclare la base de son score (`score_basis`) pour que ce ne soit pas caché.

Ce qui reste garanti sans réserve : **toute preuve trace vers une entrée réelle
de `profile.json`** (`source`), et le vérificateur d'ancrage (K4) juge in fine
chaque affirmation contre les faits transmis.

### Le maillon que l'appelant ne doit pas oublier

Le verdict d'ancrage doit être demandé **avec** les preuves retenues :

    verdict = cv_grounding.check_grounding(body, profile, lang, evidence=ev)

Sans `evidence`, le vérificateur juge contre le profil entier et peut attester un
ancrage sur des faits que le rédacteur n'a jamais vus (mesuré le 2026-07-28 : une
lettre affirmant huit ans chez Goldman Sachs obtenait `ok=True` en citant
`identity`, `meta`, `lifestyle` ou `career_goals.short_term`). `evidence` clampe
les sources recevables sur les faits que le rédacteur a réellement lus — la même
liste `cv_grounding.shown_facts` que `build_profile_facts` affiche, pas une
reconstitution qui lui ressemble. Le verdict déclare d'ailleurs contre quel
référentiel il a jugé (`referentiel.clamp`) : un `evidence=` oublié affaiblit la
garantie, et cela doit se lire.

Aucun réseau dans les tests : `complete_fn` est injectable partout ; le défaut
route par `cv_target._sovereign_complete` (gateway souveraine, budget cap
SIGIL-529) — jamais `anthropic.Anthropic` en direct (ADR-003).
"""
from __future__ import annotations

import pathlib
from typing import Any, Callable, Optional

import cv_grounding
import cv_select
import cv_target

_ROOT = pathlib.Path(__file__).resolve().parents[2]   # racine du dépôt SITE
_SKELETON_DIR = ("letters", "skeletons")

#: La coupe des puces vit dans `cv_grounding._MAX_EVIDENCE_BULLETS` et nulle part
#: ailleurs : le rédacteur affiche `cv_grounding.shown_facts`, le vérificateur
#: accepte la même liste. Une constante dupliquée ici demandait un test-miroir —
#: qui ne prouve rien de plus que l'égalité de deux nombres.
_MAX_PARAGRAPHS = 12


class LetterError(RuntimeError):
    """Refus explicite (fail-loud). Aucune prose de repli n'est jamais fabriquée."""


# ── helpers purs ────────────────────────────────────────────────────────────────

def _loc(value: Any, lang: str) -> str:
    """Résout un champ potentiellement bilingue `{fr, en}` ; '' si absent.

    Copie locale et volontaire du helper de `cv_select` : ce module ne doit pas
    dépendre d'un symbole privé d'un module en cours de refonte (LOT M).
    """
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("fr") or value.get("en") or "")
    return str(value) if value is not None else ""


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _link_display(url: Any) -> str:
    """URL affichable, sans schéma ni `www.` — même traitement que l'en-tête du CV
    (`cv_select._link_display`). Copie locale volontaire : ce module ne dépend pas
    d'un symbole privé d'un fichier en cours de refonte (LOT M)."""
    s = url.strip() if isinstance(url, str) else ""
    for pfx in ("https://", "http://"):
        if s.startswith(pfx):
            s = s[len(pfx):]
            break
    return s[4:] if s.startswith("www.") else s


# ── K2 — sélection de preuves (PURE) ───────────────────────────────────────────

def score_project(project: dict[str, Any], job_context: dict[str, Any]) -> float:
    """Recouvrement de domaines, dans [0,1]. 0.0 si le contexte ne vise aucun domaine.

    Ce n'est PAS le score du CV : les projets ne portent pas de `relevance`.
    Renvoyer 0.0 quand `domains_in` est vide est délibéré — sans domaine visé, il
    n'existe aucune raison mesurable de citer un projet plutôt qu'un autre, et en
    inventer une serait exactement ce que le plan B existe pour empêcher.
    """
    wanted = {d for d in _as_list(job_context.get("domains_in")) if isinstance(d, str)}
    if not wanted:
        return 0.0
    have = {d for d in _as_list(project.get("domains")) if isinstance(d, str)}
    return len(have & wanted) / len(wanted)


def select_evidence(profile: dict[str, Any], job_context: dict[str, Any],
                    *, max_items: int = 3) -> list[dict[str, Any]]:
    """2-3 preuves, PURE et déterministe. Ne mute jamais `profile`.

    Expériences : `cv_select.select_experiences(profile, job_context)` — le même
    appel que le CV. Projets : `score_project` (> 0 seulement). Si des projets
    qualifient, on garde au plus `max_items - 1` expériences, sinon la lettre ne
    parlerait jamais d'un projet.
    """
    exps = cv_select.select_experiences(profile, job_context)

    scored = [(score_project(p, job_context), p) for p in _as_list(profile.get("projects"))]
    scored = [(s, p) for s, p in scored if s > 0.0]
    # Tri déterministe : score desc, `featured` d'abord, puis id (jamais l'ordre du dict).
    scored.sort(key=lambda t: (-t[0], not bool(t[1].get("featured")), str(t[1].get("id") or "")))

    keep_exps = max(0, max_items - 1) if scored else max_items
    out: list[dict[str, Any]] = []
    for exp in exps[:keep_exps]:
        out.append({"kind": "experience", "id": exp.get("id") or "",
                    "source": f"experiences[{exp.get('id') or ''}]",
                    "score": float((exp.get("relevance") or {}).get(
                        job_context.get("relevance_key") or "general") or 0.0),
                    "score_basis": "relevance"})
    for s, p in scored:
        if len(out) >= max_items:
            break
        out.append({"kind": "project", "id": p.get("id") or "",
                    "source": f"projects[{p.get('id') or ''}]",
                    "score": s, "score_basis": "domains"})
    return out[:max_items]


def build_profile_facts(profile: dict[str, Any], evidence: list[dict[str, Any]],
                        lang: str) -> dict[str, Any]:
    """Charge utile transmise au rédacteur : identité minimale + preuves retenues.

    **Les faits viennent de `cv_grounding.shown_facts`, et de nulle part
    ailleurs.** C'est le maillon qui manquait : le prompt du rédacteur et le
    vocabulaire des sources que le vérificateur accepte sont désormais la même
    liste, produite une fois. Ils ne peuvent plus diverger — et ils avaient
    divergé, dans les deux sens, sur le profil de production (une date de fin
    acceptée sans avoir été montrée ; une date de projet montrée sans être
    ancrable). Chaque valeur affichée porte son chemin, calculé au même endroit.

    Une preuve dont l'id ne désigne rien dans le profil est ignorée plutôt que
    rendue vide : `draft` refuse ensuite une charge sans preuve (fail-loud).

    Rien d'autre ne sort de `profile.json`. `identity.email` et `location`
    servent l'EN-TÊTE du document, jamais la prose : ils ne sont pas dans
    `shown_facts`, donc pas dans le prompt, donc pas des sources recevables.
    Le téléphone n'est jamais projeté (le dépôt est public, la lettre part en PDF).
    """
    identity = profile.get("identity") or {}
    loc = identity.get("location") if isinstance(identity.get("location"), dict) else {}
    shown = cv_grounding.shown_facts(profile, evidence, lang)
    blocks = {(b["kind"], b["id"]): b for b in shown["items"]}

    items: list[dict[str, Any]] = []
    for ev in evidence:
        block = blocks.get((ev.get("kind"), str(ev.get("id") or "")))
        if block is None:
            continue
        head = block["head"]
        items.append({"kind": block["kind"], "source": block["source"],
                      "score": ev.get("score"), "score_basis": ev.get("score_basis"),
                      "organisation": head[0]["text"],
                      "intitule": head[1]["text"],
                      "periode": head[2]["text"],
                      "points": [a["text"] for a in block["points"]]})

    return {
        "lang": lang,
        "identity": {
            "name": shown["identity"]["text"],
            "email": _loc(identity.get("email"), lang),
            "location": ", ".join(x for x in (str(loc.get("city") or "").strip(),
                                              str(loc.get("country") or "").strip()) if x),
            "source": "identity",
        },
        "evidence": items,
    }


# ── K3 — squelettes de guidage ─────────────────────────────────────────────────

_REQUIRED_SECTION_KEYS = ("intention", "budget_mots")


def parse_skeleton(text: str) -> dict[str, Any]:
    """Parse un squelette markdown (stdlib seule — pas de dépendance YAML).

    Forme : frontmatter `---` `clé: valeur` `---`, puis des sections `## <id>`
    dont les métadonnées sont des puces `- clé: valeur`. La prose libre d'une
    section est du commentaire pour l'humain ; elle n'est PAS transmise au
    modèle (elle décrirait le squelette, pas la lettre).

    Reject-loud : frontmatter absent, `lang`/`id` manquants, section sans
    `intention` ou sans `budget_mots` entier → LetterError.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        raise LetterError("squelette sans frontmatter '---' en première ligne")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise LetterError("frontmatter non refermé") from exc

    head: dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        k, sep, v = raw.partition(":")
        if not sep:
            raise LetterError(f"ligne de frontmatter invalide : {raw!r}")
        head[k.strip()] = v.strip()

    for key in ("id", "lang"):
        if not head.get(key):
            raise LetterError(f"frontmatter sans '{key}'")

    sections: list[dict[str, Any]] = []
    for raw in lines[end + 1:]:
        line = raw.strip()
        if line.startswith("## "):
            sections.append({"id": line[3:].strip()})
        elif line.startswith("- ") and sections:
            k, sep, v = line[2:].partition(":")
            if sep:
                sections[-1][k.strip()] = v.strip()

    if not sections:
        raise LetterError("squelette sans section '## <id>'")

    for sec in sections:
        for key in _REQUIRED_SECTION_KEYS:
            if not sec.get(key):
                raise LetterError(f"section '{sec.get('id')}' sans '{key}'")
        try:
            sec["budget_mots"] = int(str(sec["budget_mots"]).strip())
        except ValueError as exc:
            raise LetterError(f"section '{sec['id']}' : budget_mots non entier") from exc

    try:
        budget = int(head.get("budget_mots", "0"))
    except ValueError as exc:
        raise LetterError("frontmatter : budget_mots non entier") from exc

    return {"id": head["id"], "lang": head["lang"],
            "registre": head.get("registre") or "neutre",
            "budget_mots": budget, "sections": sections}


def load_skeleton(skeleton_id: str, lang: str,
                  root: Optional[pathlib.Path] = None) -> dict[str, Any]:
    """Charge `letters/skeletons/<id>.<lang>.md`. Un squelette par LANGUE : aucune
    traduction automatique n'est possible par construction (spec §7)."""
    base = pathlib.Path(root) if root is not None else _ROOT
    path = base.joinpath(*_SKELETON_DIR) / f"{skeleton_id}.{lang}.md"
    if not path.is_file():
        raise LetterError(f"squelette introuvable : {path}")
    sk = parse_skeleton(path.read_text(encoding="utf-8"))
    if sk["lang"] != lang:
        raise LetterError(f"squelette {path.name} déclare lang={sk['lang']!r}, attendu {lang!r}")
    return sk


# ── K3 — brouillon ─────────────────────────────────────────────────────────────

def _fact_block(facts: dict[str, Any]) -> str:
    out = [f"CANDIDAT : {facts['identity']['name']}"]
    for i, rec in enumerate(facts["evidence"], 1):
        head = " — ".join(x for x in (rec.get("organisation"), rec.get("intitule"),
                                      rec.get("periode")) if x)
        out.append(f"[F{i}] ({rec['source']}) {head}")
        out.extend(f"    · {p}" for p in rec.get("points") or [])
    return "\n".join(out)


def _skeleton_block(skeleton: dict[str, Any]) -> str:
    out = []
    for sec in skeleton["sections"]:
        out.append(f"## {sec['id']} (≈{sec['budget_mots']} mots, registre : "
                   f"{sec.get('registre') or skeleton['registre']})")
        out.append(f"   intention : {sec['intention']}")
    return "\n".join(out)


def build_draft_prompt(facts: dict[str, Any], job_context: dict[str, Any],
                       skeleton: dict[str, Any], lang: str) -> str:
    """Prompt du rédacteur. Ne contient QUE les faits sélectionnés : ce qu'on ne
    donne pas ne peut pas être déformé."""
    reqs = "\n".join(f"  - {r}" for r in _as_list(job_context.get("requirements"))) or "  (non extraites)"
    return f"""Tu rédiges une lettre de motivation en {lang}.

RÈGLE ABSOLUE : tu ne peux affirmer sur le candidat QUE ce que les FAITS
ci-dessous énoncent. Aucune durée, aucun chiffre, aucune taille d'équipe, aucun
titre, aucune compétence qui n'y figure pas. Si un fait manque, écris moins.
Chaque affirmation portant sur le candidat sera vérifiée une par une contre son
profil, et la lettre sera REFUSÉE si l'une d'elles ne trace pas.

POSTE
  entreprise : {job_context.get('company') or '(non identifiée)'}
  intitulé   : {job_context.get('job_title') or '(non identifié)'}
  registre   : {job_context.get('register') or 'neutre'}
  marché     : {job_context.get('market') or '(non identifié)'}
  exigences saillantes :
{reqs}

FAITS DISPONIBLES (les seuls autorisés)
{_fact_block(facts)}

SQUELETTE DE GUIDAGE (intentions et budgets, PAS des fentes à remplir ;
n'écris pas les titres de section dans la lettre)
{_skeleton_block(skeleton)}

Budget total ≈ {skeleton['budget_mots']} mots.
Retourne UNIQUEMENT le corps de la lettre, en paragraphes séparés par une ligne
vide. Pas d'en-tête, pas d'adresse, pas de date, pas de signature, pas de
markdown."""


def draft(profile_facts: dict[str, Any], job_context: dict[str, Any],
          skeleton: dict[str, Any], lang: str,
          complete_fn: Optional[Callable[[str], str]] = None) -> str:
    """Brouillon LLM. Fail-loud : aucune prose de repli n'est jamais fabriquée.

    Le défaut route par `cv_target._sovereign_complete` (SIGIL-1714 / budget cap
    SIGIL-529), jamais par `anthropic.Anthropic` (ADR-003).
    """
    if skeleton.get("lang") != lang:
        raise LetterError(
            f"squelette en {skeleton.get('lang')!r} pour une lettre en {lang!r} : "
            "aucune traduction automatique (spec §7)")
    if not (profile_facts.get("evidence") or []):
        raise LetterError("aucune preuve sélectionnée — rien à écrire")
    if profile_facts.get("lang") != lang:
        raise LetterError(f"faits résolus en {profile_facts.get('lang')!r}, lettre en {lang!r}")

    fn = complete_fn if complete_fn is not None else cv_target._sovereign_complete
    prompt = build_draft_prompt(profile_facts, job_context, skeleton, lang)
    try:
        raw = fn(prompt)
    except Exception as exc:
        raise LetterError(f"rédacteur indisponible : {exc}") from exc
    text = (raw or "").strip()
    if not text:
        raise LetterError("le rédacteur a renvoyé une réponse vide")
    return text


# ── K5 (amont) — document de lettre, prêt à rendre ─────────────────────────────

_SUBJECT = {"fr": "Candidature", "en": "Application"}


def build_letter_document(profile: dict[str, Any], profile_facts: dict[str, Any],
                          job_context: dict[str, Any], body_text: str, lang: str,
                          today: Optional[str] = None) -> dict[str, Any]:
    """Structure neutre consommée par `cv_letter_render.render_letter_html`.

    `today` est **injecté**, jamais lu à l'horloge : un rendu qui dépend de
    l'heure n'est pas reproductible et pourrit ses propres tests. Aucun champ
    n'est comblé par un gabarit (« [Entreprise] ») : une valeur non ancrée est
    absente, pas inventée.
    """
    identity = profile_facts.get("identity") or {}
    links = (profile.get("identity") or {}).get("links") or {}
    paragraphs = [p.strip() for p in (body_text or "").split("\n\n")]
    paragraphs = [p for p in paragraphs if p][:_MAX_PARAGRAPHS]

    subject = _SUBJECT.get(lang, _SUBJECT["fr"])
    if job_context.get("job_title"):
        subject = f"{subject} — {job_context['job_title']}"

    return {
        "lang": lang,
        "identity": {                                   # téléphone JAMAIS projeté
            "name": identity.get("name", ""),
            "email": identity.get("email", ""),
            "location": identity.get("location", ""),
            "linkedin": _link_display(links.get("linkedin")),
        },
        "recipient": {"company": job_context.get("company")},
        "date": today,
        "subject": subject,
        "paragraphs": paragraphs,
        "signature": identity.get("name", ""),
    }
