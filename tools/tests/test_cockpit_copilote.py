"""Copilote terminal : une fenêtre Claude Code dans career-ops, amorcée sur l'inbox. Le
cockpit n'exécute aucun agent en arrière-plan (D5) : c'est Robin qui pilote la session."""
import sys
from pathlib import Path
import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import copilote  # noqa: E402


def test_le_prompt_ne_contient_aucune_apostrophe_ni_saisie_libre():
    assert "'" not in copilote.PROMPT and "agent-inbox" in copilote.PROMPT


def test_argv_avec_windows_terminal_puis_sans():
    root = Path("C:/x/career-ops")
    avec = copilote.argv_copilote(root, "C:/u/claude.exe", "C:/w/wt.exe")
    assert avec[:4] == ["C:/w/wt.exe", "-d", str(root), "--title"]
    assert avec[-3:-1] == ["-NoExit", "-Command"] and avec[-1] == f"& 'C:/u/claude.exe' '{copilote.PROMPT}'"
    sans = copilote.argv_copilote(root, "C:/u/claude.exe", None)
    assert sans[0] == "powershell.exe" and sans[-1] == avec[-1]


def test_sans_claude_on_le_dit(monkeypatch):
    monkeypatch.setattr(copilote, "claude_exe", lambda: None)
    res = copilote.ouvrir_copilote(Path("."), popen=lambda *a, **k: pytest.fail("ne doit pas lancer"))
    assert res["ok"] is False and any("claude" in m for m in res["problemes"])


@pytest.mark.skipif(sys.platform != "win32", reason="phase 1 : Windows")
def test_ouvrir_lance_dans_career_ops(monkeypatch, tmp_path):
    monkeypatch.setattr(copilote, "claude_exe", lambda: "C:/u/claude.exe")
    monkeypatch.setattr(copilote.shutil, "which", lambda n: None)
    appels = []
    res = copilote.ouvrir_copilote(tmp_path, popen=lambda argv, **kw: appels.append((argv, kw)))
    assert res["ok"] and appels[0][1]["cwd"] == str(tmp_path) and appels[0][0][0] == "powershell.exe"
