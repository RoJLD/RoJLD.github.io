"""config du cockpit : racine du site, résolution de career-ops, secret local ignoré par git.

Mesuré le 2026-09-28 : le dépôt du site est PUBLIC ; un chemin du poste commité par
erreur y serait à un `git add -A` de la ligne. D'où : la racine de career-ops vient de
l'environnement ou d'un fichier ignoré, et un test vérifie qu'il est bien ignoré."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit import config  # noqa: E402


def _faux_career_ops(tmp_path):
    d = tmp_path / "career-ops"
    d.mkdir()
    (d / "tracker.mjs").write_text("// faux\n", encoding="utf-8")
    return d


def test_la_racine_du_site_porte_profile_json():
    assert (config.SITE_ROOT / "profile.json").is_file()
    assert config.TOOLS_DIR == config.SITE_ROOT / "tools"
    assert config.CV_DIR == config.SITE_ROOT / "tools" / "cv"


def test_la_racine_et_tools_cv_sont_sur_sys_path_apres_import():
    assert str(config.SITE_ROOT) in sys.path and str(config.CV_DIR) in sys.path


def test_career_ops_root_vient_de_l_environnement_d_abord(tmp_path):
    d = _faux_career_ops(tmp_path)
    assert config.career_ops_root(env={"CAREER_OPS_ROOT": str(d)}, local_json=tmp_path / "absent.json") == d


def test_un_dossier_sans_tracker_mjs_n_est_pas_career_ops(tmp_path):
    assert config.career_ops_root(env={"CAREER_OPS_ROOT": str(tmp_path)}, local_json=tmp_path / "absent.json") is None


def test_career_ops_root_vient_ensuite_de_local_json(tmp_path):
    d = _faux_career_ops(tmp_path)
    lj = tmp_path / "local.json"
    lj.write_text(json.dumps({"career_ops_root": str(d)}), encoding="utf-8")
    assert config.career_ops_root(env={}, local_json=lj) == d


def test_un_local_json_illisible_donne_none_sans_lever(tmp_path):
    lj = tmp_path / "local.json"
    lj.write_text("{pas du json", encoding="utf-8")
    assert config.career_ops_root(env={}, local_json=lj) is None


@pytest.mark.parametrize("contenu", ["[1, 2, 3]", '"texte"'])
def test_un_local_json_valide_mais_pas_objet_donne_none_sans_lever(tmp_path, contenu):
    lj = tmp_path / "local.json"
    lj.write_text(contenu, encoding="utf-8")
    assert config.career_ops_root(env={}, local_json=lj) is None


def test_sans_rien_c_est_none(tmp_path):
    assert config.career_ops_root(env={}, local_json=tmp_path / "absent.json") is None


def test_local_json_est_ignore_par_git_et_jamais_suivi():
    rel = "tools/cockpit/local.json"
    ignore = subprocess.run(["git", "-C", str(SITE), "check-ignore", "-q", rel])
    assert ignore.returncode == 0, f"{rel} n'est pas dans .gitignore : il finirait en ligne"
    suivi = subprocess.run(["git", "-C", str(SITE), "ls-files", rel], capture_output=True, text=True)
    assert suivi.stdout.strip() == "", f"{rel} est suivi par git"


def test_un_local_json_avec_bom_est_lu(tmp_path):
    """Windows PowerShell 5.1 : `Set-Content -Encoding utf8` écrit un BOM (EF BB BF) que
    json.loads refuse. Mesuré le 2026-10-06 : le local.json du human-test en portait un, et le
    cockpit affichait « non configuré » avec le fichier sous les yeux."""
    d = _faux_career_ops(tmp_path)
    lj = tmp_path / "local.json"
    lj.write_bytes(b"\xef\xbb\xbf" + json.dumps({"career_ops_root": str(d)}).encode("utf-8"))
    assert config.career_ops_root(env={}, local_json=lj) == d


@pytest.mark.parametrize("cas, attendu", [
    ("rien", "ni CAREER_OPS_ROOT ni"),
    ("illisible", "illisible"),
    ("sans_cle", 'sans clé "career_ops_root"'),
    ("pas_objet", 'sans clé "career_ops_root"'),
    ("env_sans_tracker", "(CAREER_OPS_ROOT) ne contient pas tracker.mjs"),
    ("json_sans_tracker", "(local.json) ne contient pas tracker.mjs"),
])
def test_la_raison_nomme_la_cause_et_pas_seulement_le_remede(tmp_path, cas, attendu):
    """« non configuré » seul renvoyait à écrire un local.json qui existait déjà : chaque cas
    d'échec porte sa cause, que la page affiche (spec § 8)."""
    lj = tmp_path / "local.json"
    vide = tmp_path / "vide"
    vide.mkdir()
    env = {}
    if cas == "illisible":
        lj.write_text("{pas du json", encoding="utf-8")
    elif cas == "sans_cle":
        lj.write_text('{"autre": 1}', encoding="utf-8")
    elif cas == "pas_objet":
        lj.write_text("[1, 2]", encoding="utf-8")
    elif cas == "env_sans_tracker":
        env = {"CAREER_OPS_ROOT": str(vide)}
    elif cas == "json_sans_tracker":
        lj.write_text(json.dumps({"career_ops_root": str(vide)}), encoding="utf-8")
    racine, raison = config.resoudre_career_ops(env=env, local_json=lj)
    assert racine is None and attendu in raison, raison


def test_la_raison_est_none_quand_career_ops_est_trouve(tmp_path):
    d = _faux_career_ops(tmp_path)
    assert config.resoudre_career_ops(env={"CAREER_OPS_ROOT": str(d)}, local_json=tmp_path / "absent.json") == (d, None)
