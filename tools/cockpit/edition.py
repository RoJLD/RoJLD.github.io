"""Écrire une source depuis la page (édition du site, A1, spec § 3.4).

`textes:<clé>`     → site_texts.json, puis reconstruction du site ;
`profile:<chemin>` → profile.json par la sauvegarde gouvernée du cockpit (validation,
                     historique, reconstruction, banque préfabriquée, projection D8).
Le chemin porte `{lang}` à la place du segment de langue ; la langue vient de la page.
Jamais le HTML généré : le build suivant l'écraserait."""
from __future__ import annotations

import json
from pathlib import Path

from tools.cockpit import derive

LANGS = ("fr", "en")
LONGUEUR_MAX = 5000


class SourceRefusee(ValueError):
    """La modification est refusée ; le message dit pourquoi."""


def texte_sain(valeur) -> str:
    if not isinstance(valeur, str):
        raise SourceRefusee("texte attendu")
    propre = " ".join(valeur.split())
    if not propre:
        raise SourceRefusee("texte vide : rien n'est enregistré")
    if len(propre) > LONGUEUR_MAX:
        raise SourceRefusee(f"texte trop long ({len(propre)} > {LONGUEUR_MAX} caractères)")
    return propre


def _segments(chemin: str, lang: str) -> list:
    morceaux = chemin.split(".")
    if "{lang}" not in morceaux:
        raise SourceRefusee(f"chemin sans segment de langue {{lang}} : {chemin!r}")
    return [lang if m == "{lang}" else (int(m) if m.isdigit() else m) for m in morceaux]


def _ecrire_json(chemin, donnees) -> None:
    octets = (json.dumps(donnees, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    derive.ecrire_atomique(Path(chemin), octets)


def _reconstruire_garde(reconstruire, resultat: dict) -> dict:
    """La source est déjà écrite : un échec du build ne la reprend pas et ne devient pas un
    « Refusé ». Il est rapporté comme étape en échec (le calque l'affiche après rechargement,
    spec § 6 « la source modifiée est gardée ») ; SystemExit compris (gates du build)."""
    try:
        reconstruire()
    except (Exception, SystemExit) as exc:  # noqa: BLE001 — rapporté dans le résultat, jamais avalé
        etape = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        resultat["rapport"] = {"ok": True, "stages": {"rebuild": etape}}
    return resultat


def ecrire_source(source, lang, valeur, *, textes_path, profile_path, reconstruire, sauvegarde) -> dict:
    """Une valeur égale à la source reconstruit quand même : le calque n'envoie jamais un texte
    inchangé, le serveur ne le voit donc que sur une page périmée — quand le build est dû."""
    if lang not in LANGS:
        raise SourceRefusee(f"langue inconnue : {lang!r}")
    texte = texte_sain(valeur)
    genre, _, cle = str(source).partition(":")
    if genre == "textes":
        textes = json.loads(Path(textes_path).read_text(encoding="utf-8"))
        if cle not in textes.get(lang, {}):
            raise SourceRefusee(f"texte fixe inconnu : {cle!r}")
        if textes[lang][cle] == texte:
            return _reconstruire_garde(reconstruire, {"ok": True, "inchange": True})
        textes[lang][cle] = texte
        _ecrire_json(textes_path, textes)
        return _reconstruire_garde(reconstruire, {"ok": True})
    if genre == "profile":
        segments = _segments(cle, lang)
        profil = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        try:
            parent = profil
            for s in segments[:-1]:
                parent = parent[s]
            actuel = parent[segments[-1]]
        except (KeyError, IndexError, TypeError):
            raise SourceRefusee(f"chemin introuvable dans profile.json : {cle!r}") from None
        if not isinstance(actuel, str):
            raise SourceRefusee(f"{cle!r} n'est pas un texte dans profile.json")
        if actuel == texte:
            return _reconstruire_garde(reconstruire, {"ok": True, "inchange": True})
        parent[segments[-1]] = texte
        rapport = sauvegarde(json.dumps(profil, ensure_ascii=False, indent=2))
        return {"ok": bool(rapport.get("ok")), "rapport": rapport}
    raise SourceRefusee(f"source inconnue : {source!r}")
