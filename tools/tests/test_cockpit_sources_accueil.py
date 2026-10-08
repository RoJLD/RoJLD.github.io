"""Chaque texte de l'accueil sait d'où il vient (spec édition du site § 3.2) : un texte fixe
vient de site_texts.json, un texte de profil est retrouvé par sa valeur dans profile.json.
Une valeur ambiguë ou recomposée (dates, lignes d'organisation) n'est pas éditable sur la page."""
import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import config, sources_accueil as sa  # noqa: E402

HTML = """<span data-i18n="status">x</span><a data-i18n="nav_exp">y</a><b data-i18n="footer">z</b>
<script>const i18n = {
    fr: {
/* BUILD:i18n_textes_fr */
        nav_exp: "Expérience",
/* /BUILD:i18n_textes_fr */
/* BUILD:i18n_status_fr */
        status: "Disponible",
/* /BUILD:i18n_status_fr */
/* BUILD:i18n_footer_fr */
        footer: "Robin · 2026",
/* /BUILD:i18n_footer_fr */
    },
    en: {
/* BUILD:i18n_textes_en */
        nav_exp: "Experience",
/* /BUILD:i18n_textes_en */
/* BUILD:i18n_status_en */
        status: "Available",
/* /BUILD:i18n_status_en */
/* BUILD:i18n_footer_en */
        footer: "Robin · 2026",
/* /BUILD:i18n_footer_en */
    }
};</script>"""
PROFIL = {"identity": {"status": {"fr": "Disponible", "en": "Available"}},
          "experiences": [{"bullets": {"fr": ["Un", "Deux"], "en": ["One", "Two"]}}]}


def test_lire_regions():
    r = sa.lire_regions(HTML)
    assert r[("textes", "fr")] == {"nav_exp": "Expérience"}
    assert r[("status", "en")] == {"status": "Available"}


def test_la_carte_distingue_texte_fixe_profil_et_non_editable():
    carte = sa.carte_sources(HTML, PROFIL)
    assert carte == {"nav_exp": "textes:nav_exp", "status": "profile:identity.status.{lang}"}


def test_une_puce_de_liste_est_retrouvee_avec_son_indice():
    assert sa.source_profil(PROFIL, "Deux", "Two") == "profile:experiences.0.bullets.{lang}.1"


def test_une_valeur_ambigue_n_est_pas_editable():
    double = {"a": {"fr": "Même", "en": "Same"}, "b": {"fr": "Même", "en": "Same"}}
    assert sa.source_profil(double, "Même", "Same") is None


def test_une_traduction_qui_ne_correspond_pas_n_est_pas_editable():
    assert sa.source_profil(PROFIL, "Disponible", "Busy") is None


def test_annoter_ajoute_la_source_une_seule_fois():
    carte = sa.carte_sources(HTML, PROFIL)
    une = sa.annoter(HTML, carte)
    assert 'data-i18n="nav_exp" data-src="textes:nav_exp"' in une
    assert 'data-i18n="status" data-src="profile:identity.status.{lang}"' in une
    assert 'data-i18n="footer" data-src' not in une
    assert sa.annoter(une, carte) == une


def test_l_accueil_reel_est_presque_entierement_editable():
    html = (config.SITE_ROOT / "index.html").read_text(encoding="utf-8")
    profil = json.loads((config.SITE_ROOT / "profile.json").read_text(encoding="utf-8"))
    carte = sa.carte_sources(html, profil)
    assert carte["status"] == "profile:identity.status.{lang}"
    assert carte["nav_exp"] == "textes:nav_exp"
    assert len(carte) >= 80      # mesuré le 2026-10-08 : 94 clés éditables sur 107
