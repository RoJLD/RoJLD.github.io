#!/usr/bin/env python3
"""build_demos.py — génère demos/index.html depuis profile.json + demos/widgets/*.

Galerie de démos interactives (page autonome, design-system robin-denis.com). Chaque
démo : widget live (demos/widgets/<id>.html+js) + extrait de code du projet lié
(snippets/<project>.py, highlight.js) + lien /projects/#<project>. Filtre par catégorie.
FR-only (comme /projects/). Appelé par build_site.build().
"""
from __future__ import annotations

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demos" / "index.html"
HLJS = "11.9.0"


class BuildError(Exception):
    pass


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s: str) -> str:
    return " ".join(str(s or "").split())


def _read(rel: str) -> str:
    f = ROOT / rel
    if not f.is_file():
        raise BuildError(f"fichier absent : {rel}")
    return f.read_text(encoding="utf-8")


def _desc_fr(d: dict) -> str:
    v = d.get("desc")
    return one_line(v["fr"] if isinstance(v, dict) else (v or ""))


def collect_categories(demos: list) -> list:
    seen: list = []
    for d in demos:
        c = d.get("category")
        if c and c not in seen:
            seen.append(c)
    return seen


def render_card(d: dict) -> str:
    did = d["id"]
    widget = _read(f"demos/widgets/{did}.html")
    proj = d["project"]
    code = html.escape(_read(f"snippets/{proj}.py"), quote=False)
    return f"""<article id="{e(did)}" class="d-card" data-cat="{e(d['category'])}">
  <div class="d-head"><span class="d-cat">{e(d['category'])}</span></div>
  <h3 class="d-title">{e(d['title'])}</h3>
  <p class="d-desc">{e(_desc_fr(d))}</p>
  <div class="d-live">{widget}</div>
  <details class="snip"><summary><span class="snip-ic">&lt;/&gt;</span> Code source</summary>
  <pre class="snip-pre"><code class="language-python">{code}</code></pre></details>
  <div class="d-links"><a class="p-link" href="/projects/#{e(proj)}">Projet complet →</a></div>
</article>"""


TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Démos — Robin Denis</title>
<meta name="description" content="Démos interactives de finance quantitative — pricing d'options, simulation Monte-Carlo.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧪</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@@@HLJS@@/build/styles/github-dark.min.css">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--radius-sm:8px;--ease:cubic-bezier(.4,0,.2,1)}
[data-theme="dark"]{--bg-0:#060a12;--bg-1:#0a1020;--bg-2:#111a2e;--bg-3:#162244;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--accent-g:rgba(59,130,246,.12);--warm:#f59e42;--green:#22c55e;--violet:#a78bfa;--glass:rgba(10,16,32,.75);--shadow:rgba(0,0,0,.3)}
[data-theme="light"]{--bg-0:#f5f7fa;--bg-1:#edf0f5;--bg-2:#ffffff;--bg-3:#f0f3f8;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--accent-g:rgba(37,99,235,.08);--warm:#d97706;--green:#16a34a;--violet:#7c3aed;--glass:rgba(245,247,250,.8);--shadow:rgba(0,0,0,.06)}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg-0);color:var(--tx-1);line-height:1.7;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden;transition:background .5s var(--ease),color .5s var(--ease)}
.blob{position:fixed;border-radius:50%;filter:blur(140px);pointer-events:none;z-index:0}.b1{width:700px;height:700px;top:-300px;right:-200px;background:var(--accent);opacity:.04}
nav{position:fixed;top:0;width:100%;z-index:100;padding:12px 0;background:var(--glass);backdrop-filter:blur(24px) saturate(1.4);border-bottom:1px solid var(--border)}
.nav-i{max-width:1000px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between}
.nav-brand{font-family:var(--serif);font-size:19px;color:var(--tx-1);letter-spacing:-.03em;text-decoration:none}.nav-brand b{color:var(--accent)}
.nav-r{display:flex;align-items:center;gap:20px}
.nav-r a{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease)}
.nav-r a:hover{color:var(--tx-1)}.nav-r a.on{color:var(--accent)}
.ctrl-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}
.ctrl-btn:hover{border-color:var(--accent);transform:scale(1.1)}
.wrap{max-width:1000px;margin:0 auto;padding:0 32px;position:relative;z-index:1}
header.hd{padding:130px 0 20px;text-align:center}
header.hd h1{font-family:var(--serif);font-size:clamp(38px,6vw,56px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}
header.hd p{color:var(--tx-2);font-size:16px;font-weight:300;max-width:560px;margin:0 auto}
.filters{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:34px 0 30px;position:sticky;top:60px;z-index:50;padding:10px 0;background:linear-gradient(var(--bg-0) 70%,transparent)}
.f-btn{padding:7px 16px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;transition:all .25s var(--ease);font-family:var(--sans)}
.f-btn:hover{border-color:var(--border-hi);color:var(--tx-1)}
.f-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px;padding-bottom:60px}
.d-card{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:22px;transition:all .3s var(--ease);display:flex;flex-direction:column}
.d-card:hover{border-color:var(--border-hi);box-shadow:0 12px 32px var(--shadow)}
.d-card.hide{display:none}
.d-cat{font-size:11px;padding:3px 11px;border-radius:100px;background:var(--accent-g);color:var(--accent);font-weight:600}
.d-title{font-size:17px;font-weight:600;margin:12px 0 6px}
.d-desc{font-size:13.5px;color:var(--tx-2);line-height:1.6;margin-bottom:14px}
.d-live{background:var(--bg-1);padding:20px;border-radius:var(--radius-sm);border:1px solid var(--border);margin-bottom:14px;display:flex;justify-content:center}
.d-links{margin-top:auto}
.p-link{font-size:12px;font-weight:500;color:var(--accent);text-decoration:none}.p-link:hover{text-decoration:underline}
.snip{margin-bottom:14px;border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden}
.snip summary{cursor:pointer;padding:9px 14px;font-size:12.5px;font-weight:600;color:var(--tx-2);background:var(--bg-1);user-select:none;font-family:var(--mono);list-style:none}
.snip summary::-webkit-details-marker{display:none}
.snip summary:hover{color:var(--accent)}.snip-ic{color:var(--accent);font-weight:700;margin-right:4px}
.snip-pre{margin:0;overflow-x:auto}.snip-pre code.hljs{font-family:var(--mono);font-size:12.5px;line-height:1.6;padding:16px 18px;background:#0b1120}
.bs-mini{width:100%;max-width:340px}.bs-mini label{display:flex;justify-content:space-between;font-size:11px;color:var(--tx-3);margin-bottom:4px;font-weight:500;text-transform:uppercase;letter-spacing:.05em}
.bs-mini input[type=range]{width:100%;margin-bottom:12px;accent-color:var(--accent);height:4px}
.bs-result{display:flex;gap:16px;margin-top:8px}.bs-val{text-align:center;flex:1;padding:10px;background:var(--bg-0);border-radius:var(--radius-sm);border:1px solid var(--border)}
.bs-val .num{font-family:var(--mono);font-size:20px;font-weight:500;color:var(--accent)}.bs-val .lbl{font-size:10px;color:var(--tx-3);text-transform:uppercase;letter-spacing:.08em;margin-top:2px}
.mc-mini{width:100%;max-width:340px;text-align:center}.mc-mini canvas{width:100%;height:180px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--bg-0)}
.mc-controls{display:flex;gap:8px;margin-top:10px;justify-content:center}
.mc-btn{padding:6px 16px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12px;font-weight:600;cursor:pointer;transition:all .3s var(--ease);font-family:var(--sans)}
.mc-btn:hover,.mc-btn.active{border-color:var(--accent);color:var(--accent);background:var(--accent-g)}
footer{text-align:center;padding:40px 0;color:var(--tx-3);font-size:12px;border-top:1px solid var(--border)}
@media(max-width:640px){.wrap{padding:0 18px}.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="blob b1"></div>
<nav><div class="nav-i">
  <a class="nav-brand" href="/">R<b>.</b> Denis</a>
  <div class="nav-r">
    <a href="/#experience">Expérience</a>
    <a class="on" href="/demos/">Démos</a>
    <a href="/projects/">Projets</a>
    <a href="/explorer/">Explorer</a>
    <a href="/#contact">Contact</a>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>
<div class="wrap">
<header class="hd">
  <h1>Démos interactives</h1>
  <p>Finance quantitative jouable dans le navigateur — ajuste les paramètres, observe en temps réel. Le code source de chaque démo est ouvert.</p>
</header>
<div class="filters" id="filters">@@FILTERS@@</div>
<div class="grid" id="grid">
@@CARDS@@
</div>
<footer>Robin Denis · <a href="/" style="color:var(--accent);text-decoration:none">Retour à l'accueil</a></footer>
</div>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@@@HLJS@@/build/highlight.min.js"></script>
<script>
  if (window.hljs) hljs.highlightAll();
  // Filtrage par catégorie
  const grid = document.getElementById('grid');
  document.getElementById('filters').addEventListener('click', (ev) => {
    const btn = ev.target.closest('.f-btn'); if (!btn) return;
    document.querySelectorAll('.f-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const f = btn.dataset.filter;
    grid.querySelectorAll('.d-card').forEach(c => {
      c.classList.toggle('hide', f !== 'all' && c.dataset.cat !== f);
    });
  });
  // Widgets (extraits — source unique demos/widgets/*.js)
@@WIDGET_JS@@
  // Init widgets
  if (typeof bsCalc === 'function') bsCalc();
  if (typeof mcRun === 'function') mcRun(50);
  // Thème (partagé avec l'accueil via localStorage) + re-render widgets
  const root = document.documentElement;
  const saved = localStorage.getItem('theme');
  if (saved) root.setAttribute('data-theme', saved);
  document.getElementById('themeBtn').textContent = root.getAttribute('data-theme') === 'light' ? '☀️' : '🌙';
  function tgTheme() {
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('themeBtn').textContent = next === 'light' ? '☀️' : '🌙';
    if (typeof mcRun === 'function' && typeof currentMC !== 'undefined') mcRun(currentMC);
  }
  window.addEventListener('resize', () => { if (typeof mcRun === 'function' && typeof currentMC !== 'undefined') mcRun(currentMC); });
</script>
</body>
</html>
"""


def render_demos_page(profile: dict) -> str:
    demos = profile.get("demos", [])
    cats = collect_categories(demos)
    filter_btns = '<button class="f-btn active" data-filter="all">Toutes</button>' + "".join(
        f'<button class="f-btn" data-filter="{e(c)}">{e(c)}</button>' for c in cats)
    cards = "\n".join(render_card(d) for d in demos)
    widget_js = "\n".join(_read(f"demos/widgets/{d['id']}.js") for d in demos)
    return (TEMPLATE
            .replace("@@FILTERS@@", filter_btns)
            .replace("@@CARDS@@", cards)
            .replace("@@WIDGET_JS@@", widget_js)
            .replace("@@HLJS@@", HLJS))


def build_demos(profile: dict | None = None, write: bool = True) -> str:
    if profile is None:
        profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = render_demos_page(profile)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_demos()
    print(f"[build_demos] OK - {out.count('class=\"d-card')} démos -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
