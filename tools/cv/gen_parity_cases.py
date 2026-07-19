"""Génère les cas de parité Python↔JS.

Deux familles :
- RENDU   : structured_cv figé → HTML Python (cv-render.js doit reproduire).
- PIPELINE: profile.json + cfg → select_experiences → build_structured_cv → HTML
            (cv-select.js doit reproduire la PROJECTION, pas seulement le rendu).

Le profil lu est celui du DÉPÔT COURANT (résolu depuis __file__). Un chemin absolu
codé en dur lisait un autre checkout : les « PASS » étaient alors vacuous — verts
sur un profil qui n'était pas celui de la branche.
"""
import json
import pathlib
import sys

import cv_render
import cv_select

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_PROFILE = _ROOT / "profile.json"
_CFGS = _HERE / "cv_profiles.json"

if not _PROFILE.exists():  # fail loud — jamais de dégradation silencieuse en vert
    sys.exit(f"[parity] profile.json introuvable : {_PROFILE}")

prof = json.loads(_PROFILE.read_text(encoding="utf-8"))
cfgs = json.loads(_CFGS.read_text(encoding="utf-8"))["profiles"]

cases = []

# 1-2 : profil RÉEL du dépôt (exerce education / languages / certifications / interests)
for name, key, thr, lang in [("real_quant_en", "quant", 0.6, "en"),
                             ("real_full_fr", "general", 0.0, "fr")]:
    _cfg = {"relevance_key": key, "min_relevance": thr}
    exps = cv_select.select_experiences(prof, _cfg)
    cases.append((name, cv_select.build_structured_cv(prof, exps, lang, _cfg)))

# 3 : échappement (< > & " ') — y compris dans les NOUVEAUX blocs
cases.append(("escaping", {
    "lang": "fr",
    "identity": {"name": 'A&B <"O\'Neil">', "title": "T<i>", "email": "a@b",
                 "location": "P<a>ris", "linkedin": "x.io/<i>", "github": "g/&co"},
    "sections": [{"kind": "experience", "company": "X&Y", "title": "role's",
                  "dates": "2020 → 2021", "bullets": ["<script>alert('x')</script>", 'a "b" & c']}],
    "skills_top": ["C++", "R&D"],
    "education": [{"school": "É<c>ole", "title": "T&T", "org": "O'rg", "period": "2020",
                   "degree": "D<g>", "courses_label": "Cours & co",
                   "courses": ["<b>c1</b>", "c&2"],
                   "capstone": {"label": "PFE <x>", "summary": "S'um & co"}}],
    "languages": [{"name": "F<r>", "level": "N&tif"}],
    "certifications": ["C<e>rt & co"],
    "interests": ["<i>Échecs</i>"],
    "footer": {"updated": "2026-07-07"},
}))

# 4 : tout vide / absent — les blocs doivent être SAUTÉS identiquement des deux côtés
cases.append(("empty", {"lang": "en", "identity": {"name": "N"}, "sections": [],
                        "skills_top": [], "education": [], "languages": [],
                        "certifications": [], "interests": [], "footer": {}}))

# 5 : accents + séparateur unicode
cases.append(("accents", {"lang": "fr", "identity": {"name": "Éric Œuf", "title": "Ingénieur"},
                          "sections": [{"kind": "experience", "company": "Café", "title": "Résumé",
                                        "dates": "d", "bullets": ["été à Naïve"]}],
                          "skills_top": ["Python", "Café"], "footer": {"updated": "2026"}}))

# 6 : nouveaux blocs PARTIELS (capstone None, courses vides, niveau/nom manquant)
cases.append(("partial_sections", {
    "lang": "fr", "identity": {"name": "P", "location": "Paris, France", "github": "g/h"},
    "sections": [],
    "education": [{"school": "S1", "title": "", "org": "", "period": "", "degree": "",
                   "courses_label": "", "courses": [], "capstone": None},
                  {"school": "", "title": "T2", "org": "O2", "period": "2019",
                   "degree": "D2", "courses_label": "CL", "courses": ["c"],
                   "capstone": {"label": "L", "summary": ""}}],
    "languages": [{"name": "FR", "level": ""}, {"name": "", "level": "C1"}],
    "certifications": ["A"], "interests": [], "footer": {},
}))

render_cases = [{"name": n, "cv": cv, "html_py": cv_render.render_html(cv)} for n, cv in cases]

# ── PIPELINE : parité de la PROJECTION (ordre + structured_cv + HTML) ─────────
# `sel_cfg` sert à select_experiences, `build_cfg` à build_structured_cv (il peut
# être None : c'est le chemin du NAVIGATEUR, qui appelle sans cfg — sans ce cas,
# l'ordre par défaut des catégories n'était vérifié par rien).
_SEL = {"relevance_key": "general", "min_relevance": 0.0}

# Variante : une entrée skills SANS `name` exploitable. Témoin de l'invariant
# anti-fuite CÔTÉ JS aussi (le profil réel n'a que des `name` propres, donc la
# régression `[object Object]` / champs internes y était invisible).
_prof_noname = json.loads(json.dumps(prof))
_prof_noname.setdefault("skills", {})["programming"] = [
    {"weight": 0.9, "level": "expert", "used_in": ["x"]},   # pas de `name`
    {"name": "SQL"},
]

pipeline = []
for cfg in cfgs:
    for lang in ("fr", "en"):
        pipeline.append({"name": f"pipe_{cfg['id']}_{lang}", "sel_cfg": cfg,
                         "build_cfg": cfg, "lang": lang, "profile": None})

pipeline += [
    # build SANS cfg → exerce _DEFAULT_SKILL_CATS (ordre inclus), chemin navigateur
    {"name": "pipe_nocfg_fr", "sel_cfg": _SEL, "build_cfg": None, "lang": "fr", "profile": None},
    {"name": "pipe_nocfg_en", "sel_cfg": _SEL, "build_cfg": None, "lang": "en", "profile": None},
    # entrée skills sans `name` → anti-fuite témoin des DEUX côtés
    {"name": "pipe_noname_fr", "sel_cfg": _SEL, "build_cfg": None, "lang": "fr",
     "profile": _prof_noname},
    # cap actif → exerce skills_per_category des DEUX côtés
    {"name": "pipe_cap_fr", "sel_cfg": _SEL, "lang": "fr", "profile": None,
     "build_cfg": {**_SEL, "skills_per_category": 2}},
]

for c in pipeline:
    p = c["profile"] or prof
    exps = cv_select.select_experiences(p, c["sel_cfg"])
    scv = cv_select.build_structured_cv(p, exps, c["lang"], c["build_cfg"])
    c["order_py"] = [e.get("id") for e in exps]
    c["scv_py"] = scv
    c["html_py"] = cv_render.render_html(scv)

out = {"render": render_cases, "pipeline": {"profile": prof, "cases": pipeline}}
(_HERE / "parity_cases.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(render_cases)} cas rendu + {len(pipeline)} cas pipeline générés")
