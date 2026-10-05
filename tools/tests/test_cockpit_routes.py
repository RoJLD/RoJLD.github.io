"""Routes du cockpit : l'accueil sur /, l'atelier sous /cv/, et la chaîne de refus POST intacte."""
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit import server  # noqa: E402
from tools.cockpit.pages import accueil, cv as pages_cv  # noqa: E402


class _Srv:
    def __enter__(self):
        self.srv = server.make_server(0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}"

    def __exit__(self, *a):
        self.srv.shutdown(); self.srv.server_close()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_l_accueil_porte_le_jeton_la_nav_et_une_carte_profil():
    with _Srv() as base:
        code, body = _get(base, "/")
    assert code == 200 and "const TOKEN=" in body and 'href="/cms"' in body
    assert "Profil &amp; CV" in body and 'class="carte' in body


def test_l_atelier_vit_sous_cv_et_poste_encore_sur_generate():
    with _Srv() as base:
        code, body = _get(base, "/cv/")
        code2, body2 = _get(base, "/cv/?x=1")
    assert code == 200 and 'data-route="/generate"' in body and "__TEMPLATES__" not in body
    assert code2 == 200


def test_edit_accepte_une_chaine_de_requete():
    with _Srv() as base:
        code, _ = _get(base, "/edit?x=1")
    assert code == 200


def test_les_routes_get_sont_toutes_declarees_dans_la_table():
    assert {"/", "/cv/", "/edit", "/cms"} <= set(server.ROUTES_GET)
    assert {"/generate", "/generate-docx", "/generate-letter", "/save"} <= set(server.ROUTES_POST)


def test_une_carte_en_erreur_est_affichee_pas_masquee(monkeypatch, tmp_path):
    monkeypatch.setattr(pages_cv, "_PROFILE", tmp_path / "absent.json")
    c = accueil.carte_profil()
    assert c["etat"] == "erreur" and "FileNotFoundError" in c["lignes"][0]
