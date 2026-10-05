"""Backend Anthropos : liste lue sur le hub (unique source), état RÉEL sondé (le hub
affiche « deployed » pour Ergon qui répond 503, mesuré), trois sondes du site public
indépendantes, chacune avec son échec."""
import io, json, subprocess, sys, urllib.error
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import anthropos as an  # noqa: E402

APPS = {"satellite_version": "0.5.1", "apps": [
    {"name": "career", "version": "7.0.0", "port": 8000, "ingress_host": "ergon.elysium.local", "deployment_status": "deployed"},
    {"name": "kleos", "version": "0.1.0", "port": 8010, "ingress_host": "kleos.elysium.local", "deployment_status": "deployed"}]}


class _Rep:
    def __init__(self, corps=b"", status=200):
        self.status, self._c = status, corps
    def read(self, n=-1): return self._c
    def __enter__(self): return self
    def __exit__(self, *a): pass


def _opener(table):
    """table : url → _Rep | exception."""
    def _o(url, timeout=None):
        r = table[url]
        if isinstance(r, BaseException):
            raise r
        return r
    return _o


def test_lire_apps_et_mode_repli():
    o = _opener({"http://hub/api/apps": _Rep(json.dumps(APPS).encode())})
    a = an.lire_apps("http://hub", opener=o)
    assert a["ok"] and [x["name"] for x in a["apps"]] == ["career", "kleos"] and a["repli"] is False
    o2 = _opener({"http://hub/api/apps": _Rep(json.dumps({"satellite_version": "?", "apps": []}).encode())})
    assert an.lire_apps("http://hub", opener=o2)["repli"] is True
    o3 = _opener({"http://hub/api/apps": urllib.error.URLError("timed out")})
    a3 = an.lire_apps("http://hub", opener=o3)
    assert a3["ok"] is False and "injoignable" in a3["erreur"] and a3["apps"] == []


def test_sonder_distingue_repond_erreur_injoignable():
    err503 = urllib.error.HTTPError("http://ergon/", 503, "Service Unavailable", {}, io.BytesIO(b"no available server"))
    o = _opener({"http://ok/": _Rep(b"<html>"), "http://ergon/": err503, "http://mort/": urllib.error.URLError("refused")})
    assert an.sonder("http://ok/", opener=o)["etat"] == "repond"
    e = an.sonder("http://ergon/", opener=o)
    assert e["etat"] == "erreur" and e["code"] == 503 and e["detail"] == "no available server"
    assert an.sonder("http://mort/", opener=o)["etat"] == "injoignable"


def test_sonder_apps_ajoute_le_hub_et_garde_le_statut_declare():
    o = _opener({"http://hub/elysium/health": _Rep(b'{"status":"healthy"}'), "http://ergon.elysium.local/": urllib.error.URLError("x"),
                 "http://kleos.elysium.local/": _Rep(b"", 401)})
    rows = an.sonder_apps(APPS["apps"], "http://hub", opener=o)
    assert rows[0]["name"] == "hub" and rows[0]["probe"]["etat"] == "repond"
    assert rows[1]["declared_status"] == "deployed" and rows[1]["probe"]["etat"] == "injoignable"


def test_site_public_trois_sondes_independantes(tmp_path):
    def runner(argv, **k):
        if argv[:2] == ["git", "-C"] and "rev-parse" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="abc1234567\n", stderr="")
        if "ls-remote" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="abc1234567\trefs/heads/main\n", stderr="")
        if argv[0] == "gh":
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="gh: not logged in")
        raise AssertionError(argv)
    o = _opener({"https://robin-denis.com/": _Rep(b"<html>")})
    e = an.etat_site_public(opener=o, runner=runner, site_root=tmp_path)
    assert e["https"]["etat"] == "repond"
    assert e["git"] == {"ok": True, "head_local": "abc123456", "main_distant": "abc123456", "a_jour": True}
    assert e["pages"]["ok"] is False and "not logged in" in e["pages"]["erreur"]
