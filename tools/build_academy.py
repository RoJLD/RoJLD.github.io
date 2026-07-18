#!/usr/bin/env python3
"""build_academy.py — génère academy/index.html depuis academy.json.

Academy = flashcards + quiz auto-évalué (moteur porté de HMMstudio en vanilla).
score_quiz est PUR et indiciel (langue-agnostique) ; le gap report bilingue vit
côté JS (data-concept-<lang>). LECTURE de academy.json (profile.json non touché).
"""
from __future__ import annotations

import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "academy" / "index.html"
LEVELS = ["Recall", "Apply", "Analyze"]


class BuildError(Exception):
    pass


def load_academy(path=None):
    p = pathlib.Path(path) if path else ROOT / "academy.json"
    return json.loads(p.read_text(encoding="utf-8"))


def score_quiz(questions, answers):
    """PUR. answers[i] = index choisi ou None. Indiciel, langue-agnostique."""
    by = {lv: {"correct": 0, "total": 0} for lv in LEVELS}
    missed = []
    correct = 0
    for i, q in enumerate(questions):
        lv = q["level"]
        by[lv]["total"] += 1
        if answers[i] is not None and answers[i] == q["correct"]:
            correct += 1
            by[lv]["correct"] += 1
        else:
            missed.append(i)
    return {"total": len(questions), "correct": correct, "byLevel": by, "missedIndices": missed}


def _bi_ok(v):
    return isinstance(v, dict) and "fr" in v and "en" in v


def validate_academy(data):
    errors = []
    if not data.get("$version"):
        errors.append("academy: missing $version")
    seen = set()
    for t in data.get("topics", []):
        tid = t.get("id", "?")
        if tid in seen:
            errors.append(f"topic '{tid}': id dupliqué")
        seen.add(tid)
        for f in ("title", "subtitle", "link_label"):
            if not _bi_ok(t.get(f)):
                errors.append(f"topic '{tid}': {f} non bilingue")
        if not t.get("link"):
            errors.append(f"topic '{tid}': link manquant")
        for fc in t.get("flashcards", []):
            if fc.get("level") not in LEVELS:
                errors.append(f"topic '{tid}': flashcard level invalide '{fc.get('level')}'")
            if not _bi_ok(fc.get("front")) or not _bi_ok(fc.get("back")):
                errors.append(f"topic '{tid}': flashcard non bilingue")
        for qi, q in enumerate(t.get("questions", [])):
            if q.get("level") not in LEVELS:
                errors.append(f"topic '{tid}' q{qi}: level invalide '{q.get('level')}'")
            opts = q.get("options") or []
            if len(opts) < 2:
                errors.append(f"topic '{tid}' q{qi}: <2 options")
            if not isinstance(q.get("correct"), int) or not (0 <= q.get("correct", -1) < len(opts)):
                errors.append(f"topic '{tid}' q{qi}: correct hors range")
            for f in ("prompt", "concept", "explanation"):
                if not _bi_ok(q.get(f)):
                    errors.append(f"topic '{tid}' q{qi}: {f} non bilingue")
            for oi, o in enumerate(opts):
                if not _bi_ok(o):
                    errors.append(f"topic '{tid}' q{qi} opt{oi}: non bilingue")
    return errors


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def one_line(s) -> str:
    return " ".join(str(s or "").split())


# ══════════════════ Rendu ══════════════════

def _pill(level):
    return f'<span class="lv lv-{e(level.lower())}">{e(level)}</span>'


def render_flashcard(fc):
    ffr, fen = fc["front"]["fr"], fc["front"]["en"]
    bfr, ben = fc["back"]["fr"], fc["back"]["en"]
    return (
        f'<button type="button" class="fc" data-level="{e(fc["level"])}" '
        f'data-front-fr="{e(ffr)}" data-front-en="{e(fen)}" '
        f'data-back-fr="{e(bfr)}" data-back-en="{e(ben)}">'
        f'{_pill(fc["level"])}'
        f'<span class="fc-face" data-fr="{e(ffr)}" data-en="{e(fen)}">{e(ffr)}</span>'
        f'<span class="fc-hint" data-fr="Cliquer pour révéler" data-en="Click to reveal">Cliquer pour révéler</span>'
        f'</button>'
    )


def render_question(q, idx):
    pfr, pen = q["prompt"]["fr"], q["prompt"]["en"]
    cfr, cen = q["concept"]["fr"], q["concept"]["en"]
    xfr, xen = q["explanation"]["fr"], q["explanation"]["en"]
    opts = "".join(
        f'<button type="button" class="q-opt" data-oi="{oi}" '
        f'data-fr="{e(o["fr"])}" data-en="{e(o["en"])}">{e(o["fr"])}</button>'
        for oi, o in enumerate(q["options"])
    )
    return (
        f'<div class="q-card" data-qi="{idx}" data-correct="{q["correct"]}" data-level="{e(q["level"])}" '
        f'data-concept-fr="{e(cfr)}" data-concept-en="{e(cen)}">'
        f'<p class="q-prompt"><span class="q-num">{idx + 1}.</span> '
        f'<span data-fr="{e(pfr)}" data-en="{e(pen)}">{e(pfr)}</span></p>'
        f'<div class="q-opts">{opts}</div>'
        f'<p class="q-expl" hidden data-fr="{e(xfr)}" data-en="{e(xen)}">{e(xfr)}</p>'
        f'</div>'
    )


def render_topic(t):
    tid = t["id"]
    tfr, ten = t["title"]["fr"], t["title"]["en"]
    sfr, sen = t["subtitle"]["fr"], t["subtitle"]["en"]
    lfr, len_ = t["link_label"]["fr"], t["link_label"]["en"]
    flash = "\n".join(render_flashcard(fc) for fc in t["flashcards"])
    ques = "\n".join(render_question(q, i) for i, q in enumerate(t["questions"]))
    return (
        f'<section class="topic" data-topic="{e(tid)}">'
        f'<button type="button" class="topic-h" aria-expanded="false">'
        f'<span class="topic-tt"><span class="topic-title" data-fr="{e(tfr)}" data-en="{e(ten)}">{e(tfr)}</span>'
        f'<span class="topic-sub" data-fr="{e(sfr)}" data-en="{e(sen)}">{e(sfr)}</span></span>'
        f'<span class="topic-badge" data-topic-badge="{e(tid)}"></span>'
        f'<span class="topic-caret">▾</span></button>'
        f'<div class="topic-body">'
        f'<a class="topic-link" href="{e(t["link"])}" data-fr="{e(lfr)}" data-en="{e(len_)}">{e(lfr)}</a>'
        f'<h3 class="blk" data-fr="Flashcards" data-en="Flashcards">Flashcards</h3>'
        f'<div class="fc-grid">{flash}</div>'
        f'<h3 class="blk" data-fr="Quiz" data-en="Quiz">Quiz</h3>'
        f'<div class="quiz" data-topic="{e(tid)}">{ques}'
        f'<button type="button" class="q-submit" disabled data-fr="Valider le quiz" data-en="Submit quiz">Valider le quiz</button>'
        f'<div class="q-result" hidden></div></div>'
        f'</div></section>'
    )


# ══════════════════ Page ══════════════════

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark" data-lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Academy — Robin Denis</title>
<meta name="description" content="Academy interactive de Robin Denis — flashcards et quiz auto-évalués sur le pricing, la couverture et l'analyse on-chain.">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--radius:14px;--radius-sm:10px;--ease:cubic-bezier(.4,0,.2,1)}
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
header.hd{padding:130px 0 10px;text-align:center}
header.hd h1{font-family:var(--serif);font-size:clamp(38px,6vw,56px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}
header.hd p{color:var(--tx-2);font-size:16px;font-weight:300;max-width:580px;margin:0 auto}
.topics{padding:24px 0 40px}
.topic{border:1px solid var(--border);border-radius:var(--radius);margin:14px 0;overflow:hidden;background:var(--bg-2)}
.topic-h{width:100%;display:flex;align-items:center;gap:12px;padding:18px 20px;background:none;border:0;cursor:pointer;text-align:left;color:inherit;font-family:var(--sans)}
.topic-tt{flex:1;display:flex;flex-direction:column;gap:2px}
.topic-title{font-size:17px;font-weight:600;color:var(--tx-1)}
.topic-sub{font-size:12.5px;color:var(--tx-3)}
.topic-badge{font-size:12px;font-weight:600;color:var(--green)}
.topic-caret{color:var(--tx-3);transition:transform .3s var(--ease)}
.topic.open .topic-caret{transform:rotate(180deg)}
.topic-body{display:none;padding:0 20px 20px}
.topic.open .topic-body{display:block}
.topic-link{display:inline-block;margin:4px 0 8px;font-size:12.5px;font-weight:600;color:var(--accent);text-decoration:none}
.blk{font-family:var(--serif);font-size:19px;font-weight:400;margin:16px 0 10px;color:var(--tx-1)}
.fc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.fc{border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-1);padding:16px;min-height:130px;display:flex;flex-direction:column;gap:8px;cursor:pointer;text-align:left;color:inherit;font-family:var(--sans);transition:border-color .25s var(--ease)}
.fc:hover{border-color:var(--border-hi)}
.fc-face{color:var(--tx-1);font-size:14px;line-height:1.5;flex:1}
.fc-hint{font-size:11px;color:var(--tx-3);margin-top:auto}
.lv{align-self:flex-start;font-size:10px;font-weight:700;padding:2px 8px;border-radius:100px;text-transform:uppercase;letter-spacing:.04em}
.lv-recall{background:var(--green-g);color:var(--green)}
.lv-apply{background:var(--warm-g);color:var(--warm)}
.lv-analyze{background:rgba(167,139,250,.14);color:var(--violet)}
.quiz{margin-top:6px}
.q-card{border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-1);padding:14px;margin-bottom:10px}
.q-prompt{font-size:14px;font-weight:500;color:var(--tx-1);margin-bottom:10px}
.q-num{color:var(--accent);font-weight:700}
.q-opts{display:flex;flex-direction:column;gap:6px}
.q-opt{text-align:left;font-size:13.5px;padding:9px 12px;border-radius:8px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-1);cursor:pointer;font-family:var(--sans);transition:all .2s var(--ease)}
.q-opt:hover:not(:disabled){border-color:var(--accent)}
.q-opt.sel{border-color:var(--accent);background:var(--accent-g)}
.q-opt.ok{border-color:var(--green);background:var(--green-g)}
.q-opt.ko{border-color:#ef4444;background:rgba(239,68,68,.10)}
.q-opt:disabled{cursor:default}
.q-expl{font-size:12px;color:var(--tx-3);margin-top:8px;font-style:italic}
.q-submit{margin-top:6px;padding:9px 18px;border-radius:100px;border:0;background:var(--accent);color:#fff;font-weight:600;font-size:13px;cursor:pointer;font-family:var(--sans)}
.q-submit:disabled{background:var(--bg-3);color:var(--tx-3);cursor:not-allowed}
.q-result{margin:12px 0;padding:16px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-3)}
.q-score{font-size:16px;font-weight:600;color:var(--tx-1)}
.q-levels{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.q-gap{font-size:13px;color:var(--tx-2);margin-top:6px}
.q-retry{margin-top:10px;padding:7px 15px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-1);font-weight:600;font-size:12.5px;cursor:pointer;font-family:var(--sans)}
footer{text-align:center;padding:40px 0;color:var(--tx-3);font-size:12px;border-top:1px solid var(--border);margin-top:20px}
@media(max-width:640px){.wrap{padding:0 18px}.fc-grid{grid-template-columns:1fr}.nav-r a:not(.on){display:none}header.hd{padding:110px 0 6px}}
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
    <a href="/highlights/" data-fr="Highlights" data-en="Highlights">Highlights</a>
    <a class="on" href="/academy/" data-fr="Academy" data-en="Academy">Academy</a>
    <a href="/graph/" data-fr="Graphe" data-en="Graph">Graphe</a>
    <button class="ctrl-btn lang-btn" onclick="toggleLang()" id="langBtn" title="Langue">FR</button>
    <button class="ctrl-btn" onclick="tgTheme()" id="themeBtn" title="Thème">🌙</button>
  </div>
</div></nav>

<div class="wrap">
<header class="hd">
  <h1>Academy</h1>
  <p data-fr="Réviser puis s'auto-évaluer : flashcards et quiz sur mes sujets de prédilection. Choisissez un thème, révisez, testez-vous."
     data-en="Revise, then self-assess: flashcards and quizzes on my core topics. Pick a theme, review, test yourself.">Réviser puis s'auto-évaluer : flashcards et quiz sur mes sujets de prédilection. Choisissez un thème, révisez, testez-vous.</p>
</header>

<div class="topics" id="topics">
@@TOPICS@@
</div>

<footer>Robin Denis · @@UPDATED@@ · <a href="/" style="color:var(--accent);text-decoration:none" data-fr="Retour à l'accueil" data-en="Back home">Retour à l'accueil</a></footer>
</div>

<script>
  const LEVELS = ["Recall", "Apply", "Analyze"];
  const root = document.documentElement;
  const PROGRESS_KEY = "academy-progress";

  function curLang(){ return root.getAttribute('data-lang') || 'fr'; }
  function progress(){ try { return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || {}; } catch(e){ return {}; } }

  // ── moteur pur (miroir de build_academy.score_quiz) ──
  function scoreQuiz(cards, answers){
    const by = { Recall:{correct:0,total:0}, Apply:{correct:0,total:0}, Analyze:{correct:0,total:0} };
    const missed = []; let correct = 0;
    cards.forEach(function(c, i){
      const lv = c.dataset.level; by[lv].total += 1;
      const a = answers[i];
      if (a !== null && a === parseInt(c.dataset.correct)) { correct += 1; by[lv].correct += 1; }
      else missed.push(i);
    });
    return { total: cards.length, correct: correct, byLevel: by, missedIndices: missed };
  }

  // ── accordéon ──
  document.querySelectorAll('.topic-h').forEach(function(h){
    h.addEventListener('click', function(){
      const sec = h.closest('.topic');
      const wasOpen = sec.classList.contains('open');
      document.querySelectorAll('.topic').forEach(function(s){ s.classList.remove('open'); s.querySelector('.topic-h').setAttribute('aria-expanded','false'); });
      if (!wasOpen){ sec.classList.add('open'); h.setAttribute('aria-expanded','true'); }
    });
  });

  // ── flashcards flip ──
  document.querySelectorAll('.fc').forEach(function(fc){
    fc.addEventListener('click', function(){
      const flipped = fc.classList.toggle('flipped');
      const lang = curLang();
      fc.querySelector('.fc-face').textContent = flipped ? fc.dataset['back'+(lang==='fr'?'Fr':'En')] : fc.dataset['front'+(lang==='fr'?'Fr':'En')];
      fc.querySelector('.fc-hint').textContent = flipped ? (lang==='fr'?'Réponse · cliquer pour retourner':'Answer · click to flip back')
                                 : (lang==='fr'?'Cliquer pour révéler':'Click to reveal');
    });
  });

  // ── quiz ──
  document.querySelectorAll('.quiz').forEach(function(quiz){
    const cards = Array.prototype.slice.call(quiz.querySelectorAll('.q-card'));
    const answers = cards.map(function(){ return null; });
    const submit = quiz.querySelector('.q-submit');
    let graded = false;

    cards.forEach(function(card, qi){
      card.querySelectorAll('.q-opt').forEach(function(opt){
        opt.addEventListener('click', function(){
          if (graded) return;
          card.querySelectorAll('.q-opt').forEach(function(o){ o.classList.remove('sel'); });
          opt.classList.add('sel');
          answers[qi] = parseInt(opt.dataset.oi);
          submit.disabled = answers.indexOf(null) !== -1;
        });
      });
    });

    function grade(){
      graded = true;
      const r = scoreQuiz(cards, answers);
      cards.forEach(function(card){
        const cor = parseInt(card.dataset.correct);
        card.querySelectorAll('.q-opt').forEach(function(o){
          const oi = parseInt(o.dataset.oi);
          o.disabled = true;
          if (oi === cor) o.classList.add('ok');
          else if (o.classList.contains('sel')) o.classList.add('ko');
        });
        const ex = card.querySelector('.q-expl'); if (ex) ex.hidden = false;
      });
      quiz.__result = r; quiz.__cards = cards;
      renderResult(quiz, r, cards);
      submit.style.display = 'none';
      saveProgress(quiz.dataset.topic, r);
    }
    submit.addEventListener('click', grade);
  });

  function renderResult(quiz, r, cards){
    const fr = curLang() === 'fr';
    const box = quiz.querySelector('.q-result');
    const pills = LEVELS.filter(function(lv){ return r.byLevel[lv].total > 0; }).map(function(lv){
      const b = r.byLevel[lv];
      return '<span class="lv lv-' + lv.toLowerCase() + '">' + lv + ' ' + b.correct + '/' + b.total + '</span>';
    }).join('');
    let gap;
    if (r.missedIndices.length === 0){
      gap = '<p class="q-gap">' + (fr ? 'Parfait — aucune lacune 🎉' : 'Perfect — no gaps 🎉') + '</p>';
    } else {
      const seen = [];
      r.missedIndices.forEach(function(i){
        const c = cards[i].dataset['concept' + (fr ? 'Fr' : 'En')];
        if (seen.indexOf(c) === -1) seen.push(c);
      });
      gap = '<p class="q-gap">' + (fr ? 'Concepts à revoir : ' : 'Gaps to revisit: ') + '<b>' + seen.join(', ') + '</b>.</p>';
    }
    box.innerHTML = '<p class="q-score">' + (fr ? 'Score : ' : 'Score: ') + r.correct + ' / ' + r.total + '</p>' +
      '<div class="q-levels">' + pills + '</div>' + gap +
      '<button type="button" class="q-retry">' + (fr ? 'Recommencer' : 'Retry') + '</button>';
    box.hidden = false;
    box.querySelector('.q-retry').addEventListener('click', function(){ location.reload(); });
  }

  function saveProgress(topic, r){
    const p = progress();
    const prev = p[topic];
    if (!prev || r.correct > prev.bestCorrect){
      p[topic] = { bestCorrect: r.correct, total: r.total, at: new Date().toISOString() };
      try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(p)); } catch(e){}
    }
    paintBadges();
  }

  function paintBadges(){
    const p = progress(); const fr = curLang() === 'fr';
    document.querySelectorAll('[data-topic-badge]').forEach(function(b){
      const rec = p[b.dataset.topicBadge];
      b.textContent = rec ? ((fr ? 'Meilleur : ' : 'Best: ') + rec.bestCorrect + '/' + rec.total + ' ✓') : '';
    });
  }

  // ── langue / thème (partagés) ──
  function applyBrowseLang(lang){
    document.querySelectorAll('[data-fr][data-en]').forEach(function(el){
      el.textContent = lang === 'fr' ? el.dataset.fr : el.dataset.en;
    });
    document.querySelectorAll('.fc').forEach(function(fc){
      const flipped = fc.classList.contains('flipped');
      fc.querySelector('.fc-face').textContent = flipped ? fc.dataset['back'+(lang==='fr'?'Fr':'En')] : fc.dataset['front'+(lang==='fr'?'Fr':'En')];
      fc.querySelector('.fc-hint').textContent = flipped ? (lang==='fr'?'Réponse · cliquer pour retourner':'Answer · click to flip back') : (lang==='fr'?'Cliquer pour révéler':'Click to reveal');
    });
    root.setAttribute('data-lang', lang); root.setAttribute('lang', lang);
    document.getElementById('langBtn').textContent = lang === 'fr' ? 'FR' : 'EN';
    document.querySelectorAll('.quiz').forEach(function(quiz){ if (quiz.__result) renderResult(quiz, quiz.__result, quiz.__cards); });
    paintBadges();
  }
  function toggleLang(){ const n = curLang()==='fr'?'en':'fr'; localStorage.setItem('lang', n); applyBrowseLang(n); }
  function tgTheme(){
    const n = root.getAttribute('data-theme')==='light'?'dark':'light';
    root.setAttribute('data-theme', n); localStorage.setItem('theme', n);
    document.getElementById('themeBtn').textContent = n==='light'?'☀️':'🌙';
  }

  (function(){
    const st = localStorage.getItem('theme');
    if (st){ root.setAttribute('data-theme', st); document.getElementById('themeBtn').textContent = st==='light'?'☀️':'🌙'; }
    const sl = localStorage.getItem('lang') || 'fr';
    if (sl !== 'fr') applyBrowseLang(sl);
    paintBadges();
  })();
</script>
</body>
</html>
"""


def render_academy_page(data):
    topics = "\n".join(render_topic(t) for t in data.get("topics", []))
    return (PAGE_TEMPLATE
            .replace("@@TOPICS@@", topics)
            .replace("@@UPDATED@@", e("")))


def build_academy(data=None, write: bool = True) -> str:
    if data is None:
        data = load_academy()
    out = render_academy_page(data)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_academy()
    n = out.count('class="topic"')
    print(f"[build_academy] OK - {n} sujets -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
