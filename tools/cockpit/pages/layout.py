"""Chrome commun : nom, navigation, CSS de base, rendu des marqueurs.

Déplacé depuis atelier.py (NOM :230, _NAV :235-254, _render :731-750). Une seule
signature change : le jeton est passé en argument — aucun module de pages n'importe
server (pas de cycle)."""
from __future__ import annotations

import html
import json

NOM = "Kleos"  # nom interne inchangé (les tests le lisent)

# <style> repris tel quel de _NAV (atelier.py:235-246, commit 7e7abf0) ; seule la
# LISTE de liens change (pages sœurs du cockpit) — Ruling C9 révisé (revue finale
# opus, 2026-09-29) : la spec ne touche que la liste, jamais le style.
NAV = """<style>
.nv{display:flex;align-items:center;gap:16px;padding:2px 0 12px;margin:0 0 22px;
border-bottom:1px solid #e2e8f0;font-size:13px;flex-wrap:wrap}
.nv a{color:#475569;text-decoration:none;padding:4px 2px;border-bottom:2px solid transparent}
.nv a:hover{color:#1a1a2e;border-bottom-color:#4361ee}
.nv a:focus-visible{outline:2px solid #4361ee;outline-offset:3px;border-radius:3px}
.nv a[aria-current=page]{color:#1a1a2e;font-weight:600;border-bottom-color:#4361ee}
.nv .brand{color:#1a1a2e;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
font-size:12px;border:0}
.nv .brand:hover{border-bottom-color:transparent}
.nv .sp{flex:1}
.nv .env{color:#94a3b8;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
</style>
<nav class="nv" aria-label="Sections du cockpit">
<a class="brand" href="/">Cockpit</a>
<a href="/" __A_ACCUEIL__>Accueil</a>
<a href="/cv/" __A_ATELIER__>Profil &amp; CV</a>
<a href="/cms" __A_CMS__>Profil</a>
<a href="/edit" __A_EDIT__>JSON brut</a>
<a href="/career-ops" __A_CAREER__>Ergon &middot; career-ops</a>
<a href="/anthropos" __A_ANTHROPOS__>Anthropos</a>
<span class="sp"></span><span class="env">reseau prive</span>
</nav>"""

_PAGES = (("__A_ACCUEIL__", "accueil"), ("__A_ATELIER__", "atelier"), ("__A_CMS__", "cms"),
          ("__A_EDIT__", "edit"), ("__A_CAREER__", "career-ops"), ("__A_ANTHROPOS__", "anthropos"))

BASE_CSS = ("body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:1100px;margin:24px auto;"
            "padding:0 16px;color:#1a1a2e}h1{font-size:22px}h2{font-size:16px}a{color:#4361ee}"
            ".cartes{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}"
            ".carte{display:block;border:1px solid #e2e8f0;border-radius:8px;padding:12px;text-decoration:none;color:inherit}"
            ".carte.attention{border-color:#f0ad4e}.carte.erreur{border-color:#c0392b}"
            ".carte ul{margin:6px 0 0;padding-left:18px;font-size:13px}"
            ".ok{color:#159957}.ko{color:#c0392b}.muet{color:#666;font-size:12px}"
            "table{border-collapse:collapse;font-size:13px}td,th{border-bottom:1px solid #e2e8f0;padding:4px 8px;text-align:left}"
            "pre{background:#f6f7fb;padding:10px;overflow:auto;font-size:12px}"
            "button{padding:6px 12px;border:1px solid #ccd;border-radius:6px;background:#fff;cursor:pointer}")


def render(template: str, token: str, profile_raw: str | None = None, page: str = "") -> str:
    """Ordre = invariant de sécurité : nav et jeton d'abord, profil (échappé) en dernier."""
    nav = NAV
    for cle, ident in _PAGES:
        nav = nav.replace(cle, 'aria-current="page"' if page == ident else "")
    out = template.replace("__NAV__", nav).replace("__TOKEN__", json.dumps(token))
    if profile_raw is not None:
        out = out.replace("__PROFILE__", json.dumps(profile_raw).replace("<", "\\u003c"))
    return out


def page(titre: str, corps: str, token: str, page_id: str, head: str = "") -> str:
    """Page complète pour les pages neuves. Le corps est inséré APRÈS le rendu des marqueurs :
    une donnée qui contiendrait `__TOKEN__` ne reçoit jamais le jeton."""
    coquille = ("<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
                f"<title>{html.escape(titre)} — Cockpit</title><style>{BASE_CSS}</style>{head}</head>"
                "<body>__NAV__<script>const TOKEN=__TOKEN__;</script><main>__CORPS__</main></body></html>")  # elysium:allow-secret reason="marqueur __TOKEN__ substitué par render(), aucune valeur ici"
    return render(coquille, token, page=page_id).replace("__CORPS__", corps, 1)
