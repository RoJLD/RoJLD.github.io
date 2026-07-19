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


# ── D : édition profile.json (save_profile_edit) — pas de Playwright ────────────

def test_save_valid_writes(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"old":1}', encoding="utf-8")
    res = atelier.save_profile_edit('{"$version":"1","new":2}', p, validate_fn=lambda d: [])
    assert res["ok"] and res["errors"] == []
    assert json.loads(p.read_text(encoding="utf-8"))["new"] == 2


def test_save_invalid_json_no_write(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"keep":1}', encoding="utf-8")
    res = atelier.save_profile_edit("{bad json", p, validate_fn=lambda d: [])
    assert not res["ok"] and any("JSON invalide" in e for e in res["errors"])
    assert p.read_text(encoding="utf-8") == '{"keep":1}'  # intact


def test_save_validation_errors_no_write(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"keep":1}', encoding="utf-8")
    res = atelier.save_profile_edit('{"x":1}', p, validate_fn=lambda d: ["missing domains", "bad radar"])
    assert not res["ok"] and res["errors"] == ["missing domains", "bad radar"]
    assert p.read_text(encoding="utf-8") == '{"keep":1}'  # intact


def test_save_rejects_non_dict(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text("{}", encoding="utf-8")
    res = atelier.save_profile_edit("[1,2,3]", p, validate_fn=lambda d: [])
    assert not res["ok"]


# ── Sous-projet D : routes du CMS (édition structurée) ────────────────────────

import contextlib
import http.server
import threading
import urllib.error
import urllib.request


@contextlib.contextmanager
def _server():
    """Lance le Handler de l'atelier sur un port éphémère, le temps du test."""
    srv = http.server.HTTPServer(("127.0.0.1", 0), atelier.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_cms_route_serves_page_with_real_profile_embedded():
    """Le CMS charge le profil ENTIER : c'est ce qui permet de le resoumettre
    entier et de ne perdre aucune clé non modélisée."""
    with _server() as base:
        code, body = _get(base, "/cms")
    assert code == 200
    assert "CMS" in body
    assert "experiences" in body and "ALTEN" in body   # vrai profile.json embarqué


def test_cms_model_asset_is_served():
    with _server() as base:
        code, body = _get(base, "/assets/js/cms-model.js")
    assert code == 200 and "CMSModel" in body


def test_static_allowlist_refuses_everything_else():
    """Allowlist stricte : aucun chemin arbitraire n'atteint le disque."""
    with _server() as base:
        for path in ("/assets/js/../../profile.json", "/profile.json",
                     "/assets/js/cv-render.js", "/../atelier.py"):
            code, _ = _get(base, path)
            assert code == 404, path


def test_home_links_to_cms():
    with _server() as base:
        code, body = _get(base, "/")
    assert code == 200 and "/cms" in body
