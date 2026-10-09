"""Textes fixes de l'accueil dans site_texts.json (édition du site, A1, spec § 3.3).

Le menu, les titres de section et les libellés étaient écrits à la main dans le
dictionnaire `const i18n` d'index.html : ils vivent désormais dans site_texts.json,
que build_site injecte dans une région BUILD comme le reste du contenu."""
import json
import re
import sys
from html.parser import HTMLParser
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


def _interieurs(html, cle):
    """Contenu brut de chaque élément `data-i18n="<cle>"` (balise ouvrante, puis sa fermante)."""
    ouvrante = re.compile(r'<(\w+)\b[^>]*\sdata-i18n="' + re.escape(cle) + r'"[^>]*>')
    out = []
    for m in ouvrante.finditer(html):
        fin = html.index(f"</{m.group(1)}>", m.end())
        out.append(html[m.end():fin])
    return out


def test_le_build_reecrit_le_texte_statique_des_textes_fixes(monkeypatch, tmp_path):
    """Le texte FR écrit dans le HTML est ce que voit un visiteur FR avant tout script : le
    build le régénère depuis site_texts.json, sinon un texte édité n'apparaît jamais en FR."""
    textes = bs.load_site_texts()
    textes["fr"]["nav_exp"] = 'Parcours "pro" <b>é'
    p = tmp_path / "site_texts.json"
    p.write_text(json.dumps(textes, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bs, "SITE_TEXTS", p)
    out = bs.build_html((bs.ROOT / "index.html").read_text(encoding="utf-8"), bs.load_profile())
    interieurs = _interieurs(out, "nav_exp")
    assert interieurs and set(interieurs) == {'Parcours "pro" &lt;b&gt;é'}


def test_un_texte_fixe_a_balisage_enfant_est_refuse():
    with pytest.raises(bs.BuildError, match="nav_exp"):
        bs.synchroniser_textes_statiques('<a data-i18n="nav_exp"><b>x</b></a>', {"nav_exp": "y"})


class _TextesStatiques(HTMLParser):
    """Texte de chaque élément porteur de `data-i18n` (entités décodées, descendants compris)."""
    VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
             "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pile, self.textes = [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.VIDES:
            return
        cle = dict(attrs).get("data-i18n")
        self.pile.append((tag, cle, []))

    def handle_data(self, data):
        for _, cle, morceaux in self.pile:
            if cle is not None:
                morceaux.append(data)

    def handle_endtag(self, tag):
        if all(ouvert != tag for ouvert, _, _ in self.pile):   # fermante orpheline : ignorée
            return
        while self.pile:
            ouvert, cle, morceaux = self.pile.pop()
            if cle is not None:
                self.textes.append((cle, "".join(morceaux)))
            if ouvert == tag:
                break


def ecarts_statique_dictionnaire(html):
    """[(clé, texte statique, valeur FR du dictionnaire)] pour chaque élément qui diverge."""
    _, langues = _dictionnaire(html)
    lecteur = _TextesStatiques()
    lecteur.feed(html)
    lecteur.close()
    assert lecteur.textes, "aucun élément data-i18n lu"
    return [(cle, texte, langues["fr"].get(cle)) for cle, texte in lecteur.textes
            if " ".join(texte.split()) != " ".join(str(langues["fr"].get(cle)).split())]


def test_le_texte_statique_fr_egale_le_dictionnaire():
    """Invariant de la page publiée : un visiteur FR (applyLang ne tourne au chargement qu'en
    EN) voit le texte statique ; il doit être la valeur FR du dictionnaire, clé par clé."""
    assert ecarts_statique_dictionnaire((bs.ROOT / "index.html").read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("textes, motif", [
    ({"fr": {"a": "x"}}, "objet"),
    ({"fr": {"a": "x"}, "en": {"b": "y"}}, "clés différentes"),
    ({"fr": {"a": ""}, "en": {"a": "y"}}, "texte non vide"),
    ({"fr": {"a b": "x"}, "en": {"a b": "y"}}, "clé invalide"),
])
def test_site_texts_invalide_est_refuse(textes, motif):
    assert any(motif in e for e in bs.valider_site_texts(textes))
