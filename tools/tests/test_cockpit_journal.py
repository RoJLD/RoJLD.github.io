"""Journal des écritures du cockpit (spec édition du site § 5.4) : la publication refuse « des
modifications que le cockpit n'a pas faites » ; le cockpit tient donc le journal de ses écritures
(empreintes avant/après chaque action). Exercé contre un VRAI dépôt git temporaire ; le fichier
du journal est redirigé sous tmp_path par tools/conftest.py."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import journal  # noqa: E402


def _g(racine, *args):
    return subprocess.run(["git", "-C", str(racine), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def depot(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    subprocess.run(["git", "init", "-q", str(site)], check=True)
    _g(site, "config", "user.email", "test@example.org")
    _g(site, "config", "user.name", "Test")
    (site / "profile.json").write_text("{}\n", encoding="utf-8")
    (site / "index.html").write_text("<html></html>\n", encoding="utf-8")
    _g(site, "add", "-A")
    _g(site, "commit", "-q", "-m", "init")
    return site


def _journal():
    return json.loads(Path(journal.CHEMIN).read_text(encoding="utf-8"))


def test_le_journal_des_tests_vit_sous_le_dossier_temporaire(tmp_path):
    assert Path(journal.CHEMIN).parent == tmp_path


def test_le_vrai_journal_est_ignore_par_git():
    """Jamais servi par l'aperçu (fichier ignoré = 404), jamais dans `git status`, jamais publié."""
    cp = subprocess.run(["git", "-C", str(SITE), "check-ignore", "-q", "tools/cockpit/journal_ecritures.json"])
    assert cp.returncode == 0


def test_une_ecriture_du_cockpit_est_journalisee(depot):
    with journal.ecriture(depot):
        (depot / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    assert journal.etrangers(depot, ["profile.json"]) == []
    assert _journal() == {"profile.json": journal.empreinte(depot, "profile.json")}


def test_une_modification_anterieure_non_touchee_reste_etrangere(depot):
    (depot / "index.html").write_text("<html>à la main</html>\n", encoding="utf-8")
    with journal.ecriture(depot):
        (depot / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    assert journal.etrangers(depot, ["index.html", "profile.json"]) == ["index.html"]
    assert "index.html" not in _journal()


def test_une_retouche_apres_l_action_devient_etrangere(depot):
    with journal.ecriture(depot):
        (depot / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    (depot / "profile.json").write_text('{"a": 2}\n', encoding="utf-8")
    assert journal.etrangers(depot, ["profile.json"]) == ["profile.json"]


def test_une_exception_dans_l_action_journalise_quand_meme(depot):
    with pytest.raises(RuntimeError, match="build cassé"):
        with journal.ecriture(depot):
            (depot / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
            raise RuntimeError("build cassé")
    assert journal.etrangers(depot, ["profile.json"]) == []


def test_un_chemin_revenu_propre_quitte_le_journal(depot):
    with journal.ecriture(depot):
        (depot / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    _g(depot, "commit", "-q", "-am", "publié")                    # la publication le rend propre
    with journal.ecriture(depot):
        (depot / "index.html").write_text("<html>neuf</html>\n", encoding="utf-8")
    assert _journal() == {"index.html": journal.empreinte(depot, "index.html")}


def test_une_suppression_par_le_cockpit_est_journalisee(depot):
    with journal.ecriture(depot):
        (depot / "index.html").unlink()
    assert _journal() == {"index.html": None}
    assert journal.etrangers(depot, ["index.html"]) == []


def test_sans_git_rien_n_est_journalise(tmp_path):
    """Fermé par défaut : sans état git lisible, l'écriture n'est pas réclamée par le cockpit —
    la publication la refusera en la nommant, au lieu d'adopter ce qui traînait déjà."""
    racine = tmp_path / "pas-un-depot"
    racine.mkdir()
    with journal.ecriture(racine):
        (racine / "profile.json").write_text("{}\n", encoding="utf-8")
    assert journal.etrangers(racine, ["profile.json"]) == ["profile.json"]
    assert not Path(journal.CHEMIN).exists()


def test_un_journal_illisible_est_nomme(depot):
    Path(journal.CHEMIN).write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="journal des écritures illisible"):
        journal.etrangers(depot, ["profile.json"])
