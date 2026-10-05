"""pages/cv.py : les annotations doivent rester RÉSOLUBLES, pas seulement syntaxiquement valides.

Mesuré (revue Task 3) : `from __future__ import annotations` garde les annotations sous forme de
chaînes, donc `Callable`/`pathlib` absents de l'en-tête ne cassent PAS l'import du module — mais
`typing.get_type_hints()` (et tout linter/type-checker qui l'utilise) échoue en `NameError` dès
qu'il tente de résoudre ces chaînes. Un module qui compile n'est pas un module dont les
signatures sont exploitables."""
import sys
import typing
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit.pages import cv as pages_cv  # noqa: E402

_FONCTIONS_PUBLIQUES = (
    "generate_pdf", "generate_docx", "generate_letter",
    "save_profile_edit", "_git_commit",
)


def test_les_annotations_de_pages_cv_sont_resolubles():
    """`get_type_hints` ne doit lever ni NameError ni AttributeError sur ces fonctions."""
    for nom in _FONCTIONS_PUBLIQUES:
        fn = getattr(pages_cv, nom)
        try:
            typing.get_type_hints(fn)
        except NameError as e:
            raise AssertionError(
                f"tools.cockpit.pages.cv.{nom} : annotation non résoluble ({e}) — "
                "l'en-tête du module doit importer le nom manquant."
            ) from e
