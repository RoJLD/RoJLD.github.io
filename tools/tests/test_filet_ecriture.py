"""Le filet de tools/conftest.py : une écriture de cv.md / profile.yml hors du dossier temporaire
des tests est refusée, une écriture dedans passe (revue finale D8, F1)."""
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import derive  # noqa: E402


def test_une_ecriture_hors_du_dossier_temporaire_est_refusee():
    cible = SITE / "dossier-inexistant-du-filet" / "cv.md"       # jamais créé : le filet refuse avant
    with pytest.raises(PermissionError, match="hors du dossier temporaire des tests"):
        derive.ecrire_atomique(cible, b"x")
    assert not cible.parent.exists()


def test_une_ecriture_dans_le_dossier_temporaire_passe(tmp_path):
    cible = tmp_path / "cv.md"
    derive.ecrire_atomique(cible, b"ok")
    assert cible.read_bytes() == b"ok"
