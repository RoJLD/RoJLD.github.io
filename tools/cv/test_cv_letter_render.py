"""K5 — rendu HTML de la lettre + porte d'export.

Écart au spec, mesuré : le diagramme §2 fait converger CV et LETTRE vers
`render_html`, mais `cv_render.render_html` ne sait rendre qu'un `structured_cv`,
et la liste « Créer » du §5 ne mentionne AUCUN renderer de lettre. Par ailleurs
`build_css`, que l'audit déclare réutilisable, **n'existe pas encore** (0 hit
dans le dépôt au 2026-07-28) : c'est un livrable du plan A. Ce module apporte
donc son propre moteur CSS piloté par la donnée, de même forme (`style`), pour
que la convergence soit possible sans réécriture le jour où `build_css` atterrit.
"""
from __future__ import annotations

import json
import re

import pytest

import cv_grounding
import cv_letter_render


DOC = {
    "lang": "fr",
    "identity": {"name": "Ada Lovelace", "email": "ada@example.org",
                 "location": "Paris, France", "linkedin": "https://linkedin.com/in/ada"},
    "recipient": {"company": "Nexora Capital"},
    "date": "2026-07-28",
    "subject": "Candidature — Ingénieur Quantitatif",
    "paragraphs": ["Premier paragraphe.", "Deuxième paragraphe."],
    "signature": "Ada Lovelace",
}


def _ok_verdict():
    return {"ok": True, "claims": [], "sentences": [], "blocking": [],
            "coverage": {"phrases": 0, "rattachees": 0, "complete": True}}


def _blocked_verdict():
    return {"ok": False, "claims": [], "sentences": ["J'ai dirigé cinq personnes."],
            "blocking": [{"reason": "affirmation_non_supportee", "phrase": 1,
                          "affirmation": "J'ai dirigé cinq personnes.", "source": None}],
            "coverage": {"phrases": 1, "rattachees": 1, "complete": True}}


# ── moteur CSS piloté par la donnée ────────────────────────────────────────────

def test_css_follows_the_style_data():
    style = json.loads(json.dumps(cv_letter_render.LETTER_STYLE))
    style["palette"]["accent"] = "#ff0000"
    css = cv_letter_render.build_letter_css(style)
    assert "#ff0000" in css
    assert cv_letter_render.LETTER_STYLE["palette"]["accent"] not in css


def test_css_tolerates_a_partial_style():
    css = cv_letter_render.build_letter_css({"palette": {"ink": "#000000"}})
    assert "#000000" in css
    assert cv_letter_render.LETTER_STYLE["type"]["base"] in css   # défauts conservés


def test_css_is_deterministic():
    assert cv_letter_render.build_letter_css(cv_letter_render.LETTER_STYLE) == \
           cv_letter_render.build_letter_css(cv_letter_render.LETTER_STYLE)


# ── rendu ──────────────────────────────────────────────────────────────────────

def test_render_produces_a_standalone_a4_document():
    html = cv_letter_render.render_letter_html(DOC)
    assert html.startswith("<!doctype html>")
    assert '<html lang="fr">' in html
    assert "@page" in html and "A4" in html
    assert "http://" not in html.replace("https://linkedin.com", "")   # zéro requête externe


def test_render_keeps_paragraph_order_and_count():
    html = cv_letter_render.render_letter_html(DOC)
    paras = re.findall(r"<p class=\"lt-p\">(.*?)</p>", html, flags=re.S)
    assert paras == ["Premier paragraphe.", "Deuxième paragraphe."]


def test_render_escapes_html():
    doc = dict(DOC, paragraphs=["<script>alert(1)</script> & co"])
    html = cv_letter_render.render_letter_html(doc)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html


def test_render_omits_absent_optional_fields():
    doc = dict(DOC, date=None, recipient={"company": None})
    html = cv_letter_render.render_letter_html(doc)
    # la classe existe toujours dans la feuille de style ; c'est le MARQUAGE qui
    # doit disparaître.
    assert '<p class="lt-date">' not in html
    assert '<p class="lt-recipient">' not in html
    assert not re.search(r"\[[A-Za-zÀ-ÿ]", html)      # aucun gabarit non rempli


def test_render_never_emits_a_phone():
    doc = json.loads(json.dumps(DOC))
    doc["identity"]["phone"] = "+33 6 00 00 00 00"     # même si l'amont fautait
    assert "+33" not in cv_letter_render.render_letter_html(doc)


def test_render_is_deterministic():
    assert cv_letter_render.render_letter_html(DOC) == cv_letter_render.render_letter_html(DOC)


def test_render_refuses_a_document_without_paragraphs():
    with pytest.raises(ValueError):
        cv_letter_render.render_letter_html(dict(DOC, paragraphs=[]))


# ── la PORTE d'export ──────────────────────────────────────────────────────────

def test_gated_render_passes_on_a_green_verdict():
    html = cv_letter_render.render_letter_html_gated(DOC, _ok_verdict())
    assert "Premier paragraphe." in html


def test_gated_render_blocks_on_a_red_verdict():
    with pytest.raises(cv_grounding.GroundingBlocked) as exc:
        cv_letter_render.render_letter_html_gated(DOC, _blocked_verdict())
    assert exc.value.verdict["blocking"][0]["reason"] == "affirmation_non_supportee"


def test_gated_render_blocks_on_a_missing_verdict():
    """Fail-safe inversé : pas de verdict = pas de sortie. Un appelant qui
    « oublie » de vérifier ne doit pas obtenir une lettre."""
    for bad in (None, {}, {"ok": None}, "vert"):
        with pytest.raises(cv_grounding.GroundingBlocked):
            cv_letter_render.render_letter_html_gated(DOC, bad)


def test_gate_never_rewrites_the_letter():
    html = cv_letter_render.render_letter_html_gated(DOC, _ok_verdict())
    assert html == cv_letter_render.render_letter_html(DOC)
