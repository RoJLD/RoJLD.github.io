#!/usr/bin/env python3
"""build_articles.py — génère articles/<slug>.html et articles/<slug>.en.html.

Sources :
  - articles/src/<slug>.<lang>.md   prose + frontmatter `tldr`
  - profile.json.articles[]         catalogue (titre, date, tags, url)

Le chrome (head/CSS/nav/pied) est un gabarit ; le corps vient du Markdown ; le temps
de lecture est DÉRIVÉ du nombre de mots — la page écrite à la main annonçait « 8 min »
pour 509 mots, une valeur qu'aucune source ne pouvait contredire.

Seul builder du dépôt à dépendre d'un paquet tiers (`markdown`, cf. requirements.txt) :
l'import est paresseux, pour que les six autres continuent de tourner sans lui.

Usage (depuis la racine du repo site) :
    python tools/build_articles.py
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_site import esc, fmt_date, _bi          # noqa: E402  (utilitaires partagés)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "articles" / "src"
WORDS_PER_MINUTE = 200

LABELS = {
    "fr": {"read": "min de lecture", "back": "← Retour", "back_all": "← Retour aux articles",
           "tldr": "TL;DR :", "by": "par"},
    "en": {"read": "min read", "back": "← Back", "back_all": "← Back to articles",
           "tldr": "TL;DR:", "by": "by"},
}


class BuildError(Exception):
    pass


# ── CSS : repris verbatim de la page écrite à la main (design-system du site) ──
_CSS = """
        :root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--ease:cubic-bezier(.4,0,.2,1)}
        [data-theme="dark"]{--bg:#060a12;--bg-2:#111a2e;--border:#1a2847;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--accent-g:rgba(59,130,246,.1);--glass:rgba(10,16,32,.75)}
        [data-theme="light"]{--bg:#f5f7fa;--bg-2:#fff;--border:#d8dfe9;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--accent-g:rgba(37,99,235,.06);--glass:rgba(245,247,250,.8)}
        *{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}
        body{font-family:var(--sans);background:var(--bg);color:var(--tx-1);line-height:1.8;font-size:16px;-webkit-font-smoothing:antialiased;transition:background .5s var(--ease),color .5s var(--ease)}
        nav{position:fixed;top:0;width:100%;z-index:100;padding:14px 0;background:var(--glass);backdrop-filter:blur(24px);border-bottom:1px solid var(--border)}
        .nav-i{max-width:720px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between}
        .nav-brand{font-family:var(--serif);font-size:18px;color:var(--tx-1);text-decoration:none;letter-spacing:-.03em}.nav-brand b{color:var(--accent)}
        .nav-back{color:var(--tx-3);text-decoration:none;font-size:13px;font-weight:500;transition:color .3s var(--ease)}.nav-back:hover{color:var(--accent)}
        .theme-btn{width:34px;height:34px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;font-size:15px;display:grid;place-items:center;transition:all .3s var(--ease)}.theme-btn:hover{border-color:var(--accent);transform:rotate(30deg)}

        article{max-width:720px;margin:0 auto;padding:120px 32px 80px}
        .article-meta{margin-bottom:40px}
        .article-date{font-size:12px;color:var(--tx-3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}
        .article-tags{display:flex;gap:6px;margin-bottom:20px}.article-tag{font-size:11px;padding:3px 10px;border-radius:100px;background:var(--accent-g);color:var(--accent);font-weight:500}
        h1{font-family:var(--serif);font-size:clamp(32px,5vw,48px);font-weight:400;letter-spacing:-.03em;line-height:1.15;margin-bottom:16px}
        .article-tldr{font-size:15px;color:var(--tx-2);border-left:3px solid var(--accent);padding:14px 20px;background:var(--accent-g);border-radius:0 8px 8px 0;margin-bottom:40px;line-height:1.7}

        h2{font-family:var(--serif);font-size:26px;font-weight:400;letter-spacing:-.02em;margin:48px 0 16px;padding-top:16px;border-top:1px solid var(--border)}
        h3{font-size:18px;font-weight:600;margin:32px 0 12px}
        p{color:var(--tx-2);margin-bottom:18px;line-height:1.8}
        a{color:var(--accent);text-decoration:none}.a:hover{text-decoration:underline}
        strong{color:var(--tx-1);font-weight:600}

        code{font-family:var(--mono);font-size:13px;background:var(--bg-2);border:1px solid var(--border);padding:2px 7px;border-radius:4px;color:var(--accent)}
        pre{background:var(--bg-2);border:1px solid var(--border);border-radius:10px;padding:20px;overflow-x:auto;margin:20px 0 28px}
        pre code{border:none;padding:0;background:none;font-size:13px;line-height:1.7;color:var(--tx-2)}

        blockquote{border-left:3px solid var(--accent);padding:12px 20px;margin:24px 0;color:var(--tx-2);font-style:italic;background:var(--accent-g);border-radius:0 8px 8px 0}
        ul,ol{color:var(--tx-2);margin:12px 0 20px 24px}li{margin-bottom:6px;line-height:1.7}

        .formula{text-align:center;padding:20px;margin:24px 0;font-family:var(--mono);font-size:14px;color:var(--accent);background:var(--bg-2);border:1px solid var(--border);border-radius:10px}

        .article-footer{margin-top:60px;padding-top:32px;border-top:1px solid var(--border);display:flex;align-items:center;gap:16px}
        .af-avatar{width:48px;height:48px;border-radius:50%;background:var(--accent-g);border:1px solid var(--border);display:grid;place-items:center;font-weight:700;color:var(--accent);font-size:18px}
        .af-name{font-weight:600;font-size:15px}.af-bio{font-size:13px;color:var(--tx-3)}
        .af-back{display:inline-block;margin-top:24px;padding:10px 24px;border:1px solid var(--border);border-radius:100px;color:var(--tx-2);text-decoration:none;font-size:13px;font-weight:500;transition:all .3s var(--ease)}.af-back:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-g)}

        @media(max-width:640px){article{padding:100px 18px 60px}h1{font-size:28px}h2{font-size:22px}}
"""

_FONTS = ("https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
          "&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;"
          "0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap")

# Caractères écrits tels quels, pas en entités numériques : une entité placée dans
# une chaîne JS d'attribut `onclick` ne fonctionne QUE parce que le parseur HTML
# décode l'attribut avant que JS ne le voie. Ça marche, mais c'est une subtilité
# gratuite dans du code que personne ne relira — et qui casserait si le fragment
# migrait un jour vers un fichier .js.
_SUN, _MOON, _BOLT = "☀️", "\U0001f319", "⚡"
_THEME_TOGGLE = ("const h=document.documentElement;"
                 "if(h.getAttribute('data-theme')==='dark'){h.setAttribute('data-theme','light');"
                 f"this.textContent='{_SUN}'}}else{{h.setAttribute('data-theme','dark');"
                 f"this.textContent='{_MOON}'}}")


def _markdown():
    """Import paresseux : seul ce builder dépend d'un paquet tiers."""
    try:
        import markdown
    except ImportError as exc:                                   # pragma: no cover
        raise BuildError(
            "le paquet `markdown` est requis pour générer les articles.\n"
            "  pip install -r requirements.txt"
        ) from exc
    return markdown


def load_profile() -> dict:
    return json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))


def slug_of(article: dict) -> str:
    """Le slug vient de `url`, JAMAIS de `id`.

    `id` vaut `couverture_dynamique` et l'URL `articles/couverture-dynamique.html` :
    une dérivation `_`→`-` marcherait ici par coïncidence et casserait au premier
    identifiant accentué ou renommé. `url` est de surcroît le lien public — c'est lui
    qui fait autorité."""
    url = article.get("url")
    if not url:
        raise BuildError(f"article {article.get('id')!r} sans `url` — le slug en dérive")
    return pathlib.PurePosixPath(url).stem


def en_path_for(fr_url: str) -> str:
    """'articles/x.html' -> 'articles/x.en.html'."""
    if not fr_url.endswith(".html"):
        raise BuildError(f"URL d'article inattendue : {fr_url!r}")
    return fr_url[: -len(".html")] + ".en.html"


def reading_minutes(body: str) -> int:
    return max(1, math.ceil(len(body.split()) / WORDS_PER_MINUTE))


def parse_source(text: str) -> tuple[dict, str]:
    """'---\\nclé: valeur\\n---\\ncorps' -> ({clé: valeur}, corps). Fail-loud.

    Le `tldr` n'a pas de valeur par défaut sensée : son absence est une erreur de
    rédaction, pas un cas à combler silencieusement."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise BuildError("source d'article sans frontmatter `---` (le `tldr` est requis)")
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    if not fm.get("tldr"):
        raise BuildError("frontmatter sans `tldr`")
    return fm, m.group(2)


def md_to_html(body: str) -> str:
    """Markdown -> HTML, le bloc maison ::formula extrait AVANT conversion.

    Le contenu d'une formule est une donnée : ses `*` et `_` ne sont pas de l'emphase.
    Le sortir du flux avant de convertir est le même principe que les blocs de code
    protégés."""
    formulas: list[str] = []

    def _stash(m: re.Match) -> str:
        formulas.append(m.group(1).strip())
        return f"\n\nFORMULAPLACEHOLDER{len(formulas) - 1}\n\n"

    staged = re.sub(r"^::formula\n(.*?)\n^::$", _stash, body, flags=re.M | re.S)
    out = _markdown().markdown(staged, extensions=["fenced_code"])
    for i, f in enumerate(formulas):
        out = out.replace(f"<p>FORMULAPLACEHOLDER{i}</p>",
                          f'<div class="formula">{esc(f)}</div>')
    return out


def render_head(title: str, lang: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="{lang}" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{esc(title)}, {LABELS[lang]["by"]} Robin Denis</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>{_BOLT}</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="{_FONTS}" rel="stylesheet">
    <style>{_CSS}    </style>
</head>"""


def _author_bio(profile: dict, lang: str) -> str:
    """Dérivée de identity.tagline + première formation.

    La version écrite à la main était FR seulement ; `tagline` étant déjà bilingue,
    la dérivation fournit l'anglais sans travail supplémentaire."""
    tagline = _bi(profile["identity"]["tagline"], lang)
    edu = (profile.get("education") or [{}])[0]
    school = edu.get("school", "")
    years = re.findall(r"\d{4}", str(edu.get("period", "")))
    suffix = f" {years[-1]}" if years else ""
    return f"{tagline} · {school}{suffix}" if school else tagline


def render_article_page(profile: dict, article_id: str, lang: str) -> str:
    articles = {a.get("id"): a for a in profile.get("articles", [])}
    if article_id not in articles:
        raise BuildError(f"article {article_id!r} absent de profile.json")
    art = articles[article_id]
    lab = LABELS[lang]

    src = SRC / f"{slug_of(art)}.{lang}.md"
    if not src.exists():
        raise BuildError(f"source absente : {src.relative_to(ROOT)}")
    front, body_md = parse_source(src.read_text(encoding="utf-8"))

    title = _bi(art["title"], lang)
    meta_line = f'{fmt_date(art["date"], lang)} · {reading_minutes(body_md)} {lab["read"]}'
    tags = "\n".join(f'            <span class="article-tag">{esc(t)}</span>'
                     for t in art.get("tags", []))
    initials = (profile["identity"]["first_name"][:1]
                + profile["identity"]["last_name"][:1]).upper()

    return f"""{render_head(title, lang)}
<body>

<nav><div class="nav-i">
    <a href="../index.html" class="nav-brand">R<b>.</b> Denis</a>
    <div style="display:flex;align-items:center;gap:16px">
        <a href="../index.html" class="nav-back">{lab["back"]}</a>
        <button class="theme-btn" onclick="{_THEME_TOGGLE}">{_MOON}</button>
    </div>
</div></nav>

<article>
    <div class="article-meta">
        <div class="article-date">{esc(meta_line)}</div>
        <div class="article-tags">
{tags}
        </div>
    </div>

    <h1>{esc(title)}</h1>

    <div class="article-tldr">
        <strong>{lab["tldr"]}</strong> {esc(front["tldr"])}
    </div>

{md_to_html(body_md)}

    <div class="article-footer">
        <div class="af-avatar">{esc(initials)}</div>
        <div>
            <div class="af-name">{esc(profile["identity"]["first_name"])} {esc(profile["identity"]["last_name"])}</div>
            <div class="af-bio">{esc(_author_bio(profile, lang))}</div>
        </div>
    </div>
    <a href="../index.html#blog" class="af-back">{lab["back_all"]}</a>
</article>
</body>
</html>
"""


def build_articles(profile: dict | None = None,
                   write: bool = True) -> tuple[list[str], list[str]]:
    """Génère toutes les pages disponibles.

    Retourne (chemins produits, manques signalés). Un `.en.md` absent n'est PAS une
    erreur — la carte EN retombera sur le FR — mais il est rapporté à l'appelant :
    un repli silencieux serait un masquage."""
    if profile is None:
        profile = load_profile()
    produced: list[str] = []
    missing: list[str] = []

    for art in profile.get("articles", []):
        slug = slug_of(art) if art.get("url") else None
        for lang, rel in (("fr", art.get("url")),
                          ("en", en_path_for(art["url"]) if art.get("url") else None)):
            if slug is None or not (SRC / f"{slug}.{lang}.md").exists():
                missing.append(f"{art.get('id')} [{lang}]")
                continue
            page = render_article_page(profile, art["id"], lang)
            if write:
                out = ROOT / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(page, encoding="utf-8")
            produced.append(rel)
    return produced, missing


def main() -> int:
    produced, missing = build_articles()
    print(f"[build_articles] OK - {len(produced)} page(s) generee(s)")
    for rel in produced:
        print(f"  + {rel}")
    for m in missing:
        print(f"  ! source absente : {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
