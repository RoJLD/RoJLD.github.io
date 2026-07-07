"""Σ-CV-ATELIER sous-projet A — rendu HTML depuis structured_cv.

`render_html(structured_cv) -> str` : produit un document HTML A4 print-safe.
La construction est explicite et déterministe (pas de moteur de template) pour
que l'implémentation JS client-side (assets/js/cv-render.js) puisse la MIROITER
à l'octet près sur le même `structured_cv` (garde-fou anti-divergence — testé
séparément). CSS inline (contrainte GitHub Pages : aucune requête externe).
"""
from __future__ import annotations

import html
from typing import Any

CV_CSS = """\
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1a2e;
       font-size: 10.5pt; line-height: 1.45; margin: 0; }
.cv-header { border-bottom: 2px solid #4361ee; padding-bottom: 8px; margin-bottom: 14px; }
.cv-name { font-size: 20pt; font-weight: 700; margin: 0; }
.cv-title { font-size: 11pt; color: #4361ee; margin: 2px 0 0; }
.cv-contact { font-size: 9pt; color: #555; margin-top: 4px; }
.cv-section { margin-bottom: 12px; page-break-inside: avoid; }
.cv-exp-head { display: flex; justify-content: space-between; font-weight: 600; }
.cv-exp-company { color: #16213e; }
.cv-exp-dates { color: #777; font-size: 9pt; font-weight: 400; white-space: nowrap; }
.cv-exp-title { font-style: italic; color: #444; font-size: 9.5pt; margin-bottom: 3px; }
ul.cv-bullets { margin: 3px 0 0; padding-left: 16px; }
ul.cv-bullets li { margin-bottom: 2px; }
.cv-skills { margin-top: 10px; font-size: 9.5pt; }
.cv-skills strong { color: #4361ee; }
.cv-footer { margin-top: 16px; font-size: 8pt; color: #999; text-align: right; }
"""

_LABELS = {
    "fr": {"skills": "Compétences", "updated": "Mis à jour"},
    "en": {"skills": "Skills", "updated": "Updated"},
}


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def render_html(structured_cv: dict[str, Any]) -> str:
    """Retourne le document HTML complet (doctype + <style> inline)."""
    lang = structured_cv.get("lang", "fr")
    lab = _LABELS.get(lang, _LABELS["fr"])
    idy = structured_cv.get("identity", {})

    parts: list[str] = []
    parts.append(f'<!doctype html><html lang="{_esc(lang)}"><head><meta charset="utf-8">')
    parts.append(f"<style>{CV_CSS}</style></head><body>")

    # Header
    parts.append('<header class="cv-header">')
    parts.append(f'<h1 class="cv-name">{_esc(idy.get("name", ""))}</h1>')
    if idy.get("title"):
        parts.append(f'<p class="cv-title">{_esc(idy["title"])}</p>')
    if idy.get("email"):
        parts.append(f'<p class="cv-contact">{_esc(idy["email"])}</p>')
    parts.append("</header>")

    # Sections (expériences)
    for sec in structured_cv.get("sections", []):
        parts.append('<section class="cv-section">')
        parts.append('<div class="cv-exp-head">')
        parts.append(f'<span class="cv-exp-company">{_esc(sec.get("company", ""))}</span>')
        parts.append(f'<span class="cv-exp-dates">{_esc(sec.get("dates", ""))}</span>')
        parts.append("</div>")
        if sec.get("title"):
            parts.append(f'<div class="cv-exp-title">{_esc(sec["title"])}</div>')
        bullets = sec.get("bullets", [])
        if bullets:
            parts.append('<ul class="cv-bullets">')
            parts.extend(f"<li>{_esc(b)}</li>" for b in bullets)
            parts.append("</ul>")
        parts.append("</section>")

    # Skills
    skills = structured_cv.get("skills_top", [])
    if skills:
        parts.append(
            f'<p class="cv-skills"><strong>{_esc(lab["skills"])}:</strong> '
            f'{_esc(" · ".join(str(s) for s in skills))}</p>'
        )

    # Footer
    updated = (structured_cv.get("footer") or {}).get("updated", "")
    if updated:
        parts.append(f'<p class="cv-footer">{_esc(lab["updated"])} {_esc(updated)}</p>')

    parts.append("</body></html>")
    return "".join(parts)
