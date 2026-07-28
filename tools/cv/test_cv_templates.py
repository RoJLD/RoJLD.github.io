"""Le template `sobre` doit régénérer le CSS actuel À L'OCTET.

C'est le garde-fou central de l'extraction : tant qu'il tient, la banque de
templates ne peut pas altérer le CV par défaut — celui qui part réellement aux
recruteurs. Même motif que la migration de l'article : l'artefact d'origine est
figé en fixture, la génération doit le reproduire.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

LEGACY_CSS = (HERE / "fixtures" / "cv_css.legacy.txt").read_text(encoding="utf-8")
TEMPLATES = ROOT / "cv" / "templates"


def _charge(tid: str) -> dict:
    return json.loads((TEMPLATES / f"{tid}.json").read_text(encoding="utf-8"))


def test_sobre_regenere_le_css_a_l_octet():
    import cv_templates
    assert cv_templates.build_css(_charge("sobre")["style"]) == LEGACY_CSS


def test_fixture_non_vide():
    """Garde anti-vacuité : une fixture vide ferait passer le test précédent
    contre un moteur qui ne produit rien."""
    assert len(LEGACY_CSS) == 1483
    assert LEGACY_CSS.count("{") >= 23
