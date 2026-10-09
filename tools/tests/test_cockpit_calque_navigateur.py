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
        erreurs, envois, dialogues = [], [], []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.on("request", lambda r: envois.append(r.method) if r.url.endswith("/__cockpit/source") else None)
        page.on("dialog", lambda d: (dialogues.append(d.type), d.dismiss()))   # le rechargement ne demande rien
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
        assert erreurs == [] and dialogues == []
        b.close()


def _etat(fichiers):
    return {"branche": "main", "fetch_ok": True, "fetch_erreur": "", "en_avance": 0, "en_retard": 0,
            "fichiers": [{"chemin": c, "statut": "M"} for c in fichiers], "commits_locaux": [],
            "fichiers_commits": [], "status_erreur": "", "hors_perimetre": [], "hors_journal": []}


def test_le_panneau_se_relit_apres_verifier_et_propose_de_reessayer_le_push(apercu_reel, monkeypatch):
    """Le build des vérifications régénère des pages : la liste est relue ; les lignes de
    vérification ne s'empilent pas ; un push refusé laisse « Réessayer le push » (spec § 6)."""
    from playwright.sync_api import sync_playwright

    from tools.cockpit import publication
    url, _ = apercu_reel
    lectures, verifications = [], []

    def etat(racine):
        lectures.append(1)
        return _etat(["profile.json"] if len(lectures) == 1 else ["profile.json", "index.html"])

    def verifier(racine):
        verifications.append(1)
        ok = len(verifications) != 3          # la 3e (rejouée par « Publier ») échoue
        return [{"nom": "contrôle A", "ok": ok, "detail": "" if ok else "cassé"}]
    monkeypatch.setattr(publication, "etat", etat)
    monkeypatch.setattr(publication, "diffs_sources", lambda racine, e: {})
    monkeypatch.setattr(publication, "verifier", verifier)
    monkeypatch.setattr(publication, "publier", lambda racine, message: {
        "ok": False, "etape": "push", "commit": "abc1234", "commit_local": True, "erreur": "rejeté"})
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        erreurs = []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.goto(url + "/", wait_until="load")
        page.get_by_role("button", name="Publier", exact=True).click()
        page.get_by_text("• M profile.json").wait_for()
        assert page.get_by_text("• M index.html").count() == 0
        envoyer = page.get_by_role("button", name="Publier sur main")
        for _ in range(2):
            page.get_by_role("button", name="Vérifier").click()
            page.get_by_text("Vérifications terminées").wait_for()
        assert page.get_by_text("• M index.html").count() == 1            # état relu après le build
        assert page.get_by_text("✓ contrôle A").count() == 1              # lignes remplacées, pas empilées
        assert envoyer.is_enabled()
        envoyer.click()                                                   # 409 : vérifications rejouées en échec
        page.get_by_text("✗ contrôle A — cassé").wait_for()
        assert page.get_by_text("✓ contrôle A").count() == 0 and not envoyer.is_enabled()
        page.get_by_role("button", name="Vérifier").click()
        page.get_by_text("Vérifications terminées").wait_for()
        envoyer.click()                                                   # push refusé, commit local gardé
        reessai = page.get_by_role("button", name="Réessayer le push")
        reessai.wait_for()
        assert reessai.is_enabled() and "commit local conservé" in page.locator("body").inner_text()
        assert erreurs == []
        b.close()


def test_quitter_la_page_avec_un_texte_modifie_demande_confirmation(apercu_reel):
    """Cohérence R9 : un clic sur un lien non éditable ne perd pas une modification en silence."""
    from playwright.sync_api import Error as ErreurPlaywright
    from playwright.sync_api import sync_playwright
    url, appels = apercu_reel
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        erreurs, dialogues = [], []
        page.on("pageerror", lambda e: erreurs.append(str(e)))
        page.on("dialog", lambda d: (dialogues.append(d.type), d.dismiss()))
        page.goto(url + "/", wait_until="load")
        page.get_by_role("button", name="Éditer").click()
        titre = page.locator('[data-src="textes:nav_exp"]')
        titre.click()
        page.keyboard.press("End")
        page.keyboard.type(" pro")
        try:
            page.goto(url + "/page.html", timeout=5000)
        except ErreurPlaywright:
            pass                                                      # navigation annulée par le refus
        assert dialogues == ["beforeunload"]
        assert titre.inner_text() == "Expérience pro"
        assert appels == [] and erreurs == []
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
