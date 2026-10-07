"""Les enfants d'arrière-plan du cockpit naissent SANS console.

Le cockpit tourne sous pythonw (lancer.ps1), un processus sans console : chaque enfant console
(node, git, gh, powershell, taskkill) en recevait une neuve. Mesuré le 2026-10-07 sous pythonw :
`node --version` 56 → 360-470 ms, `kpi.mjs --json` 300 → 860-950 ms ; la carte career-ops de
l'accueil sortait de son budget de 2 s (« pas de réponse en 2.0 s ») et /career-ops mettait 2,9 s.
Avec CREATE_NO_WINDOW : 90 ms et 315 ms. Les deux lancements VISIBLES (interface web, copilote)
gardent leur console exprès et ne passent pas par ici."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit import anthropos, config, web  # noqa: E402
from tools.cockpit import career_ops as co  # noqa: E402
from tools.cockpit.pages import cv  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="CREATE_NO_WINDOW n'existe que sous Windows")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class _Espion:
    def __init__(self, stdout=""):
        self.appels, self.stdout = [], stdout

    def __call__(self, argv, **kw):
        self.appels.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, stdout=self.stdout, stderr="")


def _tous_sans_console(appels) -> bool:
    return bool(appels) and all(kw.get("creationflags", 0) & NO_WINDOW for _, kw in appels)


def test_la_constante_porte_create_no_window():
    assert config.SANS_CONSOLE == {"creationflags": NO_WINDOW}


def test_node_version_sans_console():
    e = _Espion("v22.12.0\n")
    assert co.node_version("node", runner=e) == (22, 12, 0)
    assert _tous_sans_console(e.appels)


def test_lancer_un_script_node_sans_console(tmp_path, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    vus = []

    class FauxProc:
        returncode, pid = 0, 1

        def __init__(self, argv, **kw):
            vus.append((argv, kw))

        def communicate(self, timeout=None):
            return "{}", ""

    co.lancer(["kpi.mjs", "--json"], tmp_path, 5, popen=FauxProc)
    assert _tous_sans_console(vus)


def test_tuer_l_arbre_sans_console(monkeypatch):
    e = _Espion()
    monkeypatch.setattr(subprocess, "run", e)

    class Proc:
        pid = 4242

        def wait(self, timeout=None):
            return 0

    co._tuer_arbre(Proc())
    assert _tous_sans_console(e.appels)


def test_mesurer_l_ecoute_du_web_sans_console():
    e = _Espion("127.0.0.1\n")
    assert web.adresses_ecoute(3000, run=e) == {"127.0.0.1"}
    assert _tous_sans_console(e.appels)


def test_sondes_du_site_public_sans_console(tmp_path):
    def hors_ligne(*a, **k):
        raise OSError("hors ligne")

    e = _Espion()
    anthropos.etat_site_public(opener=hors_ligne, runner=e, site_root=tmp_path, timeout=0.1)
    assert len(e.appels) == 4 and _tous_sans_console(e.appels)   # git ×2, gh ×2


def test_commit_gouverne_sans_console(tmp_path, monkeypatch):
    e = _Espion()
    monkeypatch.setattr(subprocess, "run", e)
    cv._git_commit(tmp_path, ["profile.json"], "test")
    assert len(e.appels) == 2 and _tous_sans_console(e.appels)


APPELANTS = {"run", "Popen", "runner", "popen"}


def _appels_sans_drapeau(source: str) -> list[int]:
    """Lignes des appels de lancement qui ne passent ni `creationflags=` ni `**kwargs`."""
    lignes = []
    for n in ast.walk(ast.parse(source)):
        if not isinstance(n, ast.Call):
            continue
        nom = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None)
        if nom in APPELANTS and not any(k.arg in (None, "creationflags") for k in n.keywords):
            lignes.append(n.lineno)
    return lignes


def test_aucun_lancement_du_cockpit_n_oublie_le_drapeau():
    """Un nouveau lancement ajouté sans SANS_CONSOLE réintroduirait la lenteur sous pythonw."""
    oublis = {}
    for f in sorted((SITE / "tools" / "cockpit").rglob("*.py")):
        lignes = _appels_sans_drapeau(f.read_text(encoding="utf-8"))
        if lignes:
            oublis[str(f.relative_to(SITE))] = lignes
    assert not oublis, f"lancements sans creationflags ni **kwargs : {oublis}"


def test_le_detecteur_voit_un_oubli():
    assert _appels_sans_drapeau("import subprocess\nsubprocess.run(['git'], check=True)\n") == [2]
    assert _appels_sans_drapeau("runner(['x'], **config.SANS_CONSOLE)\n") == []
