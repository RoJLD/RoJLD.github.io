"""Onglet « Site » : l'aperçu éditable de robin-denis.com (édition du site, A1)."""
from __future__ import annotations

import html

from tools.cockpit.pages import layout


def page_site(h) -> None:
    # Import À L'APPEL : server.py importe ce module avant de définir Handler, et apercu
    # hérite de server.Handler. Un import en tête ferait planter le démarrage du cockpit.
    from tools.cockpit import apercu
    etat = apercu.ETAT
    if etat["actif"]:
        url = f"http://127.0.0.1:{etat['port']}/"
        corps = (f'<p class="muet">Aperçu local du site, avec le calque d\'édition (bouton « Éditer » '
                 f'en bas à droite). <a href="{url}" target="_blank" rel="noopener">Ouvrir dans un onglet</a></p>'
                 f'<iframe src="{url}" title="Aperçu du site" '
                 f'style="width:100%;height:80vh;border:1px solid #e2e8f0;border-radius:8px"></iframe>')
    else:
        corps = f'<p class="ko">Aperçu indisponible : {html.escape(str(etat["erreur"] or "non démarré"))}</p>'
    h._send(200, "text/html; charset=utf-8",
            layout.page("Site", "<h1>Site</h1>" + corps, h.token(), "site").encode("utf-8"))
