"""Gate de la banque de PDF : aucun PDF ne sort d'un profil invalide.

Les 8 `cv/prefab/*.pdf` sont ce que télécharge un recruteur depuis le site. Le
script qui les fabrique ne validait rien et a publié « ALTEN 2026-02 → présent »
un mois après la fin du stage (2026-09-28)."""
from __future__ import annotations

import json

import pytest

import build_cv_bank


def _profil_alten_en_cours(tmp_path):
    reel = json.loads(build_cv_bank._PROFILE.read_text(encoding="utf-8"))
    alten = next(e for e in reel["experiences"] if e["id"] == "alten_2026")
    alten.update({"end": "2026-08", "current": True})
    reel["$updated"] = "2026-07-07"
    src = tmp_path / "profile.json"
    src.write_text(json.dumps(reel, ensure_ascii=False), encoding="utf-8")
    return src


def test_un_poste_en_cours_echu_bloque_la_banque_avant_tout_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(build_cv_bank, "_PROFILE", _profil_alten_en_cours(tmp_path))

    def _jamais(*_a, **_k):
        raise AssertionError("un PDF a été fabriqué malgré un profil invalide")

    monkeypatch.setattr(build_cv_bank, "build", _jamais)
    with pytest.raises(SystemExit, match="alten_2026"):
        build_cv_bank.main(today="2026-09-05")


def test_le_meme_profil_passe_le_gate_avant_la_fin_prevue(tmp_path, monkeypatch):
    """Contre-épreuve : sans elle, un gate qui refuserait tout serait vert."""
    monkeypatch.setattr(build_cv_bank, "_PROFILE", _profil_alten_en_cours(tmp_path))
    appels = []
    monkeypatch.setattr(build_cv_bank, "build", lambda p, c: appels.append(1) or [])
    monkeypatch.setattr(build_cv_bank, "_OUT", tmp_path / "prefab")
    (tmp_path / "prefab").mkdir()
    assert build_cv_bank.main(today="2026-07-20") == 0
    assert appels == [1]
