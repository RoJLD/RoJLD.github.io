"""projeter() : chaque cible a son statut, chaque refus sa cause (spec D8 § 9), rien n'est
écrasé en silence. Le CLI --rapport sert à l'import (§ 4) : il n'écrit rien."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures_cv import COMPLEMENT_BRUT, PROFIL, YML  # noqa: E402
from tools.cockpit import config, derive, projection  # noqa: E402

OUI = lambda root, rel="data/cv_private.json": True  # noqa: E731
AUJ = date(2026, 10, 7)


@pytest.fixture
def co_root(tmp_path):
    root = tmp_path / "career-ops"
    (root / "config").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "config" / "profile.yml").write_bytes(YML.replace("\n", "\r\n").encode("utf-8"))
    (root / "data" / "cv_private.json").write_text(json.dumps(COMPLEMENT_BRUT, ensure_ascii=False), encoding="utf-8")
    (root / "cv.md").write_bytes("# écrit à la main\r\n".encode("utf-8"))
    profil = tmp_path / "profile.json"
    profil.write_text(json.dumps(PROFIL, ensure_ascii=False), encoding="utf-8")
    return root, profil


def _p(co_root, **k):
    root, profil = co_root
    return projection.projeter(root=root, profile_path=profil, aujourdhui=AUJ, ignore_fn=OUI, **k)


def test_rapport_n_ecrit_rien_et_montre_le_diff(co_root):
    avant = (co_root[0] / "cv.md").read_bytes()
    r = _p(co_root, ecrire=False)
    assert r["ok"] and r["cv_md"]["etat"] == "sans_entete" and "+# Ada Lovelace — CV" in r["cv_md"]["diff"]
    assert (co_root[0] / "cv.md").read_bytes() == avant and r["profile_yml"]["changements"] == []


def test_ecrire_sans_forcer_refuse_un_cv_jamais_genere(co_root):
    r = _p(co_root, ecrire=True)
    assert r["ok"] is False and "jamais été généré" in r["cv_md"]["erreur"] and r["cv_md"]["ecrit"] is False


def test_forcer_ecrit_avec_sauvegarde_puis_a_jour(co_root):
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] and r["cv_md"]["ecrit"] and r["cv_md"]["sauvegarde"]
    assert (co_root[0] / "data" / "cv-sauvegardes").is_dir()
    r2 = _p(co_root, ecrire=True)
    assert r2["ok"] and r2["cv_md"]["etat"] == "a_jour" and r2["cv_md"]["ecrit"] is False


def test_projeter_refuse_apres_une_modification_a_la_main(co_root):
    _p(co_root, ecrire=True, forcer=True)
    cv = co_root[0] / "cv.md"
    cv.write_bytes(cv.read_bytes().replace(b"Calls.", b"Calls, many."))
    r = _p(co_root, ecrire=True)
    assert r["ok"] is False and r["cv_md"]["etat"] == "modifie" and "à la main" in r["cv_md"]["erreur"]
    assert b"Calls, many." in cv.read_bytes() and "-  - Calls, many." in r["cv_md"]["diff"]


def test_profile_yml_ecrit_quand_le_telephone_change(co_root):
    root, _ = co_root
    brut = dict(COMPLEMENT_BRUT, phone="+44 9")
    (root / "data" / "cv_private.json").write_text(json.dumps(brut), encoding="utf-8")
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["profile_yml"] == {"changements": ["candidate.phone"], "ecrit": True, "erreur": None}
    assert b'  phone: "+44 9"\r\n' in (root / "config" / "profile.yml").read_bytes()


def test_profile_yml_en_erreur_n_empeche_pas_cv_md(co_root):
    root, _ = co_root
    (root / "config" / "profile.yml").write_text("target_roles: []\n", encoding="utf-8")
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] is False and r["cv_md"]["ecrit"] and "candidate" in r["profile_yml"]["erreur"]


def test_complement_absent_est_une_erreur_nommee(co_root):
    (co_root[0] / "data" / "cv_private.json").unlink()
    r = _p(co_root, ecrire=True)
    assert r["ok"] is False and r["cv_md"] is None and r["erreurs"][0].startswith("complément privé :")


def test_career_ops_non_configure(monkeypatch, co_root):
    monkeypatch.setattr(config, "resoudre_career_ops", lambda env=None, local_json=None: (None, "ni CAREER_OPS_ROOT ni x"))
    r = projection.projeter(ecrire=False, profile_path=co_root[1])
    assert r["erreurs"] == ["career-ops non configuré : ni CAREER_OPS_ROOT ni x"]


def test_profile_json_illisible(co_root):
    co_root[1].write_text("{", encoding="utf-8")
    r = _p(co_root, ecrire=False)
    assert r["erreurs"][0].startswith("profile.json illisible")


def test_etape_sauvegarde_ne_leve_jamais(monkeypatch):
    def boum(**k):
        raise RuntimeError("disque plein")
    monkeypatch.setattr(projection, "projeter", boum)
    assert projection.etape_sauvegarde() == {"ok": False, "message": "RuntimeError: disque plein"}


def test_etape_sauvegarde_saute_si_career_ops_absent(monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: {"ok": False, "erreurs": ["career-ops non configuré : x"],
                                                             "cv_md": None, "profile_yml": None})
    assert projection.etape_sauvegarde() == {"ok": None, "saute": True, "message": "career-ops non configuré : x"}


def test_etape_sauvegarde_rapporte_un_refus(monkeypatch):
    monkeypatch.setattr(projection, "projeter", lambda **k: {
        "ok": False, "erreurs": [],
        "cv_md": {"etat": "modifie", "diff": "", "ecrit": False, "sauvegarde": None, "erreur": "cv.md modifié"},
        "profile_yml": {"changements": [], "ecrit": False, "erreur": None}})
    r = projection.etape_sauvegarde()
    assert r["ok"] is False and r["etat"] == "modifie" and r["message"] == "cv.md modifié"


def test_cli_forcer_sans_ecrire_est_refuse():
    with pytest.raises(SystemExit) as exc:
        projection.main(["--rapport", "--forcer"])
    assert exc.value.code == 2


def test_cli_rapport(monkeypatch, capsys, co_root):
    reel, (root, profil) = projection.projeter, co_root      # capturé avant le remplacement : pas de récursion
    monkeypatch.setattr(projection, "projeter", lambda **k: reel(ecrire=False, root=root, profile_path=profil,
                                                                 aujourdhui=AUJ, ignore_fn=OUI))
    assert projection.main(["--rapport"]) == 0
    sortie = capsys.readouterr().out
    assert "cv.md : sans_entete" in sortie and "+# Ada Lovelace — CV" in sortie


def test_une_ecriture_refusee_par_le_systeme_est_nommee(monkeypatch, co_root):
    def ecrit_qui_leve(chemin, octets):
        raise PermissionError("verrouillé")
    monkeypatch.setattr(derive, "ecrire_atomique", ecrit_qui_leve)
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] is False and "écriture de cv.md impossible" in r["cv_md"]["erreur"]


def test_un_cv_md_illisible_est_nomme(monkeypatch, co_root):
    vrai_lire = derive.lire
    def lire_selective(path):
        if path.name == "cv.md":
            raise PermissionError("verrouillé")
        return vrai_lire(path)
    monkeypatch.setattr(derive, "lire", lire_selective)
    r = _p(co_root, ecrire=False)
    assert r["ok"] is False and r["cv_md"]["etat"] == "illisible" and "cv.md illisible" in r["cv_md"]["erreur"]


def test_un_profil_de_forme_invalide_est_nomme(co_root):
    root, profil = co_root
    profil_invalide = dict(PROFIL)
    profil_invalide["experiences"] = [{"title": "X", "bullets": ["x"]}]
    profil.write_text(json.dumps(profil_invalide, ensure_ascii=False), encoding="utf-8")
    r = _p(co_root, ecrire=False)
    # F3 : la validation intercepte la forme avant le rendu ; erreur nommée, aucune levée.
    assert r["ok"] is False and r["cv_md"] is None and r["erreurs"][0].startswith("profile.json invalide")


def test_une_forme_que_la_validation_laisse_passer_est_nommee_par_le_rendu(monkeypatch, co_root):
    """Filet de la ligne suivante : si la validation est aveugle, le rendu nomme encore l'erreur."""
    monkeypatch.setattr(projection.validate_profile, "validate", lambda *a, **k: [])
    root, profil = co_root
    profil_invalide = dict(PROFIL)
    profil_invalide["experiences"] = [{"title": "X", "bullets": ["x"]}]
    profil.write_text(json.dumps(profil_invalide, ensure_ascii=False), encoding="utf-8")
    r = _p(co_root, ecrire=False)
    assert r["ok"] is False and r["cv_md"] is None and r["erreurs"][0].startswith("profile.json ne se rend pas en cv.md")


def test_un_profil_qui_ne_valide_pas_est_refuse_et_nomme(co_root):
    root, profil = co_root
    invalide = json.loads(json.dumps(PROFIL))
    invalide["experiences"][0]["start"] = "2021-00"
    profil.write_text(json.dumps(invalide, ensure_ascii=False), encoding="utf-8")
    avant = (root / "cv.md").read_bytes()
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] is False and r["cv_md"] is None and r["erreurs"][0].startswith("profile.json invalide")
    assert "start" in r["erreurs"][0] and (root / "cv.md").read_bytes() == avant


def test_un_cv_md_pas_en_utf8_est_nomme_sans_lever(co_root):
    root, _ = co_root
    (root / "cv.md").write_bytes("# café\n".encode("cp1252"))
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] is False and r["cv_md"]["etat"] == "illisible" and r["cv_md"]["ecrit"] is False
    assert r["cv_md"]["erreur"].startswith("cv.md illisible : pas en UTF-8")


def test_un_profile_yml_pas_en_utf8_est_nomme_sans_lever(co_root):
    root, _ = co_root
    (root / "config" / "profile.yml").write_bytes(YML.replace("Ada", "Adé").encode("cp1252"))
    r = _p(co_root, ecrire=True, forcer=True)
    assert r["ok"] is False and r["profile_yml"]["ecrit"] is False
    assert r["profile_yml"]["erreur"].startswith("profile.yml illisible : pas en UTF-8")


def test_cli_ecrire_refuse_puis_forcer_reussit(monkeypatch, capsys, co_root):
    reel, (root, profil) = projection.projeter, co_root      # capturé avant le remplacement : pas de récursion
    monkeypatch.setattr(projection, "projeter", lambda **k: reel(root=root, profile_path=profil,
                                                                 aujourdhui=AUJ, ignore_fn=OUI, **k))
    assert projection.main(["--ecrire"]) == 1
    assert "REFUS" in capsys.readouterr().err
    assert projection.main(["--ecrire", "--forcer"]) == 0
