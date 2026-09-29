"""Façade de compatibilité — le serveur vit dans tools/cockpit/ (spec 2026-09-28 § 6.1).

Gardée pour `python tools/cv/atelier.py` (Dockerfile.kleos, docker-entrypoint.sh,
satellite_manifest.json `entrypoint`) et pour les tests qui importent `atelier` depuis
tools/cv. La façade insère la racine du site elle-même : lancée depuis n'importe quel
cwd, `tools` doit se résoudre."""
import pathlib
import sys

_SITE = pathlib.Path(__file__).resolve().parents[2]
if str(_SITE) not in sys.path:
    sys.path.insert(0, str(_SITE))

from tools.cockpit.server import (  # noqa: E402,F401
    Handler, AtelierServer, make_server, main, csrf_token, reset_csrf_token,
    CSRF_HEADER, MAX_BODY_BYTES, _LOCAL_HOSTS, _bind, _hosts_autorises, _hostport_ok, _url_ok,
    REQUEST_TIMEOUT_S, LINGER_IDLE_S, LINGER_TOTAL_S,
)
from tools.cockpit.server import (  # noqa: E402,F401  — Tâche 3 : ces noms passent dans pages.cv
    generate_pdf, generate_docx, generate_letter, save_profile_edit,
    ciblage_degrade, verdict_ciblage, _page, _PROFILE, _git_commit, _regen_bank,
)
import cv_pdf, cv_render, cv_target  # noqa: E401,E402,F401

if __name__ == "__main__":
    sys.exit(main())
