"""Copilote terminal (L5) : ouvre Claude Code dans career-ops, amorcé sur agent-inbox."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROMPT = ("Run the career-ops agent-inbox mode: read data/agent-inbox.md, drain the unchecked items, "
          "then summarize the pipeline state and what is ready to send")


def claude_exe() -> str | None:
    return shutil.which("claude")


def argv_copilote(root: Path, claude: str, wt: str | None) -> list[str]:
    ps = ["powershell.exe", "-NoExit", "-Command", f"& '{claude}' '{PROMPT}'"]
    return [wt, "-d", str(root), "--title", "career-ops copilote", *ps] if wt else ps


def ouvrir_copilote(root: Path, *, popen=subprocess.Popen) -> dict:
    claude = claude_exe()
    if claude is None:
        return {"ok": False, "argv": [], "problemes": ["claude (Claude Code) introuvable dans le PATH"]}
    if sys.platform != "win32":
        return {"ok": False, "argv": [], "problemes": ["copilote terminal : Windows seulement en phase 1"]}
    wt = shutil.which("wt.exe") or shutil.which("wt")
    argv = argv_copilote(root, claude, wt)
    extra = {} if wt else {"creationflags": subprocess.CREATE_NEW_CONSOLE}
    popen(argv, cwd=str(root), **extra)
    return {"ok": True, "argv": argv, "problemes": []}
