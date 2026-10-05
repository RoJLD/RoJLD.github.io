"""Routes du cockpit : l'accueil sur /, l'atelier sous /cv/, et la chaîne de refus POST intacte."""
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

import pytest  # noqa: E402

from tools.cockpit import server  # noqa: E402
from tools.cockpit.pages import accueil, cv as pages_cv  # noqa: E402


@pytest.fixture(autouse=True)
def _cartes_locales(monkeypatch):
    """Les cartes réseau (career-ops, Anthropos) se testent dans leurs fichiers ;
    l'accueil de L1 se teste avec la carte profil seule."""
    monkeypatch.setattr(accueil, "CARTES", [accueil.carte_profil])


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


def test_une_carte_lente_ne_retient_pas_l_accueil(monkeypatch):
    """Mesuré 2026-10-04 : hub injoignable → GET / en 11,3 s (la résolution DNS d'un nom
    .local échappe au délai d'urlopen). Une carte qui ne répond pas dans le budget est
    affichée comme telle ; elle ne retient jamais la page."""
    import time

    def lente():
        time.sleep(5)
        return {"titre": "Lente", "href": "/lente", "etat": "ok", "lignes": ["trop tard"]}
    lente.titre, lente.href = "Lente", "/lente"
    monkeypatch.setattr(accueil, "CARTES", [accueil.carte_profil, lente])
    monkeypatch.setattr(accueil, "DELAI_CARTES_S", 0.5)
    t0 = time.monotonic()
    with _Srv() as base:
        code, body = _get(base, "/")
    assert code == 200 and time.monotonic() - t0 < 3
    assert "Profil" in body and "Lente" in body and "pas de réponse en 0.5 s" in body and "trop tard" not in body
    assert body.index("Profil") < body.index("Lente")                      # ordre des cartes conservé


def test_une_carte_qui_leve_s_affiche_en_erreur(monkeypatch):
    def cassee():
        raise RuntimeError("boum")
    cassee.titre = "Cassée"
    monkeypatch.setattr(accueil, "CARTES", [accueil.carte_profil, cassee])
    with _Srv() as base:
        code, body = _get(base, "/")
    assert code == 200 and "Cassée" in body and "RuntimeError: boum" in body and 'class="carte erreur"' in body
