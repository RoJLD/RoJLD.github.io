"""Interface web de career-ops (Next.js, amont 0.10) lancée à la demande, en loopback,
avec CAREER_OPS_ROOT. Elle lance `claude -p` avec Bash : sans garde d'origine ou hors
loopback, c'est une exécution de code à distance (spec § 10).

Le lancement passe par `web-local.mjs`, le lanceur de career-ops qui démarre le binaire
de Next avec `-H <loopback>` sans npm entre les deux : un seul lanceur, une seule règle."""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tools.cockpit import config

PORT_WEB = 3000
HOTE_WEB = "127.0.0.1"
URL_WEB = f"http://{HOTE_WEB}:{PORT_WEB}/"


def port_ouvert(port: int, host: str = HOTE_WEB, timeout: float = 0.5) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def node_exe() -> str | None:
    return shutil.which("node")


def est_career_ops_web(opener=urllib.request.urlopen) -> bool:
    """Le port répond : est-ce bien career-ops ? Son /api/version rend un JSON avec `version`."""
    try:
        with opener(URL_WEB + "api/version", timeout=2) as r:
            return isinstance(json.loads(r.read().decode("utf-8", "replace")).get("version"), str)
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return False


LOOPBACK = {"127.0.0.1", "::1"}


def adresses_ecoute(port: int, run=subprocess.run) -> set[str]:
    """Adresses locales sur lesquelles `port` est en écoute (Windows : Get-NetTCPConnection).
    Vide si la mesure échoue ou hors Windows — l'appelant traite « inconnu » comme « pas loopback » :
    le garde d'origine de la 0.10 ne protège pas du réseau (en-tête Host forgé), seul le bind le fait."""
    if sys.platform != "win32":
        return set()
    try:
        cp = run(["powershell", "-NoProfile", "-Command",
                  f"(Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue).LocalAddress"],
                 capture_output=True, text=True, timeout=10, **config.SANS_CONSOLE)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {ligne.strip() for ligne in (cp.stdout or "").splitlines() if ligne.strip()}


def etat_web(root: Path, *, port_ouvert_fn=port_ouvert, opener=urllib.request.urlopen,
             adresses_ecoute_fn=adresses_ecoute) -> dict:
    problemes = []
    if not (root / "web" / "src" / "proxy.ts").is_file() or not (root / "web" / "src" / "lib" / "origin-guard.mjs").is_file():
        problemes.append("web/ sans garde d'origine (proxy.ts, origin-guard.mjs) : resynchroniser sur l'amont 0.10 (plan L0)")
    if not (root / "web" / "node_modules").is_dir():
        problemes.append("web/node_modules absent : lancer `npm ci` dans web/")
    if not (root / "web-local.mjs").is_file():
        problemes.append("web-local.mjs absent de career-ops : c'est le lanceur loopback, jamais un `npm run dev` nu")
    if node_exe() is None:
        problemes.append("node introuvable dans le PATH")
    ouvert = port_ouvert_fn(PORT_WEB)
    autre = ouvert and not est_career_ops_web(opener)
    adresses = adresses_ecoute_fn(PORT_WEB) if ouvert else set()
    hors_loopback = ouvert and (not adresses or not adresses <= LOOPBACK)   # inconnu ou 0.0.0.0 : refus
    return {"pret": not problemes, "problemes": problemes, "port_ouvert": ouvert,
            "occupe_par_autre_chose": autre, "hors_loopback": hors_loopback, "url": URL_WEB}


def ouvrir_web(root: Path, *, popen=subprocess.Popen, port_ouvert_fn=port_ouvert,
               opener=urllib.request.urlopen, adresses_ecoute_fn=adresses_ecoute,
               attente_s: int = 30, sleep=time.sleep) -> dict:
    e = etat_web(root, port_ouvert_fn=port_ouvert_fn, opener=opener, adresses_ecoute_fn=adresses_ecoute_fn)
    if e["occupe_par_autre_chose"]:
        return {"ok": False, "deja": False, "url": URL_WEB,
                "problemes": [f"le port {PORT_WEB} est occupé par autre chose que career-ops : libérer le port"]}
    if e["hors_loopback"]:
        return {"ok": False, "deja": False, "url": URL_WEB,
                "problemes": [f"une instance écoute sur {PORT_WEB} hors loopback (adresses : "
                              f"{', '.join(sorted(adresses_ecoute_fn(PORT_WEB))) or 'inconnues'}) : /api/run serait joignable du réseau — "
                              "l'arrêter, le cockpit la relancera liée à 127.0.0.1"]}
    if e["port_ouvert"]:
        return {"ok": True, "deja": True, "url": URL_WEB, "problemes": []}
    if not e["pret"]:
        return {"ok": False, "deja": False, "url": URL_WEB, "problemes": e["problemes"]}
    env = {**os.environ, "CAREER_OPS_ROOT": str(root)}
    extra = {"creationflags": subprocess.CREATE_NEW_CONSOLE} if sys.platform == "win32" else {}
    popen([node_exe(), "web-local.mjs", "--host", HOTE_WEB, "--port", str(PORT_WEB)], cwd=str(root), env=env, **extra)
    for _ in range(int(attente_s * 2)):
        if port_ouvert_fn(PORT_WEB):
            return {"ok": True, "deja": False, "url": URL_WEB, "problemes": []}
        sleep(0.5)
    return {"ok": False, "deja": False, "url": URL_WEB,
            "problemes": [f"l'interface ne répond pas sur {PORT_WEB} après {attente_s} s (fenêtre web-local ouverte : lire son erreur)"]}
