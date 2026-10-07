"""Complément privé du CV (spec D8 § 3, décision D19) : téléphone, adresse, disponibilité et
expériences « CV seulement » (non listées dans profile.json public).

Il vit dans `<career-ops>/data/cv_private.json` : ignoré par la couche code de career-ops
(`.gitignore` : `/data`), suivi par la couche perso (`~/.career-ops-perso.git`). Jamais dans
`profile.json`, servi tel quel sur robin-denis.com/profile.json et lu par 7 pages du site.
Le chargeur refuse un fichier que la couche code pourrait committer : le fork est PUBLIC."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tools.cockpit import config

REL = "data/cv_private.json"
_YYYY_MM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ComplementAbsent(FileNotFoundError):
    """Le fichier n'existe pas : une projection perdrait le téléphone et deux postes."""


class ComplementInvalide(ValueError):
    """Le fichier existe mais ne peut pas servir ; le message nomme le champ."""


def chemin(root: Path) -> Path:
    return Path(root) / REL


def est_ignore(root: Path, rel: str = REL, run=subprocess.run) -> bool:
    """`git check-ignore` dans la couche code de career-ops : code 0 = ignoré."""
    try:
        cp = run(["git", "-C", str(root), "check-ignore", "-q", rel],
                 capture_output=True, timeout=10, **config.SANS_CONSOLE)
    except (OSError, subprocess.SubprocessError):
        return False
    return cp.returncode == 0


def _bilingue(v, champ: str, *, obligatoire: bool) -> dict | None:
    if v is None and not obligatoire:
        return None
    if isinstance(v, str) and v.strip():
        return {"fr": v.strip(), "en": v.strip()}
    if (isinstance(v, dict) and isinstance(v.get("fr"), str) and isinstance(v.get("en"), str)
            and v["fr"].strip() and v["en"].strip()):
        return {"fr": v["fr"].strip(), "en": v["en"].strip()}
    raise ComplementInvalide(f'{champ} : texte ou {{"fr", "en"}} non vides attendus')


def _disponibilite(v) -> dict:
    if v is None or v == "":
        return {"fr": "", "en": ""}
    if isinstance(v, str):
        return {"fr": v.strip(), "en": v.strip()}
    if isinstance(v, dict) and all(isinstance(v.get(lang, ""), str) for lang in ("fr", "en")):
        return {"fr": v.get("fr", "").strip(), "en": v.get("en", "").strip()}
    raise ComplementInvalide('availability : texte ou {"fr", "en"} attendu')


def _experience(e, i: int) -> dict:
    lieu = f"experiences_cv[{i}]"
    if not isinstance(e, dict):
        raise ComplementInvalide(f"{lieu} : objet attendu")
    societe = e.get("company")
    if not isinstance(societe, str) or not societe.strip():
        raise ComplementInvalide(f"{lieu}.company : texte non vide attendu")
    for cle in ("start", "end"):
        v = e.get(cle)
        if cle == "end" and v is None:
            continue
        if not isinstance(v, str) or not _YYYY_MM.match(v):
            raise ComplementInvalide(f"{lieu}.{cle} : 'YYYY-MM' attendu, lu {v!r}")
    puces = e.get("bullets")
    if not (isinstance(puces, dict) and all(isinstance(puces.get(lang), list)
                                            and all(isinstance(x, str) for x in puces[lang]) for lang in ("fr", "en"))):
        raise ComplementInvalide(f'{lieu}.bullets : {{"fr": [...], "en": [...]}} attendu')
    return {"company": societe.strip(),
            "location": _bilingue(e.get("location"), f"{lieu}.location", obligatoire=False),
            "title": _bilingue(e.get("title"), f"{lieu}.title", obligatoire=True),
            "type": e.get("type") or None,
            "start": e["start"], "end": e.get("end"), "current": False,
            "bullets": {"fr": list(puces["fr"]), "en": list(puces["en"])}}


def charger(root: Path, *, ignore_fn=None) -> dict:
    """Complément normalisé. Lève ComplementAbsent ou ComplementInvalide : jamais un complément
    vide à la place du vrai, qui rendrait des CV sans téléphone ni deux postes (Zero Masking)."""
    ignore_fn = ignore_fn or est_ignore
    p = chemin(root)
    if not p.is_file():
        raise ComplementAbsent(f"{p} absent : créer le complément privé (spec D8 § 4)")
    if not ignore_fn(root):
        raise ComplementInvalide(f"{REL} n'est pas ignoré par la couche code de career-ops : "
                                 "un `git add -A` le pousserait vers le fork public")
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ComplementInvalide(f"{p} illisible ({exc})") from exc
    if not isinstance(data, dict):
        raise ComplementInvalide(f"{p} : objet JSON attendu")
    tel = data.get("phone")
    if not isinstance(tel, str) or not tel.strip():
        raise ComplementInvalide("phone : texte non vide attendu (les CV envoyés le portent, fait n°6)")
    exps = data.get("experiences_cv", [])
    if not isinstance(exps, list):
        raise ComplementInvalide("experiences_cv : liste attendue")
    return {"phone": tel.strip(),
            "location": _bilingue(data.get("location"), "location", obligatoire=False),
            "availability": _disponibilite(data.get("availability")),
            "experiences_cv": [_experience(e, i) for i, e in enumerate(exps)]}
