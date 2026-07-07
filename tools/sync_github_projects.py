# tools/sync_github_projects.py
"""sync_github_projects.py — rapport de derive entre data/projects.yaml et le
GitHub public de RoJLD. Read-only : n'ecrit jamais le catalogue.

Meme patron que build_projects.py : fonctions pures + main() fin. L'acces reseau
(fetch GitHub) passe par un seam injectable `fetch_fn` (comme complete_fn dans
cv_target) -> toute la logique de diff est testable hors-ligne.

Usage (depuis la racine du repo site) :
    python tools/sync_github_projects.py            # rapport texte, exit 1 si derive
    python tools/sync_github_projects.py --json     # sortie machine
    python tools/sync_github_projects.py --include-forks
"""
from __future__ import annotations

import re
from typing import Callable, Optional

# Autorise l'optionnel prefixe www. (variantes de href reelles).
_GH = re.compile(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)", re.IGNORECASE)


def normalize_repo_url(url: Optional[str]) -> Optional[str]:
    """URL github.com -> 'owner/name' minuscule, sinon None."""
    if not url:
        return None
    m = _GH.match(url.strip())
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    if name.lower().endswith(".git"):
        name = name[:-4]
    if not name:
        return None
    return f"{owner.lower()}/{name.lower()}"


def repo_key(repo: dict) -> str:
    """Cle 'owner/name' minuscule d'un repo GitHub (full_name, sinon html_url)."""
    fn = repo.get("full_name")
    if fn:
        return fn.lower()
    return normalize_repo_url(repo.get("html_url", "")) or ""


def catalog_github_refs(catalog: dict) -> list[tuple[str, str]]:
    """[(project_id, 'owner/name')] pour chaque projet avec un links.github parseable."""
    refs: list[tuple[str, str]] = []
    for p in catalog.get("projects") or []:
        url = (p.get("links") or {}).get("github")
        key = normalize_repo_url(url) if url else None
        if key:
            refs.append((p.get("id", ""), key))
    return refs


def is_showcase_candidate(repo: dict, site_repo: str = "RoJLD.github.io",
                          include_forks: bool = False) -> bool:
    """Repo digne d'etre surface dans 'missing' : ni archive, ni fork (sauf override),
    ni le repo du site lui-meme."""
    if repo.get("archived"):
        return False
    if repo.get("fork") and not include_forks:
        return False
    if (repo.get("name") or "").lower() == site_repo.lower():
        return False
    return True


def diff_catalog(catalog: dict, repos: list, *, owner: str = "RoJLD",
                 site_repo: str = "RoJLD.github.io", include_forks: bool = False) -> dict:
    """Compare le catalogue cure au set public GitHub. Read-only, pur."""
    owner_l = owner.lower()
    live = {k for k in (repo_key(r) for r in repos) if k}
    refs = catalog_github_refs(catalog)
    ref_keys = {k for _, k in refs}

    dead_links = [{"id": pid, "key": k} for pid, k in refs
                  if k.split("/", 1)[0] == owner_l and k not in live]

    missing = []
    for r in repos:
        if not is_showcase_candidate(r, site_repo, include_forks):
            continue
        k = repo_key(r)
        if k and k not in ref_keys:
            missing.append({
                "name": r.get("name", ""),
                "url": r.get("html_url", ""),
                "desc": r.get("description"),
                "lang": r.get("language"),
                "stars": r.get("stargazers_count", 0),
                "pushed": (r.get("pushed_at") or "")[:10],
                "fork": bool(r.get("fork")),
            })
    return {"dead_links": dead_links, "missing": missing}


def has_drift(diff: dict) -> bool:
    return bool(diff.get("dead_links") or diff.get("missing"))


def _ascii(s) -> str:
    """Coerce en ASCII (contrainte sortie ASCII-only, securite console cp1252)."""
    return str(s if s is not None else "").encode("ascii", "replace").decode("ascii")


def render_report(diff: dict) -> str:
    dead = diff.get("dead_links", [])
    missing = diff.get("missing", [])
    lines = ["=== Sync GitHub <-> projects.yaml ==="]
    if dead:
        lines.append("")
        lines.append("[!] Liens morts (%d) - repo public introuvable :" % len(dead))
        for d in dead:
            lines.append("  - projet '%s' -> github.com/%s" % (d["id"], d["key"]))
    if missing:
        lines.append("")
        lines.append("[+] Repos owned absents du catalogue (%d) :" % len(missing))
        for m in missing:
            desc = m.get("desc") or "(sans description)"
            lines.append("  - %s [%s, %d*, %s] - %s" % (
                m.get("name", ""), m.get("lang") or "?", m.get("stars", 0),
                m.get("pushed", ""), desc))
            lines.append("    %s" % m.get("url", ""))
    if not dead and not missing:
        lines.append("")
        lines.append("[ok] En phase - aucun lien mort, aucun repo owned non catalogue.")
    return _ascii("\n".join(lines))


def fetch_repos_gh(user: str) -> list:
    """Fetch reel des repos publics owner via gh CLI. Non teste hors-ligne.

    `gh api ... --paginate --slurp` renvoie un array de PAGES ([[...],[...]]),
    meme pour une seule page -> on aplatit en liste plate de repos.
    """
    import json
    import subprocess
    try:
        res = subprocess.run(
            ["gh", "api", "users/%s/repos?per_page=100&type=owner" % user, "--paginate", "--slurp"],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError:
        raise SystemExit("gh CLI introuvable : installez GitHub CLI (https://cli.github.com).")
    except subprocess.CalledProcessError as exc:
        raise SystemExit("gh api a echoue : %s" % (exc.stderr or str(exc)).strip())
    pages = json.loads(res.stdout)
    return [repo for page in pages for repo in page]


def main(argv: Optional[list] = None, fetch_fn: Optional[Callable[[str], list]] = None) -> int:
    import argparse
    import json
    import pathlib

    try:
        import yaml
    except ImportError:
        raise SystemExit("PyYAML requis : pip install pyyaml")

    ap = argparse.ArgumentParser(description="Rapport de derive projects.yaml <-> GitHub public.")
    ap.add_argument("--user", default="RoJLD")
    ap.add_argument("--site-repo", default="RoJLD.github.io")
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--catalog", default=None, help="chemin projects.yaml (defaut: data/projects.yaml du repo)")
    args = ap.parse_args(argv)

    root = pathlib.Path(__file__).resolve().parents[1]
    catalog_path = pathlib.Path(args.catalog) if args.catalog else root / "data" / "projects.yaml"
    if not catalog_path.exists():
        raise SystemExit("Catalogue introuvable : %s" % catalog_path)
    try:
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SystemExit("YAML invalide (%s) : %s" % (catalog_path, exc))
    if not isinstance(catalog, dict):
        raise SystemExit("Le catalogue doit etre un mapping YAML (cle 'projects').")

    fetch = fetch_fn or fetch_repos_gh
    repos = fetch(args.user)
    diff = diff_catalog(catalog, repos, owner=args.user,
                        site_repo=args.site_repo, include_forks=args.include_forks)

    if args.as_json:
        print(json.dumps(diff, ensure_ascii=True, indent=2))
    else:
        print(render_report(diff))
    return 1 if has_drift(diff) else 0


if __name__ == "__main__":
    raise SystemExit(main())
