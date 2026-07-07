"""Génère des cas structured_cv + leur HTML Python pour le test de parité JS."""
import json
import pathlib

import cv_render
import cv_select

cases = []

# Cas 1-2 : réel profile.json, quant EN + full FR
_real = pathlib.Path(r"C:/Users/robla/VScode_Project/RoJLD.github.io/profile.json")
if _real.exists():
    prof = json.loads(_real.read_text(encoding="utf-8"))
    for name, key, thr, lang in [("real_quant_en", "quant", 0.6, "en"), ("real_full_fr", "general", 0.0, "fr")]:
        exps = cv_select.select_experiences(prof, {"relevance_key": key, "min_relevance": thr})
        cases.append((name, cv_select.build_structured_cv(prof, exps, lang)))

# Cas 3 : échappement (< > & " ')
cases.append(("escaping", {
    "lang": "fr",
    "identity": {"name": 'A&B <"O\'Neil">', "title": "T<i>", "email": "a@b"},
    "sections": [{"kind": "experience", "company": "X&Y", "title": "role's",
                  "dates": "2020 → 2021", "bullets": ["<script>alert('x')</script>", 'a "b" & c']}],
    "skills_top": ["C++", "R&D"],
    "footer": {"updated": "2026-07-07"},
}))

# Cas 4 : sections vides + skills vides
cases.append(("empty", {"lang": "en", "identity": {"name": "N"}, "sections": [],
                        "skills_top": [], "footer": {}}))

# Cas 5 : accents + séparateur unicode
cases.append(("accents", {"lang": "fr", "identity": {"name": "Éric Œuf", "title": "Ingénieur"},
                          "sections": [{"kind": "experience", "company": "Café", "title": "Résumé",
                                        "dates": "d", "bullets": ["été à Naïve"]}],
                          "skills_top": ["Python", "Café"], "footer": {"updated": "2026"}}))

out = [{"name": n, "cv": cv, "html_py": cv_render.render_html(cv)} for n, cv in cases]
pathlib.Path("parity_cases.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"{len(out)} cas générés")
