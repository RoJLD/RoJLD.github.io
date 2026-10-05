"""Adaptateur career-ops : liste blanche fermée, verrou, délai, sens des codes, lectures.

Le cockpit lance les outils de career-ops, il ne parse pas ses fichiers et n'en écrit
aucun (spec § 5). Mesuré le 2026-09-29 : `tracker.mjs --json` n'existe pas (c'est
`query --json`) ; `verify-pipeline` sort en 1 quand il TROUVE quelque chose.
Mesuré le 2026-10-03 : `watch.mjs` sans `--dry-run` alimente le registre de vivacité
dont send-queue et kpi tirent le taux de disparition ; send-queue ordonne la file."""
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))

from cockpit_fixtures import KPI, RELANCES, SEND_QUEUE, TRACKER, WATCH, FauxProc, faux_popen  # noqa: E402
from tools.cockpit import career_ops as co  # noqa: E402


@pytest.fixture
def root(tmp_path):
    (tmp_path / "tracker.mjs").write_text("// faux\n", encoding="utf-8")
    return tmp_path


def test_le_module_n_ecrit_jamais_sous_career_ops():
    src = inspect.getsource(co)
    for interdit in ("write_text(", "write_bytes(", ".unlink(", ".rename(", "shutil.move", "shutil.copy"):
        assert interdit not in src, f"career_ops.py contient {interdit!r} : seul career-ops écrit ses fichiers"
    # `open(` seul, pas `popen(` : le module lance des sous-processus, il n'ouvre aucun fichier.
    assert not re.search(r"(?<![\w.])open\(", src), "career_ops.py appelle open() : seul career-ops écrit ses fichiers"


def test_la_liste_blanche_est_fermee_et_sans_saisie_libre():
    assert set(co.COMMANDES) == {"kpi", "watch", "scan", "sante", "pistes"}
    for c in co.COMMANDES.values():
        assert all(isinstance(a, str) for a in c.args) and c.args[0].endswith(".mjs")
    assert co.COMMANDES["scan"].confirmation is True
    assert co.COMMANDES["pistes"].args == ("track-core.mjs", "--check")
    with pytest.raises(ValueError):
        co.executer("rm -rf", root=Path("."), popen=faux_popen({}))


def test_watch_tourne_sans_dry_run_pour_que_le_registre_garde_ses_verdicts():
    """--dry-run sonde toutes les annonces puis jette les verdicts : le taux de disparition
    de send-queue et de kpi ne se nourrit que de data/liveness-log.tsv."""
    w = co.COMMANDES["watch"]
    assert w.args == ("watch.mjs",) and "--dry-run" not in w.args
    assert "liveness-log.tsv" in w.ecrit and "agent-inbox.md" in w.ecrit and w.sortie == "json"


def test_executer_lance_node_dans_root_et_parse_le_json(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    popen = faux_popen({"kpi.mjs": FauxProc(out=json.dumps(KPI))})
    res = co.executer("kpi", root=root, popen=popen)
    assert popen.appels[0]["argv"] == ["node", "kpi.mjs", "--json"] and popen.appels[0]["cwd"] == str(root)
    assert res["code"] == 0 and res["sens"] == "fait" and res["json"]["stage"] == "entry"


def test_scan_exige_une_confirmation(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    with pytest.raises(ValueError, match="confirmation"):
        co.executer("scan", root=root, popen=faux_popen({}))


def test_un_delai_depasse_tue_l_arbre_et_le_dit(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    tues = []
    popen = faux_popen({"verify-pipeline.mjs": FauxProc(out="", lent=True)})
    res = co.executer("sante", root=root, popen=popen, tuer=lambda p: tues.append(p.pid))
    assert res["interrompu"] is True and res["code"] is None and tues == [4242]
    assert res["sens"] == "interrompu après 60 s"


def test_le_code_1_de_sante_est_un_resultat_pas_une_panne(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    res = co.executer("sante", root=root, popen=faux_popen({"verify-pipeline.mjs": FauxProc(out="❌ x", code=1)}))
    assert res["code"] == 1 and "incohérences" in res["sens"]


def test_une_seule_action_a_la_fois(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    with co.verrou_action("kpi"):
        with pytest.raises(co.ActionEnCours, match="kpi"):
            co.executer("sante", root=root, popen=faux_popen({"verify-pipeline.mjs": FauxProc()}))
    co.executer("sante", root=root, popen=faux_popen({"verify-pipeline.mjs": FauxProc()}))  # verrou rendu


def test_les_lectures_ont_les_bons_argv_et_une_heure_de_lecture(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    popen = faux_popen({"tracker.mjs": FauxProc(out=json.dumps(TRACKER)), "kpi.mjs": FauxProc(out=json.dumps(KPI)),
                        "followup-cadence.mjs": FauxProc(out=json.dumps(RELANCES)),
                        "send-queue.mjs": FauxProc(out=json.dumps(SEND_QUEUE))})
    t = co.lire_tracker(root, popen=popen); k = co.lire_kpi(root, popen=popen); r = co.lire_relances(root, popen=popen)
    f = co.lire_file(root, popen=popen)
    assert [a["argv"] for a in popen.appels] == [["node", "tracker.mjs", "query", "--json"], ["node", "kpi.mjs", "--json"],
                                                 ["node", "followup-cadence.mjs", "--json", "--overdue-only"],
                                                 ["node", "send-queue.mjs", "--json"]]
    assert t["ok"] and len(t["donnees"]) == 4 and re.match(r"^\d\d:\d\d$", t["lu_a"])
    assert k["donnees"]["stage"] == "entry" and r["donnees"]["metadata"]["overdue"] == 0
    assert f["ok"] and f["donnees"]["stats"]["ready"] == 2


def test_une_lecture_en_echec_nomme_la_cause(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    res = co.lire_tracker(root, popen=faux_popen({"tracker.mjs": FauxProc(err="Error: node:sqlite is not available", code=1)}))
    assert res["ok"] is False and "node:sqlite" in res["erreur"] and res["donnees"] is None


def test_numero_de_rapport_et_score():
    assert [co.numero_rapport(l) for l in TRACKER] == [23, 24, 5, 1]
    assert co.score(TRACKER[0]) == 4.5 and co.score({"score": "N/A"}) is None


def test_a_faire_ne_garde_que_les_evaluees_au_dessus_du_seuil_meilleure_d_abord():
    assert [l["id"] for l in co.a_faire(TRACKER)] == [23, 24]      # Globex est Discarded, Initech sous le seuil
    assert [l["id"] for l in co.a_faire(TRACKER, seuil=3.0)] == [23, 24, 1]


def test_la_file_garde_l_ordre_de_send_queue_pas_la_note():
    items = co.file_a_envoyer(SEND_QUEUE)
    assert [i["num"] for i in items] == ["024", "023"]      # 4.1 avant 4.5 : la priorité de la file, pas la note
    assert items[0]["piste"] == "Poste principal" and co.numero_item(items[0]) == 24
    assert co.numero_item({"num": "abc"}) is None and co.numero_item({}) is None and co.file_a_envoyer({}) == []


def test_prerequis_nomme_chaque_manque(tmp_path):
    p = co.prerequis(env={}, runner=lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="v20.1.0\n", stderr=""))
    assert p["ok"] is False and any("CAREER_OPS_ROOT" in m for m in p["problemes"])
    if p["node"]:
        assert any("< 22.5" in m for m in p["problemes"])


def test_lire_texte_et_dossiers(root):
    assert co.lire_texte(root, "ENVOI.md")["ok"] is False and "FileNotFoundError" in co.lire_texte(root, "ENVOI.md")["erreur"]
    (root / "ENVOI.md").write_text("# Liste\n", encoding="utf-8")
    t = co.lire_texte(root, "ENVOI.md")
    assert t["ok"] and t["texte"].startswith("# Liste") and t["age_h"] is not None
    v = root / "output" / "acme" / "023-quantitative-developer" / "v002"
    v.mkdir(parents=True); (v / "cv.pdf").write_bytes(b"%PDF"); (root / "output" / "acme" / "023-quantitative-developer" / "v001").mkdir()
    d = co.lire_dossiers(root)
    assert d == [{"entreprise": "acme", "dossier": "023-quantitative-developer", "version": "v002", "fichiers": ["cv.pdf"], "chemin": str(v)}]


def test_argv_postule_valide_le_numero_et_la_note():
    assert co.argv_postule(23, "", TRACKER) == ["set-status.mjs", "--report", "23", "Applied", "--json"]
    assert co.argv_postule(24, " envoyé par email ", TRACKER)[-2:] == ["--note", "envoyé par email"]
    for mauvais in (99, 0, -1, True, "23", 23.0):
        with pytest.raises(ValueError):
            co.argv_postule(mauvais, "", TRACKER)
    with pytest.raises(ValueError):
        co.argv_postule(True, "", [{"report": "[1](x)"}])      # True == 1 : jamais une conversion implicite
    with pytest.raises(ValueError, match="200"):
        co.argv_postule(23, "x" * 201, TRACKER)
    with pytest.raises(ValueError):
        co.argv_postule(23, "ligne 1\nligne 2", TRACKER)


def test_postule_relit_le_tracker_puis_lance_set_status_sous_verrou(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    succes = json.dumps({"changed": True, "num": 23, "company": "Acme", "role": "QD", "oldStatus": "Evaluated",
                         "newStatus": "Applied", "statusLogged": True, "tracker": "x"}, indent=2)   # multi-ligne, comme set-status
    popen = faux_popen({"tracker.mjs": FauxProc(out=json.dumps(TRACKER)), "set-status.mjs": FauxProc(out=succes)})
    res = co.postule(23, "via le cockpit", root=root, popen=popen)
    assert popen.appels[1]["argv"] == ["node", "set-status.mjs", "--report", "23", "Applied", "--json", "--note", "via le cockpit"]
    assert res["code"] == 0 and res["sens"] == "enregistré" and res["json"]["newStatus"] == "Applied"
    assert "follow-ups.md" in res["ecrit"]


def test_une_erreur_compacte_de_set_status_est_parsee(root, monkeypatch):
    monkeypatch.setattr(co, "node_exe", lambda: "node")
    popen = faux_popen({"tracker.mjs": FauxProc(out=json.dumps(TRACKER)),
                        "set-status.mjs": FauxProc(out='{"error":"report-number-mismatch","code":"report-number-mismatch"}\n', code=3)})
    res = co.postule(23, "", root=root, popen=popen)
    assert res["code"] == 3 and "ambigu" in res["sens"] and res["json"]["code"] == "report-number-mismatch"


def test_les_fixtures_sont_fictives():
    """Dépôt public (spec § 5, règle 3) : aucune entreprise réellement visée dans les fixtures."""
    fictives = {"Acme", "Globex", "Initech", "?"}
    vues = {l["company"] for l in TRACKER} | {i["company"] for p in SEND_QUEUE["perTrack"] for i in p["items"]}
    vues |= {d["company"] for d in SEND_QUEUE["dead"]} | {f["company"] for f in WATCH["findings"]}
    assert vues <= fictives, vues - fictives
    assert all(re.fullmatch(r"\[\d+\]\(\.\./reports/\d+-[a-z]+\.md\)", l["report"]) for l in TRACKER)


def test_kpi_declare_son_code_de_sortie_3_donnees_illisibles():
    """kpi.mjs --json sort en 3 quand racine ou tracker sont illisibles (career-ops 9eee33e2) :
    le sens du code est affiché, jamais un « code inconnu » ni un entonnoir vide."""
    assert co.COMMANDES["kpi"].codes == {0: "fait", 2: "argument invalide", 3: "données illisibles (racine ou tracker)"}
