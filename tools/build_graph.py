#!/usr/bin/env python3
"""build_graph.py — génère graph/index.html : le profil comme réseau interactif.

Topologie réutilisée de profile_pipeline.build_profile_graph (source unique, SP6) ;
layout force-directed déterministe pur-Python ; labels bilingues re-dérivés de
profile.json ; SVG pré-rendu self-contained + données embarquées.
"""
from __future__ import annotations

import html
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "graph" / "index.html"


class BuildError(Exception):
    pass


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark" data-lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Graphe du profil — Robin Denis</title>
<meta name="description" content="Le profil de Robin Denis comme réseau : domaines, expériences, projets, compétences et leurs relations.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🕸️</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--ease:cubic-bezier(.4,0,.2,1)}
[data-theme="dark"]{--bg-0:#060a12;--bg-1:#0a1020;--bg-2:#111a2e;--bg-3:#162244;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--glass:rgba(10,16,32,.75);--shadow:rgba(0,0,0,.3)}
[data-theme="light"]{--bg-0:#f5f7fa;--bg-1:#edf0f5;--bg-2:#ffffff;--bg-3:#f0f3f8;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--glass:rgba(245,247,250,.8);--shadow:rgba(0,0,0,.06)}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:var(--bg-0);color:var(--tx-1);line-height:1.6;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden;transition:background .5s var(--ease),color .5s var(--ease)}
nav{position:fixed;top:0;width:100%;z-index:100;padding:12px 0;background:var(--glass);backdrop-filter:blur(24px) saturate(1.4);border-bottom:1px solid var(--border)}
.nav-i{max-width:1200px;margin:0 auto;padding:0 32px;display:flex;align-items:center;justify-content:space-between}
.nav-brand{font-family:var(--serif);font-size:19px;color:var(--tx-1);text-decoration:none}.nav-brand b{color:var(--accent)}
.nav-r{display:flex;align-items:center;gap:18px}
.nav-r a{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease)}
.nav-r a:hover{color:var(--tx-1)}.nav-r a.on{color:var(--accent)}
.ctrl-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}
.ctrl-btn:hover{border-color:var(--accent);transform:scale(1.1)}.ctrl-btn.lang-btn{font-size:12px;font-weight:700;font-family:var(--mono)}
.wrap{max-width:1200px;margin:0 auto;padding:96px 24px 24px;position:relative}
header.hd{text-align:center;margin-bottom:16px}
header.hd h1{font-family:var(--serif);font-size:clamp(34px,5vw,48px);font-weight:400;letter-spacing:-.03em}
header.hd p{color:var(--tx-2);font-size:15px;max-width:600px;margin:6px auto 0}
.g-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:16px 0}
.g-chip{padding:6px 13px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12px;font-weight:600;cursor:pointer;transition:all .25s var(--ease)}
.g-chip:hover{border-color:var(--border-hi);color:var(--tx-1)}.g-chip.off{opacity:.35}
.g-search{padding:7px 14px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-1);font-size:13px;font-family:var(--sans);outline:none;min-width:180px}
.g-search:focus{border-color:var(--accent)}
.g-cv{margin-left:auto;display:flex;align-items:center;gap:10px}
.g-cvtoggle{padding:7px 14px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-2);font-size:12.5px;font-weight:600;cursor:pointer;transition:all .25s var(--ease)}
.g-cvtoggle.active{background:var(--accent);border-color:var(--accent);color:#fff}
.g-compose{padding:7px 15px;border-radius:100px;border:1px solid var(--accent);background:var(--accent);color:#fff;font-size:12.5px;font-weight:700;cursor:pointer;display:none}
.g-compose:disabled{opacity:.4;cursor:not-allowed}
.g-stage{position:relative;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-1);overflow:hidden;height:70vh;min-height:460px}
.g-zoom{position:absolute;bottom:12px;right:12px;display:flex;flex-direction:column;gap:6px;z-index:5}
.g-zoom button{width:34px;height:34px;border-radius:9px;border:1px solid var(--border-hi);background:var(--bg-2);color:var(--tx-1);font-size:20px;line-height:1;cursor:pointer;display:grid;place-items:center}
.g-zoom button:hover{border-color:var(--accent)}
#graph{width:100%;height:100%;display:block;cursor:grab;touch-action:none}
#graph.panning{cursor:grabbing}
.gedge{stroke:var(--border-hi);stroke-width:1;opacity:.5;transition:opacity .2s,stroke .2s}
.gedge.hl{stroke:var(--accent);opacity:.9;stroke-width:1.5}
.gnode{cursor:pointer}
.gnode circle{stroke:var(--bg-1);stroke-width:1.5;transition:opacity .2s}
.gnode text.glabel{font-family:var(--sans);font-size:9px;fill:var(--tx-2);pointer-events:none;transition:opacity .2s}
.gnode.dim{opacity:.15}
.gnode.pick circle{stroke:var(--accent);stroke-width:3}
.g-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px;font-size:11.5px;color:var(--tx-3)}
.gleg{display:flex;align-items:center;gap:5px}.gleg i{width:10px;height:10px;border-radius:50%;display:inline-block}
.g-panel{position:absolute;top:12px;right:12px;width:260px;max-width:calc(100% - 24px);background:var(--bg-2);border:1px solid var(--border-hi);border-radius:var(--radius);padding:16px;box-shadow:0 12px 32px var(--shadow);display:none}
.g-panel.show{display:block}
.g-panel .gp-type{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--tx-3);font-weight:600}
.g-panel .gp-title{font-family:var(--serif);font-size:20px;margin:2px 0 8px}
.g-panel .gp-conn{font-size:12.5px;color:var(--tx-2);line-height:1.7}
.g-panel a.gp-go{display:inline-block;margin-top:12px;padding:7px 14px;border-radius:100px;background:var(--accent);color:#fff;text-decoration:none;font-size:12.5px;font-weight:600}
.g-panel .gp-close{position:absolute;top:10px;right:12px;cursor:pointer;color:var(--tx-3);font-size:18px;line-height:1}
footer{text-align:center;padding:32px 0 8px;color:var(--tx-3);font-size:12px}
@media(max-width:640px){.wrap{padding:88px 14px 18px}.nav-r a:not(.on){display:none}.g-cv{margin-left:0;width:100%}.g-panel{top:auto;bottom:12px;right:12px;left:12px;width:auto}.g-stage{height:62vh}}
</style>
</head>
<body>
<nav><div class="nav-i">
  <a class="nav-brand" href="/">R<b>.</b> Denis</a>
  <div class="nav-r">
    <a href="/#experience" data-fr="Expérience" data-en="Experience">Expérience</a>
    <a href="/projects/" data-fr="Projets" data-en="Projects">Projets</a>
    <a href="/explorer/" data-fr="Explorer" data-en="Explore">Explorer</a>
    <a href="/highlights/" data-fr="Highlights" data-en="Highlights">Highlights</a>
    <a href="/academy/" data-fr="Academy" data-en="Academy">Academy</a>
    <a class="on" href="/graph/" data-fr="Graphe" data-en="Graph">Graphe</a>
    <button class="ctrl-btn lang-btn" onclick="toggleLang()" id="langBtn" title="Langue">FR</button>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>

<div class="wrap">
<header class="hd">
  <h1 data-fr="Graphe du profil" data-en="Profile graph">Graphe du profil</h1>
  <p data-fr="Le profil comme réseau : domaines, expériences, projets, compétences et leurs liens. Survolez, cliquez, ou composez un CV depuis une sélection de domaines."
     data-en="The profile as a network: domains, experiences, projects, skills and their links. Hover, click, or compose a CV from a domain selection.">Le profil comme réseau…</p>
</header>

<div class="g-controls">
  <div class="g-chips" id="chips" style="display:flex;flex-wrap:wrap;gap:8px">@@CHIPS_PLACEHOLDER@@</div>
  <input class="g-search" id="search" type="search" placeholder="Rechercher…" data-fr-ph="Rechercher…" data-en-ph="Search…">
  <div class="g-cv">
    <button class="g-cvtoggle" id="cvToggle" data-fr="Mode CV" data-en="CV mode">Mode CV</button>
    <button class="g-compose" id="compose" disabled data-fr="Composer mon CV" data-en="Compose my CV">Composer mon CV</button>
  </div>
</div>

<div class="g-stage">
  <svg id="graph" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid meet">
    <g id="viewport">
      <g id="edges">@@EDGES_SVG@@</g>
      <g id="nodes">@@NODES_SVG@@</g>
    </g>
  </svg>
  <div class="g-panel" id="panel">
    <span class="gp-close" onclick="closePanel()">×</span>
    <div class="gp-type" id="pType"></div>
    <div class="gp-title" id="pTitle"></div>
    <div class="gp-conn" id="pConn"></div>
    <a class="gp-go" id="pGo" href="#" data-fr="Voir la page ↗" data-en="Open page ↗">Voir la page ↗</a>
  </div>
  <div class="g-zoom"><button id="zoomIn" aria-label="Zoom avant" title="Zoom +">+</button><button id="zoomOut" aria-label="Zoom arrière" title="Zoom −">−</button></div>
</div>
<div class="g-legend">@@LEGEND@@</div>

<footer>Robin Denis · @@UPDATED@@ · <a href="/" style="color:var(--accent);text-decoration:none" data-fr="Retour à l'accueil" data-en="Back home">Retour</a></footer>
</div>

<script src="/assets/js/cv-select.js"></script>
<script src="/assets/js/cv-render.js"></script>
<script id="graph-data" type="application/json">@@DATA@@</script>
<script>
  const root = document.documentElement;
  const GD = JSON.parse(document.getElementById('graph-data').textContent);
  const NODES = GD.nodes, EDGES = GD.edges;
  const byId = {}; NODES.forEach(function(n){ byId[n.id] = n; });
  const TYPES = Array.from(new Set(NODES.map(function(n){ return n.type; })));
  const REL_LABEL = { has_domain:{fr:'domaine',en:'domain'}, context:{fr:'contexte',en:'context'},
    used_in:{fr:'utilisé dans',en:'used in'}, demo_of:{fr:'démo de',en:'demo of'}, refs:{fr:'référence',en:'refs'} };
  const TYPE_LABEL = { identity:['Moi','Me'], domain:['Domaines','Domains'], experience:['Expériences','Experience'],
    education:['Formations','Education'], project:['Projets','Projects'], article:['Articles','Articles'],
    demo:['Démos','Demos'], journey:['Parcours','Journey'], skill:['Compétences','Skills'] };
  let hiddenTypes = new Set(), cvMode = false, picked = new Set();
  let openId = null, searchQ = '', moved = false;
  let downClient = null;

  function curLang(){ return root.getAttribute('data-lang') || 'fr'; }

  // ---- Chips par type (générées client-side depuis TYPES présents) ----
  (function buildChips(){
    const box = document.getElementById('chips');
    TYPES.forEach(function(t){
      const c = document.createElement('button');
      c.className = 'g-chip'; c.dataset.type = t;
      c.setAttribute('data-fr', TYPE_LABEL[t][0]); c.setAttribute('data-en', TYPE_LABEL[t][1]);
      c.textContent = curLang() === 'fr' ? TYPE_LABEL[t][0] : TYPE_LABEL[t][1];
      box.appendChild(c);
    });
    box.addEventListener('click', function(ev){
      const c = ev.target.closest('.g-chip'); if (!c) return;
      const t = c.dataset.type;
      if (hiddenTypes.has(t)) hiddenTypes.delete(t); else hiddenTypes.add(t);
      c.classList.toggle('off', hiddenTypes.has(t));
      applyFilter();
    });
  })();

  function applyFilter(){
    document.querySelectorAll('.gnode').forEach(function(g){
      g.style.display = hiddenTypes.has(g.dataset.type) ? 'none' : '';
    });
    document.querySelectorAll('.gedge').forEach(function(l){
      const s = byId[l.dataset.s], t = byId[l.dataset.t];
      const vis = s && t && !hiddenTypes.has(s.type) && !hiddenTypes.has(t.type);
      l.style.display = vis ? '' : 'none';
    });
  }

  // ---- Recherche live ----
  document.getElementById('search').addEventListener('input', function(ev){
    searchQ = ev.target.value.trim().toLowerCase();
    applySearchDim();
  });
  function applySearchDim(){ document.querySelectorAll('.gnode').forEach(function(g){ if(!searchQ){ g.classList.remove('dim'); return; } const n=byId[g.dataset.id]; const hit=(n.fr+' '+n.en).toLowerCase().indexOf(searchQ)>=0; g.classList.toggle('dim', !hit); }); }

  // ---- Survol : surligne voisins ----
  function neighbors(id){
    const set = new Set();
    EDGES.forEach(function(ed){
      if (ed.source === id) set.add(ed.target);
      if (ed.target === id) set.add(ed.source);
    });
    return set;
  }
  document.getElementById('nodes').addEventListener('mouseover', function(ev){
    const g = ev.target.closest('.gnode'); if (!g) return;
    const id = g.dataset.id, nb = neighbors(id);
    document.querySelectorAll('.gnode').forEach(function(x){
      x.classList.toggle('dim', x.dataset.id !== id && !nb.has(x.dataset.id));
    });
    document.querySelectorAll('.gedge').forEach(function(l){
      l.classList.toggle('hl', l.dataset.s === id || l.dataset.t === id);
    });
  });
  document.getElementById('nodes').addEventListener('mouseout', function(){
    document.querySelectorAll('.gnode').forEach(function(x){ x.classList.remove('dim'); });
    applySearchDim();
    document.querySelectorAll('.gedge').forEach(function(l){ l.classList.remove('hl'); });
  });

  // ---- Clic : panneau détail OU sélection CV ----
  document.getElementById('nodes').addEventListener('click', function(ev){
    if (moved){ moved = false; return; }
    const g = ev.target.closest('.gnode'); if (!g) return;
    const id = g.dataset.id, n = byId[id];
    if (cvMode && n.type === 'domain'){
      if (picked.has(id)) picked.delete(id); else picked.add(id);
      g.classList.toggle('pick', picked.has(id));
      updateCompose();
      return;
    }
    openPanel(n);
  });

  function openPanel(n){
    openId = n.id;
    const L = curLang();
    document.getElementById('pType').textContent = TYPE_LABEL[n.type] ? TYPE_LABEL[n.type][L === 'fr' ? 0 : 1] : n.type;
    document.getElementById('pTitle').textContent = L === 'fr' ? n.fr : n.en;
    const conns = EDGES.filter(function(ed){ return ed.source === n.id || ed.target === n.id; })
      .map(function(ed){
        const other = byId[ed.source === n.id ? ed.target : ed.source];
        const rl = REL_LABEL[ed.rel] ? REL_LABEL[ed.rel][L] : ed.rel;
        return other ? (rl + ' → ' + (L === 'fr' ? other.fr : other.en)) : '';
      }).filter(Boolean);
    document.getElementById('pConn').innerHTML = conns.length
      ? conns.map(function(c){ return '<div>' + c.replace(/</g,'&lt;') + '</div>'; }).join('')
      : (L === 'fr' ? 'Aucune connexion.' : 'No connection.');
    const go = document.getElementById('pGo');
    if (n.href){ go.style.display = ''; go.href = n.href; } else { go.style.display = 'none'; }
    document.getElementById('panel').classList.add('show');
  }
  function closePanel(){ openId = null; document.getElementById('panel').classList.remove('show'); }
  window.closePanel = closePanel;

  // ---- Mode CV ----
  document.getElementById('cvToggle').addEventListener('click', function(){
    cvMode = !cvMode;
    this.classList.toggle('active', cvMode);
    document.getElementById('compose').style.display = cvMode ? 'inline-block' : 'none';
    if (!cvMode){ picked.clear(); document.querySelectorAll('.gnode.pick').forEach(function(g){ g.classList.remove('pick'); }); }
    updateCompose();
    closePanel();
  });
  function updateCompose(){
    const btn = document.getElementById('compose'), L = curLang();
    btn.disabled = picked.size === 0;
    const base = L === 'fr' ? 'Composer mon CV' : 'Compose my CV';
    btn.textContent = picked.size ? base + ' (' + picked.size + ')' : base;
  }
  document.getElementById('compose').addEventListener('click', function(){
    if (!picked.size) return;
    const w = window.open('', '_blank');                 // synchrone dans le geste du clic (popup-blocker OK)
    if (!w){ alert(curLang() === 'fr' ? 'Autorisez les pop-ups pour générer le CV.' : 'Allow pop-ups to generate the CV.'); return; }
    const doms = Array.from(picked).map(function(id){ return id.split(':')[1]; });
    fetch('/profile.json').then(function(r){ return r.json(); }).then(function(profile){
      const lang = curLang();
      const exps = window.CVSelect.selectExperiences(profile, { domains_in: doms, relevance_key: 'general', min_relevance: 2 });
      const cv = window.CVSelect.buildStructuredCv(profile, exps, lang);
      const htmlDoc = window.CVRender.renderHtml(cv);
      w.document.write(htmlDoc); w.document.close();
      w.focus(); setTimeout(function(){ w.print(); }, 300);
    }).catch(function(){
      try { w.close(); } catch (e) {}
      alert(curLang() === 'fr' ? 'Impossible de générer le CV.' : 'Could not generate the CV.');
    });
  });

  // ---- Drag de nœud (DOM pur) + pan/zoom ----
  const svg = document.getElementById('graph');
  let vb = { x:0, y:0, w:1000, h:700 }, dragNode = null, panning = false, last = null;
  function setVB(){ svg.setAttribute('viewBox', vb.x + ' ' + vb.y + ' ' + vb.w + ' ' + vb.h); }
  function svgPt(ev){
    const ctm = svg.getScreenCTM();
    if (!ctm) return { x: vb.x + vb.w / 2, y: vb.y + vb.h / 2 };
    const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }
  svg.addEventListener('pointerdown', function(ev){
    moved = false;
    downClient = { x: ev.clientX, y: ev.clientY };
    const g = ev.target.closest('.gnode');
    if (g){ dragNode = g; }
    else { panning = true; svg.classList.add('panning'); }
    last = svgPt(ev); svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener('pointermove', function(ev){
    if (!dragNode && !panning) return;
    if (downClient && Math.hypot(ev.clientX - downClient.x, ev.clientY - downClient.y) > 5) moved = true;
    const p = svgPt(ev), dx = p.x - last.x, dy = p.y - last.y;
    if (dragNode){
      const id = dragNode.dataset.id, n = byId[id];
      n.x += dx; n.y += dy;
      dragNode.setAttribute('transform', 'translate(' + n.x + ',' + n.y + ')');
      document.querySelectorAll('.gedge').forEach(function(l){
        if (l.dataset.s === id){ l.setAttribute('x1', n.x); l.setAttribute('y1', n.y); }
        if (l.dataset.t === id){ l.setAttribute('x2', n.x); l.setAttribute('y2', n.y); }
      });
    } else { vb.x -= dx; vb.y -= dy; setVB(); }
    last = svgPt(ev);
  });
  svg.addEventListener('pointerup', function(ev){ dragNode = null; panning = false; svg.classList.remove('panning'); });
  svg.addEventListener('wheel', function(ev){
    ev.preventDefault();
    const p = svgPt(ev), f = ev.deltaY < 0 ? 0.9 : 1.1;
    const nw = Math.min(2000, Math.max(200, vb.w * f)), nh = nw * (700 / 1000);
    vb.x = p.x - (p.x - vb.x) * (nw / vb.w); vb.y = p.y - (p.y - vb.y) * (nh / vb.h);
    vb.w = nw; vb.h = nh; setVB();
  }, { passive: false });
  function zoomBy(f){
    const cxv = vb.x + vb.w / 2, cyv = vb.y + vb.h / 2;
    const nw = Math.min(2000, Math.max(200, vb.w * f)), nh = nw * (700 / 1000);
    vb.x = cxv - nw / 2; vb.y = cyv - nh / 2; vb.w = nw; vb.h = nh; setVB();
  }
  document.getElementById('zoomIn').addEventListener('click', function(){ zoomBy(0.8); });
  document.getElementById('zoomOut').addEventListener('click', function(){ zoomBy(1.25); });

  // ---- Langue / thème (partagé localStorage, boot APRÈS le DOM du panneau) ----
  function applyGraphLang(lang){
    document.querySelectorAll('[data-fr][data-en]').forEach(function(el){
      el.textContent = lang === 'fr' ? el.dataset.fr : el.dataset.en;
    });
    const s = document.getElementById('search');
    s.placeholder = lang === 'fr' ? s.dataset.frPh : s.dataset.enPh;
    root.setAttribute('data-lang', lang); root.setAttribute('lang', lang);
    document.getElementById('langBtn').textContent = lang === 'fr' ? 'FR' : 'EN';
    updateCompose();
    if (openId && document.getElementById('panel').classList.contains('show')){
      openPanel(byId[openId]);
    }
  }
  function toggleLang(){ const n = curLang() === 'fr' ? 'en' : 'fr'; localStorage.setItem('lang', n); applyGraphLang(n); }
  function tgTheme(){
    const n = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', n); localStorage.setItem('theme', n);
    document.getElementById('themeBtn').textContent = n === 'light' ? '☀️' : '🌙';
  }
  window.toggleLang = toggleLang; window.tgTheme = tgTheme;

  (function boot(){
    const th = localStorage.getItem('theme');
    if (th){ root.setAttribute('data-theme', th); document.getElementById('themeBtn').textContent = th === 'light' ? '☀️' : '🌙'; }
    const lg = localStorage.getItem('lang') || 'fr';
    if (lg !== 'fr') applyGraphLang(lg);
    setVB();
  })();
</script>
</body>
</html>
"""


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _load_topology(profile):
    import sys
    cv = str(pathlib.Path(__file__).resolve().parent / "cv")
    if cv not in sys.path:
        sys.path.insert(0, cv)
    import profile_pipeline  # livré SP6, sous tools/cv/
    return profile_pipeline.build_profile_graph(profile)


def _pair(v, fallback):
    if isinstance(v, dict):
        fr = v.get("fr") or v.get("en") or fallback
        en = v.get("en") or v.get("fr") or fallback
        return {"fr": fr, "en": en}
    s = str(v) if v else fallback
    return {"fr": s, "en": s}


def _bi_label(node_id, profile):
    typ, _, rid = str(node_id).partition(":")
    if typ == "identity":
        idn = profile.get("identity", {}) or {}
        nm = f'{idn.get("first_name","")} {idn.get("last_name","")}'.strip() or rid
        return {"fr": nm, "en": nm}
    if typ == "domain":
        for d in profile.get("domains", []):
            if d.get("id") == rid:
                return _pair(d.get("label"), rid)
    if typ == "experience":
        for x in profile.get("experiences", []):
            if x.get("id") == rid:
                return _pair(x.get("title"), rid)
    if typ == "education":
        for ed in profile.get("education", []):
            if ed.get("id") == rid:
                return _pair(ed.get("title"), rid)
    if typ == "project":
        for p in profile.get("projects", []):
            if p.get("id") == rid:
                return _pair(p.get("name"), rid)
    if typ == "article":
        for a in profile.get("articles", []):
            if a.get("id") == rid:
                return _pair(a.get("title"), rid)
    if typ == "demo":
        for dm in profile.get("demos", []):
            if dm.get("id") == rid:
                return _pair(dm.get("title"), rid)
    if typ == "journey":
        try:
            j = (profile.get("journey", []) or [])[int(rid)]
            return _pair(j.get("label"), f"jalon {rid}")
        except (ValueError, IndexError):
            return {"fr": f"jalon {rid}", "en": f"milestone {rid}"}
    if typ == "skill":
        return {"fr": rid, "en": rid}
    return {"fr": rid, "en": rid}


def _abs_url(u):
    if not u:
        return ""
    if u.startswith(("http://", "https://", "/", "#")):
        return u
    return "/" + u


def _node_href(node_id, node_type, profile, lens_ids):
    _, _, rid = str(node_id).partition(":")
    if node_type == "project":
        return f"/projects/#{rid}"
    if node_type == "domain":
        return f"/highlights/?lens={rid}" if rid in lens_ids else "/explorer/"
    if node_type == "experience":
        return "/#experience"
    if node_type == "education":
        return "/#education"
    if node_type == "demo":
        return f"/demos/#{rid}"
    if node_type == "article":
        for a in profile.get("articles", []):
            if a.get("id") == rid:
                return _abs_url(a.get("url")) or "/explorer/"
        return "/explorer/"
    if node_type == "journey":
        return "/#parcours"
    if node_type == "skill":
        return "/explorer/"
    return ""


def graph_edges(profile):
    return _load_topology(profile)["edges"]


def graph_nodes(profile):
    topo = _load_topology(profile)
    out = []
    for n in topo["nodes"]:
        lab = _bi_label(n["id"], profile)
        out.append({"id": n["id"], "type": n["type"], "fr": lab["fr"], "en": lab["en"]})
    return out


def compute_layout(nodes, edges, width=1000, height=700, iterations=300):
    ids = [n["id"] for n in nodes]
    n = len(ids)
    if n == 0:
        return {}
    idx = {nid: i for i, nid in enumerate(ids)}
    cx, cy = width / 2.0, height / 2.0
    k = math.sqrt((width * height) / n) * 0.8            # distance idéale
    R = min(width, height) * 0.42
    pos = {}
    for i, nid in enumerate(ids):                        # init déterministe (cercle)
        if nid == "identity:self":
            pos[nid] = [cx, cy]
        else:
            ang = 2 * math.pi * i / n
            pos[nid] = [cx + R * math.cos(ang), cy + R * math.sin(ang)]
    adj = [(idx[ed["source"]], idx[ed["target"]])
           for ed in edges if ed["source"] in idx and ed["target"] in idx]
    t = width / 10.0
    dt = t / (iterations + 1)
    for _ in range(iterations):
        disp = {nid: [0.0, 0.0] for nid in ids}
        for i in range(n):                               # répulsion O(n²)
            for j in range(i + 1, n):
                a, b = ids[i], ids[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                dist = math.hypot(dx, dy) or 0.01
                f = k * k / dist
                ux, uy = dx / dist, dy / dist
                disp[a][0] += ux * f; disp[a][1] += uy * f
                disp[b][0] -= ux * f; disp[b][1] -= uy * f
        for si, ti in adj:                               # attraction (arêtes)
            a, b = ids[si], ids[ti]
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = math.hypot(dx, dy) or 0.01
            f = dist * dist / k
            ux, uy = dx / dist, dy / dist
            disp[a][0] -= ux * f; disp[a][1] -= uy * f
            disp[b][0] += ux * f; disp[b][1] += uy * f
        for nid in ids:                                  # déplacement borné en magnitude (identity figé)
            if nid == "identity:self":
                continue
            ddx, ddy = disp[nid]
            d = math.hypot(ddx, ddy) or 0.01
            step = min(d, t)
            pos[nid][0] += ddx / d * step
            pos[nid][1] += ddy / d * step
        t -= dt
    pad = 40.0
    others = [nid for nid in ids if nid != "identity:self"]
    if others:
        xs = [pos[nid][0] for nid in others]
        ys = [pos[nid][1] for nid in others]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        spanx = (maxx - minx) or 1.0
        spany = (maxy - miny) or 1.0
        s = min((width - 2 * pad) / spanx, (height - 2 * pad) / spany)
        offx = (width - spanx * s) / 2.0 - minx * s
        offy = (height - spany * s) / 2.0 - miny * s
        for nid in others:
            pos[nid][0] = pos[nid][0] * s + offx
            pos[nid][1] = pos[nid][1] * s + offy
    pos["identity:self"] = [float(cx), float(cy)]
    return {nid: (round(pos[nid][0], 2), round(pos[nid][1], 2)) for nid in ids}


TYPE_COLOR = {
    "identity": "var(--accent)", "domain": "#f59e42", "experience": "#22c55e",
    "education": "#a78bfa", "project": "#3b82f6", "article": "#ec4899",
    "demo": "#14b8a6", "journey": "#eab308", "skill": "#64748b",
}
TYPE_LABEL = {
    "identity": ("Moi", "Me"), "domain": ("Domaines", "Domains"),
    "experience": ("Expériences", "Experience"), "education": ("Formations", "Education"),
    "project": ("Projets", "Projects"), "article": ("Articles", "Articles"),
    "demo": ("Démos", "Demos"), "journey": ("Parcours", "Journey"), "skill": ("Compétences", "Skills"),
}
NODE_R = {"identity": 13, "domain": 9, "experience": 8, "education": 8, "project": 7}


def assemble(profile):
    import build_highlights
    lens_ids = build_highlights.lens_domains(profile)
    nodes = graph_nodes(profile)
    edges = graph_edges(profile)
    coords = compute_layout(nodes, edges)
    out_nodes = []
    for n in nodes:
        x, y = coords[n["id"]]
        out_nodes.append({"id": n["id"], "type": n["type"], "fr": n["fr"], "en": n["en"],
                          "x": float(x), "y": float(y),
                          "href": _node_href(n["id"], n["type"], profile, lens_ids)})
    return {"nodes": out_nodes, "edges": edges}


def _edges_svg(data):
    pos = {n["id"]: (n["x"], n["y"]) for n in data["nodes"]}
    out = []
    for ed in data["edges"]:
        if ed["source"] in pos and ed["target"] in pos:
            x1, y1 = pos[ed["source"]]; x2, y2 = pos[ed["target"]]
            out.append(f'<line class="gedge" data-s="{e(ed["source"])}" data-t="{e(ed["target"])}" '
                       f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    return "\n".join(out)


def _nodes_svg(data):
    out = []
    for n in data["nodes"]:
        r = NODE_R.get(n["type"], 6)
        out.append(
            f'<g class="gnode" data-id="{e(n["id"])}" data-type="{e(n["type"])}" '
            f'transform="translate({n["x"]},{n["y"]})">'
            f'<circle r="{r}" fill="{TYPE_COLOR.get(n["type"], "#888")}"/>'
            f'<text class="glabel" x="{r + 3}" y="4" data-fr="{e(n["fr"])}" data-en="{e(n["en"])}">'
            f'{e(n["fr"])}</text></g>'
        )
    return "\n".join(out)


def _legend(profile):
    import build_highlights
    present = {n["type"] for n in graph_nodes(profile)}
    items = []
    for typ, (lfr, len_) in TYPE_LABEL.items():
        if typ in present:
            items.append(f'<span class="gleg"><i style="background:{TYPE_COLOR[typ]}"></i>'
                         f'<span data-fr="{e(lfr)}" data-en="{e(len_)}">{e(lfr)}</span></span>')
    return "".join(items)


def render_graph_page(profile):
    data = assemble(profile)
    updated = profile.get("projects_meta", {}).get("updated", "")
    return (PAGE_TEMPLATE
            .replace("@@EDGES_SVG@@", _edges_svg(data))
            .replace("@@NODES_SVG@@", _nodes_svg(data))
            .replace("@@LEGEND@@", _legend(profile))
            .replace("@@CHIPS_PLACEHOLDER@@", "")
            .replace("@@DATA@@", json.dumps(data, ensure_ascii=True).replace("<", "\\u003c"))
            .replace("@@UPDATED@@", e(updated)))


def build_graph(profile=None, write: bool = True) -> str:
    if profile is None:
        profile = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    out = render_graph_page(profile)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_graph()
    n = out.count('class="gnode"')
    print(f"[build_graph] OK - {n} nœuds -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
