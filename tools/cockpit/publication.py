"""Publier le site depuis le cockpit (édition du site, A1, spec § 5).

État (fichiers modifiés, branche, avance et retard sur origin/main), vérifications, commit des
SEULS fichiers du périmètre du site, push sur origin/main, suivi de GitHub Pages. Aucun
forçage : chaque refus nomme sa cause, et un push refusé laisse le commit local, que le
prochain « Publier » pousse."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.cockpit import config

# Ce que le cockpit écrit ou régénère : sources, sorties des générateurs, banque préfabriquée.
PERIMETRE = ("profile.json", "site_texts.json", "academy.json", "index.html", "articles/", "projects/",
             "demos/", "explorer/", "highlights/", "academy/", "graph/", "cv/prefab/",
             "assets/js/cv-templates.js", "data/profile_graph.json")
SOURCES = ("profile.json", "site_texts.json", "academy.json")
DEPOT_PAGES = "RoJLD/RoJLD.github.io"
URL_SITE = "https://robin-denis.com/"
MARQUES_CALQUE = ('data-src="profile:', 'data-src="textes:', "/__cockpit/")


def _git(racine, *args, run=subprocess.run, timeout=60):
    return run(["git", "-C", str(racine), *args], capture_output=True, text=True, encoding="utf-8",
               errors="replace", timeout=timeout, **config.SANS_CONSOLE)


def dans_perimetre(chemin: str) -> bool:
    return any(chemin == p or (p.endswith("/") and chemin.startswith(p)) for p in PERIMETRE)


def _porcelaine(sortie: str) -> list:
    """`git status --porcelain=v1 -z` → [{chemin, statut}] ; un renommage compte sa cible."""
    jetons, fichiers, i = sortie.split("\0"), [], 0
    while i < len(jetons):
        jeton = jetons[i]
        i += 1
        if len(jeton) < 4:
            continue
        statut, chemin = jeton[:2], jeton[3:]
        if statut[0] in "RC":
            i += 1
        fichiers.append({"chemin": chemin, "statut": statut.strip() or statut})
    return fichiers


def etat(racine, *, run=subprocess.run) -> dict:
    branche = _git(racine, "branch", "--show-current", run=run).stdout.strip()
    fetch_ok = _git(racine, "fetch", "-q", "origin", run=run, timeout=120).returncode == 0
    compte = _git(racine, "rev-list", "--left-right", "--count", "HEAD...origin/main", run=run).stdout.split()
    avance, retard = (int(compte[0]), int(compte[1])) if len(compte) == 2 else (None, None)
    fichiers = _porcelaine(_git(racine, "status", "--porcelain=v1", "-z", "--untracked-files=all", run=run).stdout)
    return {"branche": branche, "fetch_ok": fetch_ok, "en_avance": avance, "en_retard": retard,
            "fichiers": fichiers, "hors_perimetre": [f["chemin"] for f in fichiers if not dans_perimetre(f["chemin"])]}


def refus(e: dict) -> list:
    motifs = []
    if e["branche"] != "main":
        motifs.append(f"le checkout n'est pas sur main (branche {e['branche'] or 'détachée'})")
    if not e["fetch_ok"]:
        motifs.append("origin injoignable (git fetch a échoué) : publier exige de comparer à origin/main")
    if e["en_avance"] is None:
        motifs.append("comparaison avec origin/main impossible")
    elif e["en_avance"] and e["en_retard"]:
        motifs.append(f"main locale a divergé de origin/main ({e['en_avance']} commit(s) local(aux), "
                      f"{e['en_retard']} distant(s)) : à réconcilier à la main")
    if e["hors_perimetre"]:
        motifs.append("modifications hors du périmètre du site, à committer ou annuler à la main : "
                      + ", ".join(e["hors_perimetre"][:10]))
    if not e["fichiers"] and not e["en_avance"]:
        motifs.append("rien à publier")
    return motifs


def diffs_sources(racine, e: dict, *, run=subprocess.run) -> dict:
    out = {}
    for f in e["fichiers"]:
        c = f["chemin"]
        if c in SOURCES or (c.startswith("articles/src/") and c.endswith(".md")):
            out[c] = "(nouveau fichier)" if f["statut"] == "??" else _git(racine, "diff", "--", c, run=run).stdout
    return out


def message_auto(e: dict) -> str:
    chemins = {f["chemin"] for f in e["fichiers"]}
    parts = []
    if "profile.json" in chemins:
        parts.append("profil")
    if "site_texts.json" in chemins:
        parts.append("textes de l'accueil")
    if any(c.startswith("articles/") for c in chemins):
        parts.append("articles")
    return "content(site): " + (", ".join(parts) or "pages régénérées") + " — publié depuis le cockpit"


def _pages_avec_calque(racine) -> list:
    fautives = []
    for p in Path(racine).rglob("*.html"):
        rel = p.relative_to(racine).as_posix()
        if dans_perimetre(rel) and any(m in p.read_text(encoding="utf-8", errors="replace") for m in MARQUES_CALQUE):
            fautives.append(rel)
    return fautives


def verifier(racine, *, run=subprocess.run) -> list:
    py = sys.executable

    def commande(nom, argv):
        cp = run(argv, cwd=str(racine), capture_output=True, text=True, encoding="utf-8", errors="replace",
                 timeout=600, **config.SANS_CONSOLE)
        ok = cp.returncode == 0
        return {"nom": nom, "ok": ok, "detail": "" if ok else ((cp.stdout or "") + (cp.stderr or ""))[-1500:]}

    resultats = [
        commande("profil valide (validate_profile)", [py, "tools/validate_profile.py", "profile.json"]),
        commande("construction complète du site", [py, "tools/build_site.py"]),
        commande("liens internes", [py, "-m", "pytest", "tools/tests/test_liens_internes.py", "-q", "-p", "no:cacheprovider"]),
        commande("gardes de confidentialité", [
            py, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "tools/tests/test_validate_profile.py::test_le_telephone_ne_va_jamais_dans_profile_json",
            "tools/tests/test_validate_profile.py::test_aucun_fichier_suivi_du_site_ne_nomme_un_poste_cv_seulement",
            "tools/tests/test_cockpit_public_isole.py"]),
    ]
    fautives = _pages_avec_calque(racine)
    resultats.append({"nom": "pages publiées sans calque", "ok": not fautives, "detail": ", ".join(fautives[:10])})
    return resultats


def publier(racine, message: str, *, run=subprocess.run) -> dict:
    e = etat(racine, run=run)
    motifs = refus(e)
    if motifs:
        return {"ok": False, "refus": motifs}
    if e["en_retard"]:
        ff = _git(racine, "merge", "--ff-only", "origin/main", run=run)
        if ff.returncode != 0:
            return {"ok": False, "refus": ["main locale en retard sur origin/main et l'avance rapide échoue : "
                                           + ff.stderr.strip()[-300:]]}
    chemins = [f["chemin"] for f in e["fichiers"]]
    if chemins:
        ajout = _git(racine, "add", "-A", "--", *chemins, run=run)
        if ajout.returncode != 0:
            return {"ok": False, "etape": "add", "erreur": ajout.stderr.strip()[-500:]}
        texte = (message or "").strip() or message_auto(e)
        cm = _git(racine, "commit", "-q", "-m", texte, run=run)
        if cm.returncode != 0:
            return {"ok": False, "etape": "commit", "erreur": ((cm.stdout or "") + (cm.stderr or "")).strip()[-500:]}
    sha = _git(racine, "rev-parse", "HEAD", run=run).stdout.strip()
    pousse = _git(racine, "push", "origin", "HEAD:main", run=run, timeout=180)
    if pousse.returncode != 0:
        return {"ok": False, "etape": "push", "commit": sha, "commit_local": True, "erreur": pousse.stderr.strip()[-500:]}
    return {"ok": True, "commit": sha}


def suivi_pages(sha: str, *, run=subprocess.run) -> dict:
    try:
        cp = run(["gh", "api", f"repos/{DEPOT_PAGES}/pages/builds/latest"], capture_output=True, text=True,
                 encoding="utf-8", errors="replace", timeout=30, **config.SANS_CONSOLE)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"statut": "inconnu", "erreur": f"gh indisponible : {exc}"}
    if cp.returncode != 0:
        return {"statut": "inconnu", "erreur": cp.stderr.strip()[-300:]}
    try:
        build = json.loads(cp.stdout)
    except ValueError:
        return {"statut": "inconnu", "erreur": "réponse de gh illisible"}
    if build.get("commit") != sha:
        return {"statut": "en attente", "commit": build.get("commit"), "url": URL_SITE}
    return {"statut": build.get("status", "inconnu"), "commit": sha, "url": URL_SITE,
            "erreur": (build.get("error") or {}).get("message")}
