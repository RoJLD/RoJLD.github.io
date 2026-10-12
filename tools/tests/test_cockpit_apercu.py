"""Serveur d'aperçu 8011 : il sert le site tel quel, annote l'accueil, injecte le calque, et
garde les mêmes portes que le cockpit (spec édition du site § 3.1)."""
import http.client
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import apercu, career_ops as co, edition, server  # noqa: E402
from tools.cockpit.pages import site as page_site  # noqa: E402

INDEX = """<!doctype html><html><body><h1 data-i18n="nav_exp">Expérience</h1>
<p data-i18n="status">Disponible</p>
<script>const i18n = {
    fr: {
/* BUILD:i18n_textes_fr */
        nav_exp: "Expérience",
/* /BUILD:i18n_textes_fr */
/* BUILD:i18n_status_fr */
        status: "Disponible",
/* /BUILD:i18n_status_fr */
    },
    en: {
/* BUILD:i18n_textes_en */
        nav_exp: "Experience",
/* /BUILD:i18n_textes_en */
/* BUILD:i18n_status_en */
        status: "Available",
/* /BUILD:i18n_status_en */
    }
};</script></body></html>"""


@pytest.fixture
def racine(tmp_path, monkeypatch):
    r = tmp_path / "site"
    (r / "sub").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / ".gitignore").write_text("secret.json\n", encoding="utf-8")
    (r / "index.html").write_text(INDEX, encoding="utf-8")
    (r / "page.html").write_text("<html><body><p>Page</p></body></html>", encoding="utf-8")
    (r / "sub" / "index.html").write_text("<html><body>Sous</body></html>", encoding="utf-8")
    (r / "secret.json").write_text('{"x": 1}', encoding="utf-8")
    (r / "profile.json").write_text(json.dumps({"identity": {"status": {"fr": "Disponible", "en": "Available"}}}),
                                    encoding="utf-8")
    monkeypatch.setattr(apercu, "RACINE", r)
    apercu._ignore.cache_clear()
    return r


@pytest.fixture
def srv(racine):
    s = apercu.make_apercu_server(0)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s
    s.shutdown()
    s.server_close()


def _req(s, methode, chemin, corps=None, host=None, jeton=None):
    port = s.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    entetes = {"Host": host or f"127.0.0.1:{port}"}
    if corps is not None:
        entetes.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}",
                        server.CSRF_HEADER: server.csrf_token() if jeton is None else jeton})
    c.request(methode, chemin, body=None if corps is None else json.dumps(corps), headers=entetes)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def test_l_accueil_est_annote_et_porte_le_calque(srv):
    code, corps = _req(srv, "GET", "/")
    assert code == 200
    assert 'data-i18n="nav_exp" data-src="textes:nav_exp"' in corps
    assert 'data-src="profile:identity.status.{lang}"' in corps
    assert '<script src="/__cockpit/calque.js"></script>' in corps and server.csrf_token() in corps


def test_une_autre_page_porte_le_calque_sans_annotation(srv):
    code, corps = _req(srv, "GET", "/page.html")
    assert code == 200 and "/__cockpit/calque.js" in corps and "data-src" not in corps


def test_un_dossier_sert_son_index(srv):
    assert _req(srv, "GET", "/sub/") == (200, _req(srv, "GET", "/sub/index.html")[1])


@pytest.mark.parametrize("chemin", ["/secret.json", "/.git/config", "/%2e%2e/x", "/absent.html", "/../site/index.html"])
def test_les_fichiers_caches_ignores_ou_hors_racine_sont_introuvables(srv, chemin):
    assert _req(srv, "GET", chemin)[0] == 404


def test_git_injoignable_ne_sert_rien(racine, monkeypatch):
    """Fermé par défaut : sans réponse de git, on ne sait pas si le fichier est ignoré."""
    def casse(*a, **k):
        raise OSError("git absent")
    monkeypatch.setattr(apercu.subprocess, "run", casse)
    apercu._ignore.cache_clear()
    assert apercu.fichier_servi(racine, "/index.html") is None


def test_un_hote_etranger_est_refuse(srv):
    assert _req(srv, "GET", "/", host="evil.example")[0] == 403


def test_le_calque_est_servi(srv):
    code, corps = _req(srv, "GET", "/__cockpit/calque.js")
    assert code == 200 and "Calque" in corps


def test_une_ecriture_sans_jeton_est_refusee(srv):
    assert _req(srv, "POST", "/__cockpit/source", {"source": "textes:nav_exp"}, jeton="faux")[0] == 403


def test_une_ecriture_valide_passe_par_edition(srv, monkeypatch):
    vu = {}
    monkeypatch.setattr(edition, "ecrire_source", lambda s, l, v, **k: vu.update(s=s, l=l, v=v) or {"ok": True})
    code, corps = _req(srv, "POST", "/__cockpit/source", {"source": "textes:nav_exp", "lang": "en", "valeur": "Path"})
    assert code == 200 and json.loads(corps) == {"ok": True} and vu == {"s": "textes:nav_exp", "l": "en", "v": "Path"}


def test_une_ecriture_de_source_est_journalisee(srv, racine, monkeypatch):
    """Spec § 5.4 : ce que le cockpit écrit est au journal, la publication ne le refuse pas."""
    from tools.cockpit import journal

    def ecrit(s, l, v, **k):
        (racine / "site_texts.json").write_text('{"fr": {}, "en": {}}\n', encoding="utf-8")
        return {"ok": True}
    monkeypatch.setattr(edition, "ecrire_source", ecrit)
    assert _req(srv, "POST", "/__cockpit/source", {"source": "textes:nav_exp", "lang": "fr", "valeur": "x"})[0] == 200
    assert journal.etrangers(racine, ["site_texts.json"]) == []
    (racine / "secret2.txt").write_text("à la main", encoding="utf-8")
    assert journal.etrangers(racine, ["secret2.txt"]) == ["secret2.txt"]


def test_les_pages_regenerees_par_verifier_sont_journalisees(srv, racine, monkeypatch):
    from tools.cockpit import journal, publication

    def verifie(r):
        (racine / "page.html").write_text("<html><body>régénérée</body></html>", encoding="utf-8")
        return [{"nom": "x", "ok": True, "detail": ""}]
    monkeypatch.setattr(publication, "verifier", verifie)
    assert _req(srv, "POST", "/__cockpit/publication/verifier", {})[0] == 200
    assert journal.etrangers(racine, ["page.html"]) == []


def test_un_refus_d_edition_rend_400_nomme(srv, monkeypatch):
    def refuse(*a, **k):
        raise edition.SourceRefusee("texte vide : rien n'est enregistré")
    monkeypatch.setattr(edition, "ecrire_source", refuse)
    code, corps = _req(srv, "POST", "/__cockpit/source", {"source": "textes:nav_exp", "lang": "fr", "valeur": ""})
    assert code == 400 and "texte vide" in json.loads(corps)["erreur"]


def test_une_ecriture_pendant_une_autre_action_est_refusee(srv, monkeypatch):
    monkeypatch.setattr(edition, "ecrire_source", lambda *a, **k: {"ok": True})
    with co.verrou_action("autre"):
        code, corps = _req(srv, "POST", "/__cockpit/source", {"source": "textes:nav_exp", "lang": "fr", "valeur": "x"})
    assert code == 409 and "déjà en cours" in json.loads(corps)["erreur"]


def test_demarrer_sur_un_port_occupe_rend_un_etat_lisible(monkeypatch):
    # Mesuré le 2026-10-08 sous Windows : le bind d'AtelierServer sur un port occupé est
    # refusé (WinError 10013), SO_REUSEADDR ne laisse pas deux serveurs se partager 8011.
    monkeypatch.setattr(apercu, "ETAT", dict(apercu.ETAT))
    occupe = socket.socket()
    occupe.bind(("127.0.0.1", 0))
    occupe.listen(1)
    try:
        port = occupe.getsockname()[1]
        assert apercu.demarrer(port) is None
        assert apercu.ETAT["actif"] is False and "indisponible" in apercu.ETAT["erreur"]
    finally:
        occupe.close()


def test_l_apercu_refuse_d_ecouter_hors_du_loopback(monkeypatch):
    monkeypatch.setattr(apercu, "ETAT", dict(apercu.ETAT))
    monkeypatch.setattr(server, "_bind", lambda: "0.0.0.0")
    monkeypatch.setattr(apercu, "make_apercu_server", lambda port=0: pytest.fail("aucun serveur hors loopback"))
    assert apercu.demarrer(0) is None
    assert apercu.ETAT["actif"] is False and "hors du loopback" in apercu.ETAT["erreur"]


def test_les_pages_de_l_apercu_bloquent_les_scripts_tiers(srv):
    port = srv.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    r.read()
    csp = r.getheader("Content-Security-Policy") or ""
    assert "script-src 'self' 'unsafe-inline'" in csp and "plausible" not in csp
    # Chromium rejette la source [::1] (erreur console sur chaque page de l'aperçu) : retirée
    assert csp.split("frame-ancestors")[1].split() == ["http://127.0.0.1:8010", "http://localhost:8010"]
    assert "https://" not in csp.split("frame-ancestors")[0]   # aucun script tiers : le jeton ouvre la publication


class _H:
    def __init__(self):
        self.envoye = None

    def _send(self, code, ctype, corps, extra=None):
        self.envoye = (code, corps.decode("utf-8"))

    def token(self):
        return "jeton"


def test_l_onglet_site_montre_le_cadre_ou_l_erreur(monkeypatch):
    monkeypatch.setattr(apercu, "ETAT", {"actif": True, "port": 8011, "erreur": None})
    h = _H()
    page_site.page_site(h)
    assert h.envoye[0] == 200 and '<iframe src="http://127.0.0.1:8011/"' in h.envoye[1]
    monkeypatch.setattr(apercu, "ETAT", {"actif": False, "port": 8011, "erreur": "port 8011 indisponible : occupé"})
    page_site.page_site(h)
    assert "Aperçu indisponible : port 8011 indisponible" in h.envoye[1] and "<iframe" not in h.envoye[1]


def test_le_cockpit_demarre_sans_import_circulaire():
    """Interpréteur NEUF, server importé d'abord comme par atelier.py : dans pytest, un autre
    test qui importe apercu en premier masquerait le cycle server → pages.site → apercu → server."""
    cp = subprocess.run([sys.executable, "-c", "import tools.cockpit.server, tools.cockpit.apercu"],
                        cwd=str(SITE), capture_output=True, text=True, timeout=60)
    assert cp.returncode == 0, cp.stderr


def test_publier_rejoue_les_verifications(srv, monkeypatch):
    from tools.cockpit import publication
    monkeypatch.setattr(publication, "verifier", lambda racine: [{"nom": "x", "ok": False, "detail": "d"}])
    monkeypatch.setattr(publication, "publier", lambda *a, **k: pytest.fail("publier sans vérifications"))
    code, corps = _req(srv, "POST", "/__cockpit/publication/publier", {"message": "m"})
    assert code == 409 and json.loads(corps)["refus"] == ["vérifications en échec"]


def test_le_suivi_pages_refuse_un_sha_invalide(srv):
    assert _req(srv, "GET", "/__cockpit/publication/pages?sha=;rm")[0] == 400


def test_une_erreur_imprevue_de_publication_rend_un_500_nomme(srv, monkeypatch):
    from tools.cockpit import publication

    def casse(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr(publication, "verifier", casse)
    code, corps = _req(srv, "POST", "/__cockpit/publication/verifier", {})
    assert code == 500 and "OSError: disque plein" in json.loads(corps)["erreur"]
    monkeypatch.setattr(publication, "etat", casse)
    code, corps = _req(srv, "GET", "/__cockpit/publication")
    assert code == 500 and "OSError: disque plein" in json.loads(corps)["erreur"]
