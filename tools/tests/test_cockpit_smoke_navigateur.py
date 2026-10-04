"""Ce que VOIT un utilisateur : accueil, /cv/, /career-ops (bouton « J'ai postulé » sur des
données factices), /anthropos. Mesuré sur la PR #26 : un smoke qui vérifie une propriété
proxy (disabled) rate un bouton rendu invisible — ici on lit le texte affiché après clic."""
import sys, threading
from pathlib import Path
import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
import oracle_playwright  # noqa: E402
from cockpit_fixtures import KPI, RELANCES, SEND_QUEUE, TRACKER  # noqa: E402
from tools.cockpit import anthropos as an, career_ops as co, server  # noqa: E402


def _lu(donnees):
    return lambda root, **k: {"ok": True, "donnees": donnees, "erreur": None, "lu_a": "10:00"}


@pytest.fixture
def base(monkeypatch, tmp_path):
    oracle_playwright.porte()
    monkeypatch.setattr(co, "prerequis", lambda **k: {"ok": True, "career_ops_root": str(tmp_path), "node": "node", "node_version": "25.2.1", "problemes": []})
    monkeypatch.setattr(co, "lire_kpi", _lu(KPI))
    monkeypatch.setattr(co, "lire_tracker", _lu(TRACKER))
    monkeypatch.setattr(co, "lire_relances", _lu(RELANCES))
    monkeypatch.setattr(co, "lire_file", _lu(SEND_QUEUE))
    monkeypatch.setattr(co, "postule", lambda n, note, **k: {"id": "postule", "argv": [], "code": 0, "sens": "enregistré (FACTICE)", "stdout": "",
                                                            "stderr": "", "duree_s": 0.1, "interrompu": False, "json": {"newStatus": "Applied"}, "ecrit": "x"})
    monkeypatch.setattr(co, "executer", lambda cid, **k: pytest.fail(f"le smoke ne lance aucune commande career-ops ({cid})"))
    monkeypatch.setattr(an, "lire_apps", lambda *a, **k: {"ok": False, "apps": [], "erreur": "hub injoignable : FACTICE", "repli": False, "version": None})
    monkeypatch.setattr(an, "sonder", lambda url, **k: {"etat": "injoignable", "code": None, "ms": 0, "detail": "FACTICE"})  # carte accueil, sans réseau
    monkeypatch.setattr(an, "etat_site_public", lambda **k: {"https": {"etat": "injoignable", "code": None, "ms": 0, "detail": "FACTICE"}, "git": {"ok": False, "erreur": "FACTICE"}, "pages": {"ok": False, "erreur": "FACTICE"}})
    srv = server.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown(); srv.server_close()


def test_parcours_complet_dans_un_navigateur(base):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); page = b.new_page(); erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(base + "/", wait_until="load")
        assert page.locator(".carte").count() >= 3                      # Profil & CV, career-ops, Anthropos
        page.goto(base + "/cv/", wait_until="load")
        assert page.locator('[data-route="/generate"]').is_visible()
        page.goto(base + "/career-ops", wait_until="load")
        texte = page.locator("body").inner_text()
        assert "Passage à la candidature" in texte and "File d'envoi" in texte
        boutons = page.locator("[data-n]")
        assert [boutons.nth(i).get_attribute("data-n") for i in range(boutons.count())][:2] == ["24", "23"]   # ordre de la file
        page.on("dialog", lambda d: d.accept("note du smoke") if d.type == "prompt" else d.accept())
        page.locator('[data-n="23"]').click()
        page.wait_for_function("document.getElementById('sortie').textContent.startsWith('OK')")
        assert "FACTICE" in page.locator("#sortie").inner_text()
        page.goto(base + "/anthropos", wait_until="load")
        assert "hub injoignable" in page.locator("body").inner_text()
        assert erreurs == []
        b.close()
