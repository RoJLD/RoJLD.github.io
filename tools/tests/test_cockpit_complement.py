"""Complément privé du CV (D19) : chargé, validé, et refusé s'il pourrait partir vers le fork public."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures_cv import COMPLEMENT, COMPLEMENT_BRUT  # noqa: E402
from tools.cockpit import complement  # noqa: E402

OUI = lambda root, rel=complement.REL: True  # noqa: E731


def _ecrire(root: Path, donnees, octets: bytes | None = None) -> Path:
    p = complement.chemin(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(octets if octets is not None else json.dumps(donnees, ensure_ascii=False).encode("utf-8"))
    return p


def test_le_chemin_est_dans_data_de_career_ops(tmp_path):
    assert complement.chemin(tmp_path) == tmp_path / "data" / "cv_private.json"


def test_absent_leve_complement_absent(tmp_path):
    with pytest.raises(complement.ComplementAbsent, match="cv_private.json"):
        complement.charger(tmp_path, ignore_fn=OUI)


def test_un_complement_non_ignore_est_refuse(tmp_path):
    _ecrire(tmp_path, COMPLEMENT_BRUT)
    with pytest.raises(complement.ComplementInvalide, match="fork public"):
        complement.charger(tmp_path, ignore_fn=lambda root, rel=complement.REL: False)


def test_un_complement_valide_est_normalise(tmp_path):
    _ecrire(tmp_path, COMPLEMENT_BRUT)
    assert complement.charger(tmp_path, ignore_fn=OUI) == COMPLEMENT


def test_un_bom_est_accepte(tmp_path):
    _ecrire(tmp_path, None, b"\xef\xbb\xbf" + json.dumps(COMPLEMENT_BRUT).encode("utf-8"))
    assert complement.charger(tmp_path, ignore_fn=OUI)["phone"] == "+44 0"


@pytest.mark.parametrize("champ, valeur, attendu", [
    ("phone", "", "phone"),
    ("phone", None, "phone"),
    ("availability", 3, "availability"),
    ("experiences_cv", {"pas": "une liste"}, "experiences_cv"),
])
def test_un_champ_invalide_est_nomme(tmp_path, champ, valeur, attendu):
    brut = copy.deepcopy(COMPLEMENT_BRUT)
    brut[champ] = valeur
    _ecrire(tmp_path, brut)
    with pytest.raises(complement.ComplementInvalide, match=attendu):
        complement.charger(tmp_path, ignore_fn=OUI)


@pytest.mark.parametrize("cle, valeur, attendu", [
    ("start", "2018", "experiences_cv\\[0\\].start"),
    ("end", "août 2018", "experiences_cv\\[0\\].end"),
    ("company", "", "experiences_cv\\[0\\].company"),
    ("title", {"fr": "Agente"}, "experiences_cv\\[0\\].title"),
    ("bullets", ["Appels."], "experiences_cv\\[0\\].bullets"),
])
def test_une_experience_invalide_nomme_son_champ(tmp_path, cle, valeur, attendu):
    brut = copy.deepcopy(COMPLEMENT_BRUT)
    brut["experiences_cv"][0][cle] = valeur
    _ecrire(tmp_path, brut)
    with pytest.raises(complement.ComplementInvalide, match=attendu):
        complement.charger(tmp_path, ignore_fn=OUI)


def test_illisible_est_nomme(tmp_path):
    _ecrire(tmp_path, None, b"{pas du json")
    with pytest.raises(complement.ComplementInvalide, match="illisible"):
        complement.charger(tmp_path, ignore_fn=OUI)


def test_est_ignore_suit_le_gitignore_reel(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert complement.est_ignore(tmp_path) is False
    (tmp_path / ".gitignore").write_text("/data\n", encoding="utf-8")
    assert complement.est_ignore(tmp_path) is True
