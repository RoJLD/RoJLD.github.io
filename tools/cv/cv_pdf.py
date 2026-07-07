"""Σ-CV-ATELIER — rendu HTML → PDF bytes via Chromium headless (Playwright).

Helper partagé (atelier local C). Même moteur que la banque préfab B1 (texte réel
ATS-safe), mais retourne les octets au lieu d'écrire un fichier.
"""
from __future__ import annotations


def html_to_pdf_bytes(html: str) -> bytes:
    """Rend un document HTML complet en PDF (A4, fond imprimé) et retourne les octets."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        pdf = page.pdf(format="A4", print_background=True,
                       margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        browser.close()
    return pdf
