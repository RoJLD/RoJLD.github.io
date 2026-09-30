"""layout du cockpit : marqueurs, ordre d'injection (nav et jeton AVANT le profil), échappement.

Mesuré sur atelier.py:731-750 : l'ordre est un invariant de sécurité — un profil contenant
`__TOKEN__` ne doit jamais recevoir le jeton, et `<` du profil est écrit `\\u003c`."""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit.pages import layout  # noqa: E402


def test_le_jeton_est_injecte_avant_le_profil_et_le_profil_ne_peut_pas_l_obtenir():
    out = layout.render("__NAV__<script>const TOKEN=__TOKEN__;const P=__PROFILE__;</script>",
                        "JETON-TEST", profile_raw='{"x":"__TOKEN__ <b>"}', page="cms")
    assert 'const TOKEN="JETON-TEST"' in out
    assert '__TOKEN__ \\u003cb>' in out          # le profil garde son texte, `<` échappé
    assert out.count("JETON-TEST") == 1


def test_la_page_courante_porte_aria_current():
    out = layout.render("__NAV__", "t", page="career-ops")
    assert 'href="/career-ops" aria-current="page"' in out
    assert 'href="/cv/" aria-current="page"' not in out


def test_page_compose_une_page_complete_avec_nav_jeton_et_corps():
    out = layout.page("Accueil", "<p>corps __TOKEN__</p>", "JETON-2", "accueil")
    assert out.startswith("<!doctype html>") and "<title>Accueil — Cockpit</title>" in out
    assert 'const TOKEN="JETON-2"' in out and out.count("JETON-2") == 1   # le corps ne reçoit pas le jeton
    assert "<p>corps __TOKEN__</p>" in out
    assert 'href="/" aria-current="page"' in out
