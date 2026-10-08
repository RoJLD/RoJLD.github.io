"""Le calque dans un vrai navigateur (Chromium, Playwright) : garde pendant l'envoi, modification
jamais perdue sans le dire. Serveur d'aperçu RÉEL sur un site git temporaire ; seule l'écriture de
la source est remplacée par un enregistreur lent (la réponse arrive après 0,8 s)."""
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
import oracle_playwright  # noqa: E402
from tools.cockpit import apercu, edition  # noqa: E402

PAGE = """<!doctype html><html lang="fr" data-lang="fr"><head><meta charset="utf-8"></head><body>
<h2 data-i18n="nav_exp">Expérience</h2><p data-i18n="hero_tag">Accroche</p>
<script>const i18n = {
    fr: {
/* BUILD:i18n_textes_fr */
        nav_exp: "Expérience",
        hero_tag: "Accroche",
/* /BUILD:i18n_textes_fr */
    },
    en: {
/* BUILD:i18n_textes_en */
        nav_exp: "Experience",
        hero_tag: "Tagline",
/* /BUILD:i18n_textes_en */
    }
};</script></body></html>"""


@pytest.fixture
def apercu_reel(tmp_path, monkeypatch):
    oracle_playwright.porte()
    racine = tmp_path / "site"
    racine.mkdir()
    subprocess.run(["git", "init", "-q", str(racine)], check=True)
    (racine / "index.html").write_text(PAGE, encoding="utf-8")
    (racine / "profile.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(apercu, "RACINE", racine)
    apercu._ignore.cache_clear()
    appels = []

    def lent(source, lang, valeur, **k):
        appels.append((source, lang, valeur))
        time.sleep(0.8)
        return {"ok": True}
    monkeypatch.setattr(edition, "ecrire_source", lent)
    srv = apercu.make_apercu_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", appels
    srv.shutdown()
    srv.server_close()


def test_une_double_entree_n_envoie_qu_une_fois(apercu_reel):
    from playwright.sync_api import sync_playwright
    url, appels = apercu_reel
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        erreurs, envois = [], []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.on("request", lambda r: envois.append(r.method) if r.url.endswith("/__cockpit/source") else None)
        page.goto(url + "/", wait_until="load")
        page.get_by_role("button", name="Éditer").click()
        page.locator('[data-src="textes:nav_exp"]').click()
        page.keyboard.press("End")
        page.keyboard.type(" pro")
        with page.expect_navigation(wait_until="load"):
            page.keyboard.press("Enter")
            page.keyboard.press("Enter")
        assert envois == ["POST"]
        assert appels == [("textes:nav_exp", "fr", "Expérience pro")]
        assert page.locator("body.cockpit-edition").count() == 1      # mode Éditer conservé au rechargement
        assert erreurs == []
        b.close()


def test_une_modification_en_cours_n_est_jamais_perdue_sans_le_dire(apercu_reel):
    from playwright.sync_api import sync_playwright
    url, appels = apercu_reel
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(url + "/", wait_until="load")
        page.get_by_role("button", name="Éditer").click()
        titre = page.locator('[data-src="textes:nav_exp"]')
        titre.click()
        page.keyboard.press("End")
        page.keyboard.type(" pro")
        page.locator('[data-src="textes:hero_tag"]').click()          # un autre texte
        assert titre.inner_text() == "Expérience pro"
        assert titre.get_attribute("contenteditable") == "true"
        assert "Entrée pour enregistrer" in page.locator(".cockpit-bulle").inner_text()
        page.get_by_role("button", name="Éditer").click()             # quitter le mode Éditer
        assert titre.inner_text() == "Expérience pro"
        page.keyboard.press("Escape")                                 # l'annulation explicite reste possible
        assert titre.inner_text() == "Expérience"
        assert appels == [] and erreurs == []
        b.close()
