"""Spec D8 § 10, test « Public » : le site public ignore le complément privé et la projection.
Aucun module Python suivi, hors de tools/cockpit/ et des tests, ne les importe — sinon une page
publique pourrait lire (et un jour servir) ce qui n'existe que dans career-ops."""
import ast
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INTERDITS = {"complement", "projection"}


def _noms_importes(arbre):
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield a.name
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            yield base
            for a in n.names:
                yield f"{base}.{a.name}" if base else a.name


def _vise_un_module_interdit(nom):
    return any(part in INTERDITS for part in nom.split("."))


def test_aucun_module_public_n_importe_le_complement_ni_la_projection():
    suivis = subprocess.run(["git", "-C", str(REPO), "ls-files", "*.py"], capture_output=True, text=True,
                            check=True).stdout.splitlines()
    fautifs = []
    for rel in suivis:
        if rel.startswith("tools/cockpit/") or rel.startswith("tools/tests/") or "/test_" in rel \
                or rel.startswith("test_") or Path(rel).name == "conftest.py":
            continue
        p = REPO / rel
        if not p.is_file():
            continue
        arbre = ast.parse(p.read_text(encoding="utf-8-sig"), filename=rel)
        fautifs += [f"{rel}: import {n}" for n in set(_noms_importes(arbre)) if _vise_un_module_interdit(n)]
    assert not fautifs, fautifs


def test_la_garde_voit_un_import_interdit():
    for code in ("import tools.cockpit.complement", "from tools.cockpit import projection",
                 "from tools.cockpit.projection import projeter"):
        assert any(_vise_un_module_interdit(n) for n in _noms_importes(ast.parse(code))), code
    assert not any(_vise_un_module_interdit(n) for n in _noms_importes(ast.parse("import json\nfrom pathlib import Path")))
