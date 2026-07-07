"""Smoke tests atelier local (cv_pdf + atelier.generate_pdf). Nécessite Playwright."""
from __future__ import annotations

import json

import atelier
import cv_pdf


def test_html_to_pdf_bytes_smoke():
    pdf = cv_pdf.html_to_pdf_bytes("<!doctype html><html><body><h1>Hello Robin</h1></body></html>")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_generate_pdf_targeted_pipeline():
    profile = {
        "$updated": "2026-07-07",
        "identity": {"first_name": "Robin", "last_name": "Denis"},
        "skills": {"programming": [{"name": "Python"}]},
        "domains": [{"id": "quant", "label": {"fr": "Quant", "en": "Quant"}},
                    {"id": "risk", "label": {"fr": "Risk", "en": "Risk"}}],
        "experiences": [
            {"id": "a", "company": "ALTEN", "title": {"fr": "Quant", "en": "Quant"},
             "start": "2024", "current": True, "domains": ["quant"],
             "relevance": {"quant": 0.95, "risk": 0.3, "general": 0.6},
             "bullets": {"fr": ["Modèles Vasicek"], "en": ["Vasicek models"]}},
            {"id": "b", "company": "ManCo", "title": {"fr": "Risk", "en": "Risk"},
             "start": "2021", "current": False, "domains": ["risk"],
             "relevance": {"quant": 0.2, "risk": 0.9, "general": 0.4},
             "bullets": {"fr": ["Stress tests"], "en": ["Stress tests"]}},
        ],
    }
    fake = lambda _p: json.dumps({"relevance_key": "quant", "min_relevance": 0.9, "domains_in": ["quant"]})
    cfg, pdf = atelier.generate_pdf("Quant developer Python", profile, "en", complete_fn=fake)
    assert cfg["relevance_key"] == "quant"
    assert pdf[:4] == b"%PDF"
    # le PDF ciblé quant ne contient que ALTEN (quant>=0.9), pas ManCo
    from pypdf import PdfReader
    import io
    txt = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "ALTEN" in txt and "ManCo" not in txt
    assert "Vasicek models" in txt
