"""D8 : projette profile.json + complément privé vers cv.md et config/profile.yml de career-ops.

`projeter()` ne lève pas : chaque cible a son statut, chaque refus sa cause (spec D8 § 9).
CLI (racine du site) :
  python -m tools.cockpit.projection --rapport           diff seulement, n'écrit rien (import, § 4)
  python -m tools.cockpit.projection --ecrire            projette ; refuse un cv.md modifié à la main
  python -m tools.cockpit.projection --ecrire --forcer   remplace après sauvegarde dans data/cv-sauvegardes"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from tools.cockpit import complement as comp_mod
from tools import validate_profile
from tools.cockpit import config, cv_md, derive, profile_yml

PROFILE = config.SITE_ROOT / "profile.json"
MOTIFS = {
    "modifie": "cv.md a été modifié à la main depuis la dernière projection : lire le diff, reporter "
               "ce qui doit l'être dans profile.json, ou remplacer quand même (l'ancien est sauvegardé)",
    "sans_entete": "cv.md n'a jamais été généré par le cockpit : valider le rapport d'import "
                   "(spec D8 § 4), puis remplacer quand même (l'ancien est sauvegardé)",
}


def _cause(exc: Exception) -> str:
    return f"pas en UTF-8 ({exc})" if isinstance(exc, UnicodeDecodeError) else str(exc)


def projeter(*, ecrire: bool, forcer: bool = False, root: Path | None = None, profile_path: Path = PROFILE,
             aujourdhui: date | None = None, ignore_fn=None) -> dict:
    res = {"ok": False, "erreurs": [], "cv_md": None, "profile_yml": None}
    if root is None:
        root, raison = config.resoudre_career_ops()
        if root is None:
            res["erreurs"].append(f"career-ops non configuré : {raison}")
            return res
    root = Path(root)
    try:
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        res["erreurs"].append(f"profile.json illisible : {exc}")
        return res
    invalide = validate_profile.validate(profile) if isinstance(profile, dict) else ["racine : objet attendu"]
    if invalide:      # sans `root` : pas de contrôle disque des liens, la forme seulement
        res["erreurs"].append("profile.json invalide : " + "; ".join(invalide[:5]))
        return res
    try:
        comp = comp_mod.charger(root, ignore_fn=ignore_fn)
    except (comp_mod.ComplementAbsent, comp_mod.ComplementInvalide) as exc:
        res["erreurs"].append(f"complément privé : {exc}")
        return res

    try:
        corps = cv_md.rendre(profile, comp)
    except (KeyError, TypeError, AttributeError, IndexError, ValueError) as exc:
        res["erreurs"].append(f"profile.json ne se rend pas en cv.md : {type(exc).__name__}: {exc}")
        return res

    cv_path = root / "cv.md"
    try:
        actuel = derive.lire(cv_path)
    except (OSError, ValueError) as exc:
        cv = {"etat": "illisible", "diff": "", "ecrit": False, "sauvegarde": None,
              "erreur": f"cv.md illisible : {_cause(exc)}"}
        res["cv_md"] = cv
    else:
        cv = {"etat": derive.etat(actuel, corps), "diff": derive.diff(actuel, corps),
              "ecrit": False, "sauvegarde": None, "erreur": None}
        if ecrire:
            try:
                cv.update(derive.ecrire(cv_path, corps, forcer=forcer, sauvegardes=root / "data" / "cv-sauvegardes"))
            except derive.DeriveRefusee as exc:
                cv["erreur"] = MOTIFS.get(exc.args[0], f"écriture refusée ({exc.args[0]})")
            except OSError as exc:
                cv["erreur"] = f"écriture de cv.md impossible : {exc}"
        res["cv_md"] = cv

    yml = {"changements": [], "ecrit": False, "erreur": None}
    yml_path = root / "config" / "profile.yml"
    try:
        texte = derive.lire(yml_path)
        if texte is None:
            raise FileNotFoundError(str(yml_path))
        nouveau, yml["changements"] = profile_yml.projeter(
            texte, profile_yml.valeurs(profile, comp, aujourdhui or date.today()))
        if ecrire and yml["changements"]:
            derive.ecrire_atomique(yml_path, nouveau.encode("utf-8"))
            yml["ecrit"] = True
    except FileNotFoundError:
        yml["erreur"] = f"{yml_path} absent"
    except profile_yml.CleIntrouvable as exc:
        yml["erreur"] = f"clé introuvable dans profile.yml : {exc.args[0]}"
    except UnicodeDecodeError as exc:
        yml["erreur"] = f"profile.yml illisible : {_cause(exc)}"
    except OSError as exc:
        yml["erreur"] = f"profile.yml inaccessible : {exc}"
    res["profile_yml"] = yml
    res["ok"] = cv["erreur"] is None and yml["erreur"] is None
    return res


def etape_sauvegarde() -> dict:
    """Étape `career_ops` de la sauvegarde gouvernée de /cms : jamais d'exception (profile.json
    est déjà écrit), jamais d'écrasement (forcer=False). Le refus s'affiche à côté du succès."""
    try:
        r = projeter(ecrire=True)
    except Exception as exc:  # noqa: BLE001 — rapporté à l'écran, jamais avalé
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
    if r["erreurs"]:
        saute = r["erreurs"][0].startswith("career-ops non configuré")
        return {"ok": None if saute else False, "saute": saute, "message": r["erreurs"][0]}
    cv, yml = r["cv_md"], r["profile_yml"]
    msgs = [m for m in (cv["erreur"], yml["erreur"]) if m]
    return {"ok": not msgs, "etat": cv["etat"], "ecrit": cv["ecrit"], "yml": yml["changements"],
            "message": " ; ".join(msgs)}


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):      # console Windows en cp1252 : le diff porte des accents
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):   # flux remplacé (tests, redirection) : il garde son encodage
            pass
    ap = argparse.ArgumentParser(prog="python -m tools.cockpit.projection",
                                 description="D8 : profile.json → cv.md et profile.yml de career-ops")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rapport", action="store_true", help="diff seulement, n'écrit rien (import, spec § 4)")
    g.add_argument("--ecrire", action="store_true", help="projette ; refuse un cv.md modifié à la main")
    ap.add_argument("--forcer", action="store_true", help="avec --ecrire : remplace après sauvegarde")
    a = ap.parse_args(argv)
    if a.forcer and not a.ecrire:
        ap.error("--forcer exige --ecrire")
    r = projeter(ecrire=a.ecrire, forcer=a.forcer)
    for e in r["erreurs"]:
        print(f"REFUS : {e}", file=sys.stderr)
    cv = r["cv_md"]
    if cv:
        print(f"cv.md : {cv['etat']}" + (" — écrit" if cv["ecrit"] else "")
              + (f" — sauvegarde {cv['sauvegarde']}" if cv["sauvegarde"] else ""))
        if cv["erreur"]:
            print(f"REFUS : {cv['erreur']}", file=sys.stderr)
        if a.rapport and cv["diff"]:
            print(cv["diff"])
    y = r["profile_yml"]
    if y:
        print("profile.yml : " + (", ".join(y["changements"]) or "rien à changer") + (" — écrit" if y["ecrit"] else ""))
        if y["erreur"]:
            print(f"REFUS : {y['erreur']}", file=sys.stderr)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
