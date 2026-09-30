"""I1 (revue finale opus, 2026-09-29) : `stages.prefab` est-il vraiment affiché
sur /edit ET /cms, ou seulement calculé puis jeté ?

`_EDIT` et `_CMS` (tools/cockpit/pages/cv.py) bâtissaient leur barre de statut
depuis `res.stages` (history, review, graph, rebuild) sans jamais lire
`stages.prefab` : un gate de banque refusé (build_cv_bank.main() lève SystemExit
sur profil invalide, ou Chromium échoue à mi-régénération) restait invisible
derrière un « Enregistré ✓ » vert — le profil est enregistré, mais les 8 PDF
publics restent périmés ou mélangés, et rien ne le dit à l'écran.

Ce harnais (cv_save_status_harness) exécute le VRAI script de chaque page
contre un `fetch('/save', …)` stubé et lit l'état FINAL de `#status` / `#errs` —
un oracle de comportement, pas de présence textuelle.
"""
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from tools.cockpit import server  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv_save_status_harness as statut_js  # noqa: E402


class _Srv:
    def __enter__(self):
        self.srv = server.make_server(0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}"

    def __exit__(self, *a):
        self.srv.shutdown(); self.srv.server_close()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def _rapport_gate_en_echec():
    return {
        "ok": True,
        "stages": {
            "history": {"snapshot": "20260930T120000"},
            "review": {"available": False, "notes": []},
            "graph": {"nodes": 10, "edges": 5},
            "rebuild": {"skipped": True},
            "prefab": {"ok": False,
                       "error": "RuntimeError: gate de banque prefab refuse (profil invalide)"},
        },
    }


def test_edit_montre_un_gate_de_banque_en_echec(node_requis):
    with _Srv() as base:
        code, page = _get(base, "/edit")
    assert code == 200
    r = statut_js.run_save_status(page, needle="async function save",
                                   trigger="save()", report=_rapport_gate_en_echec())
    assert "échou" in r["status_text"].lower(), r
    assert r["status_class"] == "err", r
    assert "préfab" in r["errs_text"].lower() or "prefab" in r["errs_text"].lower(), r


def test_cms_montre_un_gate_de_banque_en_echec(node_requis):
    with _Srv() as base:
        code, page = _get(base, "/cms")
        assert code == 200
        code2, cms_model_js = _get(base, "/assets/js/cms-model.js")
        assert code2 == 200
    r = statut_js.run_save_status(
        page, needle='$("save").onclick',
        trigger="document.getElementById('save').onclick()",
        report=_rapport_gate_en_echec(), prelude=cms_model_js)
    assert "échou" in r["status_text"].lower(), r
    assert r["status_class"] == "err", r
    assert "préfab" in r["errs_text"].lower() or "prefab" in r["errs_text"].lower(), r


def test_edit_reste_ok_quand_la_banque_reussit(node_requis):
    """Contre-épreuve : succès -> pas d'état d'erreur (une garde qui rougirait
    tout le temps ne garderait rien)."""
    rapport = _rapport_gate_en_echec()
    rapport["stages"]["prefab"] = {"ok": True}
    with _Srv() as base:
        code, page = _get(base, "/edit")
    assert code == 200
    r = statut_js.run_save_status(page, needle="async function save",
                                   trigger="save()", report=rapport)
    assert r["status_class"] != "err", r
    assert "préfab" in r["status_text"].lower() or "prefab" in r["status_text"].lower(), r


def test_cms_reste_ok_quand_la_banque_reussit(node_requis):
    rapport = _rapport_gate_en_echec()
    rapport["stages"]["prefab"] = {"ok": True}
    with _Srv() as base:
        code, page = _get(base, "/cms")
        assert code == 200
        code2, cms_model_js = _get(base, "/assets/js/cms-model.js")
        assert code2 == 200
    r = statut_js.run_save_status(
        page, needle='$("save").onclick',
        trigger="document.getElementById('save').onclick()",
        report=rapport, prelude=cms_model_js)
    assert r["status_class"] != "err", r
    assert "préfab" in r["status_text"].lower() or "prefab" in r["status_text"].lower(), r
