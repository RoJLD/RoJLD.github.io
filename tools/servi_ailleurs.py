"""Chemins du domaine servis par un AUTRE dépôt GitHub Pages que ce site.

GitHub Pages sert sous le même domaine (robin-denis.com) ce site utilisateur
(RoJLD/RoJLD.github.io) et chaque dépôt-projet publié (RoJLD/<nom>, sous /<nom>/).
Quand les deux portent le même chemin, le dépôt-projet l'emporte. Mesuré le
2026-10-14 : https://robin-denis.com/academy/ servait déjà l'app de RoJLD/academy
alors que ce dépôt portait encore un dossier `academy/` — mort, jamais servi.

Un lien de ce site vers un de ces chemins est donc VIVANT sans qu'aucun fichier
local ne lui corresponde. La déclaration ci-dessous est la seule façon pour les
gardes de liens de l'accepter sans s'affaiblir : elle nomme le chemin ET le dépôt
qui le sert, et tout autre chemin absent du disque reste une erreur.

Deux invariants, tenus par `tools/tests/test_liens_internes.py` :
  * un chemin déclaré n'existe PAS dans ce dépôt — sinon un dossier mort, que
    GitHub Pages ne sert jamais, serait lu par les gardes à la place du
    dépôt-projet réellement servi ;
  * la correspondance se fait par SEGMENT de chemin : `academy/` couvre
    `/academy/` et tout ce qui est dessous, jamais `/academyx/`.
"""
from __future__ import annotations

import posixpath

# Préfixe (relatif à la racine du site, terminé par `/`) -> dépôt qui le sert.
SERVI_PAR_UN_AUTRE_DEPOT = {
    "academy/": "RoJLD/academy",
}


def depot_qui_sert(chemin: str) -> str | None:
    """Dépôt qui sert `chemin` à la place de ce site, ou None.

    `chemin` est relatif à la racine du site, en POSIX ; un `/` initial est
    toléré. Il est normalisé avant comparaison (`projects/../academy/` vaut
    `academy/`) ; un chemin qui sort de la racine ne relève d'aucun dépôt.
    """
    norme = posixpath.normpath(chemin.lstrip("/"))
    if norme == ".." or norme.startswith("../"):
        return None
    for prefixe, depot in SERVI_PAR_UN_AUTRE_DEPOT.items():
        dossier = prefixe.rstrip("/")
        if norme == dossier or norme.startswith(dossier + "/"):
            return depot
    return None
