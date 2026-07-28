#!/usr/bin/env python3
"""cv_templates.py — banque de templates CV, pilotée par des données.

Un template est un fichier `cv/templates/<id>.json` : `style` est ce que le moteur
consomme, `meta` ce que le ciblage lit pour choisir. Ajouter un design coûte un
fichier de données, jamais deux implémentations — le rendu du CV existe en paire
miroir Python/JS, et dupliquer un gabarit en code coûterait 2N artefacts à tenir
synchronisés.

Miroir : `assets/js/cv-templates.js` doit reproduire `build_css` à l'octet.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "cv" / "templates"
DEFAUT = "sobre"

_META_REQUIS = ("pages", "market", "tone", "ats_safe", "sections")
_STYLE_REQUIS = ("page", "palette", "type", "density")


class TemplateError(Exception):
    pass


def _val(style: dict, groupe: str, cle: str):
    """Accès fail-loud à `style`.

    Un `.get(cle, "")` produirait un CSS syntaxiquement valide mais silencieusement
    dégradé — une couleur vide passe inaperçue à la lecture et ne casse aucun test
    de forme. On nomme donc la clé absente.
    """
    bloc = style.get(groupe)
    if not isinstance(bloc, dict):
        raise TemplateError(f"style.{groupe} manquant ou mal formé")
    if cle not in bloc:
        raise TemplateError(f"style.{groupe}.{cle} manquant")
    return bloc[cle]


def build_css(style: dict) -> str:
    """Assemble les 23 règles du CV depuis `style`.

    Les espacements structurels (en-tête, puces, pied) restent littéraux : seuls
    varient la page, la palette, l'échelle typographique et le rythme vertical
    (`density`), qui sont les leviers réels d'un design de CV.
    """
    if not isinstance(style, dict):
        raise TemplateError("style doit être un objet")

    size = _val(style, "page", "size")
    marge = _val(style, "page", "margin")

    ink = _val(style, "palette", "ink")
    ink_2 = _val(style, "palette", "ink_2")
    accent = _val(style, "palette", "accent")
    corps = _val(style, "palette", "body")
    muted = _val(style, "palette", "muted")
    faint = _val(style, "palette", "faint")
    faint_2 = _val(style, "palette", "faint_2")
    rule = _val(style, "palette", "rule")

    h1 = _val(style, "type", "h1")
    h2 = _val(style, "type", "h2")
    base = _val(style, "type", "base")
    small = _val(style, "type", "small")
    tiny = _val(style, "type", "tiny")
    micro = _val(style, "type", "micro")

    line = _val(style, "density", "line")
    section_gap = _val(style, "density", "section_gap")
    bullet_gap = _val(style, "density", "bullet_gap")

    return (
        f"@page {{ size: {size}; margin: {marge}; }}\n"
        f"* {{ box-sizing: border-box; }}\n"
        f'body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; color: {ink};\n'
        f"       font-size: {base}; line-height: {line}; margin: 0; }}\n"
        f".cv-header {{ border-bottom: 2px solid {accent}; padding-bottom: 5px; margin-bottom: 9px; }}\n"
        f".cv-name {{ font-size: {h1}; font-weight: 700; margin: 0; }}\n"
        f".cv-title {{ font-size: {h2}; color: {accent}; margin: 1px 0 0; }}\n"
        f".cv-contact {{ font-size: {tiny}; color: {muted}; margin-top: 3px; }}\n"
        f".cv-section {{ margin-bottom: {section_gap}; page-break-inside: avoid; }}\n"
        f".cv-exp-head {{ display: flex; justify-content: space-between; font-weight: 600; }}\n"
        f".cv-exp-company {{ color: {ink_2}; }}\n"
        f".cv-exp-dates {{ color: {faint}; font-size: {tiny}; font-weight: 400; white-space: nowrap; }}\n"
        f".cv-exp-title {{ font-style: italic; color: {corps}; font-size: {small}; margin-bottom: 2px; }}\n"
        f"ul.cv-bullets {{ margin: 2px 0 0; padding-left: 15px; }}\n"
        f"ul.cv-bullets li {{ margin-bottom: {bullet_gap}; }}\n"
        f".cv-skills {{ margin-top: 4px; font-size: {small}; }}\n"
        f".cv-skills strong {{ color: {accent}; }}\n"
        f".cv-footer {{ margin-top: 8px; font-size: {micro}; color: {faint_2}; text-align: right; }}\n"
        f".cv-h2 {{ font-size: {h2}; color: {accent}; margin: 0 0 4px; border-bottom: 1px solid {rule}; padding-bottom: 2px; }}\n"
        f".cv-edu-head {{ display: flex; justify-content: space-between; font-weight: 600; }}\n"
        f".cv-edu-school {{ color: {ink_2}; }}\n"
        f".cv-edu-meta {{ font-size: {small}; color: {corps}; margin-top: 1px; }}\n"
        f".cv-extra {{ margin-top: 3px; font-size: {small}; }}\n"
        f".cv-extra strong {{ color: {accent}; }}\n"
    )


def _valide(t: dict, tid: str) -> dict:
    for champ in ("id", "label", "meta", "style"):
        if champ not in t:
            raise TemplateError(f"{tid} : `{champ}` manquant")

    meta = t["meta"]
    if not isinstance(meta, dict):
        raise TemplateError(f"{tid} : meta mal formé")
    for champ in _META_REQUIS:
        if champ not in meta:
            raise TemplateError(f"{tid} : meta.{champ} manquant")
    if not isinstance(meta["sections"], list) or not meta["sections"]:
        raise TemplateError(f"{tid} : meta.sections doit être une liste non vide")

    style = t["style"]
    if not isinstance(style, dict):
        raise TemplateError(f"{tid} : style mal formé")
    for groupe in _STYLE_REQUIS:
        if groupe not in style:
            raise TemplateError(f"{tid} : style.{groupe} manquant")
    return t


def charger(template_id: str) -> dict:
    """Lit et valide un template. Fail-loud si inconnu ou incomplet."""
    chemin = TEMPLATES / f"{template_id}.json"
    if not chemin.is_file():
        raise TemplateError(f"template inconnu : {template_id!r} ({chemin} introuvable)")
    try:
        t = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"{template_id} : JSON invalide — {exc}") from exc
    return _valide(t, template_id)


def lister() -> list[dict]:
    """Tous les templates, triés par id, chacun validé."""
    if not TEMPLATES.is_dir():
        raise TemplateError(f"répertoire de templates introuvable : {TEMPLATES}")
    return [charger(p.stem) for p in sorted(TEMPLATES.glob("*.json"))]
