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
@page { size: A4; margin: 12mm 14mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: #1a1a2e;
       font-size: 9.8pt; line-height: 1.3; margin: 0; }
.cv-header { border-bottom: 2px solid #4361ee; padding-bottom: 5px; margin-bottom: 9px; }
.cv-name { font-size: 17pt; font-weight: 700; margin: 0; }
.cv-title { font-size: 10.5pt; color: #4361ee; margin: 1px 0 0; }
.cv-contact { font-size: 8.5pt; color: #555; margin-top: 3px; }
.cv-section { margin-bottom: 7px; page-break-inside: avoid; }
.cv-exp-head { display: flex; justify-content: space-between; font-weight: 600; }
.cv-exp-company { color: #16213e; }
.cv-exp-dates { color: #777; font-size: 8.5pt; font-weight: 400; white-space: nowrap; }
.cv-exp-title { font-style: italic; color: #444; font-size: 9pt; margin-bottom: 2px; }
ul.cv-bullets { margin: 2px 0 0; padding-left: 15px; }
ul.cv-bullets li { margin-bottom: 1px; }
.cv-skills { margin-top: 4px; font-size: 9pt; }
.cv-skills strong { color: #4361ee; }
.cv-footer { margin-top: 8px; font-size: 8pt; color: #999; text-align: right; }
.cv-h2 { font-size: 10.5pt; color: #4361ee; margin: 0 0 4px; border-bottom: 1px solid #dde; padding-bottom: 2px; }
.cv-edu-head { display: flex; justify-content: space-between; font-weight: 600; }
.cv-edu-school { color: #16213e; }
.cv-edu-meta { font-size: 9pt; color: #444; margin-top: 1px; }
.cv-extra { margin-top: 3px; font-size: 9pt; }
.cv-extra strong { color: #4361ee; }
"""

_LABELS = {
    "fr": {"skills": "Compétences", "updated": "Mis à jour", "education": "Formation",
           "languages": "Langues", "certifications": "Certifications",
           "interests": "Centres d'intérêt"},
    "en": {"skills": "Skills", "updated": "Updated", "education": "Education",
           "languages": "Languages", "certifications": "Certifications",
           "interests": "Interests"},
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
    # Ligne de contact : localisation • email • linkedin • github. Le TÉLÉPHONE
    # n'y figure jamais (build_structured_cv ne le projette pas) : les préfabriqués
    # sont servis publiquement sur GitHub Pages.
    contact = " • ".join(x for x in (idy.get("location", ""), idy.get("email", ""),
                                     idy.get("linkedin", ""), idy.get("github", "")) if x)
    if contact:
        parts.append(f'<p class="cv-contact">{_esc(contact)}</p>')
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

    # Formation (education) — après les expériences, comme le CV ATS de référence
    education = structured_cv.get("education", [])
    if education:
        parts.append('<section class="cv-section">')
        parts.append(f'<h2 class="cv-h2">{_esc(lab["education"])}</h2>')
        for e in education:
            parts.append('<div class="cv-edu-head">')
            parts.append(f'<span class="cv-edu-school">{_esc(e.get("school", ""))}</span>')
            parts.append(f'<span class="cv-exp-dates">{_esc(e.get("period", ""))}</span>')
            parts.append("</div>")
            # `title` recouvre souvent `school` dans profile.json ("ECE Paris" vs
            # "ECE Paris, Cycle Ingénieur") : on l'omet alors, sinon le PDF public
            # affiche deux fois le nom de l'école.
            title_txt = e.get("title", "")
            school_txt = e.get("school", "")
            if title_txt and school_txt and title_txt.startswith(school_txt):
                title_txt = ""
            sub = " — ".join(x for x in (title_txt, e.get("org", "")) if x)
            if sub:
                parts.append(f'<div class="cv-exp-title">{_esc(sub)}</div>')
            if e.get("degree"):
                parts.append(f'<div class="cv-edu-meta">{_esc(e["degree"])}</div>')
            courses = e.get("courses", [])
            if courses:
                parts.append(
                    f'<div class="cv-edu-meta"><strong>{_esc(e.get("courses_label", ""))}:</strong> '
                    f'{_esc(" · ".join(str(c) for c in courses))}</div>'
                )
            cap = e.get("capstone")
            if cap:
                cap_txt = " — ".join(x for x in (cap.get("label", ""), cap.get("summary", "")) if x)
                if cap_txt:
                    parts.append(f'<div class="cv-edu-meta">{_esc(cap_txt)}</div>')
        parts.append("</section>")

    # Compétences : une ligne LIBELLÉE par catégorie (lisibilité + structure ATS,
    # comme le CV de référence). Repli sur la liste plate historique si un
    # structured_cv ancien (sans skills_groups) est rendu.
    groups = structured_cv.get("skills_groups")
    if isinstance(groups, list) and groups:
        for g in groups:
            items = g.get("items")
            items = items if isinstance(items, list) else []
            if not items:
                continue
            parts.append(
                f'<p class="cv-skills"><strong>{_esc(g.get("label", ""))}:</strong> '
                f'{_esc(" · ".join(str(i) for i in items))}</p>'
            )
    else:
        skills = structured_cv.get("skills_top", [])
        if skills:
            parts.append(
                f'<p class="cv-skills"><strong>{_esc(lab["skills"])}:</strong> '
                f'{_esc(" · ".join(str(s) for s in skills))}</p>'
            )

    # Compléments : certifications · langues · centres d'intérêt (ordre du CV ATS)
    certs = structured_cv.get("certifications", [])
    if certs:
        parts.append(
            f'<p class="cv-extra"><strong>{_esc(lab["certifications"])}:</strong> '
            f'{_esc(" · ".join(str(c) for c in certs))}</p>'
        )

    languages = structured_cv.get("languages", [])
    if languages:
        lang_items = []
        for lg in languages:
            nm, lvl = lg.get("name", ""), lg.get("level", "")
            item = f"{nm} — {lvl}" if nm and lvl else (nm or lvl)
            if item:
                lang_items.append(item)
        if lang_items:
            parts.append(
                f'<p class="cv-extra"><strong>{_esc(lab["languages"])}:</strong> '
                f'{_esc(" · ".join(lang_items))}</p>'
            )

    interests = structured_cv.get("interests", [])
    if interests:
        parts.append(
            f'<p class="cv-extra"><strong>{_esc(lab["interests"])}:</strong> '
            f'{_esc(" · ".join(str(i) for i in interests))}</p>'
        )

    # Footer
    updated = (structured_cv.get("footer") or {}).get("updated", "")
    if updated:
        parts.append(f'<p class="cv-footer">{_esc(lab["updated"])} {_esc(updated)}</p>')

    parts.append("</body></html>")
    return "".join(parts)
