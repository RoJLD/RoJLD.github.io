"""Textes fixes de l'accueil dans site_texts.json (édition du site, A1, spec § 3.3).

Le menu, les titres de section et les libellés étaient écrits à la main dans le
dictionnaire `const i18n` d'index.html : ils vivent désormais dans site_texts.json,
que build_site injecte dans une région BUILD comme le reste du contenu."""
import json
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import build_site as bs  # noqa: E402

PAIRE = re.compile(r'(\w+):\s*("(?:[^"\\]|\\.)*")')
REGION = re.compile(r"/\* BUILD:i18n_(\w+)_(fr|en) \*/.*?/\* /BUILD:i18n_\1_\2 \*/", re.S)


def _dictionnaire(html):
    debut = html.index("const i18n = {")
    fin = re.compile(r"\n\s*\};").search(html, debut).start()
    d = html[debut:fin]
    fr_i, en_i = d.index("fr: {"), d.index("en: {")
    langues = {lang: {k: json.loads(v) for k, v in PAIRE.findall(seg)}
               for lang, seg in (("fr", d[fr_i:en_i]), ("en", d[en_i:]))}
    return d, langues


def test_site_texts_est_valide_et_bilingue():
    textes = bs.load_site_texts()
    assert bs.valider_site_texts(textes) == []
    assert {"nav_exp", "hero_tag", "sec_blog"} <= set(textes["fr"])


def test_plus_aucun_texte_ecrit_a_la_main_dans_le_dictionnaire():
    d, _ = _dictionnaire((bs.ROOT / "index.html").read_text(encoding="utf-8"))
    assert PAIRE.findall(REGION.sub("", d)) == []


def test_chaque_cle_de_la_page_existe_en_francais_et_en_anglais():
    html = (bs.ROOT / "index.html").read_text(encoding="utf-8")
    _, langues = _dictionnaire(html)
    cles = set(re.findall(r'data-i18n="(\w+)"', html))
    assert cles - set(langues["fr"]) == set()
    assert cles - set(langues["en"]) == set()


def test_le_build_injecte_site_texts(monkeypatch, tmp_path):
    textes = bs.load_site_texts()
    textes["fr"]["nav_exp"] = 'Exp "</script><b>é'
    p = tmp_path / "site_texts.json"
    p.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bs, "SITE_TEXTS", p)
    out = bs.build_html((bs.ROOT / "index.html").read_text(encoding="utf-8"), bs.load_profile())
    d, langues = _dictionnaire(out)
    assert langues["fr"]["nav_exp"] == 'Exp "</script><b>é'
    assert "</script><b>" not in d


@pytest.mark.parametrize("textes, motif", [
    ({"fr": {"a": "x"}}, "objet"),
    ({"fr": {"a": "x"}, "en": {"b": "y"}}, "clés différentes"),
    ({"fr": {"a": ""}, "en": {"a": "y"}}, "texte non vide"),
    ({"fr": {"a b": "x"}, "en": {"a b": "y"}}, "clé invalide"),
])
def test_site_texts_invalide_est_refuse(textes, motif):
    assert any(motif in e for e in bs.valider_site_texts(textes))
