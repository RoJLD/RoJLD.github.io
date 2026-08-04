"""Σ-CV-ATELIER sous-projet C — atelier local (serveur privé, jamais exposé).

Colle une fiche de poste → CV ciblé en PDF. Réutilise tout le socle :
extract_cfg (LLM souverain) → select_experiences → render_html → Playwright PDF.

Lancer localement :  python tools/cv/atelier.py    (→ http://127.0.0.1:8010)

Non servi par GitHub Pages (stdlib http.server, single-user). Fondation du futur
CMS (sous-projet D). Le LLM passe par llm_client SIGIL-1714 (sibling ELYSIUM) ;
s'il est indisponible, extract_cfg retombe sur un cfg défaut (CV général) — loud.
"""
from __future__ import annotations

import http.server
import json
import pathlib
import secrets
import socket
import sys
import time
import traceback
import urllib.parse
from typing import Any, Callable, Optional

import cv_pdf
import cv_render
import cv_target

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # repo site racine
_PROFILE = _ROOT / "profile.json"


def generate_pdf(job_posting: str, profile: dict, lang: str = "fr",
                 complete_fn: Optional[Callable[[str], str]] = None,
                 template: Optional[str] = None) -> tuple[dict, bytes]:
    """Pipeline ciblé complet → (cfg, pdf_bytes). Testable via complete_fn factice.

    `template` : identifiant de la banque (`cv/templates/<id>.json`), ou None pour
    le défaut. Il traverse jusqu'à `render_html` — un sélecteur qui n'atteindrait
    pas le rendu serait un menu inerte.
    """
    cfg, scv = cv_target.targeted_structured_cv(job_posting, profile, lang, complete_fn=complete_fn)
    pdf = cv_pdf.html_to_pdf_bytes(cv_render.render_html(scv, template))
    return cfg, pdf


def generate_docx(job_posting: str, profile: dict, lang: str = "fr",
                  complete_fn: Optional[Callable[[str], str]] = None) -> tuple[dict, bytes]:
    """Même pipeline ciblé, rendu en **.docx ATS** (texte réel, zéro tableau).

    L'overlay privé (téléphone, disponibilité) est chargé depuis `~/.elysium/` :
    absent, le document se rend sans — jamais un gabarit à sa place.
    """
    import cv_docx                                    # dépendance python-docx : paresseux
    cfg, scv = cv_target.targeted_structured_cv(job_posting, profile, lang, complete_fn=complete_fn)
    return cfg, cv_docx.render_docx_bytes(scv, private=cv_docx.load_private_overlay())


def generate_letter(job_posting: str, profile: dict, lang: str = "fr",
                    skeleton: str = "standard",
                    complete_fn: Optional[Callable[[str], str]] = None,
                    today: Optional[str] = None,
                    accepter_generique: bool = False) -> tuple[dict, Optional[dict], Optional[bytes]]:
    """Lettre de motivation ancrée → `(cfg, verdict, pdf_bytes | None)`.

    Chaîne : `extract_cfg` → `select_evidence` → `build_profile_facts` → `draft`
    → **`check_grounding`** → `build_letter_document` → `render_letter_html_gated`.

    `evidence=` est transmis au vérificateur : les sources recevables sont clampées
    sur les seuls faits que le rédacteur a VUS. L'omettre élargirait le référentiel
    au profil entier — une garantie plus faible, et silencieuse.

    **La porte reste `render_letter_html_gated`, seul chemin vers des octets.** Un
    verdict rouge n'est pas contourné ici : il est *rapporté*. On renvoie
    `pdf_bytes=None` avec le verdict, pour que l'appelant montre QUELLES phrases
    ont bloqué au lieu d'un échec opaque — refuser sans dire quoi corriger ne rend
    service à personne.

    Le ciblage est éprouvé AVANT la rédaction et renvoie `(cfg, None, None)` s'il a
    échoué : rédiger puis vérifier coûte deux appels LLM longs (mesuré : 482 s et
    644 s), et une lettre écrite sans savoir à quel poste on candidate n'a aucune
    chance d'être ancrée. Échouer tôt vaut mieux qu'échouer cher.
    """
    import cv_grounding
    import cv_letter
    import cv_letter_render

    cfg = cv_target.extract_cfg(job_posting, profile, complete_fn=complete_fn)
    if ciblage_degrade(cfg) and not accepter_generique:
        return cfg, None, None
    evidence = cv_letter.select_evidence(profile, cfg)
    facts = cv_letter.build_profile_facts(profile, evidence, lang)
    squelette = cv_letter.load_skeleton(skeleton, lang)
    corps = cv_letter.draft(facts, cfg, squelette, lang, complete_fn=complete_fn)
    verdict = cv_grounding.check_grounding(corps, profile, lang,
                                           complete_fn=complete_fn, evidence=evidence)
    doc = cv_letter.build_letter_document(profile, facts, cfg, corps, lang, today=today)
    try:
        html = cv_letter_render.render_letter_html_gated(doc, verdict)
    except cv_grounding.GroundingBlocked:
        return cfg, verdict, None
    return cfg, verdict, cv_pdf.html_to_pdf_bytes(html)


def _options_templates() -> str:
    """<option> du sélecteur, ÉNUMÉRÉS depuis la banque.

    Une liste écrite en dur prendrait du retard au premier template déposé, et le
    fichier existerait sans être choisissable.
    """
    import cv_templates
    parts = []
    for t in cv_templates.lister():
        lab = t.get("label", {}).get("fr") or t["id"]
        sel = " selected" if t["id"] == cv_templates.DEFAUT else ""
        parts.append(f'<option value="{t["id"]}"{sel}>{lab}</option>')
    return "".join(parts)


def _page(form: Optional[str] = None) -> str:
    """Le formulaire, sélecteur de template injecté (patron de _EDIT / _CMS).

    `form` permet de COMPOSER avec `_render`, qui pose le jeton anti-CSRF :
    l'appelant passe `_page(_render(_FORM))`. Le défaut `None` — et non `_FORM` —
    est imposé par deux contraintes mesurées : `_FORM` est défini APRÈS cette
    fonction (un défaut littéral lèverait `NameError` à l'import), et un test
    existant appelle `_page()` sans argument.
    """
    return (_FORM if form is None else form).replace("__TEMPLATES__", _options_templates())


def _load_validate() -> Callable[[dict], list]:
    """Charge validate_profile.validate (tools/, Track 0) via sys.path."""
    import sys
    tools_dir = str(_HERE.parent)  # tools/
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import validate_profile  # type: ignore
    return validate_profile.validate


def save_profile_edit(raw_json: str, profile_path: pathlib.Path,
                      validate_fn: Optional[Callable[[dict], list]] = None) -> dict:
    """Parse + valide + écrit profile.json (atomique). N'écrit PAS si erreurs.

    Retourne {ok, errors}. Reject-loud : JSON invalide ou règles validate_profile
    violées → ok=False + messages, le fichier reste intact.
    """
    import profile_pipeline
    parsed, errors = profile_pipeline.parse_and_validate(raw_json, validate_fn)
    if errors:
        return {"ok": False, "errors": errors}
    profile_pipeline.atomic_write_profile(parsed, profile_path)
    return {"ok": True, "errors": []}


def _regen_bank() -> None:
    import build_cv_bank  # type: ignore
    build_cv_bank.main()


def _git_commit(repo_root: pathlib.Path, paths: list[str], message: str) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(repo_root), "add", *paths], check=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", message], check=True)


# ── ciblage dégradé : le rendre VISIBLE DANS LE PRODUIT ───────────────────────
#
# Mesuré au premier usage réel (fiche Amundi, 2026-08-03) : le tier LLM a expiré
# trois fois, `extract_cfg` est retombé sur le cfg défaut, et l'atelier a livré un
# CV **générique** sous le nom `cv_cible.pdf` avec le statut « Ciblage:
# general~0.0 » — indiscernable d'un succès pour qui ne connaît pas le code.
#
# `ATELIER.md` affirme que ce repli « n'est jamais silencieux ». C'est vrai du
# JOURNAL et faux du PRODUIT : le WARNING part dans la console du serveur, pendant
# que le PDF part chez le recruteur. Un garde qui ne parle qu'à la console ne
# garde rien.
#
# Le signal fiable n'est PAS l'étiquette `general~0.0` — une fiche peut légitimement
# la produire. C'est `_field_provenance` : un cfg de repli a TOUS ses champs en
# `absent`/`default`, parce qu'aucun n'a pu être lu de la fiche.

def ciblage_degrade(cfg: dict) -> bool:
    """Vrai si le cfg est un REPLI, pas une extraction. Structurel, pas heuristique."""
    prov = cfg.get("_field_provenance") or {}
    lus = {"verbatim", "model"}
    return not any(prov.get(champ) in lus
                   for champ in ("company", "job_title", "requirements", "market"))


def verdict_ciblage(cfg: dict, accepter_generique: bool = False) -> dict:
    """Ce que l'atelier FAIT d'un ciblage dégradé.

    Retourne ``{"livrer": bool, "nom": str, "message": str}`` :
      - ``livrer``  : envoyer le PDF, ou refuser en HTTP 409 ;
      - ``nom``     : nom du fichier téléchargé — la vérité qui voyage AVEC l'artefact ;
      - ``message`` : ce que l'utilisateur lit dans la barre de statut.

    **Politique : refus par défaut, réarmement explicite.** Trois options se
    présentaient — refuser sèchement, livrer en renommant, livrer en avertissant —
    et aucune n'était bonne seule. Refuser protège mais enferme : ollama en panne,
    plus aucun CV, alors qu'un CV générique reste parfois exactement ce qu'on veut.
    Livrer, même renommé, fait du générique le chemin par DÉFAUT — celui qu'on
    prend distrait, un soir de candidature à la chaîne.

    En inversant la charge, l'accident devient impossible sans que la capacité
    disparaisse : un CV générique ne peut plus partir *par erreur*, seulement
    *exprès*, en un clic (`accepter_generique`). Le coût est un aller-retour HTTP.

    Et même réarmé, le fichier reste nommé `cv_GENERIQUE.pdf` : la décision se
    prend à l'écran, la vérité voyage avec l'artefact.
    """
    if not ciblage_degrade(cfg):
        return {"livrer": True, "nom": "cv_cible.pdf", "message": "CV ciblé"}
    if accepter_generique:
        return {"livrer": True, "nom": "cv_GENERIQUE.pdf",
                "message": "CV GÉNÉRIQUE assumé — non adapté à cette fiche"}
    return {"livrer": False, "nom": "cv_GENERIQUE.pdf",
            "message": ("Ciblage impossible (aucun champ n'a pu être lu de la fiche) : "
                        "un CV générique serait produit. Relance, ou demande-le "
                        "explicitement.")}


#: Nom interne de l'atelier. « Kleos » (κλέος) : chez Homère, le renom qui circule
#: par la parole d'autrui et survit à celui qui l'a gagné. Un CV et une lettre ne
#: sont rien d'autre — une réputation confiée à un tiers pour qu'il la répète.
#: Reste dans la famille grecque du satellite (Anthropos « l'humain », Ergon « l'œuvre »).
NOM = "Kleos"

#: Barre de navigation commune aux trois pages. Injectée par `_render` AVANT le
#: profil, pour la même raison que le jeton : un profil contenant `__NAV__` doit
#: être affiché, pas interprété.
_NAV = """<style>
.nv{display:flex;align-items:center;gap:16px;padding:2px 0 12px;margin:0 0 22px;
border-bottom:1px solid #e2e8f0;font-size:13px;flex-wrap:wrap}
.nv a{color:#475569;text-decoration:none;padding:4px 2px;border-bottom:2px solid transparent}
.nv a:hover{color:#1a1a2e;border-bottom-color:#4361ee}
.nv a:focus-visible{outline:2px solid #4361ee;outline-offset:3px;border-radius:3px}
.nv a[aria-current=page]{color:#1a1a2e;font-weight:600;border-bottom-color:#4361ee}
.nv .brand{color:#1a1a2e;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
font-size:12px;border:0}
.nv .brand:hover{border-bottom-color:transparent}
.nv .sp{flex:1}
.nv .env{color:#94a3b8;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
</style>
<nav class="nv" aria-label="Sections de l'atelier">
<a class="brand" href="/">Kleos</a>
<a href="/" __A_ATELIER__>Atelier</a>
<a href="/cms" __A_CMS__>Profil</a>
<a href="/edit" __A_EDIT__>JSON brut</a>
<span class="sp"></span><span class="env">reseau prive</span>
</nav>"""

_FORM = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Atelier — Kleos</title><style>
body{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:820px;margin:32px auto;padding:0 20px;color:#1a1a2e}
h1{font-size:22px;margin:0 0 4px}p.sub{color:#666;margin-top:0}
textarea{width:100%;min-height:220px;border:1px solid #ccd;border-radius:8px;padding:12px;font-size:14px;font-family:inherit}
textarea:focus,select:focus,button:focus-visible{outline:2px solid #4361ee;outline-offset:2px}
.row{display:flex;gap:12px;align-items:center;margin:12px 0;flex-wrap:wrap}
label.lb{font-size:12px;color:#64748b}
select,button{padding:10px 14px;border-radius:8px;font-size:14px}
select{border:1px solid #ccd;background:#fff}
button{background:#4361ee;color:#fff;border:none;cursor:pointer}
button.alt{background:#fff;color:#1a1a2e;border:1px solid #ccd}
button.warn{background:#c0392b;color:#fff;margin-top:12px}
button:disabled{opacity:.45;cursor:progress}
#status{font-size:13px;margin:14px 0 0;min-height:1.2em}#status.ko{color:#c0392b;font-weight:600}
table.gd{border-collapse:collapse;width:100%;margin-top:14px;font-size:13px}
table.gd th,table.gd td{border:1px solid #e2e8f0;padding:7px 9px;text-align:left;vertical-align:top}
table.gd th{background:#f8fafc;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#64748b}
table.gd td.mot{color:#c0392b;white-space:nowrap;font-family:ui-monospace,Consolas,monospace}
</style></head><body>
__NAV__
<h1>Atelier CV ciblé</h1>
<p class="sub">Colle une fiche de poste. Le CV est filtré vers les expériences pertinentes ;
la lettre est rédigée puis <strong>vérifiée phrase par phrase</strong> contre ton profil —
une affirmation qui ne trace pas bloque l'export.</p>
<label class="lb" for="job">Fiche de poste</label>
<textarea id="job" placeholder="Colle la fiche de poste ici..."></textarea>
<div class="row">
  <label class="lb" for="lang">Langue</label>
  <select id="lang"><option value="fr">Français</option><option value="en">English</option></select>
  <label class="lb" for="template">Gabarit</label>
  <select id="template" title="Gabarit de mise en forme">__TEMPLATES__</select>
</div>
<div class="row">
  <button id="b-pdf" data-route="/generate"
          onclick="lancer(this.dataset.route)">CV ciblé (PDF)</button>
  <button id="b-docx" class="alt" data-route="/generate-docx"
          onclick="lancer(this.dataset.route)">CV ATS (.docx)</button>
  <button id="b-lt" class="alt" data-route="/generate-letter"
          onclick="lancer(this.dataset.route)">Lettre ancrée (PDF)</button>
</div>
<p id="status" role="status" aria-live="polite"></p>
<div id="panneau"></div>
<script>
const TOKEN=__TOKEN__;   // jeton anti-CSRF : injecté par le serveur qui sert cette page
const BTNS=['b-pdf','b-docx','b-lt'];
function val(id){return document.getElementById(id).value}
function occupe(v){BTNS.forEach(function(i){document.getElementById(i).disabled=v})}
function dire(t,ko){var s=document.getElementById('status');s.textContent=t;s.className=ko?'ko':''}
function vider(){document.getElementById('panneau').textContent=''}

async function lancer(route,generique){
  const job=val('job').trim();
  vider();
  if(!job){dire('Fiche vide.',true);return}
  occupe(true);
  dire(generique?'Génération (générique assumé)...'
                :'Génération... plusieurs minutes possibles (LLM local).');
  try{
    const r=await fetch(route,{method:'POST',
      headers:{'Content-Type':'application/json','X-Atelier-Token':TOKEN},
      body:JSON.stringify({job:job,lang:val('lang'),template:val('template'),
                           generique:!!generique})});
    if(r.status===409){await refus(r,route);return}
    if(!r.ok)throw new Error('HTTP '+r.status);
    await telecharger(r);
  }catch(e){dire('Erreur: '+e.message,true)}
  finally{occupe(false)}
}

// Deux refus DISTINCTS : le ciblage (rien n'a été rédigé, réarmable) et l'ancrage
// (la lettre existe mais sur-affirme — on montre quoi corriger).
async function refus(r,route){
  if(r.headers.get('X-CV-Grounding')==='blocked'){
    const v=await r.json();
    dire('Lettre REFUSÉE : '+v.blocking.length+" affirmation(s) sans ancrage. Rien n'est sorti.",true);
    ancrage(v);return;
  }
  dire(await r.text(),true);
  rearmer(route);
}

function ancrage(v){
  const p=document.getElementById('panneau');
  const t=document.createElement('table');t.className='gd';
  const th=document.createElement('thead');
  th.innerHTML='<tr><th>#</th><th>Phrase</th><th>Motif</th></tr>';
  const tb=document.createElement('tbody');
  (v.blocking||[]).forEach(function(b){
    const tr=document.createElement('tr');
    const txt=(b.phrase!=null&&v.sentences&&v.sentences[b.phrase-1])
              ?v.sentences[b.phrase-1]:(b.affirmation||'');
    // textContent, JAMAIS innerHTML : ces phrases viennent du LLM. Une lettre
    // portant du balisage ne doit pas s'exécuter dans une page qui détient le
    // jeton anti-CSRF et le profil entier.
    [[b.phrase==null?'—':b.phrase,''],[txt,''],[b.reason||'',
      'mot']].forEach(function(c){
      const td=document.createElement('td');td.textContent=c[0];
      if(c[1])td.className=c[1];tr.appendChild(td)});
    tb.appendChild(tr)});
  t.appendChild(th);t.appendChild(tb);p.appendChild(t);
}

function rearmer(route){
  const b=document.createElement('button');b.className='warn';
  b.textContent='Générer quand même (document GÉNÉRIQUE)';
  b.onclick=function(){lancer(route,true)};
  document.getElementById('panneau').appendChild(b);
}

async function telecharger(r){
  // Le nom vient du SERVEUR : lui seul sait si le ciblage a eu lieu, et le nom du
  // fichier est la seule part du verdict qui survive à la fermeture de l'onglet.
  const m=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/);
  const nom=m?m[1]:'document';
  const blob=await r.blob();
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download=nom;a.click();URL.revokeObjectURL(url);
  const degrade=r.headers.get('X-CV-Degrade')==='1';
  dire((degrade?'[!] GÉNÉRIQUE — ':'')+nom+' téléchargé'
       +(r.headers.get('X-CV-Grounding')==='ok'?' · ancrage vérifié':'')
       +' (ciblage '+(r.headers.get('X-CV-Target')||'?')+')',degrade);
}
</script></body></html>"""


_EDIT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>JSON brut — Kleos</title><style>
body{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:900px;margin:30px auto;padding:0 20px;color:#1a1a2e}
h1{font-size:20px}a{color:#4361ee}
textarea{width:100%;min-height:58vh;border:1px solid #ccd;border-radius:8px;padding:12px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
.row{display:flex;gap:16px;align-items:center;margin:12px 0;flex-wrap:wrap}
label.cb{font-size:13px}
button{background:#4361ee;color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:14px;cursor:pointer}button:disabled{opacity:.5}
#status{font-size:13px}#status.ok{color:#159957}
#errs{color:#c0392b;font-size:13px;white-space:pre-wrap;margin-top:8px}
</style></head><body>
__NAV__
<h1>Éditer le profil (profile.json)</h1>
<p style="color:#666;font-size:13px">Validé (validate_profile) avant écriture atomique. Le site public s'hydrate de ce fichier.</p>
<textarea id="p" spellcheck="false"></textarea>
<div class="row">
  <button id="go" onclick="save()">Valider &amp; Enregistrer</button>
  <label class="cb"><input type="checkbox" id="regen"> Régénérer la banque préfab</label>
  <label class="cb"><input type="checkbox" id="commit"> Committer localement</label>
  <label class="cb"><input type="checkbox" id="govern"> Pipeline gouverné (historise · revue · graphe · rebuild)</label>
  <span id="status"></span>
</div>
<div id="errs"></div>
<script>
var TOKEN = __TOKEN__;   // jeton anti-CSRF injecté par le serveur
var P = __PROFILE__;
document.getElementById('p').value = P;
async function save(){
  var btn=document.getElementById('go'),st=document.getElementById('status'),er=document.getElementById('errs');
  er.textContent='';st.textContent='Validation...';st.className='';btn.disabled=true;
  try{
    var r=await fetch('/save',{method:'POST',
      headers:{'Content-Type':'application/json','X-Atelier-Token':TOKEN},
      body:JSON.stringify({json:document.getElementById('p').value,
        regen:document.getElementById('regen').checked,
        commit:document.getElementById('commit').checked,
        govern:document.getElementById('govern').checked})});
    var res=await r.json();
    if(res.stages){
      var s=res.stages, parts=[];
      if(s.history)parts.push('snapshot '+(s.history.snapshot||'—'));
      if(s.review)parts.push(s.review.available?('revue '+(s.review.notes.length?s.review.notes.length+' note(s)':'RAS')):'revue LLM indispo');
      if(s.graph)parts.push('graphe '+s.graph.nodes+'n/'+s.graph.edges+'a');
      if(s.rebuild)parts.push(s.rebuild.skipped?'rebuild sauté':(s.rebuild.ok?'rebuild ok':'REBUILD ÉCHOUÉ'));
      st.textContent=res.ok?('Gouverné \u2713 — '+parts.join(' · ')):'Refusé';st.className=res.ok?'ok':'';
      if(!res.ok)er.textContent=(res.errors||[]).join(String.fromCharCode(10));
      else if(s.review&&s.review.notes&&s.review.notes.length)er.textContent='Revue LLM:'+String.fromCharCode(10)+'- '+s.review.notes.join(String.fromCharCode(10)+'- ');
    } else if(res.ok){st.textContent='Enregistré. '+((res.actions||[]).join(', '));st.className='ok';}
    else{st.textContent='Refusé ('+res.errors.length+' erreur(s))';er.textContent=res.errors.join('\\n');}
  }catch(e){st.textContent='Erreur: '+e.message;}
  btn.disabled=false;
}
</script></body></html>"""


# Sous-projet D — CMS : édition STRUCTURÉE (formulaires) du même profile.json.
# La page charge le profil ENTIER, mute un sous-arbre via CMSModel (pur, immuable)
# et resoumet l'ENTIER à /save → govern_save. Aucun second chemin d'écriture, et
# aucune clé non modélisée n'est perdue (cf. assets/js/cms-model.js).
_CMS = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Profil — Kleos</title><style>
body{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#1a1a2e}
h1{font-size:20px;margin:0 0 4px}a{color:#4361ee}
.sub{color:#666;font-size:13px;margin:0 0 16px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.tab{padding:7px 13px;border:1px solid #ccd;border-radius:8px;background:#fff;cursor:pointer;font-size:14px}
.tab.on{background:#4361ee;color:#fff;border-color:#4361ee}
.cols{display:grid;grid-template-columns:270px 1fr;gap:18px;align-items:start}
.list{border:1px solid #e3e6f0;border-radius:10px;overflow:hidden}
.row{padding:9px 11px;border-bottom:1px solid #eef;cursor:pointer;font-size:14px;display:flex;justify-content:space-between;gap:8px}
.row:last-child{border-bottom:0}
.row.on{background:#eef2ff;font-weight:600}
.row .ord{color:#99a;font-size:12px;white-space:nowrap}
.form{border:1px solid #e3e6f0;border-radius:10px;padding:16px}
label{display:block;font-size:12.5px;color:#556;margin:11px 0 3px;font-weight:600}
input[type=text],textarea{width:100%;border:1px solid #ccd;border-radius:7px;padding:8px;font-size:13.5px;font-family:inherit}
textarea{min-height:76px;resize:vertical}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.pair .lg{font-size:11px;color:#89a;text-transform:uppercase;letter-spacing:.4px}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:16px 0 0}
button{padding:8px 13px;border-radius:8px;border:1px solid #ccd;background:#fff;cursor:pointer;font-size:13.5px}
button.primary{background:#4361ee;color:#fff;border-color:#4361ee}
button.danger{color:#c0392b;border-color:#f0c4bd}
#status{font-size:13px;color:#666}#status.ok{color:#159957}#status.err{color:#c0392b}
#errs{color:#c0392b;font-size:12.5px;white-space:pre-wrap;margin-top:8px}
.hint{background:#f6f8ff;border:1px solid #e3e6f0;border-radius:8px;padding:9px 11px;font-size:12.5px;color:#556;margin-bottom:14px}
</style></head><body>
__NAV__
<h1>Profil — édition structurée</h1>
<p class="sub">Les modifications passent par le <b>pipeline gouverné</b> (historique · validation · revue LLM · écriture atomique · graphe · rebuild), exactement comme l'éditeur JSON.</p>
<div class="hint">Le profil est chargé <b>entier</b> et resoumis <b>entier</b> : les sections non éditables ici (parcours, ikigai, méta…) sont préservées à l'identique.</div>
<div class="tabs" id="tabs"></div>
<div class="cols">
  <div><div class="list" id="list"></div>
    <div class="bar"><button id="add">+ Ajouter</button></div></div>
  <div class="form" id="form"></div>
</div>
<div class="bar">
  <button class="primary" id="save">Enregistrer (pipeline gouverné)</button>
  <span id="status"></span>
</div>
<div id="errs"></div>
<script src="/assets/js/cms-model.js"></script>
<script>
var TOKEN = __TOKEN__;   // jeton anti-CSRF injecté par le serveur
var profile = JSON.parse(__PROFILE__);
var M = window.CMSModel, type = "experiences", group = null, idx = 0, dirty = false;
var $ = function (id) { return document.getElementById(id); };
function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function lab(o){ return (o && (o.fr || o.en)) || ""; }

function renderTabs() {
  var h = Object.keys(M.TYPES).map(function (t) {
    return '<button class="tab' + (t === type ? " on" : "") + '" data-t="' + t + '">' + esc(lab(M.TYPES[t].label)) + "</button>";
  }).join("");
  var gs = M.groupsOf(profile, type);
  if (gs.length) {
    if (group === null || gs.indexOf(group) < 0) group = gs[0];
    h += ' <span style="width:14px"></span>' + gs.map(function (g) {
      return '<button class="tab' + (g === group ? " on" : "") + '" data-g="' + esc(g) + '">' + esc(g) + "</button>";
    }).join("");
  } else { group = null; }
  $("tabs").innerHTML = h;
  Array.prototype.forEach.call($("tabs").querySelectorAll("[data-t]"), function (b) {
    b.onclick = function () { type = b.dataset.t; group = null; idx = 0; renderAll(); };
  });
  Array.prototype.forEach.call($("tabs").querySelectorAll("[data-g]"), function (b) {
    b.onclick = function () { group = b.dataset.g; idx = 0; renderAll(); };
  });
}

function renderList() {
  var items = M.listItems(profile, type, group), tf = M.TYPES[type].titleField;
  if (idx >= items.length) idx = Math.max(0, items.length - 1);
  $("list").innerHTML = items.map(function (it, i) {
    var t = it && it[tf]; t = (t && typeof t === "object") ? lab(t) : (t || "(sans titre)");
    return '<div class="row' + (i === idx ? " on" : "") + '" data-i="' + i + '"><span>' + esc(t) +
           '</span><span class="ord">' + (i + 1) + "/" + items.length + "</span></div>";
  }).join("") || '<div class="row">(vide)</div>';
  Array.prototype.forEach.call($("list").querySelectorAll("[data-i]"), function (r) {
    r.onclick = function () { idx = +r.dataset.i; renderAll(); };
  });
}

/* La FORME est lue sur la valeur réelle (M.fieldShape), jamais supposée : dans
   profile.json `projects.name` est bilingue sur 2 entrées et une chaîne simple sur
   15. Un rendu piloté par la déclaration afficherait un champ VIDE sur ces 15 et
   remplacerait la vraie valeur à la première frappe. */
function langsFor(f, item) {
  var s = M.fieldShape(item, f);
  return (s === "bi" || s === "biLines" || s === "biList") ? ["fr", "en"] : [null];
}

function fieldHtml(f, item) {
  var h = "<label>" + esc(lab(f.label)) + "</label>";
  var multi = (f.type === "lines" || f.type === "textarea");
  function one(lg) {
    var id = "f_" + f.name + (lg ? "_" + lg : ""), val = M.readField(item, f, lg);
    if (f.type === "bool") return '<input type="checkbox" id="' + id + '"' + (val ? " checked" : "") + ">";
    if (multi) return '<textarea id="' + id + '">' + esc(val) + "</textarea>";
    return '<input type="text" id="' + id + '" value="' + esc(val) + '">';
  }
  var lgs = langsFor(f, item);
  if (lgs.length === 2) {
    return h + '<div class="pair"><div><div class="lg">fr</div>' + one("fr") +
           '</div><div><div class="lg">en</div>' + one("en") + "</div></div>";
  }
  return h + one(null);
}

function renderForm() {
  var items = M.listItems(profile, type, group), item = items[idx];
  if (!item) { $("form").innerHTML = "<p style='color:#889'>Aucun élément. Utilisez « + Ajouter ».</p>"; return; }
  $("form").innerHTML = M.TYPES[type].fields.map(function (f) { return fieldHtml(f, item); }).join("") +
    '<div class="bar"><button id="up">↑ Monter</button><button id="down">↓ Descendre</button>' +
    '<button class="danger" id="del">Supprimer</button></div>';
  M.TYPES[type].fields.forEach(function (f) {
    langsFor(f, item).forEach(function (lg) {
      var el = $("f_" + f.name + (lg ? "_" + lg : ""));
      if (el) el.oninput = el.onchange = function () { commitField(f, lg, el); };
    });
  });
  $("up").onclick = function () { profile = M.moveItem(profile, type, idx, -1, group); if (idx > 0) idx--; touch(); };
  $("down").onclick = function () { profile = M.moveItem(profile, type, idx, 1, group); idx++; touch(); };
  $("del").onclick = function () {
    if (!confirm("Supprimer cet élément ?")) return;
    profile = M.removeItem(profile, type, idx, group); touch();
  };
}

function commitField(f, lg, el) {
  var raw = (f.type === "bool") ? el.checked : el.value;
  var item = M.listItems(profile, type, group)[idx];
  var patch = M.writeField(item, f, lg, raw);   // réécrit DANS LA FORME COURANTE
  if (!patch) {   // ex. texte saisi dans un champ numérique : refus explicite
    setStatus("Valeur numérique invalide — non enregistrée", "err");
    return;
  }
  profile = M.updateItem(profile, type, idx, patch, group);
  dirty = true; setStatus("Modifié (non enregistré)", "");
  renderList();   // le titre de la liste suit l'édition
}

function touch() { dirty = true; renderAll(); setStatus("Modifié (non enregistré)", ""); }
function setStatus(msg, cls) { var s = $("status"); s.textContent = msg; s.className = cls || ""; }
function renderAll() { renderTabs(); renderList(); renderForm(); }

$("add").onclick = function () {
  profile = M.addItem(profile, type, group);
  idx = M.listItems(profile, type, group).length - 1; touch();
};

$("save").onclick = function () {
  var b = $("save"); b.disabled = true; $("errs").textContent = ""; setStatus("Enregistrement…", "");
  fetch("/save", { method: "POST",
    headers: { "Content-Type": "application/json", "X-Atelier-Token": TOKEN },
    body: JSON.stringify({ json: JSON.stringify(profile, null, 2), govern: true }) })
    .then(function (r) { return r.json(); })
    .then(function (res) {
      if (res.ok) {
        dirty = false;
        var s = res.stages || {}, parts = [];
        if (s.history) parts.push("snapshot " + (s.history.snapshot || "—"));
        if (s.review) parts.push(s.review.available ? ("revue " + (s.review.notes.length ? s.review.notes.length + " note(s)" : "RAS")) : "revue LLM indispo");
        if (s.graph) parts.push("graphe " + s.graph.nodes + "n/" + s.graph.edges + "a");
        if (s.rebuild) parts.push(s.rebuild.skipped ? "rebuild sauté"
                                  : (s.rebuild.ok ? "rebuild ok" : "REBUILD ÉCHOUÉ"));
        // Le rebuild est POST-écriture : son échec ne annule pas l'enregistrement,
        // mais doit être dit franchement plutôt que confondu avec « sauté ».
        setStatus("Enregistré ✓ — " + parts.join(" · "), s.rebuild && s.rebuild.ok === false ? "err" : "ok");
        var notes = [];
        if (s.rebuild && s.rebuild.ok === false)
          notes.push("Rebuild du site ÉCHOUÉ (profil bien enregistré) : " + s.rebuild.error);
        if (s.review && s.review.notes && s.review.notes.length)
          notes.push("Revue LLM:\\n- " + s.review.notes.join("\\n- "));
        $("errs").textContent = notes.join("\\n\\n");
      } else {
        setStatus("Refusé (" + (res.errors || []).length + " erreur(s))", "err");
        $("errs").textContent = (res.errors || []).join("\\n");
      }
    })
    .catch(function (e) { setStatus("Erreur: " + e.message, "err"); })
    .then(function () { b.disabled = false; });
};

window.onbeforeunload = function () { if (dirty) return "Modifications non enregistrées."; };
renderAll();
</script></body></html>"""

# Fichiers statiques servis à la page CMS : ALLOWLIST stricte (aucun chemin
# arbitraire ne remonte jusqu'au disque — pas de traversée possible).
_STATIC_ALLOW = {"/assets/js/cms-model.js": "application/javascript; charset=utf-8"}


# ══════════════════ Garde d'origine des requêtes (anti-CSRF) ══════════════════
#
# Écouter sur 127.0.0.1 ne protège de rien. Un POST en `Content-Type: text/plain`
# est une « requête simple » au sens CORS : le navigateur l'émet SANS preflight,
# depuis n'importe quelle page ouverte pendant que l'atelier tourne. Or les routes
# de l'atelier ÉCRIVENT sur le disque et peuvent déclencher un `git commit`.
# Quatre gardes indépendantes, toutes obligatoires sur les routes mutantes :
#   1. `Host` dans une allowlist locale — barre le DNS rebinding ;
#   2. `Origin`/`Referer` étranger refusé ;
#   3. `Content-Type` strictement JSON — c'est ce qui referme la fenêtre de la
#      « requête simple » : un JSON cross-origin exige un preflight, auquel on ne
#      répond pas (501, aucun en-tête CORS accordé — c'est la clé de voûte de
#      cette garde-là, gardée par `test_le_preflight_cors_n_est_pas_accorde`) ;
#   4. jeton tiré au démarrage, injecté dans les pages que l'atelier sert lui-même,
#      exigé en en-tête. Une page tierce ne peut pas le lire (same-origin policy).
# Plus un plafond sur `Content-Length`, appliqué AVANT toute lecture du corps.

CSRF_HEADER = "X-Atelier-Token"
MAX_BODY_BYTES = 4 * 1024 * 1024          # profile.json ≈ 46 Kio : marge large
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

# ── Trois bornes de temps, trois problèmes distincts ─────────────────────────
#
# REQUEST_TIMEOUT_S — durée qu'une opération socket peut passer SANS progresser
#   (ligne de requête, en-têtes, lecture du corps). Sans elle, une connexion qui
#   annonce `Content-Length: 4000000` et n'émet jamais rien retient son fil de
#   service indéfiniment. Mesuré avant correctif : une telle connexion occupait
#   le serveur 5,01 s (le temps du drainage) et un `GET /` LÉGITIME émis pendant
#   ce blocage n'obtenait sa réponse qu'au bout de 4,66 s — c'est une famine,
#   pas seulement une occupation.
#
# LINGER_IDLE_S / LINGER_TOTAL_S — fermeture courtoise, seule façon de faire
#   PARVENIR la réponse sans ingérer le corps. Elle s'applique à TOUTE réponse,
#   pas aux seuls refus : le chemin qui perdait le plus de réponses n'était pas
#   un refus (cf. `Handler.finish`, mesures à l'appui).
REQUEST_TIMEOUT_S = 5.0
LINGER_IDLE_S = 0.25
LINGER_TOTAL_S = 3.0

_TOKEN = secrets.token_urlsafe(32)


def csrf_token() -> str:
    """Jeton anti-CSRF de la session serveur courante."""
    return _TOKEN


def reset_csrf_token() -> str:
    """Tire un jeton neuf — appelé au démarrage du serveur (cf. `main`)."""
    global _TOKEN
    _TOKEN = secrets.token_urlsafe(32)
    return _TOKEN


def _bind() -> str:
    """Adresse d'écoute. Loopback par défaut — l'exposition est un acte DÉLIBÉRÉ.

    `ATELIER_BIND=0.0.0.0` est requis pour servir depuis un conteneur, où la
    frontière n'est plus l'interface réseau mais le pod. Le défaut ne change pas :
    lancé à la main sur le poste, l'atelier reste inatteignable du réseau.
    """
    import os
    return os.environ.get("ATELIER_BIND", "127.0.0.1").strip() or "127.0.0.1"


def _hosts_autorises() -> frozenset:
    """Hôtes acceptés dans `Host`. Le loopback TOUJOURS, plus `ATELIER_HOSTS`.

    L'allowlist ne se remplace pas, elle s'étend : un déploiement qui ajoute
    `kleos.elysium.local` ne doit pas, au passage, fermer l'accès local par lequel
    on diagnostique le déploiement lui-même.
    """
    import os
    sup = os.environ.get("ATELIER_HOSTS", "")
    return _LOCAL_HOSTS | frozenset(h.strip().lower() for h in sup.split(",") if h.strip())


def _hostport_ok(value: Optional[str], port: int) -> bool:
    """En-tête `Host` : nom dans l'allowlist ET port du serveur."""
    if not value:
        return False
    try:
        parts = urllib.parse.urlsplit("//" + value.strip())
        host, got = parts.hostname, parts.port
    except ValueError:                      # port non numérique, IPv6 malformée…
        return False
    if host is None or host.lower() not in _hosts_autorises():
        return False
    # Derrière un ingress, `Host` ne porte pas de port : `got is None` l'accepte.
    return got is None or got == port


_ERR_CLIENT = "Erreur interne — le détail est dans la console de l'atelier."


def _render(template: str, profile_raw: Optional[str] = None,
            page: str = "") -> str:
    """Injecte la navigation, le jeton, puis le profil dans une page de l'atelier.

    L'ORDRE est un invariant de sécurité, pas une commodité : navigation et jeton
    d'abord, profil ensuite. Le profil est une donnée ÉDITABLE, donc non fiable ;
    s'il contenait `__TOKEN__` ou `__NAV__`, l'ordre inverse l'y remplacerait au
    lieu de servir la page — et injecterait du balisage dans le champ d'édition.

    `page` marque l'onglet courant (`aria-current`) : sans lui la barre indique où
    l'on peut aller, jamais où l'on est.
    """
    nav = _NAV
    for cle, ident in (("__A_ATELIER__", "atelier"), ("__A_CMS__", "cms"),
                       ("__A_EDIT__", "edit")):
        nav = nav.replace(cle, 'aria-current="page"' if page == ident else "")
    out = template.replace("__NAV__", nav).replace("__TOKEN__", json.dumps(csrf_token()))
    if profile_raw is not None:
        out = out.replace("__PROFILE__", json.dumps(profile_raw).replace("<", "\\u003c"))
    return out


def _url_ok(value: str, port: int) -> bool:
    """En-têtes `Origin`/`Referer` : même allowlist, schéma http(s) exigé.

    `Origin: null` (iframe sandbox, file://) est refusé par l'absence d'HÔTE,
    pas par celle du schéma : mesuré, `urlsplit("null")` rend `hostname=None`,
    et retirer le contrôle de schéma ne le laisse toujours pas passer.

    Ce que le contrôle de schéma défend vraiment, et lui seul : une autorité
    locale portée par un schéma exotique — `ftp://127.0.0.1:<port>` a bien
    `hostname='127.0.0.1'` et le bon port, donc il passerait l'allowlist.
    """
    try:
        parts = urllib.parse.urlsplit(value.strip())
        host, got = parts.hostname, parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    if host is None or host.lower() not in _hosts_autorises():
        return False
    return got is None or got == port


class Handler(http.server.BaseHTTPRequestHandler):
    # HTTP/1.0 : la connexion se ferme après UNE requête, donc une instance de
    # Handler par requête. Ce n'est pas un détail — deux mécanismes en dépendent :
    #   · un refus répond SANS lire le corps ; en keep-alive, les octets du corps
    #     resteraient dans le flux et seraient lus comme la requête suivante ;
    #   · aucun état par-requête n'a besoin d'être réinitialisé entre requêtes.
    # L'invariant est tenu par `test_une_connexion_ne_sert_qu_une_requete` :
    # passer en HTTP/1.1 le fait rougir, et c'est bien le but.
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):  # silencieux
        pass

    def setup(self):
        super().setup()
        # Borne lue à CHAQUE requête (et non figée à la définition de la classe) :
        # un test doit pouvoir la resserrer sans reconstruire le serveur.
        try:
            self.connection.settimeout(REQUEST_TIMEOUT_S)
        except OSError:
            pass

    def _send(self, code: int, ctype: str, body: bytes, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # ── garde d'origine ──────────────────────────────────────────────────────
    def _port(self) -> int:
        return int(self.server.server_address[1])

    def _fermeture_courtoise(self) -> None:
        """Fait PARVENIR la réponse déjà écrite, puis ferme (« lingering close »).

        Fermer un socket qui porte encore des octets non lus fait émettre un RST
        par la pile Windows. Le RST purge le tampon de réception du client, qui
        perd alors la réponse **pourtant déjà écrite** (`WinError 10053/10054`) :
        la garde a bloqué, mais elle est devenue muette.

        Le premier correctif drainait le corps AVANT de répondre. Il ne tenait
        qu'à délai de lecture nul. Mesuré, client réaliste, corps de 4 194 315 o
        réellement émis (le plafond est à 4 194 304) :

            refus 413, délai 0,00 s →  1/30 perdu   · 0,05 s → 30/30 · 0,30 s → 30/30
            refus 403, délai 0,00 s →  7/30 perdus  · 0,05 s → 30/30 · 0,30 s → 30/30

        Autrement dit : la réponse n'arrivait que si le client lisait dans la
        milliseconde. Aucun navigateur ne fait ça.

        Le drainage AVANT réponse ne pouvait pas y répondre : hors plafond, il
        refuse de lire (c'est sa raison d'être), donc il ferme sur un résidu.
        La séquence correcte est l'inverse, et elle ne lit rien de la requête :

          1. la réponse est écrite et poussée ;
          2. `shutdown(SHUT_WR)` : le client reçoit un FIN — fin de réponse
             explicite, aucune fermeture brutale ;
          3. on jette (`recv` dans un tampon de 64 Kio, rien n'est conservé, rien
             n'est rendu à l'appelant) ce que le client a encore en vol, jusqu'à
             son EOF ; borné par `LINGER_IDLE_S` (rien n'arrive → on part) et par
             `LINGER_TOTAL_S` (plafond dur) ;
          4. la fermeture trouve alors un tampon vide : pas de RST.

        Le plafond garde tout son sens : aucun octet hors plafond n'entre dans le
        traitement de la requête — le refus est émis AVANT, sans attendre le
        corps (`test_le_refus_part_sans_attendre_le_corps`), et l'empreinte
        mémoire de cette étape est O(64 Kio) quelle que soit la taille annoncée.

        RÉSIDU ASSUMÉ, borné et non masqué : un client qui continuerait d'émettre
        au-delà de `LINGER_TOTAL_S` après avoir reçu le FIN retomberait sur le
        RST. Aucun client HTTP ne fait ça — recevoir la réponse et le FIN pendant
        un envoi est précisément le signal d'arrêt.
        """
        self.close_connection = True
        try:
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
        except OSError:
            return                       # le client est déjà parti : rien à sauver
        precedent = self.connection.gettimeout()
        limite = time.monotonic() + LINGER_TOTAL_S
        try:
            while True:
                restant = limite - time.monotonic()
                if restant <= 0:
                    break
                self.connection.settimeout(min(LINGER_IDLE_S, restant))
                if not self.connection.recv(65536):
                    break                # EOF : plus rien en vol, fermeture propre
        except OSError:
            pass
        finally:
            try:
                self.connection.settimeout(precedent)
            except OSError:
                pass

    def finish(self):
        """SEUL point de sortie : toute réponse se termine par une fermeture
        courtoise, qu'elle soit un refus ou un succès.

        La première version ne l'appliquait qu'aux refus, et seulement si
        `Content-Length` était lisible et strictement positif. Trois chemins y
        échappaient, et le DÉFAUT 1 s'y rejouait à l'identique — mesuré, corps de
        5 242 891 o réellement émis, 30 tirs par délai de lecture :

            CL négatif (-1)        0,00 s → 0/30 · 0,05 s → 22/30 · 0,30 s → 30/30
            CL illisible (abc)     0,00 s → 0/30 · 0,05 s → 25/30 · 0,30 s → 30/30
            CL absent, corps émis  0,00 s → 1/30 · 0,05 s → 26/30 · 0,30 s → 30/30

        Les deux premiers sont des refus dont le drapeau « corps en vol » était
        calculé à partir de la taille ANNONCÉE — or elle vaut 0 dès qu'elle est
        illisible ou négative, alors que le client, lui, émet bel et bien ses
        octets. Le troisième n'est même pas un refus : sans `Content-Length` le
        corps n'est pas lu, la réponse est un 200 ordinaire, et elle se perd de
        la même façon. Le défaut n'était donc pas dans `_refuse` : il était dans
        l'idée qu'on peut savoir à l'avance s'il reste des octets. On ne peut pas.

        D'où ce point unique. Il n'y a plus de drapeau à mal calculer, donc plus
        de chemin qui l'oublie. Le coût est un fil de service retenu au plus
        `LINGER_IDLE_S` quand le client garde son canal d'écriture ouvert sans
        rien envoyer ; le CLIENT, lui, n'attend pas — il a reçu le FIN avant que
        le nettoyage ne commence (`test_le_client_n_attend_pas_la_fin_du_nettoyage`).
        """
        self._fermeture_courtoise()
        super().finish()

    def _refuse(self, code: int, motif: str):
        """Refus sobre côté client, motif complet dans la console de l'atelier."""
        print(f"[atelier] refus {code} : {motif} — {self.command} {self.path} "
              f"host={self.headers.get('Host')!r} origin={self.headers.get('Origin')!r}",
              file=sys.stderr)
        self._send(code, "text/plain; charset=utf-8", motif.encode("utf-8"))

    def _guard_mutation(self) -> Optional[tuple[int, str]]:
        """None si la requête est légitime, sinon `(code, motif)`."""
        port = self._port()
        if not _hostport_ok(self.headers.get("Host"), port):
            return 403, "hote non autorise"
        for nom in ("Origin", "Referer"):
            v = self.headers.get(nom)
            if v is not None and not _url_ok(v, port):
                return 403, f"{nom.lower()} etranger"
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return 415, "Content-Type doit etre application/json"
        given = (self.headers.get(CSRF_HEADER) or "").encode("utf-8", "replace")
        if not secrets.compare_digest(given, csrf_token().encode("ascii")):
            return 403, "jeton anti-CSRF absent ou invalide"
        return None

    def do_GET(self):
        # Le `Host` est filtré même en lecture : /edit et /cms embarquent le profil
        # ENTIER et le jeton, qu'un rebinding DNS rendrait lisibles à un tiers.
        if not _hostport_ok(self.headers.get("Host"), self._port()):
            return self._refuse(403, "hote non autorise")
        if self.path == "/" or self.path.startswith("/?"):
            # Composition des deux substitutions de gabarit. L'ORDRE n'est pas
            # arbitraire : `_render` pose le jeton d'ABORD, pour qu'un contenu
            # injecté ensuite (les ids venus de cv/templates/*.json) ne puisse pas
            # introduire la chaîne `__TOKEN__`.
            self._send(200, "text/html; charset=utf-8",
                       _page(_render(_FORM, page="atelier")).encode("utf-8"))
        elif self.path == "/edit":
            raw = _PROFILE.read_text(encoding="utf-8")
            self._send(200, "text/html; charset=utf-8",
                       _render(_EDIT, raw, page="edit").encode("utf-8"))
        elif self.path == "/cms":
            raw = _PROFILE.read_text(encoding="utf-8")
            self._send(200, "text/html; charset=utf-8",
                       _render(_CMS, raw, page="cms").encode("utf-8"))
        elif urllib.parse.urlsplit(self.path).path in _STATIC_ALLOW:
            # urlsplit : `?v=1` (cache-busting) ne doit pas faire échouer l'allowlist
            p = urllib.parse.urlsplit(self.path).path
            self._send(200, _STATIC_ALLOW[p], (_ROOT / p.lstrip("/")).read_bytes())
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        refus = self._guard_mutation()
        if refus is not None:
            return self._refuse(*refus)
        brut = self.headers.get("Content-Length")
        try:
            length = int(brut) if brut is not None else 0
        except ValueError:
            return self._refuse(400, "Content-Length invalide")
        if length < 0:
            return self._refuse(400, "Content-Length invalide")
        if length > MAX_BODY_BYTES:
            # Souverain : on refuse SANS lire un octet du corps. La réponse est
            # rendue livrable par la fermeture courtoise, pas par une ingestion.
            return self._refuse(413, f"corps trop volumineux (plafond {MAX_BODY_BYTES} octets)")
        lu = self.rfile.read(length)
        # Le corps ANNONCÉ est consommé — ce qui ne dit rien de ce que le client
        # a réellement émis. C'est `finish` qui referme proprement, dans tous les cas.
        try:
            body = lu.decode("utf-8")
        except UnicodeDecodeError:
            return self._refuse(400, "corps non-UTF-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._send(400, "text/plain", b"bad json")
        if self.path == "/generate":
            return self._handle_generate(data)
        if self.path == "/generate-docx":
            return self._handle_generate_docx(data)
        if self.path == "/generate-letter":
            return self._handle_generate_letter(data)
        if self.path == "/save":
            return self._handle_save(data)
        self._send(404, "text/plain", b"not found")

    #: Types MIME des artefacts livrables, par extension.
    _MIME = {".pdf": "application/pdf",
             ".docx": "application/vnd.openxmlformats-officedocument"
                      ".wordprocessingml.document"}

    @staticmethod
    def _entree(data):
        """Champs communs aux trois générateurs, normalisés une seule fois."""
        return (str(data.get("job", "")),
                "en" if data.get("lang") == "en" else "fr",
                bool(data.get("generique")))

    def _livrer(self, cfg, octets: bytes, ext: str, accepte: bool):
        """Applique le VERDICT DE CIBLAGE à un artefact déjà produit.

        Partagé par le CV et le .docx : deux artefacts issus du même pipeline
        doivent obéir à la même politique, sinon l'un devient la porte dérobée
        de l'autre.
        """
        tag = f"{cfg.get('relevance_key')}~{cfg.get('min_relevance')}"
        degrade = ciblage_degrade(cfg)
        v = verdict_ciblage(cfg, accepter_generique=accepte)
        nom = v["nom"].rsplit(".", 1)[0] + ext
        if not v["livrer"]:
            # 409 : la requête est licite, l'ÉTAT ne permet pas d'y répondre.
            return self._send(409, "text/plain; charset=utf-8",
                              v["message"].encode("utf-8"),
                              {"X-CV-Target": tag, "X-CV-Degrade": "1"})
        self._send(200, self._MIME[ext], octets, {
            "Content-Disposition": f'attachment; filename="{nom}"',
            "X-CV-Target": tag,
            "X-CV-Degrade": "1" if degrade else "0",
            "X-CV-Message": urllib.parse.quote(v["message"]),
        })

    def _handle_generate(self, data):
        try:
            job, lang, accepte = self._entree(data)
            profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
            cfg, pdf = generate_pdf(job, profile, lang,
                                    template=data.get("template") or None)
            self._livrer(cfg, pdf, ".pdf", accepte)
        except Exception:
            # Le détail (chemins, clés, trace) reste côté serveur. Zero Masking :
            # rien n'est avalé — la trace complète part dans la console de l'atelier,
            # seul le client n'en obtient qu'un constat.
            traceback.print_exc()
            self._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))

    def _handle_generate_docx(self, data):
        try:
            job, lang, accepte = self._entree(data)
            profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
            cfg, docx = generate_docx(job, profile, lang)
            self._livrer(cfg, docx, ".docx", accepte)
        except Exception:
            traceback.print_exc()
            self._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))

    def _handle_generate_letter(self, data):
        """Lettre ancrée. Deux portes distinctes, deux refus distincts.

        Un `409` sans corps JSON = le CIBLAGE a échoué (rien n'a été rédigé).
        Un `409` avec `{blocking, sentences}` = la lettre existe mais son ANCRAGE
        est rouge : on renvoie les phrases fautives et leur motif. Confondre les
        deux refus condamnerait à deviner lequel des deux s'est produit.
        """
        try:
            job, lang, accepte = self._entree(data)
            from datetime import date
            profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
            cfg, verdict, pdf = generate_letter(
                job, profile, lang, skeleton=str(data.get("skeleton") or "standard"),
                today=date.today().strftime("%d/%m/%Y"), accepter_generique=accepte)
            tag = f"{cfg.get('relevance_key')}~{cfg.get('min_relevance')}"
            if verdict is None:                       # porte 1 : ciblage
                msg = verdict_ciblage(cfg)["message"]
                return self._send(409, "text/plain; charset=utf-8", msg.encode("utf-8"),
                                  {"X-CV-Target": tag, "X-CV-Degrade": "1"})
            if pdf is None:                           # porte 2 : ancrage
                corps = json.dumps({"blocking": verdict.get("blocking"),
                                    "sentences": verdict.get("sentences"),
                                    "referentiel": verdict.get("referentiel")},
                                   ensure_ascii=False).encode("utf-8")
                return self._send(409, "application/json; charset=utf-8", corps,
                                  {"X-CV-Target": tag, "X-CV-Grounding": "blocked"})
            self._send(200, "application/pdf", pdf, {
                "Content-Disposition": 'attachment; filename="lettre.pdf"',
                "X-CV-Target": tag,
                "X-CV-Grounding": "ok",
                "X-CV-Degrade": "1" if ciblage_degrade(cfg) else "0",
            })
        except Exception:
            traceback.print_exc()
            self._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))

    def _handle_save(self, data):
        try:
            if data.get("govern"):
                import profile_pipeline
                from datetime import datetime
                ts = datetime.now().strftime("%Y%m%dT%H%M%S")
                report = profile_pipeline.govern_save(
                    str(data.get("json", "")), _PROFILE,
                    _ROOT / "data" / "profile_history", _ROOT / "data" / "profile_graph.json",
                    ts, do_rebuild=bool(data.get("rebuild", True)))
                return self._send(200, "application/json; charset=utf-8",
                                  json.dumps(report, ensure_ascii=False).encode("utf-8"))
            res = save_profile_edit(str(data.get("json", "")), _PROFILE)
            if res["ok"]:
                actions = []
                if data.get("regen"):
                    _regen_bank(); actions.append("banque régénérée")
                if data.get("commit"):
                    _git_commit(_ROOT, ["profile.json", "cv/prefab"],
                                "chore(cv): edition profile via atelier")
                    actions.append("committé local")
                res["actions"] = actions
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(res, ensure_ascii=False).encode("utf-8"))
        except Exception:
            traceback.print_exc()   # idem : la trace va à la console, pas au client
            self._send(500, "application/json; charset=utf-8",
                       json.dumps({"ok": False, "errors": [_ERR_CLIENT]},
                                  ensure_ascii=False).encode("utf-8"))


class AtelierServer(http.server.ThreadingHTTPServer):
    """Un fil de service par connexion.

    Borner le temps passé sur une requête qui n'avance pas était nécessaire, mais
    pas suffisant : sur un serveur mono-fil, la borne devient simplement la durée
    de la famine. Mesuré avant correctif — une connexion hostile annonçant
    `Content-Length: 4000000` sans rien émettre occupait le serveur 5,01 s, et un
    `GET /` LÉGITIME lancé pendant ce blocage n'était servi qu'à 4,66 s. Le client
    légitime payait l'attaque.

    Écriture concurrente : les routes mutantes exigent le jeton anti-CSRF (une
    page tierce n'obtient donc pas de fil d'écriture), et l'écriture de
    `profile.json` passe par `os.replace` (atomique). Le risque résiduel est
    « dernier arrivé gagne » entre deux onglets du propriétaire — jamais un
    fichier à moitié écrit.
    """
    daemon_threads = True


def make_server(port: int = 0) -> http.server.HTTPServer:
    """Fabrique LE serveur de l'atelier — celui de `main` comme celui des tests.

    Point d'entrée unique volontaire : un test qui reconstruirait son propre
    `HTTPServer` validerait une version reconstituée, pas l'artefact livré.
    """
    return AtelierServer((_bind(), port), Handler)


def main(port: int = 8010) -> int:
    reset_csrf_token()   # un jeton neuf par démarrage de serveur
    srv = make_server(port)
    adresse = _bind()
    print(f"[atelier] http://{adresse}:{port}  (Ctrl+C pour arrêter)")
    if adresse not in _LOCAL_HOSTS:
        # Bruyant par construction : deux gardes viennent de tomber d'un coup
        # (l'écoute loopback ET l'implicite « seul l'utilisateur local parle »).
        # Ce qui les remplace est HORS de ce processus — il doit le dire.
        print(f"[atelier] ATTENTION — écoute sur {adresse}, plus seulement en local.\n"
              f"[atelier]   Cette page sert le PROFIL ENTIER et sait ÉCRIRE profile.json.\n"
              f"[atelier]   Le contrôle d'accès doit être assuré EN AMONT (ingress :\n"
              f"[atelier]   basicAuth + tailnet-only). Hôtes acceptés : "
              f"{', '.join(sorted(_hosts_autorises()))}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
