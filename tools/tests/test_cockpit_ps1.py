"""Les .ps1 livrés : ASCII pur (PowerShell 5.1 lit un fichier sans BOM en ANSI), sans
chemin du poste, sans Test-NetConnection (28 s sur port fermé, mesuré), loopback seul."""
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
PS1 = [SITE / "tools" / "cockpit" / "lancer.ps1", SITE / "tools" / "cockpit" / "installer_raccourci.ps1"]


def test_les_ps1_existent_et_sont_ascii_sans_bom():
    for p in PS1:
        b = p.read_bytes()
        assert not b.startswith(b"\xef\xbb\xbf"), f"{p.name} a un BOM"
        assert all(c < 128 for c in b), f"{p.name} contient un caractère non ASCII"


def test_aucun_chemin_du_poste_ni_sonde_lente():
    for p in PS1:
        t = p.read_text(encoding="ascii")
        assert "Users\\robla" not in t and "Users/robla" not in t
        assert "Test-NetConnection" not in t
    assert "127.0.0.1" in PS1[0].read_text(encoding="ascii") and "GetFolderPath" in PS1[1].read_text(encoding="ascii")


def test_le_lanceur_ne_promet_pas_un_port_que_le_serveur_ignore():
    """atelier.py écoute toujours sur 8010 (main() sans argument) : un paramètre -Port
    attendrait un port que personne n'ouvre, puis échouerait au bout de 15 s."""
    t = PS1[0].read_text(encoding="ascii")
    assert "param(" not in t.lower() and "$Port = 8010" in t


def test_gitattributes_fige_crlf_pour_les_ps1():
    assert "*.ps1 text eol=crlf" in (SITE / ".gitattributes").read_text(encoding="utf-8")


def test_le_journal_recoit_l_adresse_tout_de_suite():
    """Sortie redirigée = print mis en tampon jusqu'à l'arrêt : mesuré 2026-10-04, cockpit.out.log
    restait vide alors que le serveur répondait. Le human-test lit cette ligne."""
    assert '$env:PYTHONUNBUFFERED = "1"' in PS1[0].read_text(encoding="ascii")
