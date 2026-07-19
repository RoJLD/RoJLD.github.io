# Générateur d'articles — conception

**Date** : 2026-07-19
**Statut** : approuvé
**Portée** : ramener les pages d'articles sous le keystone `profile.json` → génération, et rendre le blog bilingue.

## 1. Problème

`articles/couverture-dynamique.html` (11 Ko) est **écrit à la main**. Aucun builder ne le
produit — `grep 'articles/'` sur `tools/` ne retourne rien. C'est la seule page publiée du
site qui échappe au keystone.

Le modèle, lui, existe déjà et est largement consommé. `profile.json.articles[]` porte
`id`, `domains`, `title` (fr/en), `desc` (fr/en), `url`, `date`, `tags`, `status`, et
**cinq** modules le lisent :

| Consommateur | Usage |
|---|---|
| `tools/build_site.py` | section `#blog` (cartes) — c'était le pilote SP0 |
| `tools/build_browse.py` | flux unifié de tout le contenu |
| `tools/build_graph.py` | nœuds du graphe de connaissance |
| `tools/build_highlights.py` | sélection mise en avant (cap 2) |
| `tools/cv/profile_pipeline.py` | nœuds + arêtes `has_domain` du graphe de profil |

Le manque n'est donc **pas** le modèle ni le rendu des cartes, mais la génération du corps
des pages. Second défaut, conséquence du premier : la carte est bilingue, la page est
monolingue FR (`lang="fr"`, « ← Retour » en dur). Un lecteur anglophone clique sur une
carte anglaise et atterrit en français.

## 2. Découpage mesuré de la page existante

Relevé sur `articles/couverture-dynamique.html` :

| Élément | Provenance retenue |
|---|---|
| `<head>`, CSS, `<nav>`, pied d'auteur | chrome — gabarit unique du générateur |
| `<h1>` | `articles[].title[lang]` (identique au titre de la carte — vérifié) |
| Date affichée (« Mars 2026 ») | `articles[].date` + `fmt_date()` (existe dans `build_site`) |
| « · 8 min de lecture » | **dérivé** du nombre de mots du `.md` |
| Tags | `articles[].tags[]` |
| `.article-tldr` | **distinct de `desc`** → frontmatter du `.md` |
| Corps : `h2`/`h3`/`p`/`ul`/`pre`/`blockquote`/`.formula` | le `.md` |
| Bio de pied de page | `identity` + `education` |
| Chemin FR | `articles[].url` (déjà présent) ; EN dérivé en `<base>.en.html` |

Le TL;DR n'est pas le `desc`. Le `desc` vend l'article de l'extérieur (carte, flux,
highlights) ; le TL;DR livre la conclusion à un lecteur déjà entré. Deux fonctions, deux
textes — les fusionner reviendrait à réécrire le texte de l'auteur.

Le temps de lecture est aujourd'hui écrit en dur. Le dériver du nombre de mots le rend
incapable de diverger : un paragraphe allongé met le chiffre à jour tout seul. Même
principe que le CV public, fonction pure de la source.

## 3. Architecture

```
articles/src/<slug>.<lang>.md   ──┐
                                  ├──> build_articles.py ──> articles/<slug>.html
profile.json.articles[]        ──┘                          articles/<slug>.en.html
```

**Le `.md` ne contient que la prose**, plus un frontmatter minimal :

```markdown
---
tldr: TL;DR : la couverture dynamique en delta-hedging fonctionne bien en théorie…
---

## Le modèle théorique

Le delta-hedging suppose…

::formula
Δ = ∂V/∂S
::
```

Un seul champ de frontmatter (`tldr`). Tout le reste vient de `profile.json`, qui reste la
source de vérité du catalogue : **aucun champ nouveau n'est requis dans le schéma**.

### Slug et chemins

`articles[].url` vaut déjà `articles/couverture-dynamique.html` : c'est la correspondance
`id` → chemin, et elle est publique. Le slug s'en **déduit** (`couverture-dynamique`), il
n'est pas recalculé depuis l'`id` (`couverture_dynamique`) — une dérivation
`_` → `-` marcherait ici par coïncidence et casserait au premier titre accentué.
La version EN dérive du chemin FR : `<base>.en.html`.

L'URL FR existante est donc **préservée par construction**. C'est un lien public,
potentiellement indexé.

### Repli bilingue

Si `<slug>.en.md` est absent, la carte EN pointe vers la version FR accompagnée d'un badge,
jamais vers un 404. Le générateur **le signale en sortie** — un repli silencieux serait un
masquage.

### Bascule de langue

`applyLang()` (dans `index.html`) réécrit déjà les `href` des liens `[data-cv]` au
changement de langue :

```js
const cvPdf = {fr:'cv/prefab/full_fr.pdf', en:'cv/prefab/full_en.pdf'}[lang];
document.querySelectorAll('[data-cv]').forEach(a => a.setAttribute('href', cvPdf));
```

Les cartes d'articles empruntent ce chemin éprouvé : elles portent `data-article-fr` et
`data-article-en`, et `applyLang` bascule le `href`. Aucun mécanisme nouveau.

## 4. Dépendance

Les six builders (3102 lignes) sont **100 % stdlib** — `collections`, `html`, `json`,
`math`, `pathlib`, `re`. Aucun `requirements.txt`, aucune CI : la construction se fait en
local et le HTML est commité, GitHub Pages sert le résultat.

« Zéro dépendance » n'est écrit nulle part : c'est un invariant **implicite**, et ceux-là
sont les plus fragiles — rien ne les protège. `markdown` et `markdown_it` étant déjà
installés sur la machine de développement, un `import markdown` passerait ici et casserait
partout ailleurs, sans message utile.

Décision : **utiliser `markdown` et le déclarer** dans un `requirements.txt`, avec import
paresseux dans `build_articles` et échec bruyant et actionnable s'il manque. Écrire un
convertisseur Markdown maison en expressions régulières est un piège connu — les cas
limites (code inline contenant des astérisques, `<` dans un bloc de code, listes
imbriquées) sont précisément là où ces parseurs cèdent, et les articles sont publics.
Transformer l'invariant implicite en contrat explicite coûte trois lignes.

Le reste du site continue de construire sans la dépendance : seul `build_articles` la
réclame, et `build_site.build()` propage l'échec au lieu de le taire.

### Bloc maison `::formula`

`markdown` ne connaît pas `.formula`. Un préprocesseur transforme
`::formula\n…\n::` en `<div class="formula">…</div>` **avant** la conversion, sur le même
principe que les blocs de code protégés : le contenu de la formule n'est pas interprété
comme du Markdown.

## 5. Fichiers

**Créer**
- `tools/build_articles.py` — le générateur
- `tools/tests/test_build_articles.py` — les tests
- `articles/src/couverture-dynamique.fr.md` — migration du contenu existant
- `articles/src/couverture-dynamique.en.md` — traduction
- `requirements.txt` — déclare `markdown`

**Modifier**
- `tools/build_site.py` — appel du builder ; cartes portant `data-article-fr`/`data-article-en` ; `applyLang` réécrit le `href`

**Régénéré**
- `articles/couverture-dynamique.html` (URL inchangée)
- `articles/couverture-dynamique.en.html` (nouveau)
- `index.html` (section `#blog`)

## 6. Non-régression

`articles/couverture-dynamique.html` est **publié**. La migration préserve l'URL et le
texte, mais **pas** le HTML octet pour octet : Markdown normalise le balisage, et exiger
l'identité stricte ferait entrer dans le générateur les particularités d'une page écrite à
la main.

Le test compare donc, entre l'ancienne page et la nouvelle :
- le texte dépouillé de ses balises, section par section ;
- l'ordre et le nombre des `h2`/`h3` ;
- le contenu des `.formula` et des `pre` (à l'identique — ce sont des données, pas de la
  mise en forme) ;
- l'URL.

C'est le seul endroit du plan où une différence est acceptée, et il est public : une
vérification visuelle précède le commit.

## 7. Hors périmètre

- Les autres pages écrites à la main, s'il en reste (aucune mesurée).
- Un flux RSS.
- Des commentaires.
- La rédaction du second article (`onchain_analytics`, `status: soon`) : le générateur le
  débloque, il ne l'écrit pas.
