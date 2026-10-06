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
SITE_REPO = "RoJLD/RoJLD.github.io"


def bootstrap_sys_path() -> None:
    """Les modules du moteur CV s'importent à plat (`import cv_pdf`) depuis tools/cv, et
    `tools.cockpit.*` depuis la racine du site. Idempotent."""
    for p in (SITE_ROOT, TOOLS_DIR, CV_DIR):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)


bootstrap_sys_path()


def resoudre_career_ops(env=None, local_json: Path = LOCAL_JSON) -> tuple[Path | None, str | None]:
    """(dossier de career-ops, None), ou (None, cause précise). Jamais d'exception : l'absence
    est un état affiché, et sa cause aussi — « non configuré » seul renvoyait à écrire un
    local.json qui existait déjà."""
    env = os.environ if env is None else env
    cand = (env.get("CAREER_OPS_ROOT") or "").strip()
    source = "CAREER_OPS_ROOT"
    if not cand:
        if not local_json.is_file():
            return None, f"ni CAREER_OPS_ROOT ni {local_json}"
        source = local_json.name
        try:
            # utf-8-sig : Windows PowerShell 5.1 (`Set-Content -Encoding utf8`) écrit un BOM que json refuse
            data = json.loads(local_json.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            return None, f"{local_json} illisible ({exc})"
        cand = str(data.get("career_ops_root", "")).strip() if isinstance(data, dict) else ""
        if not cand:
            return None, f'{local_json} sans clé "career_ops_root"'
    p = Path(cand).expanduser()
    if not (p / "tracker.mjs").is_file():
        return None, f"{p} ({source}) ne contient pas tracker.mjs"
    return p, None


def career_ops_root(env=None, local_json: Path = LOCAL_JSON) -> Path | None:
    """Dossier de career-ops, ou None (la cause : `resoudre_career_ops`)."""
    return resoudre_career_ops(env, local_json)[0]
