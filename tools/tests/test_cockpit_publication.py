"""Publier : état, refus nommés, commit des seuls fichiers du site, push, réessai après échec.
Exercé contre de VRAIS dépôts git temporaires (un origin nu + un clone) — spec § 5.

Une écriture du cockpit passe par `journal.ecriture` (spec § 5.4) : les tests qui simulent une
édition faite depuis le cockpit l'écrivent dans ce bloc ; un fichier écrit hors du bloc est une
modification étrangère, refusée."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from tools.cockpit import journal  # noqa: E402
from tools.cockpit import publication as pub  # noqa: E402


def _g(racine, *args):
    return subprocess.run(["git", "-C", str(racine), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def depot(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    site = tmp_path / "site"
    subprocess.run(["git", "clone", "-q", str(origin), str(site)], check=True, capture_output=True)
    _g(site, "config", "user.email", "test@example.org")
    _g(site, "config", "user.name", "Test")
    _g(site, "symbolic-ref", "HEAD", "refs/heads/main")   # clone d'un dépôt vide : branche à naître
    (site / "profile.json").write_text("{}\n", encoding="utf-8")
    (site / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (site / "tools").mkdir()
    (site / "tools" / "outil.py").write_text("x = 1\n", encoding="utf-8")
    _g(site, "add", "-A")
    _g(site, "commit", "-q", "-m", "init")
    _g(site, "push", "-q", "-u", "origin", "main")
    return site, origin


def test_rien_a_publier(depot):
    site, _ = depot
    e = pub.etat(site)
    assert e["branche"] == "main" and e["fetch_ok"] and (e["en_avance"], e["en_retard"]) == (0, 0)
    assert pub.refus(e) == ["rien à publier"]


def test_publier_committe_le_seul_perimetre_et_pousse(depot):
    site, origin = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
        (site / "index.html").write_text("<html>neuf</html>\n", encoding="utf-8")
    res = pub.publier(site, "")
    assert res["ok"] is True
    fichiers = _g(origin, "show", "--name-only", "--format=", "main").split()
    assert sorted(fichiers) == ["index.html", "profile.json"]
    assert _g(origin, "log", "-1", "--format=%s", "main").startswith("content(site): profil")


def test_hors_perimetre_est_refuse(depot):
    site, _ = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    (site / "tools" / "outil.py").write_text("x = 2\n", encoding="utf-8")
    res = pub.publier(site, "msg")
    assert res["ok"] is False and any("hors du périmètre" in m and "tools/outil.py" in m for m in res["refus"])


def test_une_modification_hors_cockpit_est_refusee(depot):
    """Spec § 5.4 : l'arbre contient des modifications que le cockpit n'a pas faites → refus
    nommé, rien n'est committé — même DANS le périmètre (index.html)."""
    site, origin = depot
    tete = _g(site, "rev-parse", "HEAD")
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    (site / "index.html").write_text("<html>à la main</html>\n", encoding="utf-8")
    res = pub.publier(site, "msg")
    assert res["ok"] is False
    assert [m for m in res["refus"] if "modifications que le cockpit n'a pas faites" in m] == [
        "modifications que le cockpit n'a pas faites (journal de ses écritures), "
        "à committer ou annuler à la main : index.html"]
    assert _g(site, "rev-parse", "HEAD") == tete and _g(origin, "rev-parse", "main") == tete


def test_hors_de_main_est_refuse(depot):
    site, _ = depot
    _g(site, "checkout", "-q", "-b", "autre")
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 1}\n', encoding="utf-8")
    assert any("pas sur main" in m for m in pub.publier(site, "msg")["refus"])


def test_une_divergence_est_refusee(depot, tmp_path):
    site, origin = depot
    autre = tmp_path / "autre"
    subprocess.run(["git", "clone", "-q", str(origin), str(autre)], check=True, capture_output=True)
    _g(autre, "config", "user.email", "t@e.org")
    _g(autre, "config", "user.name", "T")
    (autre / "index.html").write_text("<html>distant</html>\n", encoding="utf-8")
    _g(autre, "commit", "-q", "-am", "distant")
    _g(autre, "push", "-q", "origin", "main")
    (site / "profile.json").write_text('{"local": 1}\n', encoding="utf-8")
    _g(site, "commit", "-q", "-am", "local")
    assert any("divergé" in m for m in pub.publier(site, "msg")["refus"])


def test_un_retard_se_rattrape_par_avance_rapide(depot, tmp_path):
    site, origin = depot
    autre = tmp_path / "autre"
    subprocess.run(["git", "clone", "-q", str(origin), str(autre)], check=True, capture_output=True)
    _g(autre, "config", "user.email", "t@e.org")
    _g(autre, "config", "user.name", "T")
    (autre / "index.html").write_text("<html>distant</html>\n", encoding="utf-8")
    _g(autre, "commit", "-q", "-am", "distant")
    _g(autre, "push", "-q", "origin", "main")
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"local": 1}\n', encoding="utf-8")
    assert pub.publier(site, "msg")["ok"] is True
    assert _g(origin, "log", "--format=%s", "main").split("\n")[:2] == ["msg", "distant"]


def test_un_push_refuse_garde_le_commit_et_le_reessai_le_pousse(depot):
    site, origin = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 2}\n', encoding="utf-8")
    _g(site, "remote", "set-url", "--push", "origin", str(site.parent / "absent.git"))
    res = pub.publier(site, "msg")
    assert res["ok"] is False and res["etape"] == "push" and res["commit_local"] is True
    assert _g(site, "log", "-1", "--format=%s") == "msg\n"
    _g(site, "remote", "set-url", "--push", "origin", str(origin))
    res2 = pub.publier(site, "")
    assert res2["ok"] is True and res2["commit"] == res["commit"]
    assert _g(origin, "log", "-1", "--format=%s", "main") == "msg\n"


def test_les_diffs_ne_montrent_que_les_sources(depot):
    site, _ = depot
    (site / "profile.json").write_text('{"a": 3}\n', encoding="utf-8")
    (site / "index.html").write_text("<html>x</html>\n", encoding="utf-8")
    (site / "site_texts.json").write_text("{}\n", encoding="utf-8")
    d = pub.diffs_sources(site, pub.etat(site))
    assert set(d) == {"profile.json", "site_texts.json"}
    assert '+{"a": 3}' in d["profile.json"] and d["site_texts.json"] == "(nouveau fichier)"


def test_le_diff_d_une_source_indexee_est_montre(depot):
    """`git diff` compare l'arbre à l'index : une source déjà indexée montrait un diff vide."""
    site, _ = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"a": 4}\n', encoding="utf-8")
    _g(site, "add", "profile.json")
    assert '+{"a": 4}' in pub.diffs_sources(site, pub.etat(site))["profile.json"]


class _Espion:
    def __init__(self, stdout=""):
        self.appels, self.stdout = [], stdout

    def __call__(self, argv, **kw):
        self.appels.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, stdout=self.stdout, stderr="")


def test_chaque_lancement_ferme_stdin(tmp_path):
    """Lancé par pythonw depuis Git Bash, un enfant qui hérite d'un stdin invalide échoue
    (WinError 6 mesuré : pytest des vérifications en échec, publication refusée)."""
    e = _Espion(json.dumps({"status": "built", "commit": "abc1234"}))
    pub._git(tmp_path, "status", run=e)
    pub.verifier(tmp_path, run=e)
    pub.suivi_pages("abc1234", run=e)
    assert len(e.appels) == 6 and all(kw.get("stdin") is subprocess.DEVNULL for _, kw in e.appels)


def test_aucun_lancement_de_publication_ni_du_journal_n_oublie_stdin():
    import ast
    oublis = []
    for nom in ("publication.py", "journal.py"):
        arbre = ast.parse((SITE / "tools" / "cockpit" / nom).read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "run" \
                    and not any(k.arg == "stdin" for k in n.keywords):
                oublis.append(f"{nom}:{n.lineno}")
    assert oublis == []


def test_verifier_nomme_chaque_controle_et_detecte_un_calque_publie(tmp_path):
    (tmp_path / "index.html").write_text('<p data-src="textes:x">a</p>', encoding="utf-8")
    appels = []

    def run(argv, **k):
        appels.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
    res = pub.verifier(tmp_path, run=run)
    noms = [r["nom"] for r in res]
    assert noms == ["profil valide (validate_profile)", "construction complète du site", "liens internes",
                    "gardes de confidentialité", "pages publiées sans calque"]
    assert res[-1] == {"nom": "pages publiées sans calque", "ok": False, "detail": "index.html"}
    assert all(r["ok"] for r in res[:-1]) and len(appels) == 4


def test_suivi_pages(monkeypatch):
    def run(argv, **k):
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"status": "built", "commit": "abc1234"}), stderr="")
    assert pub.suivi_pages("abc1234", run=run)["statut"] == "built"
    assert pub.suivi_pages("fff0000", run=run)["statut"] == "en attente"

    def absent(argv, **k):
        raise FileNotFoundError("gh")
    assert pub.suivi_pages("abc1234", run=absent)["statut"] == "inconnu"


def test_un_commit_local_hors_perimetre_est_refuse(depot):
    site, _ = depot
    (site / "tools" / "outil.py").write_text("x = 3\n", encoding="utf-8")
    _g(site, "commit", "-q", "-am", "outil local")
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"b": 1}\n', encoding="utf-8")
    e = pub.etat(site)
    assert len(e["commits_locaux"]) == 1 and e["commits_locaux"][0].endswith("outil local")
    assert e["fichiers_commits"] == ["tools/outil.py"]
    res = pub.publier(site, "msg")
    assert res["ok"] is False and any("tools/outil.py" in m for m in res["refus"])


def test_un_renommage_depuis_hors_perimetre_est_refuse(depot):
    site, _ = depot
    (site / "articles").mkdir()
    _g(site, "mv", "tools/outil.py", "articles/outil.html")
    res = pub.publier(site, "msg")
    assert res["ok"] is False and any("tools/outil.py" in m for m in res["refus"])


def test_le_commit_ne_prend_que_les_fichiers_verifies(depot):
    site, origin = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"c": 1}\n', encoding="utf-8")

    def run(argv, **k):
        if "commit" in argv:      # un autre processus indexe un fichier entre l'état et le commit
            (site / "tools" / "outil.py").write_text("x = 9\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(site), "add", "tools/outil.py"], check=True)
        return subprocess.run(argv, **k)
    assert pub.publier(site, "msg", run=run)["ok"] is True
    assert _g(origin, "show", "--name-only", "--format=", "main").split() == ["profile.json"]


def test_un_nouveau_fichier_du_perimetre_est_publie(depot):
    site, origin = depot
    with journal.ecriture(site):
        (site / "articles").mkdir()
        (site / "articles" / "neuf.html").write_text("<p>neuf</p>\n", encoding="utf-8")
    assert pub.publier(site, "msg")["ok"] is True
    assert "articles/neuf.html" in _g(origin, "show", "--name-only", "--format=", "main").split()


def test_un_delai_depasse_au_push_est_rapporte(depot):
    site, _ = depot
    with journal.ecriture(site):
        (site / "profile.json").write_text('{"d": 1}\n', encoding="utf-8")

    def run(argv, **k):
        if "push" in argv:
            raise subprocess.TimeoutExpired(argv, 180)
        return subprocess.run(argv, **k)
    res = pub.publier(site, "msg", run=run)
    assert res["ok"] is False and res["etape"] == "push" and res["commit_local"] is True
    assert "délai dépassé" in res["erreur"] and "état du push inconnu" in res["erreur"]


def test_un_delai_depasse_dans_une_verification_est_un_echec_nomme(tmp_path):
    def run(argv, **k):
        raise subprocess.TimeoutExpired(argv, 600)
    res = pub.verifier(tmp_path, run=run)
    assert [r["ok"] for r in res[:4]] == [False] * 4
    assert all("délai dépassé" in r["detail"] for r in res[:4])


def test_un_git_status_en_echec_n_est_pas_un_arbre_propre(tmp_path):
    def run(argv, **k):
        return subprocess.CompletedProcess(argv, 128, stdout="", stderr="fatal: not a git repository")
    e = pub.etat(tmp_path, run=run)
    assert any("git status a échoué" in m and "not a git repository" in m for m in pub.refus(e))
