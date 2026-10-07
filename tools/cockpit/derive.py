"""Garde de dérive de cv.md (spec D8 § 6). La première ligne porte l'empreinte du reste du
fichier. Si l'empreinte ne correspond plus, quelqu'un a modifié cv.md à la main (« Ask », une
session Claude, add-entry.mjs, un éditeur) : on refuse d'écrire, sauf `forcer`, qui sauvegarde
d'abord. Les empreintes portent sur un texte normalisé (BOM retiré, LF) : un éditeur qui passe
le fichier en CRLF ne « modifie » rien."""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

# Contrat avec career-ops : web/src/lib/cv-generated.mjs teste le début de cette ligne.
PREFIXE = "<!-- généré par le cockpit depuis profile.json — ne pas modifier ici ; empreinte sha256:"
_ENTETE = re.compile("^" + re.escape(PREFIXE) + r"([0-9a-f]{64}) -->$")
ECRITURE_SANS_FORCER = {"absent", "en_retard", "a_jour"}


class DeriveRefusee(RuntimeError):
    """args[0] = l'état qui interdit d'écrire (« modifie » ou « sans_entete »)."""


def normaliser(texte: str) -> str:
    return texte.lstrip("\ufeff").replace("\r\n", "\n")


def empreinte(corps: str) -> str:
    return hashlib.sha256(normaliser(corps).encode("utf-8")).hexdigest()


def avec_entete(corps: str) -> str:
    corps = normaliser(corps)
    return f"{PREFIXE}{empreinte(corps)} -->\n{corps}"


def separer(texte: str) -> tuple[str | None, str]:
    """(empreinte lue dans l'en-tête, ou None ; corps normalisé)."""
    texte = normaliser(texte)
    tete, _, reste = texte.partition("\n")
    m = _ENTETE.match(tete)
    return (m.group(1), reste) if m else (None, texte)


def lire(chemin: Path) -> str | None:
    """Texte du fichier, fins de ligne intactes (pas de traduction universelle), ou None."""
    return Path(chemin).read_bytes().decode("utf-8-sig") if Path(chemin).is_file() else None


def etat(texte_actuel: str | None, corps_attendu: str) -> str:
    if texte_actuel is None:
        return "absent"
    lue, corps = separer(texte_actuel)
    if lue is None:
        return "sans_entete"
    if lue != empreinte(corps):
        return "modifie"
    return "a_jour" if corps == normaliser(corps_attendu) else "en_retard"


def diff(texte_actuel: str | None, corps_attendu: str, nom: str = "cv.md") -> str:
    avant = separer(texte_actuel)[1] if texte_actuel is not None else ""
    return "".join(difflib.unified_diff(avant.splitlines(keepends=True),
                                        normaliser(corps_attendu).splitlines(keepends=True),
                                        fromfile=f"{nom} (actuel)", tofile=f"{nom} (projeté)"))


def ecrire_atomique(chemin: Path, octets: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(Path(chemin).parent), prefix=".cockpit-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(octets)
        os.replace(tmp, chemin)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def ecrire(chemin: Path, corps: str, *, forcer: bool, sauvegardes: Path, maintenant=None) -> dict:
    """Écrit avec_entete(corps). Refuse sur « modifie » et « sans_entete », sauf `forcer`, qui
    sauvegarde d'abord l'ancien fichier, octet pour octet. Conserve le CRLF du fichier en place."""
    chemin = Path(chemin)
    octets = chemin.read_bytes() if chemin.is_file() else None
    actuel = octets.decode("utf-8-sig") if octets is not None else None
    e = etat(actuel, corps)
    if e == "a_jour":
        return {"etat": e, "ecrit": False, "sauvegarde": None}
    if e not in ECRITURE_SANS_FORCER and not forcer:
        raise DeriveRefusee(e)
    sauvegarde = None
    if e in ("modifie", "sans_entete"):
        Path(sauvegardes).mkdir(parents=True, exist_ok=True)
        sauvegarde = Path(sauvegardes) / f"cv.{(maintenant or datetime.now()).strftime('%Y%m%dT%H%M%S')}.md"
        sauvegarde.write_bytes(octets)
    texte = avec_entete(corps)
    if octets is not None and b"\r\n" in octets:
        texte = texte.replace("\n", "\r\n")
    ecrire_atomique(chemin, texte.encode("utf-8"))
    return {"etat": e, "ecrit": True, "sauvegarde": str(sauvegarde) if sauvegarde else None}
