"""Adaptateur career-ops : le cockpit LANCE les outils de career-ops (liste blanche
fermée, arguments en liste, une action à la fois, délai borné) ; il ne lit pas ses
fichiers de données autrement que par leurs outils, et n'en écrit aucun (spec § 5)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from tools.cockpit import config

NODE_MIN = (22, 5)  # tracker.mjs exige node:sqlite


@dataclass(frozen=True)
class Commande:
    id: str
    args: tuple[str, ...]          # après `node`
    ecrit: str                     # ce que LE SCRIPT écrit (montré avant confirmation)
    confirmation: bool
    delai_s: int
    codes: dict = field(default_factory=dict)   # sens déclaré des codes de sortie
    sortie: str = "texte"          # "json" → stdout parsé dans res["json"]


# Pas de `watch --dry-run` (amendement 2026-10-03) : il sonde toutes les annonces puis jette
# les verdicts, alors que data/liveness-log.tsv nourrit le taux de disparition de send-queue et kpi.
COMMANDES: dict[str, Commande] = {
    "kpi": Commande("kpi", ("kpi.mjs", "--json"), "rien", False, 30,
                    {0: "fait", 2: "argument invalide", 3: "données illisibles (racine ou tracker)"}, "json"),
    "watch": Commande("watch", ("watch.mjs",),
                      "data/agent-inbox.md (constats dédupliqués), data/liveness-log.tsv (verdicts, ajout seul)", False, 300,
                      {0: "fait, constats écrits dans l'inbox",
                       1: "tracker absent ou vide, ou un constat n'a pas pu être écrit"}, "json"),
    "scan": Commande("scan", ("scan.mjs", "--quiet"), "data/pipeline.md, data/scan-runs.tsv", True, 600,
                     {0: "fait", 1: "erreur", 130: "interrompu"}, "texte"),
    "sante": Commande("sante", ("verify-pipeline.mjs",), "rien (crée data/ et reports/ s'ils manquent)", False, 60,
                      {0: "cohérent", 1: "incohérences trouvées — pas un plantage"}, "texte"),
    "pistes": Commande("pistes", ("track-core.mjs", "--check"), "rien", False, 30,
                       {0: "configuration des pistes cohérente", 1: "erreurs de configuration des pistes",
                        2: "usage", 3: "config/profile.yml introuvable"}, "texte"),
}


class ActionEnCours(RuntimeError):
    """Une autre action tient le verrou ; le message est son nom."""


_verrou = threading.Lock()
_action_courante: str | None = None


class verrou_action:
    def __init__(self, nom: str):
        self.nom = nom

    def __enter__(self):
        global _action_courante
        if not _verrou.acquire(blocking=False):
            raise ActionEnCours(_action_courante or "?")
        _action_courante = self.nom
        return self

    def __exit__(self, *exc):
        global _action_courante
        _action_courante = None
        _verrou.release()


def node_exe() -> str | None:
    return shutil.which("node")


def node_version(exe: str, runner=subprocess.run) -> tuple[int, ...] | None:
    try:
        out = runner([exe, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.match(r"v(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(x) for x in m.groups()) if m else None


def prerequis(env=None, runner=subprocess.run) -> dict:
    """Chaque manque est nommé avec son remède (spec § 8) — jamais un entonnoir vide."""
    root = config.career_ops_root(env=env)
    problemes = []
    if root is None:
        problemes.append("career-ops non configuré : poser CAREER_OPS_ROOT, ou écrire tools/cockpit/local.json "
                         '({"career_ops_root": "<dossier contenant tracker.mjs>"})')
    exe = node_exe()
    version = node_version(exe, runner) if exe else None
    if exe is None:
        problemes.append("node introuvable dans le PATH")
    elif version is None:
        problemes.append(f"`node --version` illisible ({exe})")
    elif version[:2] < NODE_MIN:
        problemes.append(f"node {'.'.join(map(str, version))} < {NODE_MIN[0]}.{NODE_MIN[1]} (tracker.mjs exige node:sqlite)")
    return {"ok": not problemes, "career_ops_root": str(root) if root else None, "node": exe,
            "node_version": ".".join(map(str, version)) if version else None, "problemes": problemes}


def _tuer_arbre(proc) -> None:
    """Au délai, tuer TOUT l'arbre (scan lance chromium) : proc.kill() ne tuerait que node."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def lancer(argv: list[str], root: Path, delai_s: int, *, popen=subprocess.Popen, tuer=_tuer_arbre) -> dict:
    """`node <argv>` dans root, sans shell, délai borné. Ne lève pas : l'échec est décrit."""
    exe = node_exe()
    if exe is None:
        return {"code": None, "stdout": "", "stderr": "node introuvable", "duree_s": 0.0, "interrompu": False}
    t0 = time.monotonic()
    proc = popen([exe, *argv], cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                 stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    try:
        out, err = proc.communicate(timeout=delai_s)
        interrompu = False
    except subprocess.TimeoutExpired:
        tuer(proc)
        out, err = proc.communicate()
        interrompu = True
    return {"code": None if interrompu else proc.returncode, "stdout": out or "", "stderr": err or "",
            "duree_s": round(time.monotonic() - t0, 1), "interrompu": interrompu}


def _json_sortie(stdout: str):
    """set-status imprime son succès en JSON multi-ligne et ses erreurs sur une ligne :
    tout le stdout d'abord, la dernière ligne ensuite, sinon None."""
    texte = (stdout or "").strip()
    if not texte:
        return None
    for cand in (texte, texte.splitlines()[-1]):
        try:
            return json.loads(cand)
        except ValueError:
            continue
    return None


def executer(cmd_id: str, *, confirme: bool = False, root: Path | None = None,
             popen=subprocess.Popen, tuer=_tuer_arbre) -> dict:
    """Une commande de la liste blanche. Inconnue → ValueError ; verrou pris → ActionEnCours."""
    cmd = COMMANDES.get(cmd_id)
    if cmd is None:
        raise ValueError(f"commande inconnue : {cmd_id!r}")
    if cmd.confirmation and not confirme:
        raise ValueError(f"{cmd.id} exige une confirmation (écrit : {cmd.ecrit})")
    root = root or config.career_ops_root()
    if root is None:
        raise RuntimeError("career-ops non configuré")
    with verrou_action(cmd.id):
        res = lancer(list(cmd.args), root, cmd.delai_s, popen=popen, tuer=tuer)
    res.update(id=cmd.id, argv=["node", *cmd.args], ecrit=cmd.ecrit,
               sens=f"interrompu après {cmd.delai_s} s" if res["interrompu"]
               else cmd.codes.get(res["code"], f"code {res['code']} non déclaré"))
    res["json"] = _json_sortie(res["stdout"]) if cmd.sortie == "json" and not res["interrompu"] else None
    return res


def _hhmm() -> str:
    return time.strftime("%H:%M")


def _lire_json(argv: list[str], root: Path, *, popen=subprocess.Popen, delai_s: int = 30) -> dict:
    """Lecture (pas de verrou : elle n'écrit rien). {ok, donnees, erreur, lu_a}."""
    res = lancer(argv, root, delai_s, popen=popen)
    if res["interrompu"] or res["code"] != 0:
        cause = "interrompu" if res["interrompu"] else f"code {res['code']}"
        return {"ok": False, "donnees": None, "lu_a": _hhmm(),
                "erreur": f"node {' '.join(argv)} → {cause} : {res['stderr'].strip()[-400:] or res['stdout'].strip()[-400:]}"}
    donnees = _json_sortie(res["stdout"])
    if donnees is None:
        return {"ok": False, "donnees": None, "lu_a": _hhmm(), "erreur": f"node {' '.join(argv)} : sortie non JSON"}
    return {"ok": True, "donnees": donnees, "lu_a": _hhmm(), "erreur": None}


def lire_tracker(root: Path, *, popen=subprocess.Popen) -> dict:
    return _lire_json(["tracker.mjs", "query", "--json"], root, popen=popen)


def lire_kpi(root: Path, *, popen=subprocess.Popen) -> dict:
    return _lire_json(["kpi.mjs", "--json"], root, popen=popen)


def lire_relances(root: Path, *, popen=subprocess.Popen) -> dict:
    return _lire_json(["followup-cadence.mjs", "--json", "--overdue-only"], root, popen=popen)


def lire_file(root: Path, *, popen=subprocess.Popen) -> dict:
    """La file d'envoi telle que send-queue la calcule (priorité, pistes, disparues) — en
    direct, plutôt qu'ENVOI.md, qui n'est qu'une sortie de `--write` et peut dater."""
    return _lire_json(["send-queue.mjs", "--json"], root, popen=popen)


def lire_texte(root: Path, rel: str) -> dict:
    p = root / rel
    try:
        return {"ok": True, "texte": p.read_text(encoding="utf-8", errors="replace"),
                "age_h": round((time.time() - p.stat().st_mtime) / 3600, 1), "erreur": None}
    except OSError as exc:
        return {"ok": False, "texte": "", "age_h": None, "erreur": f"{rel} : {type(exc).__name__}"}


def lire_dossiers(root: Path) -> list[dict]:
    """output/<entreprise>/<n>-<rôle>/vNNN/ → dernière version de chaque dossier."""
    out = root / "output"
    res = []
    if not out.is_dir():
        return res
    for ent in sorted(p for p in out.iterdir() if p.is_dir()):
        for d in sorted(p for p in ent.iterdir() if p.is_dir()):
            versions = sorted((v for v in d.iterdir() if v.is_dir() and v.name.startswith("v")), key=lambda v: v.name)
            if versions:
                v = versions[-1]
                res.append({"entreprise": ent.name, "dossier": d.name, "version": v.name,
                            "fichiers": sorted(f.name for f in v.iterdir() if f.is_file()), "chemin": str(v)})
    return res


_NUM_RAPPORT = re.compile(r"^\[(\d+)\]")


def numero_rapport(ligne: dict) -> int | None:
    m = _NUM_RAPPORT.match(str(ligne.get("report", "")))
    return int(m.group(1)) if m else None


def score(ligne: dict) -> float | None:
    m = re.match(r"^\s*(\d+(?:\.\d+)?)/5", str(ligne.get("score", "")))
    return float(m.group(1)) if m else None


def a_faire(lignes: list[dict], seuil: float = 4.0) -> list[dict]:
    """Repli quand send-queue ne répond pas : Evaluated au-dessus du seuil, meilleure note d'abord."""
    cand = [l for l in lignes if str(l.get("status", "")).lower() == "evaluated" and (score(l) or 0.0) >= seuil]
    return sorted(cand, key=lambda l: -(score(l) or 0.0))


def file_a_envoyer(file_json: dict) -> list[dict]:
    """Les dossiers prêts dans l'ordre de send-queue (perTrack[].items), chacun avec le nom de
    sa piste. Jamais retrié : la priorité (valeur × perte hebdomadaire ÷ effort) est celle de la file."""
    res = []
    for p in file_json.get("perTrack") or []:
        piste = p.get("track") or {}
        for item in p.get("items") or []:
            res.append({**item, "piste": piste.get("label") or piste.get("id") or "?"})
    return res


def numero_item(item: dict) -> int | None:
    """`num` de send-queue = numéro de rapport complété de zéros ("024")."""
    num = str(item.get("num", ""))
    return int(num) if num.isdigit() else None


NOTE_MAX = 200
CODES_POSTULE = {0: "enregistré", 1: "usage ou état invalide", 2: "rapport introuvable",
                 3: "ambigu (numéro de ligne ≠ numéro de rapport, ou rôle)", 4: "verrou du tracker occupé"}


def argv_postule(n, note: str, lignes: list[dict]) -> list[str]:
    """n ∈ numéros de rapport du tracker (entier strict, jamais bool/str), note bornée sur une ligne."""
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise ValueError("numéro de rapport invalide")
    if n not in {numero_rapport(l) for l in lignes}:
        raise ValueError(f"le rapport {n} n'est pas dans le tracker")
    note = (note or "").strip()
    if len(note) > NOTE_MAX or "\n" in note or "\r" in note:
        raise ValueError(f"note : {NOTE_MAX} caractères max, sur une ligne")
    argv = ["set-status.mjs", "--report", str(n), "Applied", "--json"]
    if note:
        argv += ["--note", note]
    return argv


def postule(n, note: str, *, root: Path | None = None, popen=subprocess.Popen, tuer=_tuer_arbre) -> dict:
    """Le seul bouton qui fait bouger « Passage à la candidature ». Écrit PAR set-status :
    data/applications.md, data/status-log.tsv, data/follow-ups.md (mesuré 2026-09-29)."""
    root = root or config.career_ops_root()
    if root is None:
        raise RuntimeError("career-ops non configuré")
    lu = lire_tracker(root, popen=popen)
    if not lu["ok"]:
        raise RuntimeError(lu["erreur"])
    argv = argv_postule(n, note, lu["donnees"])
    with verrou_action("postule"):
        res = lancer(argv, root, 30, popen=popen, tuer=tuer)
    res.update(id="postule", argv=["node", *argv],
               ecrit="data/applications.md, data/status-log.tsv, data/follow-ups.md",
               sens="interrompu" if res["interrompu"] else CODES_POSTULE.get(res["code"], f"code {res['code']} non déclaré"))
    res["json"] = _json_sortie(res["stdout"])
    return res
