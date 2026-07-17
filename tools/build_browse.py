#!/usr/bin/env python3
"""build_browse.py — génère explorer/index.html depuis profile.json.

Flux unifié de TOUT le contenu (projets, démos, articles, expériences, formations,
recommandations) en cartes normalisées, filtrables par type + recherche live + bilingue.
Page autonome au design-system de robin-denis.com. LECTURE SEULE de profile.json.

Usage : python tools/build_browse.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "explorer" / "index.html"


class BuildError(Exception):
    pass


# type -> (badge_fr, badge_en, classe couleur)
TYPE_META = {
    "project":        ("Projet", "Project", "b-project"),
    "demo":           ("Démo", "Demo", "b-demo"),
    "article":        ("Article", "Article", "b-article"),
    "experience":     ("Expérience", "Experience", "b-experience"),
    "education":      ("Formation", "Education", "b-education"),
    "recommendation": ("Recommandation", "Reference", "b-recommendation"),
}
# type -> (chip_fr, chip_en)  (libellés pluriels pour les filtres)
CHIP_LABEL = {
    "project":        ("Projets", "Projects"),
    "demo":           ("Démos", "Demos"),
    "article":        ("Articles", "Articles"),
    "experience":     ("Expériences", "Experience"),
    "education":      ("Formations", "Education"),
    "recommendation": ("Recommandations", "References"),
}
TYPE_ORDER = ["project", "demo", "article", "experience", "education", "recommendation"]
DEMO_PIN = "9999-99"   # les démos flottent en tête


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


def _pair(v):
    """str neutre -> (v, v) ; {fr,en} -> (fr, en) ; None -> ('', '')."""
    if isinstance(v, dict):
        return (v.get("fr", ""), v.get("en", ""))
    return (v or "", v or "")


def _sortkey(s) -> str:
    """Token AAAA(-MM) le plus récent d'une chaîne date-ish. '' -> '0000-00'."""
    toks = re.findall(r"\d{4}(?:-\d{2})?", str(s or ""))
    if not toks:
        return "0000-00"
    return max(t if len(t) == 7 else t + "-00" for t in toks)


def _truncate(s, n: int = 160) -> str:
    s = one_line(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _period(start, end, current):
    sy = str(start or "")[:4]
    if current:
        return (f"{sy} – présent", f"{sy} – present")
    ey = str(end or "")[:4]
    base = f"{sy} – {ey}" if ey else sy
    return (base, base)


def _entry(type_, id_, title, desc, date_display, sort, tags, href, soon=False):
    return {
        "type": type_, "id": id_, "title": title, "desc": desc,
        "date_display": date_display, "sort": sort, "tags": list(tags or []),
        "href": href, "soon": soon,
    }


def _norm_project(p):
    tfr, ten = _pair(p.get("name", ""))
    dfr, den = _pair(p.get("summary", ""))
    return _entry("project", p.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)),
                  (p.get("date", ""), p.get("date", "")),
                  _sortkey(p.get("date", "")), p.get("tags", []),
                  f'/projects/#{p.get("id", "")}')


def _norm_demo(d):
    tfr, ten = _pair(d.get("title", ""))
    dfr, den = _pair(d.get("desc", ""))
    cat = d.get("category", "")
    return _entry("demo", d.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)), ("", ""), DEMO_PIN,
                  [cat] if cat else [], f'/demos/#{d.get("id", "")}')


def _abs_url(u):
    """URL de profile.json -> absolue (résout depuis n'importe quelle page, ex. /explorer/).
    Ancre (#...), chemin absolu (/...) et externe (http) préservés tels quels."""
    if not u:
        return ""
    if u.startswith(("http://", "https://", "/", "#")):
        return u
    return "/" + u


def _norm_article(a):
    tfr, ten = _pair(a.get("title", ""))
    dfr, den = _pair(a.get("desc", ""))
    return _entry("article", a.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)),
                  (a.get("date", ""), a.get("date", "")),
                  _sortkey(a.get("date", "")), a.get("tags", []),
                  _abs_url(a.get("url")) or "/#blog", soon=(a.get("status") == "soon"))


def _norm_experience(x):
    company = x.get("company", "")
    tfr, ten = _pair(x.get("title", ""))
    if company:
        tfr, ten = f"{tfr} · {company}", f"{ten} · {company}"
    bullets = x.get("bullets", {}) or {}
    bfr = (bullets.get("fr") or [""])[0]
    ben = (bullets.get("en") or [""])[0]
    typ = x.get("type", "")
    return _entry("experience", x.get("id", ""), (tfr, ten),
                  (one_line(bfr), one_line(ben)),
                  _period(x.get("start"), x.get("end"), x.get("current")),
                  _sortkey(x.get("end") or x.get("start")),
                  [typ] if typ else [], "/#experience")


def _norm_education(ed):
    tfr, ten = _pair(ed.get("title", ""))
    dfr, den = _pair(ed.get("org", ""))
    period = ed.get("period", "")
    return _entry("education", ed.get("id", ""), (tfr, ten),
                  (one_line(dfr), one_line(den)), (period, period),
                  _sortkey(ed.get("end") or ed.get("period")),
                  [ed.get("degree", "")] if ed.get("degree") else [], "/#education")


def _norm_recommendation(r):
    author = r.get("author", "")
    rfr, ren = _pair(r.get("role", ""))
    tfr = f"{author} · {rfr}" if rfr else author
    ten = f"{author} · {ren}" if ren else author
    xfr, xen = _pair(r.get("text", ""))
    date = r.get("date", "")
    return _entry("recommendation", r.get("id", ""), (tfr, ten),
                  (_truncate(xfr), _truncate(xen)), (date, date),
                  _sortkey(date), [], "/#testimonials")


def aggregate(profile):
    entries = []
    entries += [_norm_project(p) for p in profile.get("projects", [])]
    entries += [_norm_demo(d) for d in profile.get("demos", [])]
    entries += [_norm_article(a) for a in profile.get("articles", [])]
    entries += [_norm_experience(x) for x in profile.get("experiences", [])]
    entries += [_norm_education(ed) for ed in profile.get("education", [])]
    entries += [_norm_recommendation(r) for r in profile.get("recommendations", [])]
    entries.sort(key=lambda en: (en["sort"], en["type"], en["title"][0]), reverse=True)
    return entries


# ══════════════════ Rendu ══════════════════

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark" data-lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Explorer — Robin Denis</title>
<meta name="description" content="Parcourez tout le contenu de Robin Denis — projets, démos, articles, expériences, formations et recommandations.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--radius-sm:8px;--ease:cubic-bezier(.4,0,.2,1)}
[data-theme="dark"]{--bg-0:#060a12;--bg-1:#0a1020;--bg-2:#111a2e;--bg-3:#162244;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--accent-g:rgba(59,130,246,.12);--warm:#f59e42;--warm-g:rgba(245,158,66,.10);--green:#22c55e;--green-g:rgba(34,197,94,.10);--violet:#a78bfa;--violet-g:rgba(167,139,250,.10);--glass:rgba(10,16,32,.75);--shadow:rgba(0,0,0,.3)}
[data-theme="light"]{--bg-0:#f5f7fa;--bg-1:#edf0f5;--bg-2:#ffffff;--bg-3:#f0f3f8;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--accent-g:rgba(37,99,235,.08);--warm:#d97706;--warm-g:rgba(217,119,6,.08);--green:#16a34a;--green-g:rgba(22,163,74,.08);--violet:#7c3aed;--violet-g:rgba(124,58,237,.08);--glass:rgba(245,247,250,.8);--shadow:rgba(0,0,0,.06)}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg-0);color:var(--tx-1);line-height:1.7;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden;transition:background .5s var(--ease),color .5s var(--ease)}
.blob{position:fixed;border-radius:50%;filter:blur(140px);pointer-events:none;z-index:0}.b1{width:700px;height:700px;top:-300px;right:-200px;background:var(--accent);opacity:.04}.b2{width:500px;height:500px;bottom:-200px;left:-150px;background:var(--warm);opacity:.03}
nav{position:fixed;top:0;width:100%;z-index:100;padding:12px 0;background:var(--glass);backdrop-filter:blur(24px) saturate(1.4);border-bottom:1px solid var(--border)}
.nav-i{max-width:1000px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between}
.nav-brand{font-family:var(--serif);font-size:19px;color:var(--tx-1);letter-spacing:-.03em;text-decoration:none}.nav-brand b{color:var(--accent)}
.nav-r{display:flex;align-items:center;gap:18px}
.nav-r a{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease)}
.nav-r a:hover{color:var(--tx-1)}.nav-r a.on{color:var(--accent)}
.ctrl-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}
.ctrl-btn:hover{border-color:var(--accent);transform:scale(1.1)}
.ctrl-btn.lang-btn{font-size:12px;font-weight:700;font-family:var(--mono)}
.wrap{max-width:1000px;margin:0 auto;padding:0 32px;position:relative;z-index:1}
header.hd{padding:130px 0 10px;text-align:center}
header.hd h1{font-family:var(--serif);font-size:clamp(38px,6vw,56px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}
header.hd p{color:var(--tx-2);font-size:16px;font-weight:300;max-width:580px;margin:0 auto}
.e-controls{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:30px 0 24px;position:sticky;top:60px;z-index:50;padding:12px 0;background:linear-gradient(var(--bg-0) 78%,transparent)}
.e-search{flex:1;min-width:220px;padding:10px 16px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-1);font-family:var(--sans);font-size:14px;outline:none;transition:border-color .25s var(--ease)}
.e-search:focus{border-color:var(--accent)}
.filters{display:flex;flex-wrap:wrap;gap:8px}
.f-btn{padding:7px 15px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;transition:all .25s var(--ease);font-family:var(--sans)}
.f-btn:hover{border-color:var(--border-hi);color:var(--tx-1)}
.f-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.e-count{font-size:12px;color:var(--tx-3);white-space:nowrap;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;padding-bottom:50px}
.e-card{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:20px;display:flex;flex-direction:column;text-decoration:none;color:inherit;transition:all .3s var(--ease)}
.e-card:hover{border-color:var(--border-hi);transform:translateY(-3px);box-shadow:0 12px 32px var(--shadow)}
.e-card.hide{display:none}
.e-head{display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.e-badge{padding:3px 11px;border-radius:100px;font-size:11px;font-weight:600}
.e-badge.b-project{background:var(--accent-g);color:var(--accent)}
.e-badge.b-demo{background:var(--violet-g);color:var(--violet)}
.e-badge.b-article{background:var(--warm-g);color:var(--warm)}
.e-badge.b-experience{background:var(--green-g);color:var(--green)}
.e-badge.b-education{background:rgba(96,165,250,.12);color:#60a5fa}
.e-badge.b-recommendation{background:var(--bg-3);color:var(--tx-2)}
.e-date{font-size:11px;color:var(--tx-3);letter-spacing:.05em;text-transform:uppercase;margin-left:auto}
.e-soon{font-size:10px;padding:2px 8px;border-radius:100px;background:var(--warm-g);color:var(--warm);font-weight:600;text-transform:uppercase}
.e-title{font-size:16px;font-weight:600;line-height:1.35;margin-bottom:8px}
.e-desc{font-size:13px;color:var(--tx-2);line-height:1.6;margin-bottom:14px;flex:1}
.e-cta{color:var(--accent);font-size:13px;font-weight:600;margin-top:auto}
.e-empty{text-align:center;color:var(--tx-3);padding:50px 0;font-size:14px}
footer{text-align:center;padding:40px 0;color:var(--tx-3);font-size:12px;border-top:1px solid var(--border)}
@media(max-width:640px){.wrap{padding:0 18px}.grid{grid-template-columns:1fr}.nav-r a:not(.on){display:none}header.hd{padding:110px 0 6px}.e-count{margin-left:0}}
</style>
</head>
<body>
<div class="blob b1"></div><div class="blob b2"></div>
<nav><div class="nav-i">
  <a class="nav-brand" href="/">R<b>.</b> Denis</a>
  <div class="nav-r">
    <a href="/#experience" data-fr="Expérience" data-en="Experience">Expérience</a>
    <a href="/demos/" data-fr="Démos" data-en="Demos">Démos</a>
    <a href="/projects/" data-fr="Projets" data-en="Projects">Projets</a>
    <a class="on" href="/explorer/" data-fr="Explorer" data-en="Explore">Explorer</a>
    <a href="/highlights/" data-fr="Highlights" data-en="Highlights">Highlights</a>
    <a href="/academy/" data-fr="Academy" data-en="Academy">Academy</a>
    <button class="ctrl-btn lang-btn" onclick="toggleLang()" id="langBtn" title="Langue">FR</button>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>

<div class="wrap">
<header class="hd">
  <h1 data-fr="Explorer" data-en="Explore">Explorer</h1>
  <p data-fr="Tout le contenu en un seul endroit — projets, démos, articles, expériences, formations et recommandations. Filtrez, cherchez, plongez."
     data-en="All the content in one place — projects, demos, articles, experiences, education and references. Filter, search, dive in.">Tout le contenu en un seul endroit — projets, démos, articles, expériences, formations et recommandations. Filtrez, cherchez, plongez.</p>
</header>

<div class="e-controls">
  <input id="q" class="e-search" type="search" data-fr-ph="Rechercher…" data-en-ph="Search…" placeholder="Rechercher…" aria-label="Rechercher">
  <div class="filters" id="filters">@@CHIPS@@</div>
  <span class="e-count" id="count"></span>
</div>
<div class="e-empty" id="empty" hidden data-fr="Aucun résultat." data-en="No results.">Aucun résultat.</div>

<div class="grid" id="grid">
@@CARDS@@
</div>

<footer>Robin Denis · @@UPDATED@@ · <a href="/" style="color:var(--accent);text-decoration:none" data-fr="Retour à l'accueil" data-en="Back home">Retour à l'accueil</a></footer>
</div>

<script>
  const grid = document.getElementById('grid');
  const cards = Array.from(grid.querySelectorAll('.e-card'));
  const q = document.getElementById('q');
  const countEl = document.getElementById('count');
  const emptyEl = document.getElementById('empty');
  const root = document.documentElement;
  let curType = 'all', curQ = '';

  function curLang(){ return root.getAttribute('data-lang') || 'fr'; }

  function refresh(){
    let n = 0;
    for (const c of cards){
      const okT = curType === 'all' || c.dataset.type === curType;
      const okQ = !curQ || c.dataset.search.includes(curQ);
      const show = okT && okQ;
      c.classList.toggle('hide', !show);
      if (show) n++;
    }
    const fr = curLang() === 'fr';
    const word = fr ? (n > 1 ? ' résultats' : ' résultat') : (n > 1 ? ' results' : ' result');
    countEl.textContent = n + word;
    emptyEl.hidden = n > 0;
  }

  document.getElementById('filters').addEventListener('click', function(ev){
    const btn = ev.target.closest('.f-btn'); if (!btn) return;
    document.querySelectorAll('.f-btn').forEach(function(b){ b.classList.remove('active'); });
    btn.classList.add('active');
    curType = btn.dataset.filter;
    refresh();
  });
  q.addEventListener('input', function(){ curQ = q.value.toLowerCase().trim(); refresh(); });

  function applyBrowseLang(lang){
    document.querySelectorAll('[data-fr][data-en]').forEach(function(el){
      el.textContent = lang === 'fr' ? el.dataset.fr : el.dataset.en;
    });
    const ph = q.getAttribute(lang === 'fr' ? 'data-fr-ph' : 'data-en-ph');
    if (ph) q.setAttribute('placeholder', ph);
    root.setAttribute('data-lang', lang);
    root.setAttribute('lang', lang);
    document.getElementById('langBtn').textContent = lang === 'fr' ? 'FR' : 'EN';
    refresh();
  }
  function toggleLang(){
    const next = curLang() === 'fr' ? 'en' : 'fr';
    localStorage.setItem('lang', next);
    applyBrowseLang(next);
  }
  function tgTheme(){
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('themeBtn').textContent = next === 'light' ? '☀️' : '🌙';
  }

  (function(){
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme){ root.setAttribute('data-theme', savedTheme);
      document.getElementById('themeBtn').textContent = savedTheme === 'light' ? '☀️' : '🌙'; }
    const savedLang = localStorage.getItem('lang') || 'fr';
    applyBrowseLang(savedLang);
  })();
</script>
</body>
</html>
"""


def _search_index(en) -> str:
    tfr, ten = en["title"]
    dfr, den = en["desc"]
    bfr, ben, _ = TYPE_META[en["type"]]
    parts = [tfr, ten, dfr, den, bfr, ben] + list(en["tags"])
    return one_line(" ".join(parts)).lower()


def render_card(en) -> str:
    tfr, ten = en["title"]
    dfr, den = en["desc"]
    dtfr, dten = en["date_display"]
    bfr, ben, cls = TYPE_META[en["type"]]
    search = e(_search_index(en))
    soon = ('<span class="e-soon" data-fr="à venir" data-en="soon">à venir</span>'
            if en["soon"] else "")
    date = (f'<span class="e-date" data-fr="{e(dtfr)}" data-en="{e(dten)}">{e(dtfr)}</span>'
            if (dtfr or dten) else "")
    return (
        f'<a class="e-card" href="{e(en["href"])}" data-type="{e(en["type"])}" data-search="{search}">'
        f'<div class="e-head">'
        f'<span class="e-badge {cls}" data-fr="{e(bfr)}" data-en="{e(ben)}">{e(bfr)}</span>'
        f'{soon}{date}</div>'
        f'<h3 class="e-title" data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</h3>'
        f'<p class="e-desc" data-fr="{e(dfr)}" data-en="{e(den)}">{e(dfr)}</p>'
        f'<span class="e-cta" data-fr="Voir →" data-en="View →">Voir →</span>'
        f'</a>'
    )


def _chips() -> str:
    chips = ['<button class="f-btn active" data-filter="all" data-fr="Tous" data-en="All">Tous</button>']
    for t in TYPE_ORDER:
        cfr, cen = CHIP_LABEL[t]
        chips.append(
            f'<button class="f-btn" data-filter="{e(t)}" data-fr="{e(cfr)}" data-en="{e(cen)}">{e(cfr)}</button>'
        )
    return "".join(chips)


def render_browse_page(profile) -> str:
    cards = "\n".join(render_card(en) for en in aggregate(profile))
    updated = profile.get("projects_meta", {}).get("updated", "")
    return (PAGE_TEMPLATE
            .replace("@@CHIPS@@", _chips())
            .replace("@@CARDS@@", cards)
            .replace("@@UPDATED@@", e(updated)))


def build_browse(profile=None, write: bool = True) -> str:
    if profile is None:
        profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = render_browse_page(profile)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_browse()
    n = out.count('class="e-card"')
    print(f"[build_browse] OK - {n} entries -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
