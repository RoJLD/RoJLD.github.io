"""Le pied de page doit rester dérivé de `profile.json.$updated`.

H5 a remplacé une date écrite en dur (figée à « Mars 2026 ») par une valeur
dérivée de `$updated`. Une revue par mutation a refigé la date à la main dans
`index.html` : la suite est restée verte — aucun test ne nommait le pied de
page. Le défaut est moins grave qu'un thème perdu, parce qu'un simple
`build_site.py` répare l'artefact (mesuré : `index.html` redevient identique à
l'octet). Mais deux régressions échappent à cette auto-réparation :

  * l'artefact publié PEUT dériver de sa source entre deux builds — c'est
    exactement l'état que le site a connu pendant quatre mois ;
  * si c'est le GÉNÉRATEUR qui régresse (date en dur réintroduite), alors la
    réparation automatique devient une propagation automatique, et plus rien
    ne la signale.

D'où deux niveaux : la fonction, et l'accord entre l'artefact et sa source.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_site as bs  # noqa: E402


def _profil() -> dict:
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


# --- 1. La fonction dérive bien de la donnée ---------------------------------

def test_le_pied_de_page_derive_de_updated():
    p = _profil()
    p["$updated"] = "2026-07-07"
    assert bs.footer_text(p, "fr") == "Robin Denis · Dernière mise à jour Juillet 2026"
    assert bs.footer_text(p, "en") == "Robin Denis · Last updated July 2026"


def test_le_pied_de_page_suit_la_donnee_et_nest_pas_constant():
    """Une date en dur passerait le test précédent ; pas celui-ci."""
    p = _profil()
    p["$updated"] = "2025-01"
    assert bs.footer_text(p, "fr") == "Robin Denis · Dernière mise à jour Janvier 2025"
    assert bs.footer_text(p, "en") == "Robin Denis · Last updated January 2025"


@pytest.mark.parametrize("mauvais", ["", None, "juillet 2026", "2026", "2026-13"])
def test_une_date_malformee_echoue_fort(mauvais):
    """Zero Masking : un `$updated` illisible doit crier, pas produire un repli."""
    p = _profil()
    p["$updated"] = mauvais
    with pytest.raises(bs.BuildError):
        bs.footer_text(p, "fr")


# --- 2. L'artefact publié est d'accord avec sa source ------------------------

def _index() -> str:
    return (ROOT / "index.html").read_text(encoding="utf-8")


def test_le_pied_de_page_publie_correspond_a_profile_json():
    """Attrape la dérive artefact/source SANS avoir à reconstruire.

    C'est la mutation exacte qui passait verte : refiger « Mars 2026 » à la
    main dans `index.html`.
    """
    attendu = bs.footer_text(_profil(), "fr")
    zone = re.search(r"<!-- BUILD:footer -->(.*?)<!-- /BUILD:footer -->", _index(), re.S)
    assert zone, "zone BUILD:footer absente d'index.html — le build ne l'injecte plus"
    assert zone.group(1) == bs.esc(attendu), (
        f"pied de page publié désaccordé avec profile.json : "
        f"{zone.group(1)!r} != {attendu!r}")


@pytest.mark.parametrize("lang", ("fr", "en"))
def test_le_dictionnaire_i18n_publie_porte_la_meme_date(lang):
    """Les trois sites du pied de page doivent dire la même chose.

    La date vivait dans le dictionnaire i18n, HORS zone BUILD : c'est
    précisément ce qui l'avait rendue inatteignable par le build et l'avait
    laissée figée à mars 2026.
    """
    attendu = bs.footer_text(_profil(), lang)
    bloc = re.search(r"/\* BUILD:i18n_footer_%s \*/(.*?)/\* /BUILD:i18n_footer_%s \*/"
                     % (lang, lang), _index(), re.S)
    assert bloc, f"zone BUILD:i18n_footer_{lang} absente d'index.html"
    assert bs.js_str(attendu) in bloc.group(1), (
        f"dictionnaire i18n [{lang}] désaccordé : {attendu!r} absent de {bloc.group(1)!r}")
