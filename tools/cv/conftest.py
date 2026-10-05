"""Les tests de tools/cv importent les modules à plat (mode prepend de pytest) ; les
imports `tools.cockpit.*` exigent la racine du site sur sys.path."""
import sys
from pathlib import Path

_SITE = Path(__file__).resolve().parents[2]
if str(_SITE) not in sys.path:
    sys.path.insert(0, str(_SITE))
