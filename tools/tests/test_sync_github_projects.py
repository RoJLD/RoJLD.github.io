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


# ── Les liens RoJLD du profil, confrontés au relevé des dépôts publics ───────
#
# Pourquoi un relevé committé et pas un appel réseau : un test qui interroge
# github.com punit un poste hors ligne et rend la suite non déterministe. Le
# réseau n'intervient donc qu'à la régénération, à la main :
#     python tools/sync_github_projects.py --temoin data/depots_publics_rojld.json
#
# Ce que ces gardes attrapent, mesuré le 2026-10-15 en visiteur anonyme :
#   * `projects[anthropos].links.github` -> https://github.com/RoJLD/Anthropos
#     rend 404 (dépôt passé privé). Le piège du diagnostic : `gh api
#     repos/RoJLD/Anthropos` AUTHENTIFIÉ rend 200 et `private: true` — la vue du
#     propriétaire, pas celle du recruteur. Le relevé, lui, vient de
#     `users/RoJLD/repos`, qui ne liste que le public (vérifié : le même ensemble
#     de 27 dépôts avec et sans jeton).
#   * `projects[hmm-studio].links.live` -> https://rojld.github.io/HMMstudio/
#     rend 301 vers http://robin-denis.com/HMMstudio/, qui rend 404 : le dépôt ne
#     publie pas de Pages (`has_pages: false`, et
#     `api.github.com/repos/RoJLD/HMMstudio/pages` -> 404). La carte de /projects/
#     affichait deux boutons dont un mort.
#
# Et le second défaut échappe au détecteur du dépôt MÊME CORRIGÉ : mesuré,
# `normalize_repo_url("https://rojld.github.io/HMMstudio/")` rend None, donc
# `catalog_github_refs` ne voit rien et `dead_links` reste vide. Élargir la
# fonction à tous les champs de `links` ferme l'angle mort du CHAMP, pas celui de
# l'HÔTE. La garde `fautifs_pages_sans_publication` ci-dessous est la seule à
# couvrir celui-là — bâtir la garde sur `dead_links` seul aurait refermé le
# dossier en y laissant le lien mort.
#
# Ce qu'elles n'attrapent PAS, et il faut le dire : le relevé vieillit. Un dépôt
# refermé demain ne sera vu qu'à la prochaine régénération. Ces gardes empêchent
# la RÉCIDIVE et tout lien NEUF vers un dépôt non public ; elles ne remplacent
# pas `python tools/sync_github_projects.py` joué de temps en temps avec le
# réseau. Elles ne voient rien d'un domaine tiers (l'URL d'un article), rien de
# `projects_meta.github_profile` (hors des trois sources de `_local_urls`), et
# `has_pages` dit qu'un dépôt publie des Pages, pas que le chemin exact existe.
import re  # noqa: E402

import validate_profile as vp  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_TEMOIN = _ROOT / "data" / "depots_publics_rojld.json"

# GitHub Pages sert `/<segment>/` depuis le dépôt-projet `RoJLD/<segment>` quand
# celui-ci publie des Pages ; sinon le site utilisateur répond 404. Les deux
# écritures mènent au même endroit, le domaine personnalisé n'y change rien
# (mesuré : rojld.github.io/HMMstudio/ -> 301 -> robin-denis.com/HMMstudio/ -> 404).
_PAGE_PROJET = re.compile(
    r"^https?://(?:www\.)?(?:rojld\.github\.io|robin-denis\.com)/([^/#?]+)", re.IGNORECASE)


def _temoin():
    return json.loads(_TEMOIN.read_text(encoding="utf-8"))


def _profil_publie():
    return json.loads((_ROOT / "profile.json").read_text(encoding="utf-8"))


def depots_rojld_vises(profil):
    """[(label, url, nom)] de chaque URL du profil qui vise github.com/RoJLD/<nom>.

    L'énumération des URL est empruntée à `validate_profile._local_urls` : les
    trois sources du corpus (TOUS les champs de `projects[].links`,
    `articles[].url`, `identity.links.*`), déjà tenues par leurs propres tests
    (`test_validateur_refuse_un_lien_mort_dans_identity_links` et sa jumelle sur
    les articles rougissent si une source disparaît). La ré-écrire ici donnerait
    un second recensement à maintenir, qui dériverait du premier sans bruit —
    c'est exactement le défaut que `catalog_github_refs` portait.
    """
    vises = []
    for label, url in vp._local_urls(profil):
        cle = s.normalize_repo_url(url)
        if not cle:
            continue
        owner, nom = cle.split("/", 1)
        if owner == "rojld":
            vises.append((label, url, nom))
    return vises


def pages_projet_visees(profil):
    """[(label, url, segment)] de chaque URL du profil visant `/<segment>/` du domaine."""
    vises = []
    for label, url in vp._local_urls(profil):
        m = _PAGE_PROJET.match(url or "")
        if m:
            vises.append((label, url, m.group(1)))
    return vises


def fautifs_depots_non_publics(profil, temoin):
    """Liens visant un dépôt RoJLD absent du relevé public : 404 pour un visiteur."""
    publics = {r["name"].lower() for r in temoin["repos"]}
    return [f"{label} -> {url}" for label, url, nom in depots_rojld_vises(profil)
            if nom not in publics]


def fautifs_pages_sans_publication(profil, temoin, root):
    """Liens visant `/<segment>/` que personne ne sert.

    Deux façons légitimes d'être servi, une seule suffit : le dépôt-projet
    `RoJLD/<segment>` publie des Pages, ou `<segment>` est écrit sur CE disque et
    le site utilisateur le sert. On ne consulte PAS `servi_ailleurs` : il déclare
    qu'un autre dépôt sert un chemin, pas qu'il le publie — le relevé est le plus
    exigeant des deux témoins, et c'est celui qu'on veut ici.
    """
    avec_pages = {r["name"].lower() for r in temoin["repos"] if r.get("has_pages")}
    return [f"{label} -> {url}" for label, url, seg in pages_projet_visees(profil)
            if seg.lower() not in avec_pages and not (root / seg).exists()]


def test_le_temoin_des_depots_publics_est_renseigne():
    """Contre-vacuité côté relevé : un relevé vide rendrait les gardes muettes."""
    t = _temoin()
    assert t["owner"] == "RoJLD"
    noms = {r["name"] for r in t["repos"]}
    assert "RoJLD.github.io" in noms, "le dépôt du site lui-même manque au relevé"
    assert len(noms) >= 20, f"relevé suspect : {len(noms)} dépôts (27 relevés le 2026-10-15)"
    assert any(r.get("has_pages") for r in t["repos"]), \
        "aucun dépôt à Pages : la garde des pages-projets ne jugerait plus rien"


def test_le_profil_declare_bien_des_liens_rojld_a_juger():
    """Contre-vacuité côté profil : sans ce plancher, la garde suivante passerait
    en ne jugeant rien le jour où l'énumération des URL rétrécit.

    Mesuré le 2026-10-15 : 4 liens RoJLD avant correctif (anthropos, hmm-studio,
    ppe-politique-monetaire, portfolio-site), 3 après le retrait d'Anthropos.
    """
    vises = depots_rojld_vises(_profil_publie())
    assert len(vises) >= 3, f"seulement {len(vises)} liens RoJLD examinés : {vises}"


def test_aucun_lien_ne_vise_un_depot_rojld_absent_du_temoin():
    """La garde du premier défaut mesuré : un recruteur ne doit pas tomber sur un 404."""
    fautifs = fautifs_depots_non_publics(_profil_publie(), _temoin())
    assert not fautifs, (
        f"depot RoJLD absent du releve des depots publics (404 anonyme) : {fautifs} — "
        "si le depot vient d'etre ouvert, regenerer le releve : "
        "python tools/sync_github_projects.py --temoin data/depots_publics_rojld.json")


def test_aucun_lien_ne_vise_une_page_projet_que_personne_ne_sert():
    """La garde du second défaut, celui du champ `links.live` : /HMMstudio/ rend 404."""
    fautifs = fautifs_pages_sans_publication(_profil_publie(), _temoin(), _ROOT)
    assert not fautifs, f"`/<segment>/` sans Pages publiees ni dossier sur ce disque : {fautifs}"


# Les deux gardes ci-dessus sont DORMANTES sur le corpus corrigé : le profil
# publié n'a plus aucun lien mort, donc les vider les laisserait vertes. Le
# corpus ne pouvant plus fournir la preuve, on la fabrique — même procédé que les
# capacités dormantes du validateur (cf. test_liens_internes.py).

def test_la_garde_des_depots_nomme_un_depot_prive_injecte():
    """Le lien retiré du profil le 2026-10-15, rejoué sur un profil fabriqué."""
    profil = {"projects": [{"id": "fantome",
                            "links": {"github": "https://github.com/RoJLD/Anthropos"}}]}
    assert [v[2] for v in depots_rojld_vises(profil)] == ["anthropos"]
    fautifs = fautifs_depots_non_publics(profil, _temoin())
    assert len(fautifs) == 1 and "Anthropos" in fautifs[0], fautifs


def test_la_garde_des_pages_juge_les_deux_sens():
    """Une garde qui crie à tort est une garde qu'on éteint : `/demos/` est écrit
    sur ce disque et le site utilisateur le sert, alors que `/HMMstudio/` ne l'est
    nulle part (ni dossier local, ni Pages du dépôt-projet).
    """
    vivant = {"identity": {"links": {"demos": "https://robin-denis.com/demos/"}}}
    assert pages_projet_visees(vivant), "le lien doit entrer dans le champ de la garde"
    assert fautifs_pages_sans_publication(vivant, _temoin(), _ROOT) == []

    mort = {"projects": [{"id": "fantome",
                          "links": {"live": "https://rojld.github.io/HMMstudio/"}}]}
    assert len(fautifs_pages_sans_publication(mort, _temoin(), _ROOT)) == 1


def test_les_gardes_lisent_tous_les_champs_de_links():
    """Le défaut du 2026-10-15 n'était pas dans `links.github` : il était dans
    `links.live`. Une garde qui ne lit qu'un champ nommé referme le dossier en
    laissant le lien mort dedans.
    """
    profil = {"projects": [{"id": "x", "links": {
        "live": "https://github.com/RoJLD/jamais-public",
        "demo": "https://github.com/RoJLD/jamais-public-non-plus",
        "pdf": "https://rojld.github.io/jamais-publie/",
    }}]}
    fautifs = fautifs_depots_non_publics(profil, _temoin())
    assert len(fautifs) == 2, fautifs
    assert {f.split(" -> ")[0].rsplit(".", 1)[-1] for f in fautifs} == {"live", "demo"}
    assert len(fautifs_pages_sans_publication(profil, _temoin(), _ROOT)) == 1


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
