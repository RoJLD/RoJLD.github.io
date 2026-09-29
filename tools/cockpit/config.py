"""Configuration du cockpit : chemins, bootstrap de sys.path, emplacement de career-ops.

Le dépôt du site est PUBLIC : rien d'ici ne contient un chemin du poste. L'emplacement
de career-ops vient de `CAREER_OPS_ROOT`, sinon de `tools/cockpit/local.json` (ignoré par
git), sinon il n'y en a pas — et la page career-ops le dit (spec § 8), sans planter."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = SITE_ROOT / "tools"
CV_DIR = TOOLS_DIR / "cv"
LOCAL_JSON = Path(__file__).resolve().parent / "local.json"
HUB_URL = os.environ.get("ANTHROPOS_HUB_URL", "http://anthropos.elysium.local")
SITE_PUBLIC_URL = "https://robin-denis.com/"


def bootstrap_sys_path() -> None:
    """Les modules du moteur CV s'importent à plat (`import cv_pdf`) depuis tools/cv, et
    `tools.cockpit.*` depuis la racine du site. Idempotent."""
    for p in (SITE_ROOT, TOOLS_DIR, CV_DIR):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


bootstrap_sys_path()


def career_ops_root(env=None, local_json: Path = LOCAL_JSON) -> Path | None:
    """Dossier de career-ops, ou None. Jamais d'exception : l'absence est un état affiché."""
    env = os.environ if env is None else env
    cand = (env.get("CAREER_OPS_ROOT") or "").strip()
    if not cand and local_json.is_file():
        try:
            cand = str(json.loads(local_json.read_text(encoding="utf-8")).get("career_ops_root", "")).strip()
        except (OSError, ValueError):
            return None
    if not cand:
        return None
    p = Path(cand).expanduser()
    return p if (p / "tracker.mjs").is_file() else None
