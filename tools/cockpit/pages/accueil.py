"""Accueil : une carte par espace. Chaque page qui possède une donnée fournit sa carte
(CARTES) ; L2 et L3 ajoutent career-ops et Anthropos. Une carte en erreur s'affiche en
erreur — jamais masquée derrière un zéro (spec § 8)."""
from __future__ import annotations

import html
import json
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
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


# Les cartes réseau (Anthropos, career-ops) se calculent en parallèle, dans un budget : hub
# injoignable mesuré à 11,3 s par GET / (la résolution DNS d'un nom .local échappe au délai
# d'urlopen). Une carte hors budget dit qu'elle n'a pas répondu ; elle ne retient pas la page.
DELAI_CARTES_S = 2.0


def _carte_sans_reponse(f) -> dict:
    return {"titre": getattr(f, "titre", f.__name__), "href": getattr(f, "href", "/"), "etat": "attention",
            "lignes": [f"pas de réponse en {DELAI_CARTES_S} s : la page détaillée dit pourquoi"]}


def _carte_en_erreur(f, exc: BaseException) -> dict:
    return {"titre": getattr(f, "titre", f.__name__), "href": getattr(f, "href", "/"), "etat": "erreur",
            "lignes": [f"{type(exc).__name__}: {exc}"]}


def _cartes() -> list[dict]:
    """Une carte par fonction de CARTES, dans l'ordre ; jamais plus de DELAI_CARTES_S d'attente."""
    pool = ThreadPoolExecutor(max_workers=max(len(CARTES), 1), thread_name_prefix="carte")
    futurs = [(f, pool.submit(f)) for f in CARTES]
    fin = time.monotonic() + DELAI_CARTES_S
    cartes = []
    for f, futur in futurs:
        try:
            cartes.append(futur.result(timeout=max(fin - time.monotonic(), 0)))
        except FuturesTimeout:
            cartes.append(_carte_sans_reponse(f))
        except Exception as exc:  # une carte qui casse s'affiche en erreur (spec § 8), la page reste servie
            cartes.append(_carte_en_erreur(f, exc))
    pool.shutdown(wait=False, cancel_futures=True)   # une sonde bloquée finit seule, sans retenir la réponse
    return cartes


def page_accueil(h) -> None:
    corps = "<h1>Cockpit</h1><div class=\"cartes\">" + "".join(_carte_html(c) for c in _cartes()) + "</div>"
    h._send(200, "text/html; charset=utf-8", layout.page("Accueil", corps, h.token(), "accueil").encode("utf-8"))
