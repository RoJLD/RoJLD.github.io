"""Projection du bloc `candidate:` et du préavis dans config/profile.yml de career-ops (spec
D8 § 5). Édition ligne à ligne : un aller-retour YAML perdrait les commentaires de Robin.
Seules les clés listées changent ; narrative, target_roles, compensation… restent écrits à la
main. Une clé introuvable, commentée ou en double est un refus nommé, jamais un ajout."""
from __future__ import annotations

import re
from datetime import date

from tools.cockpit.cv_md import lien_court, t

CLES_CANDIDAT = ("full_name", "email", "phone", "location", "linkedin", "portfolio_url", "github")
COMMENTAIRE_PREAVIS = "# projeté depuis profile.json (identity.availability)"
_VALEUR = re.compile(r"""^[ \t]+[A-Za-z_]+:[ \t]*(?P<v>"(?:[^"\\]|\\.)*"|'[^']*'|[^#]*?)[ \t]*(?:#.*)?$""")
_PREAVIS = re.compile(r"^(?P<indent>[ \t]+)notice_period_days:[ \t]*(?P<v>\d*)")


class CleIntrouvable(KeyError):
    """args[0] = chemin de la clé (« candidate.github », « … (en double) »)."""


def preavis_jours(disponibilite, aujourdhui: date) -> int | None:
    """`identity.availability` ('YYYY-MM') : 0 si le mois est atteint, sinon les jours jusqu'au
    1er de ce mois. None si la date est absente ou illisible : on ne l'invente pas."""
    m = re.match(r"^(\d{4})-(0[1-9]|1[0-2])$", str(disponibilite or ""))
    if not m:
        return None
    return max((date(int(m.group(1)), int(m.group(2)), 1) - aujourdhui).days, 0)


def _texte(v) -> str:
    """'' pour une valeur absente ou null : jamais le mot « None »."""
    return "" if v is None else str(v)


def valeurs(profile: dict, complement: dict, aujourdhui: date) -> dict:
    ide = profile.get("identity", {})
    liens, lieu = ide.get("links", {}), ide.get("location") or {}
    loc = t(complement.get("location"), "en") or ", ".join(x for x in (lieu.get("city"), lieu.get("country")) if x)
    return {"full_name": f"{ide.get('first_name') or ''} {ide.get('last_name') or ''}".strip(),
            "email": _texte(ide.get("email")), "phone": _texte(complement.get("phone")), "location": loc,
            "linkedin": lien_court(liens.get("linkedin")), "portfolio_url": _texte(liens.get("portfolio")),
            "github": lien_court(liens.get("github")),
            "notice_period_days": preavis_jours(ide.get("availability"), aujourdhui)}


def _quoter(v: str) -> str:
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lue(ligne: str) -> str:
    m = _VALEUR.match(ligne.rstrip("\r\n"))
    v = (m.group("v") if m else "").strip()
    if v[:1] == '"':
        return re.sub(r"\\(.)", r"\1", v[1:-1])
    if v[:1] == "'":
        return v[1:-1]
    return v


def _fin(ligne: str) -> str:
    return ligne[len(ligne.rstrip("\r\n")):]


def projeter(texte: str, vals: dict) -> tuple[str, list[str]]:
    lignes = texte.splitlines(keepends=True)
    debut = next((i for i, ligne in enumerate(lignes) if ligne.rstrip("\r\n") == "candidate:"), None)
    if debut is None:
        raise CleIntrouvable("candidate")
    fin = next((i for i in range(debut + 1, len(lignes)) if lignes[i][:1] not in (" ", "\t", "#", "\r", "\n")),
               len(lignes))
    changements = []
    for cle in CLES_CANDIDAT:
        idx = [i for i in range(debut + 1, fin) if re.match(rf"^  {cle}:", lignes[i])]
        if len(idx) != 1:
            raise CleIntrouvable(f"candidate.{cle}" + (" (en double)" if idx else ""))
        i = idx[0]
        if vals[cle] in ("", None):      # absent du profil : la ligne de Robin reste telle quelle (comme le préavis)
            continue
        if _lue(lignes[i]) != str(vals[cle]):
            lignes[i] = f"  {cle}: {_quoter(vals[cle])}{_fin(lignes[i])}"
            changements.append(f"candidate.{cle}")
    n = vals.get("notice_period_days")
    if n is not None:
        idx = [i for i, ligne in enumerate(lignes) if _PREAVIS.match(ligne)]
        if len(idx) != 1:
            raise CleIntrouvable("cover_letter.notice_period_days" + (" (en double)" if idx else ""))
        i = idx[0]
        m = _PREAVIS.match(lignes[i])
        if m.group("v") != str(n):
            lignes[i] = f"{m.group('indent')}notice_period_days: {n}  {COMMENTAIRE_PREAVIS}{_fin(lignes[i])}"
            changements.append("cover_letter.notice_period_days")
    return "".join(lignes), changements
