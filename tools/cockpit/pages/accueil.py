"""Accueil : une carte par espace. Chaque page qui possède une donnée fournit sa carte
(CARTES) ; L2 et L3 ajoutent career-ops et Anthropos. Une carte en erreur s'affiche en
erreur — jamais masquée derrière un zéro (spec § 8)."""
from __future__ import annotations

import html
import json
from typing import Callable

from tools.cockpit.pages import layout

CARTES: list[Callable[[], dict]] = []


def carte_profil() -> dict:
    from tools.cockpit.pages import cv  # import tardif : les tests rebindent cv._PROFILE
    try:
        p = json.loads(cv._PROFILE.read_text(encoding="utf-8"))
        return {"titre": "Profil & CV", "href": "/cv/", "etat": "ok",
                "lignes": [p["identity"]["status"]["fr"], f"mis à jour {p.get('$updated', '?')}",
                           f"{len(p.get('experiences', []))} expériences · {len(p.get('projects', []))} projets"]}
    except Exception as exc:
        return {"titre": "Profil & CV", "href": "/cv/", "etat": "erreur",
                "lignes": [f"profile.json illisible : {type(exc).__name__}: {exc}"]}


CARTES.append(carte_profil)


def _carte_html(c: dict) -> str:
    lignes = "".join(f"<li>{html.escape(str(l))}</li>" for l in c["lignes"])
    return (f'<a class="carte {html.escape(c["etat"])}" href="{html.escape(c["href"])}">'
            f'<h2>{html.escape(c["titre"])}</h2><ul>{lignes}</ul></a>')


def page_accueil(h) -> None:
    corps = "<h1>Cockpit</h1><div class=\"cartes\">" + "".join(_carte_html(f()) for f in CARTES) + "</div>"
    h._send(200, "text/html; charset=utf-8", layout.page("Accueil", corps, h.token(), "accueil").encode("utf-8"))
