"""Les points d'entrée de la projection D8 : sauvegarde gouvernée, page /career-ops, route,
carte d'accueil, overlay du .docx."""
import json
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures_cv import COMPLEMENT_BRUT  # noqa: E402
from test_cockpit_page_career_ops import _Srv, configure  # noqa: E402,F401
from tools.cockpit import career_ops as co, complement, config, projection  # noqa: E402
from tools.cockpit.pages import career_ops as page  # noqa: E402
from tools.cockpit.pages import cv as page_cv  # noqa: E402


def _res(etat="en_retard", erreurs=None, cv_err=None, yml=None):
    return {"ok": not erreurs and not cv_err, "erreurs": erreurs or [],
            "cv_md": None if erreurs else {"etat": etat, "diff": "-a\n+b\n", "ecrit": False, "sauvegarde": None, "erreur": cv_err},
            "profile_yml": None if erreurs else {"changements": yml or [], "ecrit": False, "erreur": None}}


class _H:
    def __init__(self):
        self.reponses = []
    def _send(self, code, ctype, body):
        self.reponses.append((code, json.loads(body)))


def test_la_sauvegarde_gouvernee_porte_l_etape_career_ops(monkeypatch):
    import profile_pipeline
    monkeypatch.setattr(profile_pipeline, "govern_save", lambda *a, **k: {"ok": True, "stages": {}})
    monkeypatch.setattr(page_cv, "_regen_bank", lambda: None)
    monkeypatch.setattr(projection, "etape_sauvegarde", lambda: {"ok": True, "etat": "en_retard", "ecrit": True,
                                                                  "yml": [], "message": ""})
    h = _H()
    page_cv.handle_save(h, {"govern": True, "json": "{}"})
    assert h.reponses[0][1]["stages"]["career_ops"]["ok"] is True


def test_le_js_des_deux_pages_affiche_l_etape():
    assert "s.career_ops" in page_cv._EDIT and "s.career_ops" in page_cv._CMS


def test_la_page_montre_le_panneau_et_les_boutons(configure, monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: _res("modifie"))
    with _Srv() as s:
        code, body = s.get("/career-ops")
    assert code == 200 and "CV pour career-ops" in body and "modifié à la main" in body
    assert 'data-projeter="diff"' in body and 'data-projeter="forcer"' in body


def test_pas_de_remplacer_quand_meme_si_en_retard(configure, monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: _res("en_retard", yml=["candidate.phone"]))
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert 'data-projeter="forcer"' not in body and "candidate.phone" in body


def test_le_complement_absent_est_dit_sans_bouton(configure, monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: _res(erreurs=["complément privé : x absent"]))
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert "complément privé : x absent" in body and 'data-projeter="ecrire"' not in body


def test_route_forcer_sans_ecrire_400(configure):
    with _Srv() as s:
        code, body = s.post("/career-ops/projeter", {"forcer": True})
    assert code == 400 and "forcer exige ecrire" in body


@pytest.mark.parametrize("res, code", [(_res("a_jour"), 200), (_res("modifie", cv_err="refus"), 409),
                                       (_res(erreurs=["complément privé : absent"]), 503)])
def test_route_projeter_codes(configure, monkeypatch, res, code):
    vu = {}
    monkeypatch.setattr(projection, "projeter", lambda **k: vu.update(k) or res)
    with _Srv() as s:
        c, body = s.post("/career-ops/projeter", {"ecrire": True})
    assert c == code and vu == {"ecrire": True, "forcer": False} and json.loads(body)["cv_md"] == res["cv_md"]


def test_la_carte_d_accueil_dit_l_etat_de_cv_md(configure, monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: _res("a_jour"))
    assert "cv.md : à jour" in page.carte_career_ops()["lignes"]


def test_le_docx_prend_le_telephone_du_complement(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cv_private.json").write_text(json.dumps(COMPLEMENT_BRUT), encoding="utf-8")
    monkeypatch.setattr(config, "career_ops_root", lambda env=None, local_json=None: tmp_path)
    monkeypatch.setattr(complement, "est_ignore", lambda root, rel=complement.REL, run=None: True)
    assert page_cv._overlay_prive() == {"phone": "+44 0", "availability": {"fr": "", "en": ""}}
