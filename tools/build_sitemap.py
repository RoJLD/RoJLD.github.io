"""build_sitemap.py — `sitemap.xml` et `robots.txt`, dérivés des pages SUIVIES par git.

Les trois fichiers d'indexation du site rendaient 404 : `sitemap.xml`, `robots.txt`
et `404.html` (mesuré en ligne le 2026-10-19). Ce générateur livre les deux premiers ;
le troisième est livré par `tools/build_404.py`, et ce générateur l'écarte du sitemap.

POURQUOI GIT ET PAS LE DISQUE. `corpus_publie.pages_publiees()` parcourt le disque
par `rglob`. Dans un checkout propre, elle rend exactement les pages que git suit
(15 le 2026-10-20, comptées sur une copie vierge de la branche de la page 404) ;
sur un poste, elle y ajoute toute page HTML présente sans être suivie. Sur celui
de l'Architecte, ce sont les maquettes d'architecture internes de
`.superpowers/brainstorm/`, que `.gitignore` écarte en rappelant que ce dépôt est
PUBLIC. L'écart est donc le nombre de ces pages non suivies, et il varie d'un poste
à l'autre. Un sitemap dérivé du disque les déclarerait à un explorateur — soit vers des
404 (elles ne sont pas poussées), soit, si elles l'étaient un jour, vers du contenu
interne. GitHub Pages ne sert que ce qui est suivi : c'est donc git qui dit la
vérité, et `git ls-files` qui est la source.

POURQUOI PAS DE `lastmod`. Le tenir vrai exigerait de coupler ce générateur à
l'historique (date du dernier commit touchant chaque page). Un `lastmod` faux est
pire que pas de `lastmod` : un explorateur qui s'y fie revisite au mauvais moment,
ou cesse de revisiter. On déclare l'ensemble des URL, et rien qu'on ne puisse garder
vrai.

OÙ IL EST BRANCHÉ. `build_site.py` l'appelle EN DERNIER, après ses huit frères
(compté le 2026-10-20 : `build()` importe neuf générateurs, celui-ci compris ; ce
paragraphe en annonçait six quand ils étaient déjà sept), donc la porte
« Publier » du cockpit — qui lance `build_site.py` — le rejoue sans que personne ait
à s'en souvenir. La leçon du 2026-10-15 (« une garde citée n'est pas une garde qui
s'exécute ») vaut aussi pour un fichier dérivé : s'il n'a pas d'écrivain dans la
porte qui tourne, il dérive.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Répertoires suivis par git mais JAMAIS servis comme des pages.
HORS_SITE = ("tools/", ".github/")

# Pages servies qui ne sont pas des pages d'atterrissage :
#
#   * les deux widgets de démonstration, conçus pour être atteints depuis `/demos/`
#     (et par l'Academy, qui pointe `robin-denis.com/demos/#bs`). Un visiteur qui
#     tomberait dessus depuis un moteur verrait un fragment hors de son cadre ;
#   * la page 404 (`tools/build_404.py`). GitHub Pages la sert à la place de toute
#     adresse absente : déclarée, elle serait une page « introuvable » proposée
#     comme résultat de recherche. Elle dit aussi `noindex`, et c'est cette
#     directive qui rend l'écart obligatoire et non facultatif : la garde
#     `test_aucune_page_qui_refuse_l_indexation_n_est_declaree_au_sitemap` rougit
#     si une page `noindex` entre dans le sitemap ;
#   * les quatre outils autonomes (`analyzer`, `match`, `radar`, `simulator`).
#     Chacun porte `<meta name="robots" content="noindex">` depuis le commit qui
#     l'a créé (analyzer 16fc446 le 2026-03-27, match c305360 et simulator
#     0b8260a le 2026-03-28, radar 9e969ad le 2026-04-01), et le sitemap de #39
#     (d1f0315, 2026-10-19) les déclarait quand même, faute de lire les
#     directives des pages. Décision du 2026-10-20 : respecter leur `noindex`
#     d'origine. Les écarter ne change rien à l'indexation réelle, puisqu'elles
#     la refusent déjà ; ça retire la contradiction d'un sitemap qui propose des
#     pages qui se refusent. La même garde `noindex` les tient : en retirer une
#     d'ici et régénérer le sitemap la fait rougir en nommant la page.
#
# Cette liste est VOLONTAIREMENT explicite : le test
# `test_toute_page_servie_est_declaree_ou_ecartee_sciemment` rougit dès qu'une
# page apparaît sans qu'on ait tranché son sort. C'est le but — pas une corvée.
# (Ce commentaire citait jusqu'au 2026-10-20 un nom de test qui n'existe pas,
# `…_ou_exclue_consciemment`.)
PAS_DES_PAGES_D_ATTERRISSAGE = (
    "404.html",
    "analyzer.html",
    "demos/widgets/bs.html",
    "demos/widgets/mc.html",
    "match.html",
    "radar.html",
    "simulator.html",
)


class SitemapError(RuntimeError):
    """Le générateur refuse de produire un sitemap qu'il ne peut pas garantir."""


def hote() -> str:
    """Le domaine canonique, lu dans `CNAME` — jamais écrit en dur.

    Si le domaine change, `CNAME` est le fichier que GitHub Pages lit : le faire
    diverger d'une constante Python donnerait un sitemap qui déclare des URL sur un
    hôte que le site ne sert plus.
    """
    cname = ROOT / "CNAME"
    if not cname.exists():
        raise SitemapError("CNAME absent : impossible de connaître le domaine servi")
    nom = cname.read_text(encoding="utf-8").strip()
    if not nom or "/" in nom or " " in nom:
        raise SitemapError(f"CNAME illisible : {nom!r}")
    return nom


def pages_suivies() -> tuple[str, ...]:
    """Les pages HTML que git suit — donc celles que GitHub Pages sert."""
    try:
        cp = subprocess.run(
            ["git", "ls-files", "-z", "*.html"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SitemapError(f"git ls-files a échoué : {exc}") from exc
    if cp.returncode != 0:
        raise SitemapError(f"git ls-files a rendu {cp.returncode} : {cp.stderr.strip()[:200]}")
    rels = [r for r in cp.stdout.split("\0") if r]
    if not rels:
        raise SitemapError("git ls-files n'a rendu aucune page : le sitemap serait vide")
    return tuple(sorted(r for r in rels if not r.startswith(HORS_SITE)))


def url_de(rel: str, h: str) -> str:
    """Chemin de fichier -> URL canonique, comme GitHub Pages la sert.

    `index.html` -> `/`, `x/index.html` -> `/x/`, `y.html` -> `/y.html`.
    """
    if rel == "index.html":
        chemin = "/"
    elif rel.endswith("/index.html"):
        chemin = "/" + rel[: -len("index.html")]
    else:
        chemin = "/" + rel
    return f"https://{h}{chemin}"


def racines_deleguees(h: str) -> tuple[str, ...]:
    """Les chemins du DOMAINE servis par un autre dépôt — déclarés, pas devinés.

    `/academy/` répond 200 sur l'hôte, servi par le dépôt-projet RoJLD/academy
    (mesuré le 2026-10-14 : le dépôt-projet l'emporte sur le dossier du site). Un
    sitemap qui ne décrirait que CE déploiement laisserait cette URL hors de
    l'index alors qu'elle appartient au domaine. La délégation est déclarée dans
    `servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT`, dont les gardes de liens font déjà
    autorité : on la relit au lieu d'écrire une liste parallèle.

    On ne déclare que la RACINE déléguée : ce dépôt ne connaît pas, et ne doit pas
    inventer, les URL internes de l'autre (l'Academy est une application d'une
    seule page). À l'autre dépôt de déclarer les siennes.
    """
    import servi_ailleurs
    return tuple(sorted(
        f"https://{h}/{prefixe}" for prefixe in servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT))


def urls() -> tuple[str, ...]:
    """Les URL à déclarer : pages suivies (moins les écartées) + racines déléguées."""
    h = hote()
    gardees = [p for p in pages_suivies() if p not in PAS_DES_PAGES_D_ATTERRISSAGE]
    return tuple(sorted(
        [url_de(p, h) for p in gardees] + list(racines_deleguees(h))))


def rendu_sitemap(liste: tuple[str, ...]) -> str:
    lignes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in liste:
        lignes.append(f"  <url><loc>{u}</loc></url>")
    lignes.append("</urlset>")
    return "\n".join(lignes) + "\n"


def rendu_robots(h: str) -> str:
    return "\n".join([
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: https://{h}/sitemap.xml",
    ]) + "\n"


def build_sitemap(write: bool = True) -> tuple[str, str]:
    """Rend (sitemap.xml, robots.txt) et, si `write`, les écrit à la racine."""
    liste = urls()
    xml = rendu_sitemap(liste)
    txt = rendu_robots(hote())
    if write:
        (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8", newline="\n")
        (ROOT / "robots.txt").write_text(txt, encoding="utf-8", newline="\n")
    return xml, txt


if __name__ == "__main__":
    x, _ = build_sitemap()
    print(f"[build_sitemap] OK — {x.count('<loc>')} URL déclarées, robots.txt écrit")
