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
from tools import servi_ailleurs  # noqa: E402
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


# ── Le périmètre suit le site RÉEL : retrait de l'Academy (spec Academy § 9.3, 2026-10-14).
# `/academy/` est servie par le dépôt-projet RoJLD/academy ; `academy.json` et `academy/` sont
# sortis du dépôt. Aucun test ne confrontait `PERIMETRE` ni `SOURCES` au site : y laisser les
# deux entrées mortes passait vert, et le cockpit aurait publié sans un mot un `academy/`
# ressuscité — un dossier que GitHub Pages ne sert jamais.

def test_le_perimetre_ne_couvre_aucun_chemin_servi_par_un_autre_depot():
    """Un chemin servi par un autre dépôt n'est pas à publier depuis ce site : il y serait mort."""
    couverts = sorted(p for p in servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT
                      if pub.dans_perimetre(p) or pub.dans_perimetre(p + "index.html"))
    assert couverts == [], (f"le périmètre de publication couvre {couverts}, que "
                            f"{[servi_ailleurs.SERVI_PAR_UN_AUTRE_DEPOT[c] for c in couverts]} sert à sa place")


def test_chaque_entree_du_perimetre_et_des_sources_existe_dans_le_site():
    """Le périmètre décrit ce que le cockpit écrit ou régénère : chaque entrée existe dans le site.

    Une entrée orpheline n'est pas inerte — elle autorise en silence la publication de ce qui
    viendrait la remplir (c'est ce que `academy.json` et `academy/` auraient fait)."""
    absentes = [p for p in dict.fromkeys(pub.PERIMETRE + pub.SOURCES) if not (SITE / p).exists()]
    assert absentes == [], f"entrées du périmètre ou des sources absentes du site : {absentes}"


# ── Ce que la porte NOMME doit exister. Même motif que le périmètre orphelin ci-dessus, un
# cran plus haut : `verifier()` nomme des chemins d'outils et de fichiers de tests, ET deux
# node-ids `fichier::test`. Mesuré
# le 2026-10-15 : `pytest f.py::test_absent` sort en 4 (« ERROR: not found », et aucun des
# node-ids voisins ne tourne), `pytest f_mal_ecrit.py` sort en 4 aussi — donc un nom faux
# fait bien ROUGIR la porte, il ne passe pas en silence. Ce test-ci sert à l'attraper AVANT
# que Robin clique « Publier » et reçoive un rouge qui ne parle pas de son profil.
#
# Il ne dit rien du trou inverse — une garde qui existe mais que la porte ne nomme pas. Celui-là
# ne se ferme pas par un test : il se ferme en posant la garde dans un fichier que la porte joue
# EN ENTIER (cf. l'en-tête de tools/tests/test_liens_internes.py).

def _cibles_nommees_par_verifier() -> list:
    """Les chaînes de `verifier()` qui désignent un fichier du dépôt (outil ou test)."""
    import ast
    arbre = ast.parse((SITE / "tools" / "cockpit" / "publication.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arbre)
              if isinstance(n, ast.FunctionDef) and n.name == "verifier")
    return [n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value.startswith("tools/")]


def test_la_porte_ne_nomme_que_des_fichiers_et_des_tests_qui_existent():
    import ast
    cibles = _cibles_nommees_par_verifier()
    # Contre-vacuité : si l'extraction cesse de voir les cibles, ce test ne juge plus rien.
    assert len(cibles) >= 4, f"cibles de verifier() introuvables dans le source : {cibles}"
    assert any("::" in c for c in cibles), "aucun node-id nommé : l'extraction a dérivé"

    manquants = []
    for cible in cibles:
        chemin, _, suite = cible.partition("::")
        fichier = SITE / chemin
        if not fichier.is_file():
            manquants.append(f"{cible} (fichier absent)")
            continue
        if not suite:
            continue
        noms = {n.name for n in ast.walk(ast.parse(fichier.read_text(encoding="utf-8")))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        manquants += [f"{cible} (test absent : {part})" for part in suite.split("::")
                      if part not in noms]
    assert manquants == [], (
        f"la porte de publication nomme ce qui n'existe pas : {manquants} — "
        "une porte qui nomme un test absent sort en 4 et ne vérifie plus rien")


# ── « Vérifier » lancé par le cockpit (pythonw) : mesuré le 2026-10-12, les deux gardes de
# confidentialité échouaient en WinError 6. Sous pythonw (sous-système GUI), la capture par
# descripteurs de pytest ferme le handle d'entrée standard que Windows garde en STD_INPUT_HANDLE :
# le git lancé par le test héritait d'un handle mort. Sous python.exe, tout passe.

def test_le_python_console_remplace_pythonw(tmp_path):
    (tmp_path / "pythonw.exe").write_bytes(b"")
    (tmp_path / "python.exe").write_bytes(b"")
    assert pub._python_console(tmp_path / "pythonw.exe") == str(tmp_path / "python.exe")
    assert pub._python_console(tmp_path / "python.exe") == str(tmp_path / "python.exe")


def test_sans_python_console_voisin_l_interpreteur_reste_le_meme(tmp_path):
    (tmp_path / "pythonw.exe").write_bytes(b"")
    assert pub._python_console(tmp_path / "pythonw.exe") == str(tmp_path / "pythonw.exe")


def test_verifier_lance_ses_outils_avec_le_python_console(tmp_path, monkeypatch):
    (tmp_path / "pythonw.exe").write_bytes(b"")
    (tmp_path / "python.exe").write_bytes(b"")
    monkeypatch.setattr(pub.sys, "executable", str(tmp_path / "pythonw.exe"))
    lances = []

    def run(argv, **k):
        lances.append(argv[0])
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
    pub.verifier(tmp_path, run=run)
    assert lances == [str(tmp_path / "python.exe")] * 4


@pytest.mark.skipif(sys.platform != "win32", reason="pythonw n'existe que sous Windows")
def test_sous_pythonw_un_test_qui_lance_git_passe(tmp_path):
    """La situation du cockpit, de bout en bout : un parent sous pythonw lance pytest comme
    `verifier`, et le test lancé démarre lui-même un sous-processus (git)."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.is_file():
        pytest.skip("pythonw.exe absent à côté de l'interpréteur")
    test = tmp_path / "test_lance_git.py"
    test.write_text("import subprocess\n\n\ndef test_git():\n"
                    "    assert subprocess.run(['git', '--version'], capture_output=True).returncode == 0\n",
                    encoding="utf-8")
    script = ("import subprocess, sys\n"
              f"sys.path.insert(0, {str(SITE)!r})\n"
              "from tools.cockpit import publication\n"
              "cp = subprocess.run([publication._python_console(), '-m', 'pytest', '-q', '-p', 'no:cacheprovider', "
              f"{str(test)!r}], stdin=subprocess.DEVNULL, capture_output=True, text=True, "
              "creationflags=subprocess.CREATE_NO_WINDOW)\n"
              "print(cp.returncode)\n"
              "print(cp.stdout[-800:])\n")
    cp = subprocess.run([str(pythonw), "-c", script], capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert cp.stdout.splitlines()[:1] == ["0"], cp.stdout + cp.stderr
