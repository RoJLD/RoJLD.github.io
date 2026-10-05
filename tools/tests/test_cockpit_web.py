"""Interface web de career-ops : jamais lancée sans garde d'origine, jamais hors loopback,
jamais confondue avec un autre service sur le port 3000. Lancée par web-local.mjs, le
lanceur loopback de career-ops (jamais un `npm run dev` nu, qui écoute sur 0.0.0.0)."""
import subprocess, sys
from pathlib import Path
import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import web  # noqa: E402


def _root_pret(tmp_path):
    (tmp_path / "web" / "src" / "lib").mkdir(parents=True)
    (tmp_path / "web" / "src" / "proxy.ts").write_text("x", encoding="utf-8")
    (tmp_path / "web" / "src" / "lib" / "origin-guard.mjs").write_text("x", encoding="utf-8")
    (tmp_path / "web" / "node_modules").mkdir()
    (tmp_path / "web-local.mjs").write_text("// lanceur loopback\n", encoding="utf-8")
    return tmp_path


def test_sans_garde_d_origine_on_refuse_de_lancer(tmp_path, monkeypatch):
    (tmp_path / "web").mkdir()
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    e = web.etat_web(tmp_path, port_ouvert_fn=lambda p: False)
    assert e["pret"] is False and any("garde d'origine" in m for m in e["problemes"])


def test_sans_web_local_on_refuse_de_lancer(tmp_path, monkeypatch):
    root = _root_pret(tmp_path)
    (root / "web-local.mjs").unlink()
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    e = web.etat_web(root, port_ouvert_fn=lambda p: False)
    assert e["pret"] is False and any("web-local.mjs" in m for m in e["problemes"])


def test_pret_quand_garde_node_modules_lanceur_et_node_sont_la(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    e = web.etat_web(_root_pret(tmp_path), port_ouvert_fn=lambda p: False)
    assert e["pret"] is True and e["problemes"] == [] and e["url"] == "http://127.0.0.1:3000/"


def test_port_pris_par_autre_chose_est_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    monkeypatch.setattr(web, "est_career_ops_web", lambda opener=None: False)
    res = web.ouvrir_web(_root_pret(tmp_path), popen=lambda *a, **k: pytest.fail("ne doit pas lancer"),
                         port_ouvert_fn=lambda p: True, adresses_ecoute_fn=lambda p: {"127.0.0.1"})
    assert res["ok"] is False and any("3000" in m and "autre" in m for m in res["problemes"])


def test_deja_lancee_on_ouvre_sans_relancer(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    monkeypatch.setattr(web, "est_career_ops_web", lambda opener=None: True)
    res = web.ouvrir_web(_root_pret(tmp_path), popen=lambda *a, **k: pytest.fail("ne doit pas lancer"),
                         port_ouvert_fn=lambda p: True, adresses_ecoute_fn=lambda p: {"127.0.0.1"})
    assert res == {"ok": True, "deja": True, "url": "http://127.0.0.1:3000/", "problemes": []}


def test_instance_hors_loopback_n_est_pas_reutilisee(tmp_path, monkeypatch):
    """`npm run dev` nu écoute en 0.0.0.0 : /api/run (claude -p) joignable du LAN, le garde d'origine
    de la 0.10 ne couvre pas un en-tête Host forgé. Le cockpit ne réutilise pas cette instance et
    nomme la cause. Adresse inconnue = refus."""
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    monkeypatch.setattr(web, "est_career_ops_web", lambda opener=None: True)
    root = _root_pret(tmp_path)
    for adresses in ({"0.0.0.0"}, {"127.0.0.1", "0.0.0.0"}, set()):
        res = web.ouvrir_web(root, popen=lambda *a, **k: pytest.fail("ne doit pas lancer"),
                             port_ouvert_fn=lambda p: True, adresses_ecoute_fn=lambda p, a=adresses: a)
        assert res["ok"] is False and res["deja"] is False and any("loopback" in m for m in res["problemes"]), adresses
    e = web.etat_web(root, port_ouvert_fn=lambda p: True, adresses_ecoute_fn=lambda p: {"0.0.0.0"})
    assert e["hors_loopback"] is True


def test_instance_en_loopback_ipv4_ou_ipv6_est_reutilisee(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    monkeypatch.setattr(web, "est_career_ops_web", lambda opener=None: True)
    root = _root_pret(tmp_path)
    for adresses in ({"127.0.0.1"}, {"::1"}, {"127.0.0.1", "::1"}):
        e = web.etat_web(root, port_ouvert_fn=lambda p: True, adresses_ecoute_fn=lambda p, a=adresses: a)
        assert e["hors_loopback"] is False, adresses


def test_port_ferme_n_est_pas_hors_loopback_et_ne_sonde_pas_les_adresses(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    e = web.etat_web(_root_pret(tmp_path), port_ouvert_fn=lambda p: False,
                     adresses_ecoute_fn=lambda p: pytest.fail("port fermé : rien à lire"))
    assert e["hors_loopback"] is False


def test_adresses_ecoute_lit_get_nettcpconnection(monkeypatch):
    monkeypatch.setattr(web.sys, "platform", "win32")
    vus = []
    def run(argv, **kw):
        vus.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="127.0.0.1\r\n::1\r\n\r\n", stderr="")
    assert web.adresses_ecoute(3000, run=run) == {"127.0.0.1", "::1"}
    assert "Get-NetTCPConnection -LocalPort 3000 -State Listen" in vus[0][-1]
    def casse(argv, **kw):
        raise OSError("powershell absent")
    assert web.adresses_ecoute(3000, run=casse) == set()          # mesure impossible = inconnu, pas loopback
    monkeypatch.setattr(web.sys, "platform", "linux")
    assert web.adresses_ecoute(3000, run=run) == set()


def test_lancement_par_web_local_en_loopback_avec_career_ops_root(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    root = _root_pret(tmp_path)
    appels, etats = [], iter([False, False, True])
    popen = lambda argv, **kw: appels.append((argv, kw))
    res = web.ouvrir_web(root, popen=popen, port_ouvert_fn=lambda p: next(etats), attente_s=5, sleep=lambda s: None)
    argv, kw = appels[0]
    assert argv == ["node", "web-local.mjs", "--host", "127.0.0.1", "--port", "3000"]
    assert "npm" not in " ".join(argv)
    assert kw["cwd"] == str(root) and kw["env"]["CAREER_OPS_ROOT"] == str(root)
    assert res["ok"] is True and res["deja"] is False


def test_si_le_port_ne_s_ouvre_pas_on_le_dit(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "node_exe", lambda: "node")
    res = web.ouvrir_web(_root_pret(tmp_path), popen=lambda *a, **k: None, port_ouvert_fn=lambda p: False, attente_s=1, sleep=lambda s: None)
    assert res["ok"] is False and any("après 1 s" in m for m in res["problemes"])
