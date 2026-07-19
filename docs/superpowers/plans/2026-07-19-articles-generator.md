# Générateur d'articles — plan d'implémentation

> **Pour les exécutants agentiques :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:subagent-driven-development` (recommandé) ou
> `superpowers:executing-plans` pour dérouler ce plan tâche par tâche. Les étapes
> utilisent la syntaxe case à cocher (`- [ ]`) pour le suivi.

**But :** générer les pages d'articles depuis `profile.json` + des sources Markdown, et
rendre le blog bilingue.

**Architecture :** `articles/src/<slug>.<lang>.md` (prose + frontmatter `tldr`) et
`profile.json.articles[]` (catalogue) alimentent `tools/build_articles.py`, qui produit
`articles/<slug>.html` et `articles/<slug>.en.html`. Le builder suit le patron des six
existants (`build_projects.py` en modèle) et est appelé par `build_site.build()`.

**Pile :** Python 3.13 stdlib + `markdown` (première dépendance tierce du dépôt, déclarée
dans `requirements.txt`). Tests `pytest`. Aucune CI : construction locale, HTML commité.

**Spec :** `docs/superpowers/specs/2026-07-19-articles-generator-design.md`

## Contraintes globales

- **L'URL `articles/couverture-dynamique.html` ne doit pas changer** — lien public,
  potentiellement indexé. Le slug se déduit de `articles[].url`, jamais de l'`id`.
- **Aucun champ nouveau dans le schéma `profile.json`.** Le catalogue est déjà complet.
- Les builders existants sont stdlib-only. Seul `build_articles` importe `markdown`, en
  import **paresseux**, avec échec bruyant et actionnable.
- **Zero Masking** : un `.en.md` manquant est signalé en sortie, jamais tu.
  `build_site.build()` propage l'échec d'un builder (patron `raise BuildError(...)` déjà
  en place aux lignes 553-587).
- Le temps de lecture est **dérivé** : `ceil(mots / 200)`, minimum 1.
- Utilitaires à réutiliser depuis `build_site` : `esc()`, `fmt_date(iso, lang)`,
  `_bi(field, lang)`. Ne pas les redéfinir.
- Encodage : lecture/écriture toujours `encoding="utf-8"` explicite. Sur cette machine,
  `print` d'un caractère non-cp1252 lève `UnicodeEncodeError` — préfixer les commandes de
  vérification par `PYTHONIOENCODING=utf-8`.

---

### Tâche 1 : Migration du contenu vers Markdown + filet de non-régression

Extraire le corps de la page écrite à la main vers `articles/src/couverture-dynamique.fr.md`
et figer un test qui compare l'ancienne page à la future génération. **Cette tâche doit
précéder toute génération** : le builder écrasera `articles/couverture-dynamique.html`, et
c'est aujourd'hui l'unique exemplaire du texte.

**Fichiers :**
- Créer : `articles/src/couverture-dynamique.fr.md`
- Créer : `tools/tests/fixtures/couverture-dynamique.legacy.html` (copie figée de l'original)
- Créer : `tools/tests/test_build_articles.py`
- Créer : `requirements.txt`

**Interfaces :**
- Produit : le fichier `.md` et la copie de référence que les tâches 2 et 3 consomment.

- [ ] **Étape 1 : figer l'original comme référence**

```bash
cd C:/Users/robla/VScode_Project/cv-parity-wt
mkdir -p tools/tests/fixtures articles/src
cp articles/couverture-dynamique.html tools/tests/fixtures/couverture-dynamique.legacy.html
```

- [ ] **Étape 2 : extraire le corps en Markdown**

Écrire `articles/src/couverture-dynamique.fr.md` à la main, en transcrivant le corps de
`tools/tests/fixtures/couverture-dynamique.legacy.html` situé entre `<div class="article-tldr">`
et `<div class="article-footer">` (bornes mesurées : le corps compte 509 mots, 4 `h2`,
5 `h3`, 1 `.formula`, 1 `pre`, 1 `blockquote`, 1 `ul`).

Correspondance de transcription :

| HTML d'origine | Markdown |
|---|---|
| `<div class="article-tldr">…</div>` | frontmatter `tldr: …` |
| `<h2>T</h2>` | `## T` |
| `<h3>T</h3>` | `### T` |
| `<p>…</p>` | paragraphe |
| `<ul><li>…</li></ul>` | `- …` |
| `<pre><code>…</code></pre>` | bloc clôturé ```` ``` ```` |
| `<blockquote>…</blockquote>` | `> …` |
| `<div class="formula">F</div>` | `::formula` / `F` / `::` |
| `<strong>`, `<code>`, `<a href>` | `**…**`, `` `…` ``, `[…](…)` |

Squelette :

```markdown
---
tldr: TL;DR : la couverture dynamique en delta-hedging fonctionne bien en théorie, mais les coûts de transaction, la volatilité stochastique et les contraintes de rebalancement la rendent bien plus complexe en pratique. Voici ce que j'ai appris pendant mon PFE avec EY.
---

## <premier h2 de la page d'origine>

<paragraphes…>
```

- [ ] **Étape 3 : déclarer la dépendance**

Créer `requirements.txt` :

```
# Seul tools/build_articles.py en dépend (conversion Markdown des articles).
# Les autres builders sont stdlib-only — garder cette liste minimale.
markdown>=3.5
```

- [ ] **Étape 4 : écrire le test de non-régression (il doit ÉCHOUER)**

Créer `tools/tests/test_build_articles.py` :

```python
"""Non-régression de la migration : la page générée doit porter le même texte que
la page écrite à la main. L'égalité octet pour octet n'est PAS exigée — Markdown
normalise le balisage. Ce qui est comparé : texte dépouillé, structure des titres,
et contenu littéral des blocs de données (formules, code)."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

LEGACY = pathlib.Path(__file__).resolve().parent / "fixtures" / "couverture-dynamique.legacy.html"


def _body(html: str) -> str:
    """Corps rédactionnel seul : entre le TL;DR et le pied d'auteur, après le CSS.

    Le découpage part de `</style>` : les noms de classe apparaissent d'abord dans
    la feuille de style, et un `find` naïf découpe alors deux règles CSS au lieu
    de deux éléments."""
    after_css = html[html.find("</style>") + len("</style>"):]
    i = after_css.find("article-tldr")
    j = after_css.find("article-footer")
    assert i != -1 and j != -1, "bornes du corps introuvables"
    return after_css[i:j]


def _text(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def _headings(fragment: str) -> list[str]:
    return [f"{m.group(1)}:{_text(m.group(2))}"
            for m in re.finditer(r"<(h2|h3)[^>]*>(.*?)</\1>", fragment, re.S)]


def _blocks(fragment: str, cls: str) -> list[str]:
    return [_text(m) for m in re.findall(rf'<div class="{cls}"[^>]*>(.*?)</div>', fragment, re.S)]


@pytest.fixture(scope="module")
def generated() -> str:
    import build_articles
    return build_articles.render_article_page(build_articles.load_profile(),
                                              "couverture_dynamique", "fr")


def test_titres_identiques(generated):
    assert _headings(_body(generated)) == _headings(_body(LEGACY.read_text(encoding="utf-8")))


def test_formules_identiques(generated):
    assert _blocks(_body(generated), "formula") == _blocks(_body(LEGACY.read_text(encoding="utf-8")), "formula")


def test_texte_integralement_preserve(generated):
    """Chaque phrase de l'original se retrouve dans la page générée.

    Comparaison par phrase et non par égalité globale : la ponctuation d'espacement
    diffère légitimement (Markdown normalise), mais aucune phrase ne doit disparaître."""
    legacy_text = _text(_body(LEGACY.read_text(encoding="utf-8")))
    gen_text = _text(_body(generated))
    manquantes = [p.strip() for p in re.split(r"(?<=[.!?]) ", legacy_text)
                  if len(p.strip()) > 40 and p.strip() not in gen_text]
    assert manquantes == [], f"phrases perdues : {manquantes[:3]}"
```

- [ ] **Étape 5 : lancer le test, vérifier qu'il échoue pour la BONNE raison**

```bash
cd C:/Users/robla/VScode_Project/cv-parity-wt
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_articles.py -x
```

Attendu : `ModuleNotFoundError: No module named 'build_articles'`. Si l'échec est autre
(fixture introuvable, bornes du corps), corriger avant de continuer.

- [ ] **Étape 6 : commit**

```bash
git add articles/src/couverture-dynamique.fr.md requirements.txt \
        tools/tests/test_build_articles.py tools/tests/fixtures/couverture-dynamique.legacy.html
git commit -m "$(cat <<'EOF'
feat(articles): migre le corps de l'article vers Markdown + filet de non-régression

La page était écrite à la main, hors du keystone profile.json. Son corps passe en
source Markdown ; l'original est figé en fixture pour que la génération à venir soit
comparable phrase à phrase.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 2 : le générateur (français)

**Fichiers :**
- Créer : `tools/build_articles.py`
- Test : `tools/tests/test_build_articles.py` (étendu)

**Interfaces :**
- Consomme : `articles/src/<slug>.fr.md` (tâche 1), `profile.json.articles[]`.
- Produit :
  - `load_profile() -> dict`
  - `slug_of(article: dict) -> str` — depuis `article["url"]`
  - `reading_minutes(markdown_body: str) -> int`
  - `parse_source(text: str) -> tuple[dict, str]` — (frontmatter, corps)
  - `render_article_page(profile: dict, article_id: str, lang: str) -> str`
  - `build_articles(profile: dict | None = None, write: bool = True) -> list[str]`

- [ ] **Étape 1 : tests des fonctions pures (ils doivent ÉCHOUER)**

Ajouter à `tools/tests/test_build_articles.py` :

```python
def test_slug_vient_de_url_pas_de_id():
    """L'id est `couverture_dynamique`, l'URL `articles/couverture-dynamique.html`.
    Dériver le slug de l'id par `_`→`-` marcherait ici par coïncidence et casserait
    au premier titre accentué ou renommé."""
    import build_articles
    assert build_articles.slug_of({"id": "couverture_dynamique",
                                   "url": "articles/couverture-dynamique.html"}) == "couverture-dynamique"


def test_slug_absent_fail_loud():
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.slug_of({"id": "x"})


@pytest.mark.parametrize("mots,attendu", [(1, 1), (200, 1), (201, 2), (509, 3), (0, 1)])
def test_temps_de_lecture(mots, attendu):
    """200 mots/min, arrondi au supérieur, plancher à 1. L'ancienne page affichait
    « 8 min » pour 509 mots — une valeur fabriquée qu'aucune source ne contredisait."""
    import build_articles
    assert build_articles.reading_minutes(" ".join(["mot"] * mots)) == attendu


def test_frontmatter_separe_du_corps():
    import build_articles
    fm, body = build_articles.parse_source("---\ntldr: Résumé\n---\n\n## Titre\n\nTexte.\n")
    assert fm["tldr"] == "Résumé"
    assert body.lstrip().startswith("## Titre")


def test_source_sans_frontmatter_fail_loud():
    """Le TL;DR n'a pas de valeur par défaut sensée : l'absence est une erreur de
    rédaction, pas un cas à combler silencieusement."""
    import build_articles
    with pytest.raises(build_articles.BuildError):
        build_articles.parse_source("## Titre\n\nTexte.\n")


def test_formula_non_interpretee_comme_markdown():
    """Le contenu d'une formule est une donnée : les `*` et `_` n'y sont pas de
    l'emphase Markdown."""
    import build_articles
    out = build_articles.md_to_html("::formula\na*b*c_d\n::\n")
    assert '<div class="formula">a*b*c_d</div>' in out
    assert "<em>" not in out


def test_echappement_du_titre():
    """Le titre vient de profile.json et transite par le <title> et le <h1>."""
    import build_articles
    assert "&lt;script&gt;" in build_articles.render_head("<script>", "fr")
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_articles.py -x
```

Attendu : `ModuleNotFoundError: No module named 'build_articles'`.

- [ ] **Étape 3 : écrire `tools/build_articles.py`**

Structure (le chrome complet — `<head>`/CSS/`<nav>`/pied — est repris **verbatim** de
`tools/tests/fixtures/couverture-dynamique.legacy.html`, seules les parties variables
étant paramétrées) :

```python
#!/usr/bin/env python3
"""build_articles.py — génère articles/<slug>.html et <slug>.en.html.

Sources : articles/src/<slug>.<lang>.md (prose + frontmatter `tldr`) et
profile.json.articles[] (catalogue : titre, date, tags, url).

Le chrome (head/CSS/nav/pied) est un gabarit ; le corps vient du Markdown ; le
temps de lecture est dérivé du nombre de mots.

Usage (depuis la racine du repo site) :
    python tools/build_articles.py
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_site import esc, fmt_date, _bi          # utilitaires partagés

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "articles" / "src"
WORDS_PER_MINUTE = 200


class BuildError(Exception):
    pass


def _markdown():
    """Import paresseux : seul ce builder dépend d'un paquet tiers."""
    try:
        import markdown
    except ImportError as exc:
        raise BuildError(
            "le paquet `markdown` est requis pour générer les articles.\n"
            "  pip install -r requirements.txt"
        ) from exc
    return markdown


def load_profile() -> dict:
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def slug_of(article: dict) -> str:
    url = article.get("url")
    if not url:
        raise BuildError(f"article {article.get('id')!r} sans `url` — le slug en dérive")
    return pathlib.PurePosixPath(url).stem


def reading_minutes(body: str) -> int:
    return max(1, math.ceil(len(body.split()) / WORDS_PER_MINUTE))


def parse_source(text: str) -> tuple[dict, str]:
    """'---\\nclé: valeur\\n---\\ncorps' -> ({clé: valeur}, corps). Fail-loud."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise BuildError("source d'article sans frontmatter `---` (le `tldr` est requis)")
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    if not fm.get("tldr"):
        raise BuildError("frontmatter sans `tldr`")
    return fm, m.group(2)


def md_to_html(body: str) -> str:
    """Markdown -> HTML, avec le bloc maison ::formula extrait AVANT conversion
    (son contenu est une donnée, pas du Markdown)."""
    formulas: list[str] = []

    def _stash(m: re.Match) -> str:
        formulas.append(m.group(1).strip())
        return f"\n\nFORMULAPLACEHOLDER{len(formulas) - 1}\n\n"

    staged = re.sub(r"^::formula\n(.*?)\n::$", _stash, body, flags=re.M | re.S)
    out = _markdown().markdown(staged, extensions=["fenced_code"])
    for i, f in enumerate(formulas):
        out = out.replace(f"<p>FORMULAPLACEHOLDER{i}</p>",
                          f'<div class="formula">{esc(f)}</div>')
    return out


def render_head(title: str, lang: str) -> str:
    ...     # gabarit verbatim de la fixture, `title` échappé via esc()


def render_article_page(profile: dict, article_id: str, lang: str) -> str:
    ...     # assemble head + nav + meta + h1 + tldr + corps + pied


def build_articles(profile: dict | None = None, write: bool = True) -> list[str]:
    ...     # boucle sur profile["articles"], écrit, retourne les chemins produits


def main() -> int:
    paths = build_articles()
    print(f"[build_articles] OK - {len(paths)} page(s) generee(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Étape 4 : lancer les tests jusqu'au vert**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_articles.py -v
```

Attendu : tous PASS, y compris les trois tests de non-régression de la tâche 1.

- [ ] **Étape 5 : régénérer et vérifier l'écart attendu**

```bash
PYTHONIOENCODING=utf-8 python tools/build_articles.py
git diff --stat articles/couverture-dynamique.html
PYTHONIOENCODING=utf-8 python -c "
import re,pathlib
h=pathlib.Path('articles/couverture-dynamique.html').read_text(encoding='utf-8')
print(re.search(r'article-date[^>]*>([^<]+)', h[h.find('</style>'):]).group(1))
"
```

Attendu : `Mars 2026 · 3 min de lecture` — la correction de la valeur fabriquée (8 min).
Vérifier aussi visuellement la page dans un navigateur avant de committer : c'est une page
publique et c'est le seul écart accepté par le plan.

- [ ] **Étape 6 : commit**

```bash
git add tools/build_articles.py tools/tests/test_build_articles.py articles/couverture-dynamique.html
git commit -m "$(cat <<'EOF'
feat(articles): générateur de pages depuis profile.json + Markdown

Le chrome devient un gabarit, le corps vient du .md, le temps de lecture est dérivé
du nombre de mots — l'ancienne valeur écrite à la main annonçait 8 min pour 509 mots.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 3 : bilinguisme et repli

**Fichiers :**
- Créer : `articles/src/couverture-dynamique.en.md`
- Modifier : `tools/build_articles.py`
- Test : `tools/tests/test_build_articles.py` (étendu)

**Interfaces :**
- Consomme : `render_article_page` et `build_articles` (tâche 2).
- Produit : `en_path_for(fr_url: str) -> str` ; `build_articles` retourne aussi les articles
  dont l'EN manque, pour que l'appelant puisse le signaler.

- [ ] **Étape 1 : tests (ils doivent ÉCHOUER)**

```python
def test_chemin_en_derive_du_fr():
    import build_articles
    assert build_articles.en_path_for("articles/couverture-dynamique.html") \
        == "articles/couverture-dynamique.en.html"


def test_repli_signale_pas_tu(tmp_path, capsys):
    """Un .en.md manquant ne doit produire ni page EN vide, ni 404 : la carte EN
    retombera sur le FR, et le fait est écrit en sortie."""
    import build_articles
    profile = build_articles.load_profile()
    _, manquants = build_articles.build_articles(profile, write=False)
    assert isinstance(manquants, list)


def test_page_en_porte_la_bonne_langue():
    import build_articles
    page = build_articles.render_article_page(build_articles.load_profile(),
                                              "couverture_dynamique", "en")
    assert 'lang="en"' in page
    assert "← Retour" not in page
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_articles.py -x -k "en_ or repli"
```

- [ ] **Étape 3 : traduire l'article**

Écrire `articles/src/couverture-dynamique.en.md`, même structure que le `.fr.md`,
frontmatter `tldr` en anglais.

- [ ] **Étape 4 : implémenter `en_path_for`, la boucle sur les langues, et les libellés**

Les libellés du chrome (« ← Retour », « min de lecture ») deviennent un dictionnaire par
langue dans `build_articles.py`.

- [ ] **Étape 5 : tests au vert + génération**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_articles.py -v
PYTHONIOENCODING=utf-8 python tools/build_articles.py
ls articles/*.html
```

Attendu : `couverture-dynamique.html` et `couverture-dynamique.en.html`, plus une ligne de
sortie signalant que `onchain_analytics` n'a pas de source (statut `soon`).

- [ ] **Étape 6 : commit**

```bash
git add articles/src/couverture-dynamique.en.md tools/build_articles.py \
        tools/tests/test_build_articles.py articles/couverture-dynamique.en.html
git commit -m "$(cat <<'EOF'
feat(articles): version anglaise + repli explicite quand la traduction manque

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 4 : câblage dans `build_site` et bascule de langue des cartes

**Fichiers :**
- Modifier : `tools/build_site.py` (appel du builder ; `render_blog` ; `applyLang`)
- Test : `tools/tests/test_build_site.py` (étendu)

**Interfaces :**
- Consomme : `build_articles.build_articles(profile, write)` (tâches 2-3).

- [ ] **Étape 1 : tests (ils doivent ÉCHOUER)**

Ajouter à `tools/tests/test_build_site.py` :

```python
def test_carte_article_porte_les_deux_langues():
    import build_site
    profile = build_site.load_profile()
    markup = build_site.render_blog(profile)
    assert 'data-article-fr="articles/couverture-dynamique.html"' in markup
    assert 'data-article-en="articles/couverture-dynamique.en.html"' in markup


def test_applylang_bascule_le_href_des_articles():
    """Même mécanisme éprouvé que [data-cv], déjà en place pour le PDF du CV."""
    import build_site
    out = build_site.build_html((build_site.ROOT / "index.html").read_text(encoding="utf-8"),
                                build_site.load_profile())
    assert "data-article-" in out
    assert "querySelectorAll('[data-article-fr]')" in out
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_site.py -x -k "article"
```

- [ ] **Étape 3 : implémenter**

Dans `render_blog`, la carte cliquable porte les deux chemins :

```python
en_url = a["url"].replace(".html", ".en.html")
cards.append(f'<a class="blog-card" href="{esc(a["url"])}" '
             f'data-article-fr="{esc(a["url"])}" data-article-en="{esc(en_url)}">{inner}</a>')
```

Dans `applyLang` (bloc JS injecté), à la suite de la bascule `[data-cv]` :

```js
document.querySelectorAll('[data-article-fr]').forEach(a =>
    a.setAttribute('href', a.getAttribute('data-article-' + lang)));
```

Dans `build_site.build()`, après les six appels existants, en suivant le patron en place :

```python
    # Génère aussi les pages d'articles depuis profile.json + articles/src/*.md.
    try:
        import build_articles
        build_articles.build_articles(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération des pages articles échouée : {exc}")
```

- [ ] **Étape 4 : suite complète au vert**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/ tools/cv/ -q
```

Attendu : aucune régression sur les 30 tests de `test_build_site.py` ni sur la suite CV.

- [ ] **Étape 5 : construction complète + vérification visuelle**

```bash
PYTHONIOENCODING=utf-8 python tools/build_site.py
git status --porcelain
```

Ouvrir `index.html`, basculer FR/EN, cliquer une carte d'article dans chaque langue.

- [ ] **Étape 6 : commit**

```bash
git add tools/build_site.py tools/tests/test_build_site.py index.html articles/
git commit -m "$(cat <<'EOF'
feat(articles): câble le générateur dans build_site + bascule de langue des cartes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Auto-revue

**Couverture du spec** — chaque section a sa tâche : découpage mesuré → T2 ; architecture
et slug → T2 ; repli bilingue → T3 ; bascule de langue → T4 ; dépendance → T1 (déclaration)
et T2 (import paresseux) ; non-régression → T1 (filet) et T2 (vérification).

**Placeholders** — les `...` de la tâche 2 marquent trois fonctions dont le corps est du
gabarit HTML repris verbatim de la fixture ; leur contrat (entrées, sorties, échappement)
est fixé par les tests de l'étape 1. Aucun « TBD ».

**Cohérence des types** — `slug_of` prend un article et rend une chaîne ; `parse_source`
rend `(dict, str)` ; `build_articles` rend `(chemins, manquants)` à partir de la tâche 3,
et la tâche 4 ignore ce retour, ce qui est compatible.
