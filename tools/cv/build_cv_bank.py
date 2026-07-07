"""Σ-CV-ATELIER sous-projet B1 — génération de la banque de préfabriqués.

Lit profile.json (source de vérité) + cv_profiles.json (cfgs) → pour chaque
(profil × langue) : select_experiences → build_structured_cv → render_html →
Chromium headless page.pdf() (VRAI PDF texte, ATS-safe, même template CSS que le
client) → cv/prefab/{id}_{lang}.pdf + cv/prefab/index.json.

À lancer localement par Robin quand profile.json change :
    python tools/cv/build_cv_bank.py

Note churn (Σ-PROJECTION-IS-PURE-FN-OF-SOURCE) : Chromium embarque une date de
création dans le PDF → les octets varient d'un run à l'autre même sans changement
de contenu. Les PDF ne sont donc PAS byte-stables ; ne pas les régénérer sans
changement de profil pour éviter des diffs binaires bruités.
"""
from __future__ import annotations

import json
import pathlib
import sys

import cv_render
import cv_select

_HERE = pathlib.Path(__file__).resolve().parent           # tools/cv
_ROOT = _HERE.parents[1]                                    # repo root
_PROFILE = _ROOT / "profile.json"
_CFG = _HERE / "cv_profiles.json"
_OUT = _ROOT / "cv" / "prefab"
_LANGS = ("fr", "en")


def build(profile: dict, cfgs: list[dict]) -> list[dict]:
    """Génère les PDF et retourne le manifeste (liste d'entrées index.json)."""
    from playwright.sync_api import sync_playwright

    _OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for cfg in cfgs:
            for lang in _LANGS:
                exps = cv_select.select_experiences(profile, cfg)
                scv = cv_select.build_structured_cv(profile, exps, lang)
                html = cv_render.render_html(scv)
                page.set_content(html, wait_until="load")
                fname = f"{cfg['id']}_{lang}.pdf"
                page.pdf(path=str(_OUT / fname), format="A4", print_background=True,
                         margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
                manifest.append({
                    "id": cfg["id"],
                    "label": cfg["label"],
                    "lang": lang,
                    "file": f"cv/prefab/{fname}",
                    "n_experiences": len(exps),
                })
        browser.close()
    return manifest


def main() -> int:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    cfgs = json.loads(_CFG.read_text(encoding="utf-8"))["profiles"]
    manifest = build(profile, cfgs)
    (_OUT / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[cv-bank] {len(manifest)} PDF generes -> {_OUT}")
    for m in manifest:
        print(f"  {m['file']:32} ({m['n_experiences']} exp)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
