# Templates CV phase 1 — plan d'implémentation

> **Pour les exécutants agentiques :** SOUS-COMPÉTENCE REQUISE —
> `superpowers:subagent-driven-development` ou `superpowers:executing-plans`.
> Les étapes utilisent la syntaxe case à cocher (`- [ ]`).

**But :** transformer le template CV unique, aujourd'hui dupliqué en code, en une banque de
templates pilotée par des données, sans changer d'un octet le CV produit par défaut.

**Architecture :** `cv/templates/<id>.json` porte `style` (ce que le moteur consomme) et
`meta` (ce que le ciblage lit pour choisir). `build_css(style)` existe des deux côtés de la
paire miroir Python/JS. Un huitième builder génère `assets/js/cv-templates.js` depuis les
JSON, pour que le navigateur y accède sans réseau.

**Pile :** Python 3.13 stdlib, Node pour le harnais de parité, `pytest`.

**Spec :** `docs/superpowers/specs/2026-07-19-documents-cibles-design.md` (§3 et §6).

## Contraintes globales

- **Le CSS du template `sobre` doit être identique À L'OCTET à l'actuel `CV_CSS`**
  (1483 octets, 23 règles). C'est le garde-fou central : il se vérifie par machine, via une
  fixture figée avant toute modification.
- `tools/cv/cv_render.py` (187 lignes) et `assets/js/cv-render.js` (176 lignes) forment une
  **paire miroir**. Toute fonction ajoutée d'un côté l'est à l'identique de l'autre. Les
  42 cas de parité existants restent verts **sans modification**.
- Les 8 PDF préfabriqués `cv/prefab/*.pdf` restent produits par le même chemin.
- L'atelier fonctionne sans template choisi : défaut = `sobre`.
- `assets/js/cv-templates.js` est **généré** — jamais édité à la main, et le builder est
  idempotent.
- Aucune dépendance tierce nouvelle. Le site doit rester utilisable hors ligne : pas de
  `fetch` des templates depuis le navigateur.
- Sur cette machine, préfixer toute commande Python par `PYTHONIOENCODING=utf-8`.

---

### Tâche 1 : figer l'existant et extraire `sobre`

Produire le fichier de données du template actuel et prouver qu'il régénère le CSS
d'aujourd'hui à l'octet près. **Aucune modification du moteur à ce stade** : la tâche
livre la donnée et le test qui la contraint.

**Fichiers :**
- Créer : `tools/cv/fixtures/cv_css.legacy.txt` (copie figée de `CV_CSS`)
- Créer : `cv/templates/sobre.json`
- Créer : `tools/cv/test_cv_templates.py`

**Interfaces :**
- Produit : `cv/templates/sobre.json` et la fixture, consommés par les tâches 2 et 3.

- [ ] **Étape 1 : figer le CSS actuel**

```bash
cd C:/Users/robla/VScode_Project/cv-parity-wt
mkdir -p tools/cv/fixtures cv/templates
PYTHONIOENCODING=utf-8 python -c "
import sys, pathlib; sys.path.insert(0, 'tools/cv')
import cv_render
pathlib.Path('tools/cv/fixtures/cv_css.legacy.txt').write_text(cv_render.CV_CSS, encoding='utf-8')
print(len(cv_render.CV_CSS), 'octets figés')
"
```

Attendu : `1483 octets figés`.

- [ ] **Étape 2 : écrire le test (il doit ÉCHOUER)**

Créer `tools/cv/test_cv_templates.py` :

```python
"""Le template `sobre` doit régénérer le CSS actuel À L'OCTET.

C'est le garde-fou central de l'extraction : tant qu'il tient, la banque de
templates ne peut pas altérer le CV par défaut — celui qui part réellement aux
recruteurs. Même motif que la migration de l'article : l'artefact d'origine est
figé en fixture, la génération doit le reproduire.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

LEGACY_CSS = (HERE / "fixtures" / "cv_css.legacy.txt").read_text(encoding="utf-8")
TEMPLATES = ROOT / "cv" / "templates"


def _charge(tid: str) -> dict:
    return json.loads((TEMPLATES / f"{tid}.json").read_text(encoding="utf-8"))


def test_sobre_regenere_le_css_a_l_octet():
    import cv_templates
    assert cv_templates.build_css(_charge("sobre")["style"]) == LEGACY_CSS


def test_fixture_non_vide():
    """Garde anti-vacuité : une fixture vide ferait passer le test précédent
    contre un moteur qui ne produit rien."""
    assert len(LEGACY_CSS) == 1483
    assert LEGACY_CSS.count("{") >= 23
```

- [ ] **Étape 3 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/cv/test_cv_templates.py -q
```

Attendu : `ModuleNotFoundError: No module named 'cv_templates'`.

- [ ] **Étape 4 : écrire `cv/templates/sobre.json`**

Décomposer `tools/cv/fixtures/cv_css.legacy.txt` en `style`. Relevé de l'existant :
8 couleurs (`#1a1a2e`, `#16213e`, `#4361ee`, `#444`, `#555`, `#777`, `#999`, `#dde`),
6 tailles (`17pt`, `10.5pt`, `9.8pt`, `9pt`, `8.5pt`, `8pt`), page `A4` marge `12mm 14mm`.

```json
{
  "id": "sobre",
  "label": { "fr": "Sobre", "en": "Plain" },
  "meta": {
    "pages": 1,
    "market": ["FR", "EU"],
    "tone": "corporate",
    "ats_safe": true,
    "sections": ["identity", "experience", "education", "skills", "languages",
                 "certifications", "interests"]
  },
  "style": {
    "page":    { "size": "A4", "margin": "12mm 14mm" },
    "palette": { "ink": "#1a1a2e", "ink_2": "#16213e", "accent": "#4361ee",
                 "body": "#444", "muted": "#555", "faint": "#777", "faint_2": "#999",
                 "rule": "#dde" },
    "type":    { "h1": "17pt", "h2": "10.5pt", "base": "9.8pt", "small": "9pt",
                 "tiny": "8.5pt", "micro": "8pt" },
    "density": { "line": 1.3 }
  }
}
```

Les noms de clés doivent couvrir **exactement** les valeurs présentes dans la fixture : si
une valeur n'a pas de clé, l'étape 6 échouera à reproduire le CSS.

- [ ] **Étape 5 : commit**

```bash
git add tools/cv/fixtures/cv_css.legacy.txt cv/templates/sobre.json tools/cv/test_cv_templates.py
git commit -m "$(cat <<'EOF'
feat(cv-templates): fige le CSS actuel et extrait le template `sobre` en donnée

Le garde-fou de toute l'extraction : le template par défaut doit régénérer le CSS
d'aujourd'hui à l'octet près. La fixture est figée avant toute modification du moteur.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 2 : le moteur `build_css`, côté Python

**Fichiers :**
- Créer : `tools/cv/cv_templates.py`
- Modifier : `tools/cv/cv_render.py`
- Test : `tools/cv/test_cv_templates.py` (étendu)

**Interfaces :**
- Consomme : `cv/templates/sobre.json` (tâche 1).
- Produit :
  - `charger(template_id: str) -> dict` — lit et valide un template
  - `lister() -> list[dict]` — tous les templates, triés par `id`
  - `build_css(style: dict) -> str`
  - `DEFAUT = "sobre"`
  - `cv_render.render_html(structured_cv, template=None)` — `None` ⇒ `sobre`

- [ ] **Étape 1 : tests (ils doivent ÉCHOUER)**

```python
def test_build_css_est_pur():
    """Mêmes entrées, même sortie — condition nécessaire de la parité."""
    import cv_templates
    st = _charge("sobre")["style"]
    assert cv_templates.build_css(st) == cv_templates.build_css(st)


def test_build_css_reflete_la_palette():
    """Garde anti-gabarit-figé : un moteur qui ignorerait `style` et renverrait la
    constante passerait le test d'identité octet de la tâche 1."""
    import cv_templates
    st = json.loads(json.dumps(_charge("sobre")["style"]))
    st["palette"]["accent"] = "#ff0000"
    css = cv_templates.build_css(st)
    assert "#ff0000" in css and "#4361ee" not in css


def test_style_incomplet_fail_loud():
    """Une clé absente ne doit pas produire un CSS silencieusement dégradé."""
    import cv_templates
    st = json.loads(json.dumps(_charge("sobre")["style"]))
    del st["palette"]["accent"]
    with pytest.raises(cv_templates.TemplateError, match="accent"):
        cv_templates.build_css(st)


def test_charger_template_inconnu_fail_loud():
    import cv_templates
    with pytest.raises(cv_templates.TemplateError, match="inconnu|introuvable"):
        cv_templates.charger("nexistepas")


def test_meta_declare_les_champs_attendus():
    """`meta` est ce que le ciblage lira pour CHOISIR un template : ses champs sont
    un contrat, pas de la documentation."""
    import cv_templates
    for t in cv_templates.lister():
        for champ in ("pages", "market", "tone", "ats_safe", "sections"):
            assert champ in t["meta"], f"{t['id']} : meta.{champ} manquant"
        assert isinstance(t["meta"]["sections"], list) and t["meta"]["sections"]


def test_render_html_sans_template_est_inchange():
    """Non-régression : l'appel historique à un argument doit produire exactement
    ce qu'il produisait."""
    import cv_render
    scv = {"lang": "fr", "identity": {"name": "N"}, "sections": [],
           "skills_top": [], "footer": {}}
    assert LEGACY_CSS in cv_render.render_html(scv)
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/cv/test_cv_templates.py -q
```

- [ ] **Étape 3 : écrire `tools/cv/cv_templates.py`**

```python
#!/usr/bin/env python3
"""cv_templates.py — banque de templates CV, pilotée par des données.

Un template est un fichier `cv/templates/<id>.json` : `style` est ce que le moteur
consomme, `meta` ce que le ciblage lit pour choisir. Ajouter un design coûte un
fichier de données, jamais deux implémentations — le rendu du CV existe en paire
miroir Python/JS, et dupliquer un gabarit en code coûterait 2N artefacts à tenir
synchronisés.

Miroir : `assets/js/cv-templates.js` doit reproduire `build_css` à l'octet.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "cv" / "templates"
DEFAUT = "sobre"


class TemplateError(Exception):
    pass


def charger(template_id: str) -> dict:
    ...     # lit, valide meta + style, fail-loud si inconnu ou incomplet


def lister() -> list[dict]:
    ...     # tous les *.json, triés par id, chacun validé


def build_css(style: dict) -> str:
    ...     # assemble les 23 règles depuis palette/type/density/page
```

`build_css` reconstruit les 23 règles à partir de `style`. Chaque accès à une clé
passe par un helper qui lève `TemplateError` en nommant la clé absente — un
`.get(k, "")` produirait un CSS dégradé silencieux.

- [ ] **Étape 4 : câbler `cv_render.render_html`**

Ajouter le paramètre optionnel `template` ; `None` ⇒ `charger(DEFAUT)`. La constante
`CV_CSS` **reste en place** et devient la valeur de repli, pour que le module
fonctionne même si `cv/templates/` est absent (clone partiel).

- [ ] **Étape 5 : tests au vert + suite complète**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/cv/ tools/tests/ -q
```

Attendu : tous verts, dont les tests de parité et de rendu existants inchangés.

- [ ] **Étape 6 : mutation testing**

Muter une par une, restaurer entre chaque, et confirmer le ROUGE :
`build_css` renvoyant `CV_CSS` en dur · le helper d'accès remplacé par `.get(k, "")` ·
`DEFAUT` pointant un autre id · `lister()` ne validant plus `meta`.

Un mutant survivant signale un test vacant, **pas** un mutant inoffensif : le vérifier
en observant le comportement, pas le diff.

- [ ] **Étape 7 : commit**

```bash
git add tools/cv/cv_templates.py tools/cv/cv_render.py tools/cv/test_cv_templates.py
git commit -m "$(cat <<'EOF'
feat(cv-templates): moteur build_css piloté par les données, côté Python

Le CSS du template par défaut reste identique à l'octet ; CV_CSS demeure comme repli
si cv/templates/ est absent.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 3 : le miroir navigateur

**Fichiers :**
- Créer : `tools/build_cv_templates.py`
- Créer : `assets/js/cv-templates.js` (**généré**)
- Modifier : `assets/js/cv-render.js`
- Modifier : `tools/build_site.py`
- Test : `tools/tests/test_build_cv_templates.py`, `tools/cv/parity.js`

**Interfaces :**
- Consomme : `cv_templates.lister()` (tâche 2).
- Produit : `window.CVTemplates = { DEFAUT, all, get(id), buildCss(style) }`.

- [ ] **Étape 1 : tests (ils doivent ÉCHOUER)**

```python
def test_bundle_contient_tous_les_templates():
    import build_cv_templates, cv_templates
    js = build_cv_templates.build_cv_templates(write=False)
    for t in cv_templates.lister():
        assert f'"{t["id"]}"' in js


def test_bundle_idempotent():
    import build_cv_templates
    assert build_cv_templates.build_cv_templates(write=False) \
        == build_cv_templates.build_cv_templates(write=False)


def test_bundle_sans_fetch():
    """Le site doit fonctionner hors ligne : les templates sont INLINÉS, jamais
    récupérés par le réseau."""
    import build_cv_templates
    js = build_cv_templates.build_cv_templates(write=False)
    for interdit in ("fetch(", "XMLHttpRequest", "import(", "require("):
        assert interdit not in js


def test_echec_du_builder_templates_remonte(monkeypatch):
    """Zero Masking, même leçon que pour les articles : un builder dont l'échec est
    avalé laisse la construction verte avec un artefact périmé."""
    import pytest, build_cv_templates
    monkeypatch.setattr(build_cv_templates, "build_cv_templates",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boum")))
    with pytest.raises(bs.BuildError, match="templates"):
        bs.build(write=False)
```

Et dans `tools/cv/parity.js`, un cas **par template**, énuméré depuis les données et non
écrit à la main — une liste manuelle prendrait du retard au premier ajout :

```js
for (const t of data.templates) {
  check(`css:${t.id}`, t.css_py, CVTemplates.buildCss(t.style));
}
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/test_build_cv_templates.py -q
```

- [ ] **Étape 3 : écrire le builder et le miroir JS**

`tools/build_cv_templates.py` suit le patron des sept builders existants
(`build_projects.py` en modèle) : `build_cv_templates(profile=None, write=True) -> str`,
un `main()`, et un appel depuis `build_site.build()` enrobé en `BuildError`.

`assets/js/cv-templates.js` porte les templates inlinés et `buildCss`, transcription
exacte de la fonction Python. `assets/js/cv-render.js` accepte le paramètre `template`
comme son homologue.

- [ ] **Étape 4 : parité**

```bash
cd tools/cv
PYTHONIOENCODING=utf-8 python gen_parity_cases.py && node parity.js
```

Attendu : les 42 cas existants verts, **plus** un cas CSS par template.

- [ ] **Étape 5 : suite complète + construction**

```bash
cd C:/Users/robla/VScode_Project/cv-parity-wt
PYTHONIOENCODING=utf-8 python -m pytest tools/tests/ tools/cv/ -q
PYTHONIOENCODING=utf-8 python tools/build_site.py
git status --porcelain
```

- [ ] **Étape 6 : commit**

```bash
git add tools/build_cv_templates.py assets/js/cv-templates.js assets/js/cv-render.js \
        tools/build_site.py tools/tests/test_build_cv_templates.py \
        tools/cv/gen_parity_cases.py tools/cv/parity.js
git commit -m "$(cat <<'EOF'
feat(cv-templates): miroir navigateur généré + un cas de parité par template

Les templates sont inlinés dans un bundle généré : le site reste utilisable hors
ligne. Les cas de parité sont énumérés depuis les données, pas listés à la main.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Tâche 4 : deux nouveaux templates + choix dans l'atelier

**Fichiers :**
- Créer : `cv/templates/dense.json`, `cv/templates/ats.json`
- Modifier : `tools/cv/atelier.py`
- Test : `tools/cv/test_cv_templates.py`, `tools/cv/test_atelier.py`

- [ ] **Étape 1 : tests (ils doivent ÉCHOUER)**

```python
@pytest.mark.parametrize("tid", ["sobre", "dense", "ats"])
def test_chaque_template_produit_un_css_valide(tid):
    import cv_templates
    css = cv_templates.build_css(_charge(tid)["style"])
    assert css.count("{") == css.count("}")
    assert "@page" in css and "None" not in css


def test_les_templates_different_vraiment():
    """Trois fichiers produisant le même CSS seraient une banque en trompe-l'œil."""
    import cv_templates
    css = {t: cv_templates.build_css(_charge(t)["style"]) for t in ("sobre", "dense", "ats")}
    assert len(set(css.values())) == 3


def test_ats_est_declare_et_reellement_sobre():
    """`meta.ats_safe` est lu par le ciblage : il doit décrire le fichier, pas le
    flatter. Un template ATS n'a ni couleur d'accent ni fantaisie typographique."""
    import cv_templates
    t = _charge("ats")
    assert t["meta"]["ats_safe"] is True
    css = cv_templates.build_css(t["style"])
    assert t["style"]["palette"]["accent"] in ("#000", "#000000", "#1a1a2e")


def test_atelier_expose_les_templates():
    import atelier
    page = atelier._page()
    for tid in ("sobre", "dense", "ats"):
        assert tid in page
```

- [ ] **Étape 2 : lancer, vérifier l'échec**

- [ ] **Étape 3 : écrire les deux templates**

`dense` — même palette, densité accrue (marges 10mm, base 9pt, interligne 1.2) pour tenir
un parcours plus long sur une page. `ats` — noir sur blanc, sans accent ni règle colorée,
destiné aux robots d'analyse.

- [ ] **Étape 4 : câbler le choix dans l'atelier**

Un sélecteur alimenté par `cv_templates.lister()`, défaut `sobre`, transmis à
`/generate`. Les libellés viennent de `label[lang]`.

- [ ] **Étape 5 : vérification humaine**

Générer les trois PDF et les regarder. C'est le seul endroit du plan qu'aucun test ne
couvre : « le CV est-il beau » n'est pas une assertion.

```bash
cd tools/cv && PYTHONIOENCODING=utf-8 python atelier.py
```

- [ ] **Étape 6 : suite complète, parité, commit**

---

## Auto-revue

**Couverture du spec** — §3 modèle → T1 ; moteur → T2 ; miroir navigateur et harnais de
parité → T3 ; `meta` et choix → T2/T4 ; §6 non-régression → T1 (fixture octet), T2
(render_html inchangé), T3 (42 cas verts), T4 (PDF regardés).

**Placeholders** — les `...` de la tâche 2 marquent trois fonctions dont le contrat est
fixé par les tests de l'étape 1 et dont le corps est mécanique (assemblage de chaînes
depuis un dict). Aucun « TBD ».

**Cohérence des types** — `charger` rend un `dict` complet ; `lister` une `list[dict]` ;
`build_css` prend le sous-dict `style` et rend `str`. La tâche 3 consomme `lister()` et la
tâche 4 `charger()`. `render_html(scv, template=None)` reste rétro-compatible à un argument.

**Risque identifié** — la tâche 2 introduit une asymétrie temporaire : `build_css` existe
en Python et pas encore en JS. Les 42 cas de parité portent sur le rendu et non sur le CSS,
donc ils restent verts ; l'asymétrie est refermée en tâche 3. À ne pas livrer en s'arrêtant
à la tâche 2.
