"""Garde de structure : chaque `section[id]` de l'accueil vit dans `div.box`.

Cette garde n'existait pas — c'est pour cela qu'un `</div>` surnuméraire a pu
vivre dans la section Expérience et expulser SEPT sections hors du conteneur,
sur le site publié, sans qu'aucun test ne rougisse.

`div.box` porte le `max-width:860px` de l'accueil. Une section qui en sort est
rendue sur toute la largeur de la fenêtre, icônes collées au bord gauche. Rien
dans la suite ne le voyait : les gardes existantes lisent des *chaînes* (ancres,
href, textes i18n), et une chaîne reste présente quelle que soit sa place dans
l'arbre.

Pourquoi un `</div>` en trop fait tant de dégâts : HTML5 (§ *an end tag whose
tag name is "div"*) ne l'ignore pas, il DÉPILE jusqu'à avoir dépilé un `div` —
emportant au passage les `<section>` ouvertes, qui ne font pas barrière de
portée (`section` n'est pas dans la liste « in scope »). Un `</div>` de trop
dans la première section sort donc toutes les suivantes du conteneur.

Mesuré le 2026-10-15 sur 04699d1, en file:// dans Chromium à 390/768/1280/1920 :
7 des 9 `section[id]` avaient `<body>` pour parent (#education #skills #demos
#testimonials #blog #interests #contact), `div.box` ne comptait plus que 3
enfants au lieu de 11, et `#contact` était rendue à x=0 sur toute la largeur.
Le document portait 2 fermetures orphelines (`</section>` ligne 257, `</div>`
ligne 344). Les 13 autres pages suivies, elles, étaient équilibrées : c'est
pourquoi la garde des orphelines porte sur tout le corpus.
"""
from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ACCUEIL = ROOT / "index.html"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import corpus_publie  # noqa: E402

# Éléments sans contenu : ils n'ont pas de `</x>`, et les empiler fausserait tout.
VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}


class _Arbre(HTMLParser):
    """Pile des éléments ouverts, dépilée comme le fait un navigateur."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pile: list[tuple[str, dict]] = []
        self.sections: list[tuple[str, int, str, str | None]] = []
        self.fermetures_orphelines: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag in VIDES:
            return
        attributs = dict(attrs)
        if tag == "section" and attributs.get("id"):
            parent, pattrs = self.pile[-1] if self.pile else ("(racine)", {})
            self.sections.append(
                (attributs["id"], self.getpos()[0], parent, pattrs.get("class")))
        self.pile.append((tag, attributs))

    def handle_endtag(self, tag):
        if tag in VIDES:
            return
        for i in range(len(self.pile) - 1, -1, -1):
            if self.pile[i][0] == tag:
                del self.pile[i:]
                return
        # Aucune ouverture correspondante : le navigateur ignore la balise, et
        # c'est le symptôme d'un déséquilibre en amont.
        self.fermetures_orphelines.append((self.getpos()[0], tag))


def _lire(texte: str) -> _Arbre:
    a = _Arbre()
    a.feed(texte)
    return a


def _dans_la_box(parent: str, classe: str | None) -> bool:
    return parent == "div" and bool(classe) and "box" in classe.split()


def test_chaque_section_de_l_accueil_est_enfant_de_div_box():
    arbre = _lire(ACCUEIL.read_text(encoding="utf-8"))
    dehors = [(sid, ligne, parent, classe)
              for sid, ligne, parent, classe in arbre.sections
              if not _dans_la_box(parent, classe)]
    assert dehors == [], (
        "des sections de l'accueil n'ont pas `div.box` pour parent IMMEDIAT, "
        "donc elles echappent au max-width:860px (le seul emboitement legitime "
        "aujourd'hui est section > div.sb > div.sb-in ; une enveloppe en plus "
        "autour d'une section serait a autoriser ici consciemment) : "
        + " ; ".join(f"#{s} ligne {l} a pour parent <{p} class={c!r}>"
                     for s, l, p, c in dehors))


@pytest.mark.parametrize("page", corpus_publie.pages_publiees())
def test_aucune_page_publiee_ne_porte_de_fermeture_orpheline(page):
    """Le symptôme, sur tout le corpus — pas seulement sur l'accueil.

    Une `</div>` ou `</section>` sans ouverture correspondante est la trace du
    déséquilibre qui déplace les éléments. Mesuré le 2026-10-15 : les 13 autres
    pages suivies étaient déjà propres, seule l'accueil rougissait. La garde ne
    coûte donc rien aux autres et attrape la prochaine.

    Le nombre de cas suit le disque, et non une liste : dans un worktree neuf il
    vaut 14, et 20 dans l'arbre de travail de Robin, où six pages non suivies de
    `.superpowers/brainstorm/` traînent (elles sont équilibrées, mesuré — mais
    elles expliquent qu'un même commit ne collecte pas le même compte partout).
    """
    arbre = _lire((ROOT / page).read_text(encoding="utf-8", errors="replace"))
    assert arbre.fermetures_orphelines == [], (
        f"{page} : balises de fermeture sans ouverture correspondante — "
        + " ; ".join(f"</{t}> ligne {l}" for l, t in arbre.fermetures_orphelines))


def test_l_accueil_porte_bien_des_sections_a_verifier():
    """Contre-vacuité, sans nombre écrit à la main.

    Un parseur qui ne trouverait aucune section rendrait le premier test vert
    sans rien garder. L'attendu n'est pas un chiffre : c'est le décompte obtenu
    par une SECONDE lecture, textuelle celle-là, qui ne partage aucune ligne
    avec le parseur.
    """
    texte = ACCUEIL.read_text(encoding="utf-8")
    au_texte = re.findall(r"<section\b[^>]*\bid=", texte)
    arbre = _lire(texte)
    assert au_texte, "aucune <section id=…> dans l'accueil : la garde ne garde rien"
    assert len(arbre.sections) == len(au_texte), (
        f"le parseur voit {len(arbre.sections)} sections, le texte en compte "
        f"{len(au_texte)}")


def test_la_sonde_distingue_bien_une_page_saine_d_une_page_a_div_en_trop():
    """Contre-vacuité de la SONDE : sur une entrée fabriquée, elle doit dire non.

    L'ENTRÉE est décrite ici (deux sections dans un `div.box`, puis la même page
    avec un `</div>` de plus) ; la SORTIE attendue est le verdict du navigateur :
    la seconde section quitte le conteneur et deux fermetures deviennent
    orphelines. Sans cette épreuve, une sonde cassée rendrait tout vert.
    """
    saine = ('<body><div class="box">'
             '<section id="a"><div class="sb"><div class="sb-in">x</div></div></section>'
             '<section id="b">y</section>'
             "</div></body>")
    bonne = _lire(saine)
    assert [(s, p, c) for s, _l, p, c in bonne.sections] == [
        ("a", "div", "box"), ("b", "div", "box")]
    assert bonne.fermetures_orphelines == []

    cassee = saine.replace("x</div></div></section>", "x</div></div></div></section>")
    assert cassee != saine
    mauvaise = _lire(cassee)
    assert [(s, p, c) for s, _l, p, c in mauvaise.sections] == [
        ("a", "div", "box"), ("b", "body", None)]
    assert [t for _l, t in mauvaise.fermetures_orphelines] == ["section", "div"]

    # Le PREDICAT, et pas seulement le parseur. Sans ces quatre lignes, rendre
    # `_dans_la_box` toujours vrai laissait TOUT le fichier vert : la garde qui a
    # attrape le defaut de production devenait un no-op sans un seul rouge
    # (trouve par relecture adverse, 2026-10-15). Le verdict porte ici sur une
    # entree dont la reponse est connue d'avance, donc il est verifiable.
    assert [_dans_la_box(p, c) for _s, _l, p, c in bonne.sections] == [True, True]
    assert [_dans_la_box(p, c) for _s, _l, p, c in mauvaise.sections] == [True, False]
    assert _dans_la_box("div", "box") is True
    assert _dans_la_box("div", "boxed") is False, (
        "le predicat doit comparer des CLASSES entieres, pas des sous-chaines")
    assert _dans_la_box("div", None) is False
    assert _dans_la_box("body", None) is False
    assert _dans_la_box("section", "box") is False


def test_les_regions_generees_de_l_accueil_sont_equilibrees_en_div():
    """Le surplus appartient au HTML écrit à la main, pas au générateur.

    `build_site.py` remplace ce qui vit entre `<!-- BUILD:x -->` et
    `<!-- /BUILD:x -->` (bornes conservées, cf. `inject`). Si une région générée
    était déséquilibrée, corriger `index.html` ne servirait à rien : le prochain
    build réécrirait le défaut. Mesuré le 2026-10-15 : la région
    `BUILD:experience` ouvre et ferme 16 `div`, le surplus vit APRÈS sa borne
    fermante. Ce test fixe la frontière de responsabilité — et rougira si un
    générateur se met à émettre un `div` non fermé.
    """
    texte = ACCUEIL.read_text(encoding="utf-8")
    regions = re.findall(r"<!-- BUILD:([a-z_]+) -->(.*?)<!-- /BUILD:\1 -->", texte,
                         re.DOTALL)
    assert regions, "aucune région BUILD dans l'accueil"
    desequilibrees = {nom: (len(re.findall(r"<div\b", corps)),
                            len(re.findall(r"</div\s*>", corps)))
                      for nom, corps in regions
                      if len(re.findall(r"<div\b", corps))
                      != len(re.findall(r"</div\s*>", corps))}
    assert desequilibrees == {}, (
        f"régions générées déséquilibrées (ouvertes, fermées) : {desequilibrees}")


def test_la_box_de_l_accueil_porte_bien_son_max_width():
    """L'autre moitie du symptome : la regle CSS qui contraint le conteneur.

    La garde de structure ci-dessus verifie ou vivent les sections ; elle ne dit
    rien de la declaration qui les contraint. Mesure du 2026-10-15 : retirer la
    seule declaration `max-width` de `.box` (index.html ligne 43) reproduit
    exactement le symptome de production -- neuf sections rendues sur toute la
    largeur de la fenetre -- avec la suite ENTIEREMENT verte. Une porte qui ne
    garde qu'une moitie du chemin n'est pas une porte.

    La valeur n'est pas figee a 860px : on garde qu'une borne EXISTE, pas
    laquelle, pour qu'un choix de design reste libre sans rouvrir la porte.
    """
    texte = ACCUEIL.read_text(encoding="utf-8")
    regles = re.findall(r"\.box\s*\{([^}]*)\}", texte)
    assert regles, "aucune regle `.box{...}` dans l'accueil"
    avec_borne = [r for r in regles if re.search(r"max-width\s*:\s*\d", r)]
    assert avec_borne, (
        "`.box` ne porte plus de `max-width` : les sections de l'accueil "
        "s'etaleront sur toute la largeur de la fenetre, ce qui est le symptome "
        f"corrige le 2026-10-15. Regles `.box` trouvees : {regles!r}")
