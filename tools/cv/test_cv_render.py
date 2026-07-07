"""Tests du rendu HTML Σ-CV-ATELIER (sous-projet A)."""
from __future__ import annotations

import cv_render


def _cv(**over):
    base = {
        "lang": "fr",
        "identity": {"name": "Robin Denis", "title": "Quant Dev", "email": "r@x.io"},
        "sections": [
            {"kind": "experience", "company": "ALTEN", "title": "Quant Dev",
             "dates": "2024-09 → présent", "bullets": ["Pilotage CryptoExploration", "Vasicek/CIR"]},
        ],
        "skills_top": ["Python", "C++", "SQL"],
        "footer": {"updated": "2026-07-07"},
    }
    base.update(over)
    return base


def test_document_skeleton_and_lang():
    out = cv_render.render_html(_cv(lang="en"))
    assert out.startswith("<!doctype html>")
    assert '<html lang="en">' in out
    assert "<style>" in out and "@page" in out  # CSS inline
    assert out.rstrip().endswith("</html>")


def test_identity_rendered():
    out = cv_render.render_html(_cv())
    assert "Robin Denis" in out
    assert "Quant Dev" in out
    assert "r@x.io" in out


def test_all_section_fields_present():
    out = cv_render.render_html(_cv())
    assert "ALTEN" in out
    assert "2024-09 → présent" in out
    assert "Pilotage CryptoExploration" in out
    assert "Vasicek/CIR" in out
    assert out.count("<li>") == 2


def test_html_escaping_prevents_injection():
    cv = _cv(sections=[{"kind": "experience", "company": "X&Co", "title": "t",
                        "dates": "d", "bullets": ["<script>alert(1)</script>"]}])
    out = cv_render.render_html(cv)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
    assert "X&amp;Co" in out


def test_skills_and_footer():
    out = cv_render.render_html(_cv())
    assert "Python · C++ · SQL" in out
    assert "Compétences" in out  # label FR
    assert "Mis à jour 2026-07-07" in out


def test_english_labels():
    out = cv_render.render_html(_cv(lang="en"))
    assert "Skills" in out
    assert "Updated" in out


def test_empty_sections_still_valid_doc():
    out = cv_render.render_html(_cv(sections=[], skills_top=[]))
    assert out.startswith("<!doctype html>")
    assert "Robin Denis" in out
    assert "<li>" not in out


def test_deterministic():
    cv = _cv()
    assert cv_render.render_html(cv) == cv_render.render_html(cv)
