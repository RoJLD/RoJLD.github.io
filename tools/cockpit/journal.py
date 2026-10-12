"""Journal des écritures du cockpit (édition du site, A1, spec § 5.4).

La publication refuse quand « l'arbre contient des modifications que le cockpit n'a pas faites ».
Pour le savoir, chaque action qui écrit dans le site passe par `ecriture(racine)` : on relève
l'empreinte de chaque fichier modifié de l'arbre avant et après l'action, et ce que l'action a
changé est consigné (chemin → sha256, None pour un fichier supprimé). Une modification présente
AVANT l'action et que l'action ne touche pas reste étrangère ; un fichier retouché ensuite hors du
cockpit ne correspond plus à son empreinte et redevient étranger. Le fichier du journal est ignoré
par git : ni servi par l'aperçu, ni publié.

Limite assumée (ruling R17) : une retouche étrangère faite PENDANT une action, ou dans un fichier
que le cockpit réécrit ensuite, est absorbée par l'action."""
from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import threading
from pathlib import Path

from tools.cockpit import config, derive

CHEMIN = config.SITE_ROOT / "tools" / "cockpit" / "journal_ecritures.json"
_VERROU = threading.Lock()


class EtatIllisible(RuntimeError):
    """`git status` n'a pas répondu : l'état de l'arbre est inconnu."""


def _chemin(chemin) -> Path:
    return Path(CHEMIN if chemin is None else chemin)   # CHEMIN lu à l'appel : les tests le redirigent


def empreinte(racine, rel) -> str | None:
    p = Path(racine) / rel
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    except FileNotFoundError:
        return None


def instantane(racine, *, run=subprocess.run) -> dict:
    """{chemin: empreinte} de chaque fichier de l'ensemble modifié de l'arbre (suivis et non suivis)."""
    from tools.cockpit import publication   # ici : publication importe ce module
    st = publication._git(racine, "status", "--porcelain=v1", "-z", "--untracked-files=all", run=run)
    if st.returncode != 0:
        raise EtatIllisible(st.stderr.strip()[-300:] or f"code {st.returncode}")
    return {f["chemin"]: empreinte(racine, f["chemin"]) for f in publication._porcelaine(st.stdout)}


def lire(chemin=None) -> dict:
    p = _chemin(chemin)
    if not p.is_file():
        return {}
    try:
        donnees = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(donnees, dict):
            raise ValueError("objet JSON attendu")
    except ValueError as exc:
        raise ValueError(f"journal des écritures illisible ({p}) : {exc} — le supprimer le remet à zéro "
                         "(toutes les modifications en cours deviennent étrangères)") from None
    return donnees


def _consigner(avant: dict, apres: dict, chemin=None) -> None:
    nouveaux = {p: e for p, e in apres.items() if p not in avant or avant[p] != e}
    with _VERROU:
        journal = lire(chemin)
        fusion = {p: e for p, e in journal.items() if p in apres}   # un chemin redevenu propre sort
        fusion.update(nouveaux)
        if fusion != journal:
            octets = (json.dumps(fusion, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            derive.ecrire_atomique(_chemin(chemin), octets)


@contextlib.contextmanager
def ecriture(racine, *, chemin=None, run=subprocess.run):
    """Toute écriture du cockpit dans le site se fait dans ce bloc. Consigné même si l'action
    lève (une source écrite puis un build en échec reste une écriture du cockpit).

    Fermé par défaut : sans `git status` lisible avant ET après, rien n'est consigné — la
    publication refusera ces fichiers en les nommant, au lieu d'adopter ce qui traînait déjà."""
    try:
        avant = instantane(racine, run=run)
    except EtatIllisible:
        avant = None
    try:
        yield
    finally:
        if avant is not None:
            try:
                apres = instantane(racine, run=run)
            except EtatIllisible:
                apres = None
            if apres is not None:
                _consigner(avant, apres, chemin)


def etrangers(racine, chemins, *, chemin=None) -> list:
    """Les chemins dont l'empreinte actuelle n'est pas celle consignée (sans entrée = étranger)."""
    journal = lire(chemin)
    return [c for c in chemins if c not in journal or journal[c] != empreinte(racine, c)]
