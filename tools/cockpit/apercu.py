"""Serveur d'aperçu du site (édition du site, A1, spec § 3.1).

127.0.0.1:8011, dans le processus du cockpit et avec ses gardes (Host, Origin, Content-Type
JSON, jeton anti-CSRF). Il sert le checkout du site TEL QUEL, annote l'accueil (`data-src`)
et injecte le calque d'édition dans chaque page HTML. Il n'écrit jamais ce qu'il sert : le
site publié ne porte ni `data-src` ni calque. Les pages du site utilisent des liens racine
(`/projects/`, `fetch('/profile.json')`), d'où une origine dédiée plutôt qu'un préfixe."""
from __future__ import annotations

import functools
import json
import mimetypes
import subprocess
import threading
import urllib.parse
from pathlib import Path

from tools.cockpit import career_ops as co
from tools.cockpit import config, edition, server, sources_accueil

PORT = 8011
RACINE = config.SITE_ROOT
CALQUE = Path(__file__).resolve().parent / "static" / "calque.js"
ETAT = {"actif": False, "port": PORT, "erreur": None}


@functools.lru_cache(maxsize=4096)
def _ignore(racine: str, rel: str) -> bool:
    """`git check-ignore` FERMÉ par défaut : code 1 = suivi ou servable ; 0 = ignoré ;
    tout le reste (git absent, dépôt illisible) = traité comme ignoré, donc jamais servi.
    complement.est_ignore fait l'inverse (ouvert en cas d'échec), à juste titre pour lui."""
    try:
        cp = subprocess.run(["git", "-C", racine, "check-ignore", "-q", "--", rel],
                            capture_output=True, timeout=10, **config.SANS_CONSOLE)
    except (OSError, subprocess.SubprocessError):
        return True
    return cp.returncode != 1


def fichier_servi(racine, chemin_url: str):
    """Fichier à servir, ou None (404) : pas de traversée, pas de segment caché, rien
    d'ignoré par git — l'aperçu sert ce que Pages servirait, jamais local.json."""
    segments = [s for s in urllib.parse.unquote(chemin_url).split("/") if s]
    if any(s.startswith(".") or "\\" in s or ":" in s for s in segments):
        return None
    base = Path(racine).resolve()
    try:
        cible = base.joinpath(*segments).resolve() if segments else base
        cible.relative_to(base)
    except (OSError, ValueError):
        return None
    if cible.is_dir():
        cible = cible / "index.html"
    if not cible.is_file() or _ignore(str(base), cible.relative_to(base).as_posix()):
        return None
    return cible


def injecter_calque(page: str, jeton: str) -> str:
    etat = json.dumps({"jeton": jeton}).replace("<", "\\u003c")
    balise = f'<script>window.__COCKPIT__={etat};</script><script src="/__cockpit/calque.js"></script>'
    i = page.lower().rfind("</body>")
    return page[:i] + balise + page[i:] if i >= 0 else page + balise


def _json(h, code: int, obj: dict) -> None:
    h._send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _profil() -> dict:
    return json.loads((Path(RACINE) / "profile.json").read_text(encoding="utf-8"))


def post_source(h, data: dict) -> None:
    """Les chemins lus sont CEUX des écrivains (build_site.SITE_TEXTS, pages.cv._PROFILE) :
    lire un fichier et en faire écrire un autre serait une source de vérité dédoublée."""
    from tools.cockpit.pages import cv as pages_cv
    import build_site
    try:
        with co.verrou_action("edition-site"):
            res = edition.ecrire_source(
                data.get("source"), data.get("lang"), data.get("valeur"),
                textes_path=build_site.SITE_TEXTS, profile_path=pages_cv._PROFILE,
                reconstruire=lambda: build_site.build(write=True),
                sauvegarde=lambda brut: pages_cv.sauvegarde_gouvernee(brut))
    except edition.SourceRefusee as exc:
        return _json(h, 400, {"ok": False, "erreur": str(exc)})
    except co.ActionEnCours as exc:
        return _json(h, 409, {"ok": False, "erreur": f"action déjà en cours : {exc}"})
    except Exception as exc:  # noqa: BLE001 — reconstruction en échec : rapportée, jamais avalée
        return _json(h, 500, {"ok": False, "erreur": f"{type(exc).__name__}: {exc}"})
    return _json(h, 200 if res.get("ok") else 422, res)


ROUTES_GET: dict = {}
ROUTES_POST: dict = {"/__cockpit/source": post_source}


class ApercuHandler(server.Handler):
    def _routes_post(self):
        return ROUTES_POST

    def do_GET(self):
        if not server._hostport_ok(self.headers.get("Host"), self._port()):
            return self._refuse(403, "hote non autorise")
        chemin = urllib.parse.urlsplit(self.path).path
        if chemin == "/__cockpit/calque.js":
            return self._send(200, "application/javascript; charset=utf-8", CALQUE.read_bytes(),
                              {"Cache-Control": "no-store"})
        route = ROUTES_GET.get(chemin)
        if route is not None:
            return route(self)
        fichier = fichier_servi(RACINE, chemin)
        if fichier is None:
            return self._send(404, "text/plain; charset=utf-8", "introuvable".encode("utf-8"))
        octets = fichier.read_bytes()
        ctype = mimetypes.guess_type(fichier.name)[0] or "application/octet-stream"
        if fichier.suffix.lower() == ".html":
            page = octets.decode("utf-8", "replace")
            if fichier == (Path(RACINE) / "index.html").resolve():
                page = sources_accueil.annoter(page, sources_accueil.carte_sources(page, _profil()))
            octets, ctype = injecter_calque(page, self.token()).encode("utf-8"), "text/html"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        return self._send(200, ctype, octets, {"Cache-Control": "no-store"})


def make_apercu_server(port: int = 0):
    return server.AtelierServer((server._bind(), port), ApercuHandler)


def demarrer(port: int = PORT):
    """Lance l'aperçu dans un fil. Jamais d'exception : un port occupé est un état affiché."""
    try:
        srv = make_apercu_server(port)
    except OSError as exc:
        ETAT.update(actif=False, port=port, erreur=f"port {port} indisponible : {exc}")
        return None
    threading.Thread(target=srv.serve_forever, daemon=True, name="apercu-site").start()
    ETAT.update(actif=True, port=srv.server_address[1], erreur=None)
    return srv
