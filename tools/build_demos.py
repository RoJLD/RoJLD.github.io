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

import nav

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
    gist = d.get("gist")
    gist_link = (f'<a class="p-link" href="{e(gist)}" target="_blank" rel="noopener">Gist ↗</a>'
                 if gist else "")
    return f"""<article id="{e(did)}" class="d-card" data-cat="{e(d['category'])}">
  <div class="d-head"><span class="d-cat">{e(d['category'])}</span></div>
  <h3 class="d-title">{e(d['title'])}</h3>
  <p class="d-desc">{e(_desc_fr(d))}</p>
  <div class="d-live">{widget}</div>
  <details class="snip"><summary><span class="snip-ic">&lt;/&gt;</span> Code source</summary>
  <pre class="snip-pre"><code class="language-python">{code}</code></pre></details>
  <div class="d-links"><a class="p-link" href="/projects/#{e(proj)}">Projet complet →</a>{gist_link}</div>
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
.nav-i{max-width:none;margin:0;padding:0 24px 0 max(24px,calc(50% - 468px));display:flex;align-items:center;position:relative}
.nav-brand{font-family:var(--serif);font-size:19px;color:var(--tx-1);letter-spacing:-.03em;text-decoration:none;white-space:nowrap;flex-shrink:0;margin-right:28px}.nav-brand b{color:var(--accent)}
.nav-r{display:flex;align-items:center;gap:20px;flex:1 1 auto;min-width:0;padding-block:6px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;-ms-overflow-style:none;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;scroll-padding-inline:8px}
.nav-r::-webkit-scrollbar{display:none}
.nav-r>a{flex-shrink:0}
.nav-r a{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease);min-height:24px;padding-block:3px}
.nav-r a:hover{color:var(--tx-1)}.nav-r a.on{color:var(--accent)}
.ctrl-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}
.ctrl-btn:hover{border-color:var(--accent);transform:scale(1.1)}
.nav-btns{display:flex;align-items:center;gap:8px;flex-shrink:0;margin-left:16px;position:relative}
.nav-btns::before{content:'';position:absolute;top:-12px;bottom:-12px;left:-40px;width:40px;pointer-events:none;background:linear-gradient(to right,rgba(0,0,0,0),var(--glass))}
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
@media(max-width:1620px){.nav-r{gap:14px}.nav-r a{font-size:11px;letter-spacing:.02em;padding-block:4px}.nav-brand{font-size:18px;margin-right:20px}.nav-i{padding-left:max(20px,calc(50% - 468px));padding-right:20px}.nav-btns{margin-left:12px}.ctrl-btn{width:34px;height:34px}}
@media(max-width:1150px){.nav-r{gap:11px}.nav-r a{font-size:10.5px;letter-spacing:.01em;padding-block:4px}.nav-brand{font-size:17px;margin-right:14px}.nav-i{padding-left:max(14px,calc(50% - 468px));padding-right:14px}.nav-btns{margin-left:8px}.ctrl-btn{width:32px;height:32px}}
@media(max-width:1023px){/* AUCUN `order:` ici, et c'est la raison d'etre de ce bloc. Il reordonnait les boutons AVANT la rangee visuellement (order 2 contre 3) alors que le DOM les garde APRES, et la tabulation suit le DOM. Mesure du 2026-10-19 — tabulation reelle (Tab en boucle, Chromium 145), 6 pages x 13 largeurs : 36 inversions ordre-visuel/ordre-de-tabulation, TOUTES sous 1024 px, zero au-dessus. A 390 px le focus descendait jusqu'a « Contact » (y=115) puis remontait de 105 px sur « FR » (y=10). WCAG 2.4.3 Focus Order, niveau A, et 1.3.2. L'ordre visuel est donc celui du DOM : marque, rangee, boutons — trois rangees empilees sous le seuil (barre 155 -> 180 px a 390 px ; elle est `position:static`, donc elle part au defilement). Deplacer `.nav-btns` AVANT `.nav-r` dans le balisage ne corrigerait pas le defaut, il le deplacerait au-dessus du seuil : 0 inversion mesuree a >=1024 px aujourd'hui, 7 largeurs x 6 pages apres. */nav{position:static;padding:10px 0}.nav-i{flex-wrap:wrap;row-gap:6px;padding:0 18px}.nav-brand{font-size:19px}.nav-btns{margin-left:auto}.nav-btns::before{display:none}.ctrl-btn{width:38px;height:38px}.nav-r{flex:1 1 100%;flex-wrap:wrap;row-gap:2px;column-gap:14px;overflow:visible;padding-block:0}.nav-r a{font-size:11px;letter-spacing:.02em;padding-block:5px}header.hd{padding:22px 0 20px}.filters{top:0}}
</style>
</head>
<body>
<div class="blob b1"></div>
@@NAV@@
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
  // AUCUNE bascule de langue sur cette page, et c'est un RETRAIT assume, pas un
  // oubli : cf. `tools/nav.py` (_PAGES["demos"]["bouton_langue"] = False) et la
  // garde `test_la_langue_annoncee_est_celle_du_contenu`. Mesure du 2026-10-19,
  // parseur HTML sur l'artefact publie : 33 chaines de texte visible hors nav
  // (28 distinctes), dont 0 traduisible — un bouton EN aurait annonce une langue
  // qu'aucune de ces 33 chaines ne livre. Le bouton revient avec la traduction.
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
            .replace("@@NAV@@", nav.render_nav("demos"))
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
