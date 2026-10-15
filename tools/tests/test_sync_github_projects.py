# tools/tests/test_sync_github_projects.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # tools/ on path
import sync_github_projects as s


def test_normalize_repo_url_basic():
    assert s.normalize_repo_url("https://github.com/RoJLD/ELYSIUM") == "rojld/elysium"


def test_normalize_repo_url_strips_git_suffix_and_slash():
    assert s.normalize_repo_url("https://github.com/RoJLD/ELYSIUM.git") == "rojld/elysium"
    assert s.normalize_repo_url("https://github.com/RoJLD/repo-name/") == "rojld/repo-name"


def test_normalize_repo_url_http_and_case():
    assert s.normalize_repo_url("http://github.com/A/B") == "a/b"


def test_normalize_repo_url_rejects_non_github():
    assert s.normalize_repo_url("index.html#demos") is None
    assert s.normalize_repo_url("https://gitlab.com/x/y") is None
    assert s.normalize_repo_url("https://github.com/RoJLD") is None   # no repo segment
    assert s.normalize_repo_url(None) is None
    assert s.normalize_repo_url("") is None


def test_repo_key_from_full_name_and_fallback():
    assert s.repo_key({"full_name": "RoJLD/Anthropos"}) == "rojld/anthropos"
    assert s.repo_key({"html_url": "https://github.com/RoJLD/Fusion"}) == "rojld/fusion"
    assert s.repo_key({}) == ""


def test_catalog_github_refs_extracts_only_github_links():
    catalog = {"projects": [
        {"id": "elysium", "links": {"github": "https://github.com/RoJLD/ELYSIUM"}},
        {"id": "pfe", "links": {"article": "articles/x.html"}},          # no github
        {"id": "demo", "links": {"demo": "index.html#demos"}},           # no github
        {"id": "weird", "links": {"github": "https://gitlab.com/a/b"}},  # not github -> skip
        {"id": "nolinks"},                                               # no links key
    ]}
    assert s.catalog_github_refs(catalog) == [("elysium", "rojld/elysium")]


def test_catalog_github_refs_empty_catalog():
    assert s.catalog_github_refs({}) == []
    assert s.catalog_github_refs({"projects": None}) == []


def _repo(**kw):
    base = {"name": "Thing", "fork": False, "archived": False}
    base.update(kw)
    return base


def test_is_showcase_candidate_plain_owned_repo():
    assert s.is_showcase_candidate(_repo(name="Anthropos")) is True


def test_is_showcase_candidate_excludes_fork_archived_site():
    assert s.is_showcase_candidate(_repo(fork=True)) is False
    assert s.is_showcase_candidate(_repo(archived=True)) is False
    assert s.is_showcase_candidate(_repo(name="RoJLD.github.io")) is False
    assert s.is_showcase_candidate(_repo(name="rojld.github.io")) is False  # case-insensitive


def test_is_showcase_candidate_include_forks_override():
    assert s.is_showcase_candidate(_repo(fork=True), include_forks=True) is True
    # archived stays excluded even with include_forks
    assert s.is_showcase_candidate(_repo(fork=True, archived=True), include_forks=True) is False


def _gh_repo(name, fork=False, archived=False, desc=None, lang="Python", stars=0, pushed="2026-01-02T09:00:00Z"):
    return {"name": name, "full_name": f"RoJLD/{name}", "html_url": f"https://github.com/RoJLD/{name}",
            "fork": fork, "archived": archived, "description": desc, "language": lang,
            "stargazers_count": stars, "pushed_at": pushed}


def _catalog(*github_urls):
    return {"projects": [{"id": u.rsplit("/", 1)[-1].lower(), "links": {"github": u}} for u in github_urls]}


def test_diff_flags_dead_link_and_missing():
    catalog = _catalog("https://github.com/RoJLD/ELYSIUM")  # ELYSIUM not among live repos
    repos = [_gh_repo("Anthropos", desc="Career OS"),
             _gh_repo("GitNexus", fork=True),
             _gh_repo("RoJLD.github.io", lang="HTML")]
    diff = s.diff_catalog(catalog, repos)
    assert diff["dead_links"] == [{"id": "elysium", "key": "rojld/elysium"}]
    names = {m["name"] for m in diff["missing"]}
    assert "Anthropos" in names          # owned, unreferenced -> surfaced
    assert "GitNexus" not in names       # fork excluded
    assert "RoJLD.github.io" not in names  # site repo excluded


def test_diff_matched_link_not_dead():
    catalog = _catalog("https://github.com/RoJLD/Anthropos")
    repos = [_gh_repo("Anthropos")]
    diff = s.diff_catalog(catalog, repos)
    assert diff["dead_links"] == []
    assert diff["missing"] == []        # Anthropos is referenced -> not missing


def test_diff_other_owner_link_not_flagged_dead():
    catalog = _catalog("https://github.com/someoneelse/upstream")
    repos = [_gh_repo("Anthropos")]
    diff = s.diff_catalog(catalog, repos)
    assert diff["dead_links"] == []     # different owner -> out of scope


def test_diff_missing_payload_fields():
    catalog = _catalog()  # empty catalog
    repos = [_gh_repo("HMMstudio", desc=None, lang="Python", stars=1, pushed="2026-06-11T10:00:00Z")]
    diff = s.diff_catalog(catalog, repos)
    m = diff["missing"][0]
    assert m == {"name": "HMMstudio", "url": "https://github.com/RoJLD/HMMstudio",
                 "desc": None, "lang": "Python", "stars": 1, "pushed": "2026-06-11", "fork": False}


def test_diff_include_forks():
    catalog = _catalog()
    repos = [_gh_repo("GitNexus", fork=True)]
    assert s.diff_catalog(catalog, repos)["missing"] == []
    assert {m["name"] for m in s.diff_catalog(catalog, repos, include_forks=True)["missing"]} == {"GitNexus"}


def test_has_drift():
    assert s.has_drift({"dead_links": [], "missing": []}) is False
    assert s.has_drift({"dead_links": [{"id": "x", "key": "a/b"}], "missing": []}) is True
    assert s.has_drift({"dead_links": [], "missing": [{"name": "Y"}]}) is True


def test_render_report_in_sync_is_ascii_and_positive():
    txt = s.render_report({"dead_links": [], "missing": []})
    assert txt.isascii()
    assert "[ok]" in txt.lower() or "en phase" in txt.lower()


def test_render_report_lists_dead_and_missing():
    diff = {"dead_links": [{"id": "elysium", "key": "rojld/elysium"}],
            "missing": [{"name": "Anthropos", "url": "https://github.com/RoJLD/Anthropos",
                         "desc": "Career OS", "lang": "Python", "stars": 0, "pushed": "2026-04-03", "fork": False}]}
    txt = s.render_report(diff)
    assert txt.isascii()
    assert "elysium" in txt
    assert "Anthropos" in txt
    assert "https://github.com/RoJLD/Anthropos" in txt


import json


def _write_catalog(tmp_path, *github_urls):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(_catalog(*github_urls)), encoding="utf-8")
    return p


def test_main_returns_1_on_drift(tmp_path, capsys):
    cat = _write_catalog(tmp_path, "https://github.com/RoJLD/ELYSIUM")
    fake = lambda user: [_gh_repo("Anthropos", desc="Career OS")]
    rc = s.main(["--catalog", str(cat)], fetch_fn=fake)
    out = capsys.readouterr().out
    assert rc == 1
    assert "elysium" in out
    assert "Anthropos" in out


def test_main_returns_0_when_in_sync(tmp_path, capsys):
    cat = _write_catalog(tmp_path, "https://github.com/RoJLD/Anthropos")
    fake = lambda user: [_gh_repo("Anthropos"), _gh_repo("RoJLD.github.io", lang="HTML")]
    rc = s.main(["--catalog", str(cat)], fetch_fn=fake)
    assert rc == 0
    assert "En phase" in capsys.readouterr().out


def test_main_json_output_is_valid(tmp_path, capsys):
    cat = _write_catalog(tmp_path)
    fake = lambda user: [_gh_repo("HMMstudio", stars=1)]
    rc = s.main(["--catalog", str(cat), "--json"], fetch_fn=fake)
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["missing"][0]["name"] == "HMMstudio"


# ── Corrections revue finale (opus) ─────────────────────────────────────────

def test_normalize_repo_url_www_prefix():
    assert s.normalize_repo_url("https://www.github.com/RoJLD/ELYSIUM") == "rojld/elysium"


def test_render_report_coerces_non_ascii():
    diff = {"dead_links": [], "missing": [{
        "name": "HMMstudio", "url": "https://github.com/RoJLD/HMMstudio",
        "desc": "toolkit \U0001f680 中文", "lang": "Python",
        "stars": 1, "pushed": "2026-06-11", "fork": False}]}
    txt = s.render_report(diff)
    assert txt.isascii()
    assert "HMMstudio" in txt


def test_fetch_repos_gh_flattens_slurp_pages(monkeypatch):
    import subprocess

    class _R:
        stdout = '[[{"full_name":"RoJLD/A"}],[{"full_name":"RoJLD/B"}]]'

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _R())
    repos = s.fetch_repos_gh("RoJLD")
    assert [r["full_name"] for r in repos] == ["RoJLD/A", "RoJLD/B"]  # liste plate de dicts


def test_fetch_repos_gh_reports_gh_failure(monkeypatch):
    import subprocess
    import pytest

    def _boom(*a, **k):
        raise subprocess.CalledProcessError(1, "gh", stderr="bad creds")

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(SystemExit):
        s.fetch_repos_gh("RoJLD")


def test_main_missing_catalog_clear_error(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        s.main(["--catalog", str(tmp_path / "nope.yaml")], fetch_fn=lambda u: [])


def test_main_json_output_is_ascii(tmp_path, capsys):
    cat = _write_catalog(tmp_path)
    fake = lambda user: [_gh_repo("HMMstudio", desc="rocket \U0001f680")]
    rc = s.main(["--catalog", str(cat), "--json"], fetch_fn=fake)
    out = capsys.readouterr().out
    assert out.isascii()
    json.loads(out)  # toujours du JSON valide


def test_report_header_mentions_profile_json():
    assert "profile.json" in s.render_report({"dead_links": [], "missing": []})


# ── Le relevé des dépôts publics (`--temoin`) ────────────────────────────────

def test_temoin_depots_publics_ne_garde_que_le_necessaire():
    """Le relevé ne retient que ce dont une garde hors-ligne a besoin : le nom, la
    publication de Pages, le caractère de fork. Un relevé qui recopierait la
    réponse GitHub entière changerait à chaque étoile reçue, donc à chaque commit.
    """
    repos = [{"name": "Zeta", "has_pages": False, "fork": False, "stargazers_count": 7},
             {"name": "alpha", "has_pages": True, "fork": True}]
    t = s.temoin_depots_publics(repos, owner="RoJLD", releve="2026-10-15")
    assert t["owner"] == "RoJLD" and t["releve"] == "2026-10-15"
    assert t["repos"] == [{"name": "alpha", "has_pages": True, "fork": True},
                          {"name": "Zeta", "has_pages": False, "fork": False}]
    assert "--temoin" in t["$comment"]   # le fichier porte sa propre commande de régénération


def test_main_temoin_ecrit_le_releve_et_sort_sans_rapport(tmp_path, capsys):
    """`--temoin` relève, il ne juge pas : le catalogue dérive ici (ELYSIUM absent
    des dépôts rendus) et le code de sortie reste 0.
    """
    cat = _write_catalog(tmp_path, "https://github.com/RoJLD/ELYSIUM")
    cible = tmp_path / "temoin.json"
    rc = s.main(["--catalog", str(cat), "--temoin", str(cible)],
                fetch_fn=lambda u: [{"name": "HMMstudio", "has_pages": False, "fork": False}])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Liens morts" not in out
    assert out.isascii()
    ecrit = json.loads(cible.read_text(encoding="utf-8"))
    assert [r["name"] for r in ecrit["repos"]] == ["HMMstudio"]


# ── Les gardes de corpus de ces liens vivent dans test_liens_internes.py ─────
#
# Elles sont nées ici le 2026-10-15 (§ « Les liens RoJLD du profil ») et en sont
# parties le même jour : `publication.py::verifier()`, la porte du bouton
# « Publier », joue `tools/tests/test_liens_internes.py` en entier et ne joue PAS
# ce fichier. Mesuré sur une copie de l'arbre, les deux liens morts remis dans
# `profile.json` : la porte rendait 5 contrôles sur 5 « OK » quand `pytest
# tools/tests/test_sync_github_projects.py` rendait « 2 failed ».
#
# Ce qui reste ici juge l'OUTIL (`--temoin`, `catalog_github_refs`, `diff_catalog`)
# et n'a pas à être dans la porte. Ce qui juge le CORPUS PUBLIÉ — le profil
# confronté au relevé des dépôts publics — doit l'être : à poser dans
# `test_liens_internes.py`, pas ici.


# ── Le détecteur lisait UN champ de `links`, le défaut était dans un autre ────

def test_catalog_github_refs_lit_tous_les_champs_de_links():
    """Mesuré le 2026-10-15 : le `links.live` de `hmm-studio` visait une URL morte
    et n'entrait JAMAIS dans `dead_links` — la fonction ne lisait que
    `links.github`. Le détecteur du dépôt était aveugle au champ même où était le
    défaut, et une garde bâtie sur lui refermait le dossier en y laissant le lien
    mort. `render_links` (build_projects.py) affiche pourtant les cinq champs.
    """
    catalog = {"projects": [
        {"id": "a", "links": {"live": "https://github.com/RoJLD/mort-dans-live"}},
        {"id": "b", "links": {"demo": "https://github.com/RoJLD/mort-dans-demo"}},
        {"id": "c", "links": {"github": "https://github.com/RoJLD/vivant",
                              "article": "https://github.com/RoJLD/vivant/blob/main/README.md"}},
    ]}
    assert s.catalog_github_refs(catalog) == [
        ("a", "rojld/mort-dans-live"),
        ("b", "rojld/mort-dans-demo"),
        ("c", "rojld/vivant"),   # deux champs, un seul dépôt : pas de doublon dans dead_links
    ]


def test_diff_signale_un_lien_mort_hors_du_champ_github():
    """Le rapport doit nommer le fautif quel que soit le champ de `links` qui le porte."""
    catalog = {"projects": [{"id": "hmm", "links": {
        "github": "https://github.com/RoJLD/HMMstudio",
        "live": "https://github.com/RoJLD/HMMstudio-studio"}}]}
    diff = s.diff_catalog(catalog, [_gh_repo("HMMstudio")])
    assert diff["dead_links"] == [{"id": "hmm", "key": "rojld/hmmstudio-studio"}]
