#!/usr/bin/env python3
"""build_projects.py — génère projects/index.html depuis profile.json (projects, project_tag_labels, projects_meta).

Page statique autonome, native au design-system de robin-denis.com
(mêmes variables CSS / fonts / thèmes que index.html). Filtrage par tag en JS,
snippets colorés via highlight.js (CDN). Aucun état serveur.

Usage (depuis la racine du repo site) :
    python tools/build_projects.py
"""
from __future__ import annotations

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "projects" / "index.html"


class BuildError(Exception):
    pass

TYPE_LABEL = {"academic": "Académique", "personal": "Personnel", "professional": "Professionnel"}
TYPE_CLASS = {"academic": "v", "personal": "b", "professional": "g"}

HLJS = "11.9.0"


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _fr(v):
    """Champ str OU {fr,en} -> version fr (page projets FR-only)."""
    return v["fr"] if isinstance(v, dict) else (v or "")


def one_line(s: str) -> str:
    return " ".join(str(s or "").split())


def tag_label(tag: str, labels: dict) -> str:
    return labels.get(tag, tag.replace("-", " ").title())


def render_links(p: dict) -> str:
    links = p.get("links") or {}
    order = [
        ("github", "GitHub", "code"),
        ("demo", "Démo", "play"),
        ("live", "Live", "external"),
        ("article", "Article", "doc"),
        ("pdf", "PDF", "doc"),
    ]
    out = []
    for key, label, _ in order:
        url = links.get(key)
        if url:
            out.append(f'<a class="p-link" href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>')
    if not out and p.get("code_status"):
        out.append(f'<span class="p-status">{e(p["code_status"])}</span>')
    return "".join(out)


def render_snippet(p: dict) -> str:
    sn = p.get("snippet")
    if not sn:
        return ""
    lang = e(sn.get("lang", "text"))
    label = e(sn.get("label", "Code"))
    fpath = ROOT / sn.get("file", "")
    if not fpath.is_file():
        raise BuildError(f"snippet introuvable : {sn.get('file')!r} (projet {p.get('id')})")
    code = html.escape(fpath.read_text(encoding="utf-8"), quote=False)
    note = sn.get("note")
    note_html = f'<p class="snip-note">{e(one_line(note))}</p>' if note else ""
    return (
        f'<details class="snip"><summary><span class="snip-ic">&lt;/&gt;</span> {label}</summary>'
        f'<pre class="snip-pre"><code class="language-{lang}">{code}</code></pre>{note_html}</details>'
    )


def render_card(p: dict, labels: dict) -> str:
    ptype = p.get("type", "personal")
    tags = p.get("tags", []) or []
    tags_attr = e(",".join(tags))
    tag_html = "".join(
        f'<span class="p-tag" data-tag="{e(t)}">{e(tag_label(t, labels))}</span>' for t in tags
    )
    featured = " featured" if p.get("featured") else ""
    return f"""<article id="{e(p.get('id', ''))}" class="p-card{featured}" data-tags="{tags_attr}" data-type="{e(ptype)}">
  <div class="p-head">
    <span class="p-type tg {TYPE_CLASS.get(ptype, 'b')}">{e(TYPE_LABEL.get(ptype, ptype))}</span>
    <span class="p-date">{e(p.get('date', ''))}</span>
  </div>
  <h3 class="p-title">{e(_fr(p.get('name', '')))}</h3>
  <p class="p-summary">{e(one_line(_fr(p.get('summary', ''))))}</p>
  <div class="p-tags">{tag_html}</div>
  {render_snippet(p)}
  <div class="p-links">{render_links(p)}</div>
</article>"""


def collect_tags(projects: list[dict]) -> list[str]:
    seen: list[str] = []
    for p in projects:
        for t in p.get("tags", []) or []:
            if t not in seen:
                seen.append(t)
    return seen


def render_projects_page(profile: dict) -> str:
    projects = profile.get("projects", [])
    labels = profile.get("project_tag_labels", {})
    updated = profile.get("projects_meta", {}).get("updated", "")
    all_tags = collect_tags(projects)

    filter_btns = '<button class="f-btn active" data-filter="all">Tous</button>' + "".join(
        f'<button class="f-btn" data-filter="{e(t)}">{e(tag_label(t, labels))}</button>' for t in all_tags
    )
    cards = "\n".join(render_card(p, labels) for p in projects)

    return f"""<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Projets — Robin Denis</title>
<meta name="description" content="Projets académiques, personnels et professionnels de Robin Denis — quant, ML, infrastructure, hardware.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS}/build/styles/github-dark.min.css">
<style>
:root{{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--radius-sm:8px;--ease:cubic-bezier(.4,0,.2,1)}}
[data-theme="dark"]{{--bg-0:#060a12;--bg-1:#0a1020;--bg-2:#111a2e;--bg-3:#162244;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--accent-g:rgba(59,130,246,.12);--warm:#f59e42;--warm-g:rgba(245,158,66,.10);--green:#22c55e;--green-g:rgba(34,197,94,.10);--violet:#a78bfa;--violet-g:rgba(167,139,250,.10);--glass:rgba(10,16,32,.75);--shadow:rgba(0,0,0,.3)}}
[data-theme="light"]{{--bg-0:#f5f7fa;--bg-1:#edf0f5;--bg-2:#ffffff;--bg-3:#f0f3f8;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--accent-g:rgba(37,99,235,.08);--warm:#d97706;--warm-g:rgba(217,119,6,.08);--green:#16a34a;--green-g:rgba(22,163,74,.08);--violet:#7c3aed;--violet-g:rgba(124,58,237,.08);--glass:rgba(245,247,250,.8);--shadow:rgba(0,0,0,.06)}}
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--sans);background:var(--bg-0);color:var(--tx-1);line-height:1.7;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden;transition:background .5s var(--ease),color .5s var(--ease)}}
.blob{{position:fixed;border-radius:50%;filter:blur(140px);pointer-events:none;z-index:0}}.b1{{width:700px;height:700px;top:-300px;right:-200px;background:var(--accent);opacity:.04}}.b2{{width:500px;height:500px;bottom:-200px;left:-150px;background:var(--warm);opacity:.03}}
nav{{position:fixed;top:0;width:100%;z-index:100;padding:12px 0;background:var(--glass);backdrop-filter:blur(24px) saturate(1.4);border-bottom:1px solid var(--border)}}
.nav-i{{max-width:1000px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between}}
.nav-brand{{font-family:var(--serif);font-size:19px;color:var(--tx-1);letter-spacing:-.03em;text-decoration:none}}.nav-brand b{{color:var(--accent)}}
.nav-r{{display:flex;align-items:center;gap:20px}}
.nav-r a{{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease)}}
.nav-r a:hover{{color:var(--tx-1)}}.nav-r a.on{{color:var(--accent)}}
.ctrl-btn{{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}}
.ctrl-btn:hover{{border-color:var(--accent);transform:scale(1.1)}}
.wrap{{max-width:1000px;margin:0 auto;padding:0 32px;position:relative;z-index:1}}
header.hd{{padding:130px 0 20px;text-align:center}}
header.hd h1{{font-family:var(--serif);font-size:clamp(38px,6vw,56px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}}
header.hd p{{color:var(--tx-2);font-size:16px;font-weight:300;max-width:560px;margin:0 auto}}
.filters{{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:34px 0 30px;position:sticky;top:60px;z-index:50;padding:10px 0;background:linear-gradient(var(--bg-0) 70%,transparent)}}
.f-btn{{padding:7px 16px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;transition:all .25s var(--ease);font-family:var(--sans)}}
.f-btn:hover{{border-color:var(--border-hi);color:var(--tx-1)}}
.f-btn.active{{background:var(--accent);border-color:var(--accent);color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;padding-bottom:60px}}
.p-card{{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:22px;transition:all .3s var(--ease);display:flex;flex-direction:column}}
.p-card:hover{{border-color:var(--border-hi);transform:translateY(-3px);box-shadow:0 12px 32px var(--shadow)}}
.p-card.featured{{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent-g)}}
.p-card.hide{{display:none}}
.p-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
.p-date{{font-size:11px;color:var(--tx-3);letter-spacing:.05em;text-transform:uppercase}}
.p-title{{font-size:17px;font-weight:600;line-height:1.35;margin-bottom:8px}}
.p-summary{{font-size:13.5px;color:var(--tx-2);line-height:1.6;margin-bottom:14px;flex:1}}
.p-tags{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}}
.p-tag{{font-size:11px;padding:3px 10px;border-radius:100px;background:var(--bg-3);color:var(--tx-3);font-weight:500}}
.tg{{padding:3px 11px;border-radius:100px;font-size:11px;font-weight:600}}
.tg.b{{background:var(--accent-g);color:var(--accent)}}.tg.g{{background:var(--green-g);color:var(--green)}}.tg.v{{background:var(--violet-g);color:var(--violet)}}
.snip{{margin-bottom:14px;border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden}}
.snip summary{{cursor:pointer;padding:9px 14px;font-size:12.5px;font-weight:600;color:var(--tx-2);background:var(--bg-1);user-select:none;font-family:var(--mono);list-style:none}}
.snip summary::-webkit-details-marker{{display:none}}
.snip summary:hover{{color:var(--accent)}}
.snip-ic{{color:var(--accent);font-weight:700;margin-right:4px}}
.snip[open] summary{{border-bottom:1px solid var(--border)}}
.snip-pre{{margin:0;overflow-x:auto}}
.snip-pre code.hljs{{font-family:var(--mono);font-size:12.5px;line-height:1.6;padding:16px 18px;background:#0b1120}}
.snip-note{{font-size:12px;color:var(--tx-3);padding:10px 14px;line-height:1.5;font-style:italic}}
.p-links{{display:flex;flex-wrap:wrap;gap:8px;margin-top:auto}}
.p-link{{font-size:12px;font-weight:500;color:var(--accent);text-decoration:none;padding:6px 14px;border:1px solid var(--accent-g);border-radius:100px;transition:all .3s var(--ease)}}
.p-link:hover{{background:var(--accent-g);border-color:var(--accent)}}
.p-status{{font-size:12px;color:var(--tx-3);padding:6px 0;font-style:italic}}
footer{{text-align:center;padding:40px 0;color:var(--tx-3);font-size:12px;border-top:1px solid var(--border)}}
@media(max-width:640px){{.wrap{{padding:0 18px}}.grid{{grid-template-columns:1fr}}.nav-r a:not(.nav-projects){{display:none}}header.hd{{padding:110px 0 10px}}}}
</style>
</head>
<body>
<div class="blob b1"></div><div class="blob b2"></div>
<nav><div class="nav-i">
  <a class="nav-brand" href="/">R<b>.</b> Denis</a>
  <div class="nav-r">
    <a href="/#experience">Expérience</a>
    <a href="/#demos">Démos</a>
    <a class="nav-projects on" href="/projects/">Projets</a>
    <a href="/explorer/">Explorer</a>
    <a href="/highlights/">Highlights</a>
    <a href="/academy/">Academy</a>
    <a href="/graph/">Graphe</a>
    <a href="/#contact">Contact</a>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>

<div class="wrap">
<header class="hd">
  <h1>Projets</h1>
  <p>Réalisations académiques, personnelles et professionnelles — de la finance quantitative à l'infrastructure souveraine, en passant par le hardware.</p>
</header>

<div class="filters" id="filters">{filter_btns}</div>

<div class="grid" id="grid">
{cards}
</div>

<footer>Robin Denis · {e(updated)} · <a href="/" style="color:var(--accent);text-decoration:none">Retour à l'accueil</a></footer>
</div>

<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@{HLJS}/build/highlight.min.js"></script>
<script>
  if (window.hljs) hljs.highlightAll();
  // Filtrage par tag
  const grid = document.getElementById('grid');
  document.getElementById('filters').addEventListener('click', (ev) => {{
    const btn = ev.target.closest('.f-btn'); if (!btn) return;
    document.querySelectorAll('.f-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    grid.querySelectorAll('.p-card').forEach(c => {{
      const tags = (c.dataset.tags || '').split(',');
      c.classList.toggle('hide', f !== 'all' && !tags.includes(f));
    }});
  }});
  // Thème (partagé avec l'accueil via localStorage)
  const root = document.documentElement;
  const saved = localStorage.getItem('theme');
  if (saved) root.setAttribute('data-theme', saved);
  document.getElementById('themeBtn').textContent = root.getAttribute('data-theme') === 'light' ? '☀️' : '🌙';
  function tgTheme() {{
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('themeBtn').textContent = next === 'light' ? '☀️' : '🌙';
  }}
</script>
</body>
</html>
"""


def build_projects(profile: dict | None = None, write: bool = True) -> str:
    if profile is None:
        profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = render_projects_page(profile)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_projects()
    print(f"[build_projects] OK - {out.count('class=\"p-card')} projets -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
