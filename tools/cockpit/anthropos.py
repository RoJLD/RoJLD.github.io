"""Backend Anthropos vu du poste : liste des apps lue sur le hub (GET /api/apps — la
copie de satellite_manifest.json embarquée dans l'image), état RÉEL sondé en parallèle,
et le site public par trois sondes indépendantes. Stdlib seule."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from tools.cockpit import config


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def lire_apps(hub_url: str = config.HUB_URL, *, opener=urllib.request.urlopen, timeout: float = 3.0) -> dict:
    url = hub_url.rstrip("/") + "/api/apps"
    try:
        with opener(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "apps": [], "erreur": f"hub en erreur HTTP {exc.code}", "repli": False, "version": None}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "apps": [], "erreur": f"hub injoignable : {type(exc).__name__}: {exc}", "repli": False, "version": None}
    version = data.get("satellite_version")
    return {"ok": True, "apps": data.get("apps", []), "erreur": None, "repli": version == "?", "version": version}


def sonder(url: str, *, opener=urllib.request.urlopen, timeout: float = 3.0) -> dict:
    t0 = time.monotonic()
    try:
        with opener(url, timeout=timeout) as r:
            code = r.status
            r.read(64)
    except urllib.error.HTTPError as exc:
        detail = (exc.read(64) if hasattr(exc, "read") else b"").decode("utf-8", "replace").strip()
        return {"etat": "erreur", "code": exc.code, "ms": _ms(t0), "detail": detail or str(exc.reason)}
    except (urllib.error.URLError, OSError) as exc:
        return {"etat": "injoignable", "code": None, "ms": _ms(t0), "detail": f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"}
    return {"etat": "repond", "code": code, "ms": _ms(t0), "detail": ""}


def sonder_apps(apps: list[dict], hub_url: str = config.HUB_URL, *, opener=urllib.request.urlopen, timeout: float = 3.0) -> list[dict]:
    """Le hub s'exclut de sa liste : il est ajouté en tête, sondé sur /elysium/health."""
    cibles = [{"name": "hub", "ingress_host": urllib.parse.urlsplit(hub_url).netloc, "declared_status": "deployed",
               "url": hub_url.rstrip("/") + "/elysium/health"}]
    for a in apps:
        cibles.append({"name": a.get("name"), "ingress_host": a.get("ingress_host"),
                       "declared_status": a.get("deployment_status", "deployed"), "url": f"http://{a.get('ingress_host')}/"})
    with ThreadPoolExecutor(max_workers=8) as ex:
        sondes = list(ex.map(lambda c: sonder(c["url"], opener=opener, timeout=timeout), cibles))
    return [{**c, "probe": s} for c, s in zip(cibles, sondes)]


def etat_site_public(*, opener=urllib.request.urlopen, runner=subprocess.run, site_root=config.SITE_ROOT, timeout: float = 5.0) -> dict:
    """Trois sondes, trois états d'échec : jamais un OK fusionné."""
    res = {"https": sonder(config.SITE_PUBLIC_URL, opener=opener, timeout=timeout), "git": {}, "pages": {}}
    try:
        head = runner(["git", "-C", str(site_root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, **config.SANS_CONSOLE).stdout.strip()
        dist = runner(["git", "-C", str(site_root), "ls-remote", "origin", "refs/heads/main"], capture_output=True, text=True, timeout=20, **config.SANS_CONSOLE).stdout.split()
        res["git"] = {"ok": True, "head_local": head[:9], "main_distant": (dist[0] if dist else "?")[:9], "a_jour": bool(dist) and dist[0] == head}
    except (OSError, subprocess.SubprocessError) as exc:
        res["git"] = {"ok": False, "erreur": f"{type(exc).__name__}: {exc}"}
    try:
        b = runner(["gh", "api", f"repos/{config.SITE_REPO}/pages/builds/latest", "--jq", "{status,commit,updated_at}"],
                   capture_output=True, text=True, timeout=20, **config.SANS_CONSOLE)
        build = json.loads(b.stdout) if b.returncode == 0 and b.stdout.strip() else None
        p = runner(["gh", "pr", "list", "--repo", config.SITE_REPO, "--state", "open", "--json", "number,title"],
                   capture_output=True, text=True, timeout=20, **config.SANS_CONSOLE)
        res["pages"] = {"ok": build is not None, "build": build, "pr_ouvertes": json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None,
                        "erreur": None if build is not None else (b.stderr.strip()[-200:] or "gh api sans réponse")}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        res["pages"] = {"ok": False, "build": None, "pr_ouvertes": None, "erreur": f"{type(exc).__name__}: {exc}"}
    return res
