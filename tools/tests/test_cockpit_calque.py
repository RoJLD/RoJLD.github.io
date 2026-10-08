"""Cœur du calque d'édition exécuté dans node (comme les autres oracles JS du site)."""
import json
import subprocess
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_node  # noqa: E402

CALQUE = SITE / "tools" / "cockpit" / "static" / "calque.js"


def _node(expression: str):
    node = oracle_node.porte()
    programme = f"const C = require({json.dumps(str(CALQUE))});\nconsole.log(JSON.stringify({expression}));"
    out = subprocess.run([node, "-e", programme], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_texte_sain_replie_les_blancs():
    assert _node('C.texteSain("  a\\n  b\\t c ")') == "a b c"


def test_langue_courante_ne_connait_que_fr_et_en():
    assert _node('[C.langCourante("en"), C.langCourante("fr"), C.langCourante(null), C.langCourante("de")]') == ["en", "fr", "fr", "fr"]


def test_la_requete_porte_le_jeton_et_un_corps_json():
    r = _node('C.requeteSource("textes:nav_exp", "en", "  Path \\n ", "J1")')
    assert r["url"] == "/__cockpit/source" and r["init"]["method"] == "POST"
    assert r["init"]["headers"] == {"Content-Type": "application/json", "X-Atelier-Token": "J1"}
    assert json.loads(r["init"]["body"]) == {"source": "textes:nav_exp", "lang": "en", "valeur": "Path"}


def test_les_messages_d_erreur_sont_lisibles():
    assert _node('C.messageErreur(400, JSON.stringify({erreur: "texte vide"}))') == "Refusé (400) : texte vide"
    assert _node('C.messageErreur(422, JSON.stringify({rapport: {errors: ["a", "b"]}}))') == "Refusé (422) : a ; b"
    assert _node('C.messageErreur(500, "pas du json")') == "Refusé (500) : pas du json"


def test_les_etapes_en_echec_de_la_sauvegarde_sont_signalees():
    corps = json.dumps({"ok": True, "rapport": {"ok": True, "stages": {
        "prefab": {"ok": False, "error": "SystemExit: gate"}, "career_ops": {"ok": True}}}})
    assert _node(f"C.alertesEtapes({json.dumps(corps)})") == ["prefab : SystemExit: gate"]
    assert _node('C.alertesEtapes(JSON.stringify({ok: true}))') == []
    assert _node('C.alertesEtapes("pas du json")') == []


def test_le_calque_n_injecte_jamais_de_html():
    source = CALQUE.read_text(encoding="utf-8")
    assert "innerHTML" not in source and "eval(" not in source and "insertAdjacentHTML" not in source


def test_resume_et_droit_de_publier():
    rep = ('{etat: {fichiers: [{chemin: "profile.json", statut: "M"}], hors_perimetre: []}, '
           'refus: [], diffs: {}, message: "m"}')
    assert _node(f"C.resumeEtat({rep}).fichiers") == ["M profile.json"]
    assert _node(f"C.peutPublier({rep}, {{ok: true}})") is True
    assert _node(f"C.peutPublier({rep}, {{ok: false}})") is False
    assert _node(f"C.peutPublier({rep}, null)") is False
    refuse = '{etat: {fichiers: [], hors_perimetre: []}, refus: ["rien à publier"], diffs: {}, message: ""}'
    assert _node(f"C.peutPublier({refuse}, {{ok: true}})") is False


def test_le_resume_porte_les_commits_locaux():
    rep = '{etat: {fichiers: [], hors_perimetre: [], commits_locaux: ["abc1234 un commit"]}, refus: [], diffs: {}}'
    assert _node(f"C.resumeEtat({rep}).commits") == ["abc1234 un commit"]
    assert _node("C.resumeEtat({etat: {fichiers: []}}).commits") == []
