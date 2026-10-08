"""Filet commun à tools/tests/ et tools/cv/ : aucun test n'écrit hors de son dossier temporaire.

Mesuré à la revue finale de D8 : deux tests de tools/cv/test_atelier.py passaient par la vraie
sauvegarde gouvernée, dont l'étape `career_ops` résout career-ops par CAREER_OPS_ROOT /
tools/cockpit/local.json et réécrivait le VRAI cv.md et le VRAI profile.yml du poste. On ne
remplace pas `config.resoudre_career_ops` (test_cockpit_config le teste) : on ferme la porte
d'écriture, `derive.ecrire_atomique`, par où passent cv.md et profile.yml."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SITE = Path(__file__).resolve().parents[1]
if str(_SITE) not in sys.path:
    sys.path.insert(0, str(_SITE))


def sous(dossier: Path, chemin: Path) -> bool:
    try:
        Path(chemin).resolve().relative_to(Path(dossier).resolve())
    except ValueError:
        return False
    return True


@pytest.fixture(autouse=True)
def _filet_ecriture_hors_tmp(monkeypatch, tmp_path_factory):
    from tools.cockpit import derive

    base = tmp_path_factory.getbasetemp()
    vraie = derive.ecrire_atomique

    def gardee(chemin, octets):
        if not sous(base, chemin):
            raise PermissionError(f"écriture hors du dossier temporaire des tests refusée : {chemin}")
        return vraie(chemin, octets)

    monkeypatch.setattr(derive, "ecrire_atomique", gardee)
