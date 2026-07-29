"""K5 — rendu HTML de la lettre, et **porte** d'export.

### L'écart au spec, et pourquoi ce fichier existe

Le diagramme du spec (§2) fait converger CV et LETTRE vers un `render_html`
unique. Mesuré le 2026-07-28 : `cv_render.render_html` ne sait rendre qu'un
`structured_cv` (en-tête, expériences, formation, compétences) — rien d'une
lettre ; et la liste « Créer » du §5 ne mentionne **aucun** renderer de lettre.
L'audit note l'écart et ajoute que `build_css` serait réutilisable car piloté par
la donnée : `grep -rn build_css` rend **0 hit** dans le dépôt — `build_css` est un
livrable du **plan A**, pas encore posé. Ce module apporte donc son propre moteur
CSS, avec la **même forme de donnée** (`style` : `page` / `palette` / `type` /
`density`, cf. spec §3), pour que la convergence se fasse par substitution le
jour où `build_css` atterrit, sans réécrire le rendu.

Pas de miroir JS : l'atelier n'a pas d'aperçu client pour la lettre (`do_GET` ne
sert que `/`, `/edit`, `/cms`). Aucune paire à maintenir, donc aucun cas de
parité à ajouter.

### La porte

`render_letter_html_gated(doc, verdict)` est le seul point d'export prévu : il
n'écrit rien tant que le verdict d'ancrage n'est pas vert, et un verdict absent
ou mal formé vaut refus (fail-safe inversé, ADR-003). Il ne réécrit jamais la
lettre — `render_letter_html_gated(doc, vert)` rend exactement
`render_letter_html(doc)`.
"""
from __future__ import annotations

import html
from typing import Any

import cv_grounding

#: Style par défaut. Même forme que `style` d'un template CV (spec §3), pour que
#: la lettre devienne un template en donnée sans changer de moteur.
LETTER_STYLE: dict[str, dict[str, Any]] = {
    "page": {"size": "A4", "margin": "22mm 20mm"},
    "palette": {"ink": "#1a1a2e", "accent": "#4361ee", "muted": "#555", "rule": "#dde"},
    "type": {"base": "10.5pt", "h1": "13pt", "h2": "11pt", "small": "9pt"},
    "density": {"line": 1.5, "section_gap": "12pt", "para_gap": "9pt"},
}

_LABELS = {
    "fr": {"subject": "Objet"},
    "en": {"subject": "Subject"},
}


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _merged(style: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Fusion à deux niveaux avec les défauts : un `style` partiel est légitime."""
    out = {k: dict(v) for k, v in LETTER_STYLE.items()}
    for group, values in (style or {}).items():
        if group in out and isinstance(values, dict):
            out[group].update(values)
    return out


def build_letter_css(style: dict[str, Any] | None = None) -> str:
    """CSS de la lettre, **piloté par la donnée**. Déterministe."""
    s = _merged(style)
    page, pal, typ, den = s["page"], s["palette"], s["type"], s["density"]
    return f"""\
@page {{ size: {page['size']}; margin: {page['margin']}; }}
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: {pal['ink']};
       font-size: {typ['base']}; line-height: {den['line']}; margin: 0; }}
.lt-head {{ border-bottom: 1px solid {pal['rule']}; padding-bottom: 6px;
       margin-bottom: {den['section_gap']}; }}
.lt-name {{ font-size: {typ['h1']}; font-weight: 700; margin: 0; }}
.lt-contact {{ font-size: {typ['small']}; color: {pal['muted']}; margin-top: 3px; }}
.lt-recipient {{ font-size: {typ['base']}; margin-bottom: {den['para_gap']}; }}
.lt-date {{ font-size: {typ['small']}; color: {pal['muted']}; text-align: right;
       margin-bottom: {den['section_gap']}; }}
.lt-subject {{ font-size: {typ['h2']}; color: {pal['accent']}; font-weight: 600;
       margin: 0 0 {den['section_gap']}; }}
.lt-p {{ margin: 0 0 {den['para_gap']}; text-align: justify; }}
.lt-sign {{ margin-top: {den['section_gap']}; text-align: right; }}
"""


def render_letter_html(letter_doc: dict[str, Any],
                       style: dict[str, Any] | None = None) -> str:
    """Document HTML A4 complet (CSS inline — GitHub Pages, zéro requête externe).

    `letter_doc` = sortie de `cv_letter.build_letter_document`. Aucun champ absent
    n'est comblé par un gabarit : ce qui n'est pas ancré n'est pas rendu.
    """
    paragraphs = [p for p in (letter_doc.get("paragraphs") or []) if str(p).strip()]
    if not paragraphs:
        raise ValueError("lettre sans paragraphe — rien à rendre")

    lang = letter_doc.get("lang") or "fr"
    lab = _LABELS.get(lang, _LABELS["fr"])
    idy = letter_doc.get("identity") or {}
    recipient = letter_doc.get("recipient") or {}

    parts: list[str] = [
        f'<!doctype html><html lang="{_esc(lang)}"><head><meta charset="utf-8">',
        f"<style>{build_letter_css(style)}</style></head><body>",
        '<header class="lt-head">',
        f'<h1 class="lt-name">{_esc(idy.get("name", ""))}</h1>',
    ]
    # Ligne de contact : le TÉLÉPHONE n'y figure jamais — la projection ne le
    # porte pas, et le rendu ne le lit pas davantage (double garde : le dépôt est
    # public et la lettre part en PDF chez un tiers).
    contact = " • ".join(x for x in (idy.get("location", ""), idy.get("email", ""),
                                     idy.get("linkedin", "")) if x)
    if contact:
        parts.append(f'<p class="lt-contact">{_esc(contact)}</p>')
    parts.append("</header>")

    if recipient.get("company"):
        parts.append(f'<p class="lt-recipient">{_esc(recipient["company"])}</p>')
    if letter_doc.get("date"):
        parts.append(f'<p class="lt-date">{_esc(letter_doc["date"])}</p>')
    if letter_doc.get("subject"):
        parts.append(f'<p class="lt-subject">{_esc(lab["subject"])} : '
                     f'{_esc(letter_doc["subject"])}</p>')

    parts.extend(f'<p class="lt-p">{_esc(p)}</p>' for p in paragraphs)

    if letter_doc.get("signature"):
        parts.append(f'<p class="lt-sign">{_esc(letter_doc["signature"])}</p>')
    parts.append("</body></html>")
    return "".join(parts)


def render_letter_html_gated(letter_doc: dict[str, Any], verdict: Any,
                             style: dict[str, Any] | None = None) -> str:
    """Rendu **sous condition** du verdict d'ancrage. Porte, pas filtre.

    Un verdict absent, non-dict, ou dont `ok` n'est pas exactement `True` refuse
    l'export : un appelant qui oublie de vérifier ne doit pas obtenir de lettre.
    """
    if not isinstance(verdict, dict) or verdict.get("ok") is not True:
        raise cv_grounding.GroundingBlocked(
            verdict if isinstance(verdict, dict)
            else {"ok": False, "blocking": [{"reason": "verdict_absent", "phrase": None,
                                             "affirmation": "", "source": None}]})
    return render_letter_html(letter_doc, style)
