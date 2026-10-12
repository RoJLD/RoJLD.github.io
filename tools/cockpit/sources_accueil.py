"""Carte « clé data-i18n de l'accueil → source éditable » (édition du site, A1, spec § 3.2).

Les textes de l'accueil sont posés par le dictionnaire `const i18n` d'index.html, région par
région (`/* BUILD:i18n_<nom>_<lang> */`). La région `textes` vient de site_texts.json ; les
autres sont produites depuis profile.json par build_site. Un texte de profil est retrouvé
par sa VALEUR : éditable seulement si la valeur française désigne une seule feuille `fr` de
profile.json et que la même feuille `en` porte la valeur anglaise. Dates, lignes
d'organisation et autres textes recomposés ne sont donc pas éditables sur la page — /cms
reste leur éditeur. Rien ici n'écrit : l'annotation est faite à la volée par l'aperçu."""
from __future__ import annotations

import json
import re

REGION = re.compile(r"/\* BUILD:i18n_(\w+)_(fr|en) \*/(.*?)/\* /BUILD:i18n_\1_\2 \*/", re.S)
PAIRE = re.compile(r'(\w+):\s*("(?:[^"\\]|\\.)*")')
_ATTR = re.compile(r'data-i18n="(\w+)"(?! data-src=)')


def lire_regions(html: str) -> dict:
    return {(m.group(1), m.group(2)): {k: json.loads(v) for k, v in PAIRE.findall(m.group(3))}
            for m in REGION.finditer(html)}


def _chemins(noeud, valeur, lang, prefixe=()):
    """(chemin, position du segment de langue) de chaque feuille `lang` qui vaut `valeur`."""
    if isinstance(noeud, dict):
        for k, v in noeud.items():
            if k == lang and isinstance(v, str) and v == valeur:
                yield prefixe + (k,), len(prefixe)
            elif k == lang and isinstance(v, list):
                for i, x in enumerate(v):
                    if isinstance(x, str) and x == valeur:
                        yield prefixe + (k, i), len(prefixe)
            if isinstance(v, (dict, list)):
                yield from _chemins(v, valeur, lang, prefixe + (k,))
    elif isinstance(noeud, list):
        for i, v in enumerate(noeud):
            if isinstance(v, (dict, list)):
                yield from _chemins(v, valeur, lang, prefixe + (i,))


def _resoudre(noeud, segments):
    for s in segments:
        noeud = noeud[s]
    return noeud


def source_profil(profile: dict, valeur_fr: str, valeur_en: str) -> str | None:
    candidats = list(_chemins(profile, valeur_fr, "fr"))
    if len(candidats) != 1:
        return None
    segments, pos = candidats[0]
    segments_en = tuple("en" if j == pos else s for j, s in enumerate(segments))
    try:
        if _resoudre(profile, segments_en) != valeur_en:
            return None
    except (KeyError, IndexError, TypeError):
        return None
    return "profile:" + ".".join("{lang}" if j == pos else str(s) for j, s in enumerate(segments))


def carte_sources(html: str, profile: dict) -> dict:
    regions = lire_regions(html)
    carte = {}
    for nom in {n for n, _lang in regions}:
        fr, en = regions.get((nom, "fr"), {}), regions.get((nom, "en"), {})
        for cle in fr.keys() & en.keys():
            if nom == "textes":
                carte[cle] = f"textes:{cle}"
            else:
                source = source_profil(profile, fr[cle], en[cle])
                if source:
                    carte[cle] = source
    return carte


def annoter(html: str, carte: dict) -> str:
    return _ATTR.sub(lambda m: m.group(0) + (f' data-src="{carte[m.group(1)]}"' if m.group(1) in carte else ""), html)
