"""profile.yml de career-ops : seules les clés d'identité et le préavis bougent ; commentaires,
ordre et fins de ligne survivent ; une clé introuvable est un refus nommé."""
import sys
from datetime import date
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures_cv import COMPLEMENT, PROFIL, YML  # noqa: E402
from tools.cockpit import profile_yml  # noqa: E402

AUJ = date(2026, 10, 7)


def test_valeurs_depuis_profil_et_complement():
    v = profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ)
    assert v == {"full_name": "Ada Lovelace", "email": "ada@example.org", "phone": "+44 0",
                 "location": "London W1, UK", "linkedin": "linkedin.com/in/ada",
                 "portfolio_url": "https://ada.example.org/", "github": "github.com/ada",
                 "notice_period_days": None}


@pytest.mark.parametrize("dispo, attendu", [("2026-09", 0), ("2026-10", 0), ("2026-12", 55), (None, None), ("bientôt", None)])
def test_preavis(dispo, attendu):
    assert profile_yml.preavis_jours(dispo, AUJ) == attendu


def test_rien_a_changer_rend_le_texte_identique():
    texte, changes = profile_yml.projeter(YML, profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ))
    assert texte == YML and changes == []


def test_seule_la_ligne_changee_bouge_et_le_crlf_survit():
    crlf = YML.replace("\n", "\r\n")
    vals = dict(profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ), phone='+44 "1"')
    texte, changes = profile_yml.projeter(crlf, vals)
    assert changes == ["candidate.phone"]
    assert '  phone: "+44 \\"1\\""\r\n' in texte
    assert texte.replace('  phone: "+44 \\"1\\""', '  phone: "+44 0"') == crlf


def test_le_preavis_change_et_son_commentaire_aussi():
    vals = dict(profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ), notice_period_days=55)
    texte, changes = profile_yml.projeter(YML, vals)
    assert changes == ["cover_letter.notice_period_days"]
    assert "  notice_period_days: 55  # projeté depuis profile.json (identity.availability)\n" in texte


def test_le_preavis_inchange_garde_son_commentaire():
    vals = dict(profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ), notice_period_days=0)
    texte, changes = profile_yml.projeter(YML, vals)
    assert changes == [] and "  notice_period_days: 0  # disponible\n" in texte


def test_cle_absente_refus_nomme():
    sans = YML.replace('  github: "github.com/ada"\n', "")
    with pytest.raises(profile_yml.CleIntrouvable) as exc:
        profile_yml.projeter(sans, profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ))
    assert exc.value.args[0] == "candidate.github"


def test_cle_commentee_compte_comme_absente():
    commentee = YML.replace('  github: "github.com/ada"', '  # github: "github.com/ada"')
    with pytest.raises(profile_yml.CleIntrouvable, match="candidate.github"):
        profile_yml.projeter(commentee, profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ))


def test_cle_en_double_refus_nomme():
    double = YML.replace('  github: "github.com/ada"\n', '  github: "github.com/ada"\n  github: "x"\n')
    with pytest.raises(profile_yml.CleIntrouvable, match="en double"):
        profile_yml.projeter(double, profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ))


def test_sans_bloc_candidate():
    with pytest.raises(profile_yml.CleIntrouvable, match="candidate"):
        profile_yml.projeter("target_roles:\n  primary: []\n", profile_yml.valeurs(PROFIL, COMPLEMENT, AUJ))
