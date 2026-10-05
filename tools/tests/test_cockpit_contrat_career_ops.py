"""Contrat réel : les formes que le cockpit lit existent bien dans le career-ops du poste.
Ignoré, en le disant, quand career-ops manque (CI sans poste) ; l'absence de l'interpréteur passe
par la porte du dépôt (oracle_node.porte, ELYSIUM_REQUIRE_NODE compris). Lecture seule :
le seul appel qui écrirait (set-status) passe en --dry-run, et le tracker est comparé octet à octet."""
import sys
from pathlib import Path
import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
import oracle_node  # noqa: E402
from tools.cockpit import career_ops as co  # noqa: E402


@pytest.fixture
def root():
    oracle_node.porte()   # le seul chemin vers l'interpréteur passe par la porte
    r = co.config.career_ops_root()
    if r is None:
        pytest.skip("career-ops absent du poste (CAREER_OPS_ROOT ou tools/cockpit/local.json) : contrat réel non exécutable")
    return r


def test_kpi_tracker_relances_ont_les_cles_attendues(root):
    k, t, r = co.lire_kpi(root), co.lire_tracker(root), co.lire_relances(root)
    assert k["ok"] and {"stage", "threshold", "kpis"} <= set(k["donnees"]) and {x["key"] for x in k["donnees"]["kpis"]} >= {"scan_yield", "application_rate"}
    assert t["ok"] and isinstance(t["donnees"], list) and {"id", "company", "role", "score", "status", "report"} <= set(t["donnees"][0])
    assert r["ok"] and {"metadata", "entries"} <= set(r["donnees"]) and "overdue" in r["donnees"]["metadata"]


def test_les_ajouts_du_2026_10_02_ont_les_cles_que_la_page_lit(root):
    """kpi : pulse et channels ; send-queue : perTrack (track, items, wip, hours), stats, dead."""
    k, f = co.lire_kpi(root), co.lire_file(root)
    assert k["ok"] and {"pulse", "channels"} <= set(k["donnees"])
    assert {"conversations28", "sends7", "sends28", "inbound28", "followups"} <= set(k["donnees"]["pulse"])
    assert all({"channel", "label", "evaluated", "aboveThreshold", "applied"} <= set(c) for c in k["donnees"]["channels"])
    assert f["ok"], f["erreur"]
    fj = f["donnees"]
    assert {"perTrack", "stats", "dead"} <= set(fj)
    assert {"ready", "hours", "oldest", "oldestDays", "expectedLostPerWeek"} <= set(fj["stats"])
    for p in fj["perTrack"]:
        assert {"track", "items", "wip", "hours"} <= set(p) and {"id", "label"} <= set(p["track"])
        assert {"count", "limit", "exceeded"} <= set(p["wip"])
    for item in co.file_a_envoyer(fj):
        assert co.numero_item(item) is not None and {"company", "role", "score", "waitingDays"} <= set(item)


def test_pistes_sort_avec_un_code_declare(root):
    res = co.lancer(list(co.COMMANDES["pistes"].args), root, 30)
    assert res["code"] in co.COMMANDES["pistes"].codes, (res["code"], res["stderr"])


def test_set_status_accepte_report_n_en_dry_run_sans_rien_ecrire(root):
    """--dry-run ne prend pas le verrou et n'écrit pas (mesuré set-status.mjs) : contrat réel sans effet."""
    lignes = co.lire_tracker(root)["donnees"]
    n = next(co.numero_rapport(l) for l in lignes if co.numero_rapport(l))
    avant = (root / "data" / "applications.md").read_bytes()
    argv = co.argv_postule(n, "", lignes) + ["--dry-run"]
    res = co.lancer(argv, root, 30)
    assert res["code"] == 0, res["stderr"]
    j = co._json_sortie(res["stdout"])
    assert j and j.get("dryRun") is True and j.get("newStatus") == "Applied"
    assert (root / "data" / "applications.md").read_bytes() == avant
