"""Page Anthropos : le déclaré (hub) à côté du mesuré (sonde), et l'état du site public ;
hub injoignable = dit, jamais une liste de secours."""
import sys, threading, urllib.request
from pathlib import Path
SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import anthropos as an, server  # noqa: E402


def _get(path):
    srv = server.make_server(0); threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}", timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    finally:
        srv.shutdown(); srv.server_close()


def test_la_page_montre_declare_et_mesure_et_le_site(monkeypatch):
    monkeypatch.setattr(an, "lire_apps", lambda *a, **k: {"ok": True, "apps": [{"name": "career", "ingress_host": "ergon.elysium.local", "deployment_status": "deployed"}], "erreur": None, "repli": False, "version": "0.5.1"})
    monkeypatch.setattr(an, "sonder_apps", lambda apps, *a, **k: [
        {"name": "hub", "ingress_host": "anthropos.elysium.local", "declared_status": "deployed", "url": "http://anthropos.elysium.local/elysium/health", "probe": {"etat": "repond", "code": 200, "ms": 150, "detail": ""}},
        {"name": "career", "ingress_host": "ergon.elysium.local", "declared_status": "deployed", "url": "http://ergon.elysium.local/", "probe": {"etat": "erreur", "code": 503, "ms": 80, "detail": "no available server"}}])
    monkeypatch.setattr(an, "etat_site_public", lambda **k: {"https": {"etat": "repond", "code": 200, "ms": 300, "detail": ""},
                                                             "git": {"ok": True, "head_local": "7e7abf039", "main_distant": "7e7abf039", "a_jour": True},
                                                             "pages": {"ok": False, "build": None, "pr_ouvertes": None, "erreur": "gh absent"}})
    code, body = _get("/anthropos")
    assert code == 200 and "deployed" in body and "503" in body and "no available server" in body and "repond" in body
    assert "7e7abf039" in body and "à jour" in body and "gh absent" in body


def test_hub_injoignable_est_dit_sans_liste_de_secours(monkeypatch):
    monkeypatch.setattr(an, "lire_apps", lambda *a, **k: {"ok": False, "apps": [], "erreur": "hub injoignable : URLError: timed out", "repli": False, "version": None})
    monkeypatch.setattr(an, "etat_site_public", lambda **k: {"https": {"etat": "injoignable", "code": None, "ms": 0, "detail": "x"}, "git": {"ok": False, "erreur": "y"}, "pages": {"ok": False, "erreur": "z"}})
    code, body = _get("/anthropos")
    assert code == 200 and "hub injoignable" in body and "ergon" not in body
