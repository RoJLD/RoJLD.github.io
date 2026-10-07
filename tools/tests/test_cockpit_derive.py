"""Garde de dérive de cv.md : une modification à la main n'est jamais écrasée en silence."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import derive  # noqa: E402

CORPS = "# Ada — CV\n\nligne\n"
AUTRE = "# Ada — CV\n\nautre ligne\n"
T0 = datetime(2026, 10, 7, 12, 0, 0)


def test_le_marqueur_est_le_contrat_avec_career_ops():
    # web/src/lib/cv-generated.mjs (career-ops) teste le même préfixe.
    assert derive.PREFIXE.startswith("<!-- généré par le cockpit depuis profile.json")


def test_entete_puis_separer_rend_le_corps_et_son_empreinte():
    lue, corps = derive.separer(derive.avec_entete(CORPS))
    assert corps == CORPS and lue == derive.empreinte(CORPS)


def test_crlf_et_bom_ne_comptent_pas_comme_une_modification():
    crlf = "\ufeff" + derive.avec_entete(CORPS).replace("\n", "\r\n")
    assert derive.etat(crlf, CORPS) == "a_jour"


@pytest.mark.parametrize("actuel, attendu", [
    (None, "absent"),
    (CORPS, "sans_entete"),
    (derive.avec_entete(CORPS).replace("ligne", "LIGNE"), "modifie"),
    (derive.avec_entete(CORPS), "a_jour"),
    (derive.avec_entete(AUTRE), "en_retard"),
])
def test_etat(actuel, attendu):
    assert derive.etat(actuel, CORPS) == attendu


def test_diff_montre_l_ancien_et_le_nouveau():
    d = derive.diff(derive.avec_entete(AUTRE), CORPS)
    assert "-autre ligne" in d and "+ligne" in d and "cv.md (projeté)" in d


def test_ecrire_un_fichier_absent(tmp_path):
    p = tmp_path / "cv.md"
    r = derive.ecrire(p, CORPS, forcer=False, sauvegardes=tmp_path / "s")
    assert r == {"etat": "absent", "ecrit": True, "sauvegarde": None}
    assert p.read_bytes() == derive.avec_entete(CORPS).encode("utf-8")


def test_ecrire_en_retard_conserve_le_crlf(tmp_path):
    p = tmp_path / "cv.md"
    p.write_bytes(derive.avec_entete(AUTRE).replace("\n", "\r\n").encode("utf-8"))
    r = derive.ecrire(p, CORPS, forcer=False, sauvegardes=tmp_path / "s")
    assert r["ecrit"] and r["sauvegarde"] is None
    assert p.read_bytes() == derive.avec_entete(CORPS).replace("\n", "\r\n").encode("utf-8")


def test_ecrire_a_jour_n_ecrit_rien(tmp_path):
    p = tmp_path / "cv.md"
    p.write_bytes(derive.avec_entete(CORPS).encode("utf-8"))
    avant = p.stat().st_mtime_ns
    assert derive.ecrire(p, CORPS, forcer=False, sauvegardes=tmp_path / "s")["ecrit"] is False
    assert p.stat().st_mtime_ns == avant


@pytest.mark.parametrize("contenu, etat", [
    (derive.avec_entete(CORPS).replace("ligne", "LIGNE"), "modifie"),
    ("# écrit à la main\n", "sans_entete"),
])
def test_ecrire_refuse_un_cv_modifie_a_la_main(tmp_path, contenu, etat):
    p = tmp_path / "cv.md"
    p.write_bytes(contenu.encode("utf-8"))
    with pytest.raises(derive.DeriveRefusee) as exc:
        derive.ecrire(p, CORPS, forcer=False, sauvegardes=tmp_path / "s")
    assert exc.value.args[0] == etat and p.read_bytes() == contenu.encode("utf-8")
    assert not (tmp_path / "s").exists()


def test_forcer_sur_un_cv_modifie_sauvegarde_les_octets_modifies_puis_ecrit(tmp_path):
    p = tmp_path / "cv.md"
    modifie = derive.avec_entete(CORPS).replace("ligne", "LIGNE").encode("utf-8")
    p.write_bytes(modifie)
    r = derive.ecrire(p, CORPS, forcer=True, sauvegardes=tmp_path / "s", maintenant=T0)
    sauvegarde = tmp_path / "s" / "cv.20261007T120000.md"
    assert r == {"etat": "modifie", "ecrit": True, "sauvegarde": str(sauvegarde)}
    assert sauvegarde.read_bytes() == modifie
    assert derive.etat(derive.lire(p), CORPS) == "a_jour"


def test_forcer_sauvegarde_puis_ecrit(tmp_path):
    p = tmp_path / "cv.md"
    p.write_bytes(b"# ecrit a la main\r\n")
    r = derive.ecrire(p, CORPS, forcer=True, sauvegardes=tmp_path / "s", maintenant=T0)
    sauvegarde = tmp_path / "s" / "cv.20261007T120000.md"
    assert r == {"etat": "sans_entete", "ecrit": True, "sauvegarde": str(sauvegarde)}
    assert sauvegarde.read_bytes() == b"# ecrit a la main\r\n"
    assert derive.etat(derive.lire(p), CORPS) == "a_jour"
