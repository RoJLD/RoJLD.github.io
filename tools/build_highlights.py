#!/usr/bin/env python3
"""build_highlights.py — génère highlights/index.html depuis profile.json.

Vue pitch pondérée par lentille (?lens=<domaine>). Scoring 100% Python émis en
attributs data-lens-<id>/data-gen/data-idx ; le JS lit et trie, ne recalcule rien
(anti-parité Σ-CLIENT-SERVER-RENDER-PARITY).
"""
from __future__ import annotations

import collections
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "highlights" / "index.html"


class BuildError(Exception):
    pass


CAPS = {"skills": 10, "experiences": 3, "projects": 6, "demos": 2, "articles": 2}
REL_AXES = {"quant", "risk", "dev"}   # axes de experience.relevance (hors general)
LENS_MIN = 2                          # seuil domaine -> lentille (exp+projets)


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


def _pair(v):
    if isinstance(v, dict):
        return (v.get("fr", ""), v.get("en", ""))
    return (v or "", v or "")


def _truncate(s, n: int = 150) -> str:
    s = one_line(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _period(start, end, current):
    sy = str(start or "")[:4]
    if current:
        return (f"{sy} – présent", f"{sy} – present")
    ey = str(end or "")[:4]
    base = f"{sy} – {ey}" if ey else sy
    return (base, base)


def _abs_url(u):
    if not u:
        return ""
    if u.startswith(("http://", "https://", "/", "#")):
        return u
    return "/" + u


# ── Lentilles data-driven ──
def lens_domains(profile):
    t = collections.Counter()
    for x in profile.get("experiences", []):
        for d in x.get("domains", []) or []:
            t[d] += 1
    for p in profile.get("projects", []):
        for d in p.get("domains", []) or []:
            t[d] += 1
    order = [d.get("id") for d in profile.get("domains", [])]
    return [d for d in order if t.get(d, 0) >= LENS_MIN]


def domain_label(profile, did):
    for d in profile.get("domains", []):
        if d.get("id") == did:
            return _pair(d.get("label", did))
    return (did, did)


def flat_skills(profile):
    out = []
    for cat, lst in (profile.get("skills") or {}).items():
        if cat == "radar_scores":
            continue
        for s in (lst or []):
            out.append(s)
    return out


def demo_domains(profile, demo):
    proj = demo.get("project")
    for p in profile.get("projects", []):
        if p.get("id") == proj:
            return p.get("domains", []) or []
    return []


# ── Scores par lentille (signature uniforme (profile, item, lens)) ──
def score_skill(profile, s, lens):
    return s.get("weight", 0) if lens in (s.get("contexts") or []) else None


def score_experience(profile, x, lens):
    rel = x.get("relevance") or {}
    in_dom = lens in (x.get("domains") or [])
    rel_l = rel.get(lens, 0) if lens in REL_AXES else 0
    if not in_dom and rel_l <= 0:
        return None
    return 3 * in_dom + rel_l + 0.5 * rel.get("general", 0)


def score_project(profile, p, lens):
    if lens not in (p.get("domains") or []):
        return None
    return 3 + 2 * (1 if p.get("featured") else 0)


def score_demo(profile, d, lens):
    return 3 if lens in demo_domains(profile, d) else None


def score_article(profile, a, lens):
    return 3 if lens in (a.get("domains") or []) else None


# ── Scores vue générale ──
def gen_skill(s):
    return s.get("weight", 0)


def gen_experience(x):
    return (x.get("relevance") or {}).get("general", 0.5)


def gen_project(p):
    return 1 + 2 * (1 if p.get("featured") else 0)


def gen_demo(d):
    return 1.0


def gen_article(a):
    return 1.0


def _fmt(n):
    return f"{n:g}"


def lens_attrs(profile, lenses, item, scorer):
    """-> ' data-lens-quant="3.6" ...' pour les lentilles où l'item est inclus (score>0)."""
    parts = []
    for L in lenses:
        sc = scorer(profile, item, L)
        if sc is not None and sc > 0:
            parts.append(f'data-lens-{L}="{_fmt(sc)}"')
    return (" " + " ".join(parts)) if parts else ""


# ══════════════════ Page ══════════════════

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark" data-lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Highlights — Robin Denis</title>
<meta name="description" content="Le profil de Robin Denis, orientable par domaine — quant, data, dev, IA… Un lien taillé pour votre angle.">
<meta property="og:title" content="Robin Denis — Highlights">
<meta property="og:description" content="Profil orientable par domaine : quant, data, dev, IA, DeFi…">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--ease:cubic-bezier(.4,0,.2,1)}
[data-theme="dark"]{--bg-0:#060a12;--bg-1:#0a1020;--bg-2:#111a2e;--bg-3:#162244;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--accent-g:rgba(59,130,246,.12);--warm:#f59e42;--warm-g:rgba(245,158,66,.10);--green:#22c55e;--green-g:rgba(34,197,94,.10);--violet:#a78bfa;--glass:rgba(10,16,32,.75);--shadow:rgba(0,0,0,.3)}
[data-theme="light"]{--bg-0:#f5f7fa;--bg-1:#edf0f5;--bg-2:#ffffff;--bg-3:#f0f3f8;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--accent-g:rgba(37,99,235,.08);--warm:#d97706;--warm-g:rgba(217,119,6,.08);--green:#16a34a;--green-g:rgba(22,163,74,.08);--violet:#7c3aed;--glass:rgba(245,247,250,.8);--shadow:rgba(0,0,0,.06)}
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
header.hd{padding:130px 0 6px;text-align:center}
header.hd h1{font-family:var(--serif);font-size:clamp(38px,6vw,56px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}
header.hd p{color:var(--tx-2);font-size:16px;font-weight:300;max-width:580px;margin:0 auto}
.h-banner{text-align:center;margin:14px auto 0;max-width:640px;color:var(--accent);font-weight:600;font-size:14px}
.h-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:26px 0 8px;position:sticky;top:60px;z-index:50;padding:12px 0;background:linear-gradient(var(--bg-0) 80%,transparent)}
.h-chip{padding:7px 15px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;transition:all .25s var(--ease);font-family:var(--sans)}
.h-chip:hover{border-color:var(--border-hi);color:var(--tx-1)}
.h-chip.active{background:var(--accent);border-color:var(--accent);color:#fff}
.h-copy{margin-left:auto;padding:7px 15px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;font-family:var(--sans);transition:all .25s var(--ease)}
.h-copy:hover{border-color:var(--accent);color:var(--tx-1)}
.h-sec{margin:26px 0}
.h-st{font-family:var(--serif);font-size:24px;font-weight:400;margin-bottom:14px;color:var(--tx-1)}
.h-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.h-sec[data-sec="skills"] .h-list{display:flex;flex-wrap:wrap;gap:8px}
.h-skill{padding:7px 14px;border-radius:100px;background:var(--bg-3);color:var(--tx-1);font-size:13px;font-weight:600;font-family:var(--mono)}
.h-card{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:18px;text-decoration:none;color:inherit;transition:all .3s var(--ease);display:block}
.h-card:hover{border-color:var(--border-hi);transform:translateY(-3px);box-shadow:0 12px 32px var(--shadow)}
.h-h{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}
.h-card h3{font-size:15.5px;font-weight:600;line-height:1.35;margin-bottom:6px}
.h-date{font-size:11px;color:var(--tx-3);letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}
.h-card p{font-size:13px;color:var(--tx-2);line-height:1.55}
footer{text-align:center;padding:40px 0;color:var(--tx-3);font-size:12px;border-top:1px solid var(--border);margin-top:20px}
@media(max-width:640px){.wrap{padding:0 18px}.h-list{grid-template-columns:1fr}.nav-r a:not(.on){display:none}header.hd{padding:110px 0 6px}.h-copy{margin-left:0}}
</style>
</head>
<body>
<div class="blob b1"></div><div class="blob b2"></div>
<nav><div class="nav-i">
  <a class="nav-brand" href="/">R<b>.</b> Denis</a>
  <div class="nav-r">
    <a href="/#experience" data-fr="Expérience" data-en="Experience">Expérience</a>
    <a href="/projects/" data-fr="Projets" data-en="Projects">Projets</a>
    <a href="/explorer/" data-fr="Explorer" data-en="Explore">Explorer</a>
    <a class="on" href="/highlights/" data-fr="Highlights" data-en="Highlights">Highlights</a>
    <button class="ctrl-btn lang-btn" onclick="toggleLang()" id="langBtn" title="Langue">FR</button>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>

<div class="wrap">
<header class="hd">
  <h1>Highlights</h1>
  <p data-fr="Mon profil, orientable par domaine. Choisissez une lentille — le contenu se réordonne pour la mettre en avant."
     data-en="My profile, focusable by domain. Pick a lens — the content reorders to foreground it.">Mon profil, orientable par domaine. Choisissez une lentille — le contenu se réordonne pour la mettre en avant.</p>
  <div class="h-banner" id="banner" hidden></div>
</header>

<div class="h-controls">
  <div class="h-chips" id="lenses" style="display:flex;flex-wrap:wrap;gap:8px">@@CHIPS@@</div>
  <button class="h-copy" id="copy" data-fr="Copier le lien" data-en="Copy link">Copier le lien</button>
</div>

@@SECTIONS@@

<footer>Robin Denis · @@UPDATED@@ · <a href="/" style="color:var(--accent);text-decoration:none" data-fr="Retour à l'accueil" data-en="Back home">Retour à l'accueil</a></footer>
</div>

<script>
  const CAPS = @@CAPS@@;
  const LENS_LABELS = @@LABELS@@;
  const LENS_IDS = @@IDS@@;
  const root = document.documentElement;
  let curLens = '';

  function curLang(){ return root.getAttribute('data-lang') || 'fr'; }
  function camel(id){ return 'lens' + id.replace(/(^|-)([a-z])/g, function(m, p1, c){ return c.toUpperCase(); }); }

  function applyLens(lens){
    curLens = lens;
    document.querySelectorAll('.h-chip').forEach(function(c){
      c.classList.toggle('active', c.dataset.lens === lens);
    });
    document.querySelectorAll('.h-sec').forEach(function(sec){
      const list = sec.querySelector('.h-list');
      const cap = CAPS[sec.dataset.sec] || 6;
      let items = Array.prototype.slice.call(list.children);
      if (lens){
        const key = camel(lens);
        items = items.filter(function(it){ return it.dataset[key] !== undefined; })
                     .sort(function(a,b){ return parseFloat(b.dataset[key]) - parseFloat(a.dataset[key]); });
      } else {
        items = items.sort(function(a,b){ return parseInt(a.dataset.idx) - parseInt(b.dataset.idx); });
      }
      Array.prototype.slice.call(list.children).forEach(function(it){ it.style.display = 'none'; });
      items.slice(0, cap).forEach(function(it){ it.style.display = ''; list.appendChild(it); });
      sec.style.display = items.length ? '' : 'none';
    });
    updateBanner();
  }

  function updateBanner(){
    const b = document.getElementById('banner');
    if (curLens && LENS_LABELS[curLens]){
      const lab = LENS_LABELS[curLens][curLang()];
      b.textContent = (curLang() === 'fr' ? 'Profil orienté ' : 'Profile focused on ') + lab;
      b.hidden = false;
    } else { b.hidden = true; }
  }

  document.getElementById('lenses').addEventListener('click', function(ev){
    const c = ev.target.closest('.h-chip'); if (!c) return;
    const lens = c.dataset.lens;
    applyLens(lens);
    history.replaceState(null, '', lens ? ('?lens=' + lens) : location.pathname);
  });

  document.getElementById('copy').addEventListener('click', function(){
    const b = document.getElementById('copy');
    navigator.clipboard.writeText(location.href).then(function(){
      b.textContent = curLang() === 'fr' ? 'Copié ✓' : 'Copied ✓';
      setTimeout(function(){ b.textContent = curLang() === 'fr' ? b.dataset.fr : b.dataset.en; }, 1400);
    });
  });

  function applyBrowseLang(lang){
    document.querySelectorAll('[data-fr][data-en]').forEach(function(el){
      el.textContent = lang === 'fr' ? el.dataset.fr : el.dataset.en;
    });
    root.setAttribute('data-lang', lang); root.setAttribute('lang', lang);
    document.getElementById('langBtn').textContent = lang === 'fr' ? 'FR' : 'EN';
    updateBanner();
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
    if (savedLang !== 'fr') applyBrowseLang(savedLang);
    const params = new URLSearchParams(location.search);
    const lens = params.get('lens') || '';
    applyLens(LENS_IDS.indexOf(lens) >= 0 ? lens : '');
  })();
</script>
</body>
</html>
"""


# ══════════════════ Rendu ══════════════════

def render_skill(profile, lenses, s, idx):
    la = lens_attrs(profile, lenses, s, score_skill)
    return (f'<span class="h-skill" data-idx="{idx}" data-gen="{_fmt(gen_skill(s))}"{la}>'
            f'{e(s.get("name", ""))}</span>')


def render_experience(profile, lenses, x, idx):
    tfr, ten = _pair(x.get("title", ""))
    company = x.get("company", "")
    if company:
        tfr, ten = f"{tfr} · {company}", f"{ten} · {company}"
    bullets = x.get("bullets") or {}
    bfr = (bullets.get("fr") or [""])[0]
    ben = (bullets.get("en") or [""])[0]
    pfr, pen = _period(x.get("start"), x.get("end"), x.get("current"))
    la = lens_attrs(profile, lenses, x, score_experience)
    return (
        f'<a class="h-card" href="/#experience" data-idx="{idx}" data-gen="{_fmt(gen_experience(x))}"{la}>'
        f'<div class="h-h"><h3 data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</h3>'
        f'<span class="h-date" data-fr="{e(pfr)}" data-en="{e(pen)}">{e(pfr)}</span></div>'
        f'<p data-fr="{e(one_line(bfr))}" data-en="{e(one_line(ben))}">{e(one_line(bfr))}</p></a>'
    )


def render_project(profile, lenses, p, idx):
    nfr, nen = _pair(p.get("name", ""))
    sfr, sen = _pair(p.get("summary", ""))
    la = lens_attrs(profile, lenses, p, score_project)
    return (
        f'<a class="h-card" href="/projects/#{e(p.get("id",""))}" data-idx="{idx}" '
        f'data-gen="{_fmt(gen_project(p))}"{la}>'
        f'<h3 data-fr="{e(nfr)}" data-en="{e(nen)}">{e(nfr)}</h3>'
        f'<p data-fr="{e(one_line(sfr))}" data-en="{e(one_line(sen))}">{e(one_line(sfr))}</p></a>'
    )


def render_demo(profile, lenses, d, idx):
    tfr, ten = _pair(d.get("title", ""))
    dfr, den = _pair(d.get("desc", ""))
    la = lens_attrs(profile, lenses, d, score_demo)
    return (
        f'<a class="h-card" href="/demos/#{e(d.get("id",""))}" data-idx="{idx}" '
        f'data-gen="{_fmt(gen_demo(d))}"{la}>'
        f'<h3 data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</h3>'
        f'<p data-fr="{e(one_line(dfr))}" data-en="{e(one_line(den))}">{e(one_line(dfr))}</p></a>'
    )


def render_article(profile, lenses, a, idx):
    tfr, ten = _pair(a.get("title", ""))
    dfr, den = _pair(a.get("desc", ""))
    la = lens_attrs(profile, lenses, a, score_article)
    href = _abs_url(a.get("url")) or "/#blog"
    return (
        f'<a class="h-card" href="{e(href)}" data-idx="{idx}" data-gen="{_fmt(gen_article(a))}"{la}>'
        f'<h3 data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</h3>'
        f'<p data-fr="{e(one_line(dfr))}" data-en="{e(one_line(den))}">{e(one_line(dfr))}</p></a>'
    )


def _section_html(sec_key, title_fr, title_en, cards_html):
    return (
        f'<section class="h-sec" data-sec="{sec_key}">'
        f'<h2 class="h-st" data-fr="{e(title_fr)}" data-en="{e(title_en)}">{e(title_fr)}</h2>'
        f'<div class="h-list">{cards_html}</div></section>'
    )


def _chips(profile, lenses):
    chips = ['<button class="h-chip active" data-lens="" data-fr="Général" data-en="General">Général</button>']
    for L in lenses:
        lfr, len_ = domain_label(profile, L)
        chips.append(
            f'<button class="h-chip" data-lens="{e(L)}" data-fr="{e(lfr)}" data-en="{e(len_)}">{e(lfr)}</button>'
        )
    return "".join(chips)


def render_highlights_page(profile):
    lenses = lens_domains(profile)

    def sec(sec_key, tfr, ten, items, gen_fn, renderer):
        ordered = sorted(items, key=gen_fn, reverse=True)
        cards = "\n".join(renderer(profile, lenses, it, i) for i, it in enumerate(ordered))
        return _section_html(sec_key, tfr, ten, "\n" + cards + "\n")

    sections = (
        sec("skills", "Compétences clés", "Key skills", flat_skills(profile), gen_skill, render_skill)
        + sec("experiences", "Expériences", "Experience", profile.get("experiences", []), gen_experience, render_experience)
        + sec("projects", "Projets", "Projects", profile.get("projects", []), gen_project, render_project)
        + sec("demos", "Démos", "Demos", profile.get("demos", []), gen_demo, render_demo)
        + sec("articles", "Articles", "Articles", profile.get("articles", []), gen_article, render_article)
    )
    labels = {L: {"fr": domain_label(profile, L)[0], "en": domain_label(profile, L)[1]} for L in lenses}
    return (PAGE_TEMPLATE
            .replace("@@CHIPS@@", _chips(profile, lenses))
            .replace("@@SECTIONS@@", sections)
            .replace("@@CAPS@@", json.dumps(CAPS))
            .replace("@@LABELS@@", json.dumps(labels, ensure_ascii=True))
            .replace("@@IDS@@", json.dumps(lenses))
            .replace("@@UPDATED@@", e(profile.get("projects_meta", {}).get("updated", ""))))


def build_highlights(profile=None, write: bool = True) -> str:
    if profile is None:
        profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = render_highlights_page(profile)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_highlights()
    n = out.count('class="h-card"')
    print(f"[build_highlights] OK - {n} cartes -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
