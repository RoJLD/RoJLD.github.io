"""Écrire une source depuis la page : textes fixes dans site_texts.json puis reconstruction,
champs de profil par la sauvegarde gouvernée — jamais le HTML généré (spec § 3.4)."""
import json
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import edition  # noqa: E402
from tools.cockpit.pages import cv as page_cv  # noqa: E402

TEXTES = {"fr": {"nav_exp": "Expérience"}, "en": {"nav_exp": "Experience"}}
PROFIL = {"identity": {"status": {"fr": "Disponible", "en": "Available"}},
          "experiences": [{"bullets": {"fr": ["Un", "Deux"], "en": ["One", "Two"]}}]}


@pytest.fixture
def site(tmp_path):
    (tmp_path / "site_texts.json").write_text(json.dumps(TEXTES, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "profile.json").write_text(json.dumps(PROFIL, ensure_ascii=False), encoding="utf-8")
    appels = {"reconstruire": 0, "sauvegarde": []}

    def reconstruire():
        appels["reconstruire"] += 1

    def sauvegarde(brut):
        appels["sauvegarde"].append(json.loads(brut))
        return {"ok": True, "stages": {}}

    def ecrire(source, lang, valeur):
        return edition.ecrire_source(source, lang, valeur, textes_path=tmp_path / "site_texts.json",
                                     profile_path=tmp_path / "profile.json",
                                     reconstruire=reconstruire, sauvegarde=sauvegarde)
    return tmp_path, appels, ecrire


def test_un_texte_fixe_est_ecrit_puis_le_site_reconstruit(site):
    racine, appels, ecrire = site
    assert ecrire("textes:nav_exp", "fr", "  Parcours \n pro ") == {"ok": True}
    assert json.loads((racine / "site_texts.json").read_text(encoding="utf-8"))["fr"]["nav_exp"] == "Parcours pro"
    assert appels["reconstruire"] == 1


def test_un_texte_inchange_reconstruit_quand_meme(site):
    """Le calque n'envoie jamais un texte inchangé : le serveur ne voit « inchangé » que sur
    une page périmée — exactement quand une reconstruction est due (ruling R16)."""
    _, appels, ecrire = site
    assert ecrire("textes:nav_exp", "fr", "Expérience") == {"ok": True, "inchange": True}
    assert appels["reconstruire"] == 1


def test_un_champ_de_profil_inchange_reconstruit_quand_meme(site):
    _, appels, ecrire = site
    assert ecrire("profile:identity.status.{lang}", "fr", "Disponible") == {"ok": True, "inchange": True}
    assert appels["reconstruire"] == 1 and appels["sauvegarde"] == []


@pytest.mark.parametrize("exc, attendu", [(RuntimeError("build cassé"), "RuntimeError: build cassé"),
                                          (SystemExit("gate"), "SystemExit: gate")])
def test_un_echec_de_reconstruction_garde_la_source_et_le_dit(site, exc, attendu):
    """Spec § 6 : échec de la régénération → bandeau ; la source modifiée est gardée."""
    racine, _, _ = site

    def casse():
        raise exc
    res = edition.ecrire_source("textes:nav_exp", "fr", "Parcours", textes_path=racine / "site_texts.json",
                                profile_path=racine / "profile.json", reconstruire=casse,
                                sauvegarde=lambda brut: pytest.fail("pas de sauvegarde de profil"))
    assert res["ok"] is True
    assert res["rapport"]["stages"]["rebuild"] == {"ok": False, "error": attendu}
    assert json.loads((racine / "site_texts.json").read_text(encoding="utf-8"))["fr"]["nav_exp"] == "Parcours"
    res = edition.ecrire_source("textes:nav_exp", "fr", "Parcours", textes_path=racine / "site_texts.json",
                                profile_path=racine / "profile.json", reconstruire=casse,
                                sauvegarde=lambda brut: pytest.fail("pas de sauvegarde de profil"))
    assert res["ok"] is True and res["inchange"] is True                 # le réessai reconstruit encore
    assert res["rapport"]["stages"]["rebuild"] == {"ok": False, "error": attendu}


def test_un_texte_piege_est_stocke_tel_quel(site):
    racine, _, ecrire = site
    ecrire("textes:nav_exp", "en", 'Exp "</script><b>é')
    assert json.loads((racine / "site_texts.json").read_text(encoding="utf-8"))["en"]["nav_exp"] == 'Exp "</script><b>é'


def test_la_langue_de_la_page_choisit_la_feuille(site):
    _, appels, ecrire = site
    assert ecrire("profile:identity.status.{lang}", "en", "Open to work")["ok"] is True
    envoye = appels["sauvegarde"][0]
    assert envoye["identity"]["status"] == {"fr": "Disponible", "en": "Open to work"}


def test_une_puce_de_liste_est_ecrite_a_son_indice(site):
    _, appels, ecrire = site
    ecrire("profile:experiences.0.bullets.{lang}.1", "fr", "Deux bis")
    assert appels["sauvegarde"][0]["experiences"][0]["bullets"]["fr"] == ["Un", "Deux bis"]


def test_un_refus_de_la_sauvegarde_gouvernee_est_rendu(site):
    racine, _, _ = site
    res = edition.ecrire_source("profile:identity.status.{lang}", "fr", "Autre",
                                textes_path=racine / "site_texts.json", profile_path=racine / "profile.json",
                                reconstruire=lambda: None,
                                sauvegarde=lambda brut: {"ok": False, "errors": ["règle X"]})
    assert res == {"ok": False, "rapport": {"ok": False, "errors": ["règle X"]}}


@pytest.mark.parametrize("source, lang, valeur, motif", [
    ("textes:nav_exp", "de", "x", "langue inconnue"),
    ("textes:nav_exp", "fr", "   ", "texte vide"),
    ("textes:nav_exp", "fr", 42, "texte attendu"),
    ("textes:inconnue", "fr", "x", "texte fixe inconnu"),
    ("profile:identity.status.fr", "fr", "x", "segment de langue"),
    ("profile:identity.absent.{lang}", "fr", "x", "chemin introuvable"),
    ("profile:experiences.0.bullets.{lang}", "fr", "x", "n'est pas un texte"),
    ("html:index", "fr", "x", "source inconnue"),
])
def test_les_refus_sont_nommes(site, source, lang, valeur, motif):
    _, appels, ecrire = site
    with pytest.raises(edition.SourceRefusee, match=motif):
        ecrire(source, lang, valeur)
    assert appels["reconstruire"] == 0 and appels["sauvegarde"] == []


def test_un_texte_trop_long_est_refuse(site):
    _, _, ecrire = site
    with pytest.raises(edition.SourceRefusee, match="trop long"):
        ecrire("textes:nav_exp", "fr", "x" * (edition.LONGUEUR_MAX + 1))


def _enregistreur(vu):
    import contextlib

    @contextlib.contextmanager
    def ecriture(racine, **k):
        vu.append(("entre", racine))
        try:
            yield
        finally:
            vu.append(("sort", racine))
    return ecriture


def test_la_sauvegarde_gouvernee_ecrit_sous_le_journal(monkeypatch):
    """Spec § 5.4 : toute écriture du cockpit est au journal — profil, historique, pages
    reconstruites et banque préfabriquée sont écrits DANS le bloc journal.ecriture(_ROOT)."""
    import profile_pipeline
    from tools.cockpit import journal, projection
    vu = []
    monkeypatch.setattr(journal, "ecriture", _enregistreur(vu))
    monkeypatch.setattr(profile_pipeline, "govern_save",
                        lambda *a, **k: vu.append(("govern",)) or {"ok": True, "stages": {}})
    monkeypatch.setattr(page_cv, "_regen_bank", lambda: vu.append(("banque",)))
    monkeypatch.setattr(projection, "etape_sauvegarde", lambda: {"ok": True, "message": ""})
    page_cv.sauvegarde_gouvernee("{}")
    assert vu == [("entre", page_cv._ROOT), ("govern",), ("banque",), ("sort", page_cv._ROOT)]


def test_la_sauvegarde_non_gouvernee_ecrit_sous_le_journal(monkeypatch):
    from tools.cockpit import journal
    vu = []
    monkeypatch.setattr(journal, "ecriture", _enregistreur(vu))
    monkeypatch.setattr(page_cv, "save_profile_edit", lambda raw, path: vu.append(("profil",)) or {"ok": True})
    monkeypatch.setattr(page_cv, "_regen_bank", lambda: vu.append(("banque",)))
    monkeypatch.setattr(page_cv, "_git_commit", lambda *a: vu.append(("commit",)))

    class H:
        def _send(self, code, ctype, corps):
            vu.append(("envoi", code))
    page_cv.handle_save(H(), {"json": "{}", "regen": True, "commit": True})
    assert vu == [("entre", page_cv._ROOT), ("profil",), ("banque",), ("commit",), ("sort", page_cv._ROOT),
                  ("envoi", 200)]


def test_sauvegarde_gouvernee_porte_banque_et_career_ops(monkeypatch):
    import profile_pipeline
    from tools.cockpit import projection
    monkeypatch.setattr(profile_pipeline, "govern_save", lambda *a, **k: {"ok": True, "stages": {}})
    monkeypatch.setattr(page_cv, "_regen_bank", lambda: None)
    monkeypatch.setattr(projection, "etape_sauvegarde", lambda: {"ok": True, "message": ""})
    rapport = page_cv.sauvegarde_gouvernee("{}")
    assert rapport["stages"]["prefab"] == {"ok": True} and rapport["stages"]["career_ops"]["ok"] is True
