"""Espace « Profil & CV » : générateurs, gabarits et handlers de l'atelier (déplacés
depuis atelier.py, comportement inchangé). Aucun import de server."""
from __future__ import annotations

import json
import pathlib
import sys
import traceback
import urllib.parse
from datetime import date
from typing import Callable, Optional

from tools.cockpit import config
from tools.cockpit.pages import layout

import cv_pdf      # noqa: E402  (test_cv_templates patche cv_target.* via ce module)
import cv_render   # noqa: E402
import cv_target   # noqa: E402

_ROOT = config.SITE_ROOT
_PROFILE = _ROOT / "profile.json"   # les tests le rebindent sur une copie : doit rester ICI
_ERR_CLIENT = "Erreur interne — le détail est dans la console de l'atelier."


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


#: Types MIME des artefacts livrables, par extension.
_MIME = {".pdf": "application/pdf",
         ".docx": "application/vnd.openxmlformats-officedocument"
                  ".wordprocessingml.document"}


def entree(data):                      # ex Handler._entree (998-1003)
    """Champs communs aux trois générateurs, normalisés une seule fois."""
    return (str(data.get("job", "")),
            "en" if data.get("lang") == "en" else "fr",
            bool(data.get("generique")))


def livrer(h, cfg, octets: bytes, ext: str, accepte: bool):   # ex Handler._livrer (1005-1026), self→h
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
        return h._send(409, "text/plain; charset=utf-8",
                       v["message"].encode("utf-8"),
                       {"X-CV-Target": tag, "X-CV-Degrade": "1"})
    h._send(200, _MIME[ext], octets, {
        "Content-Disposition": f'attachment; filename="{nom}"',
        "X-CV-Target": tag,
        "X-CV-Degrade": "1" if degrade else "0",
        "X-CV-Message": urllib.parse.quote(v["message"]),
    })


def handle_generate(h, data):          # ex Handler._handle_generate (1028-1046), self→h, self._entree→entree, self._livrer→livrer
    try:
        job, lang, accepte = entree(data)
        profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
        # `str(...)` comme le `skeleton` de _handle_letter deux methodes plus bas :
        # coercion A LA FRONTIERE. Sans elle, un dict traversait jusqu'a
        # `cv_render._css_du_template`, qui le passait tel quel a `build_css` en
        # court-circuitant la validation — des valeurs choisies par le client
        # atterrissaient dans le <style> rendu par Chromium.
        demande = data.get("template")
        cfg, pdf = generate_pdf(job, profile, lang,
                                template=str(demande) if demande else None)
        livrer(h, cfg, pdf, ".pdf", accepte)
    except Exception:
        # Le détail (chemins, clés, trace) reste côté serveur. Zero Masking :
        # rien n'est avalé — la trace complète part dans la console de l'atelier,
        # seul le client n'en obtient qu'un constat.
        traceback.print_exc()
        h._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))


def handle_generate_docx(h, data):     # ex 1048-1056
    try:
        job, lang, accepte = entree(data)
        profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
        cfg, docx = generate_docx(job, profile, lang)
        livrer(h, cfg, docx, ".docx", accepte)
    except Exception:
        traceback.print_exc()
        h._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))


def handle_generate_letter(h, data):   # ex 1058-1093
    """Lettre ancrée. Deux portes distinctes, deux refus distincts.

    Un `409` sans corps JSON = le CIBLAGE a échoué (rien n'a été rédigé).
    Un `409` avec `{blocking, sentences}` = la lettre existe mais son ANCRAGE
    est rouge : on renvoie les phrases fautives et leur motif. Confondre les
    deux refus condamnerait à deviner lequel des deux s'est produit.
    """
    try:
        job, lang, accepte = entree(data)
        profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
        cfg, verdict, pdf = generate_letter(
            job, profile, lang, skeleton=str(data.get("skeleton") or "standard"),
            today=date.today().strftime("%d/%m/%Y"), accepter_generique=accepte)
        tag = f"{cfg.get('relevance_key')}~{cfg.get('min_relevance')}"
        if verdict is None:                       # porte 1 : ciblage
            msg = verdict_ciblage(cfg)["message"]
            return h._send(409, "text/plain; charset=utf-8", msg.encode("utf-8"),
                           {"X-CV-Target": tag, "X-CV-Degrade": "1"})
        if pdf is None:                           # porte 2 : ancrage
            corps = json.dumps({"blocking": verdict.get("blocking"),
                                "sentences": verdict.get("sentences"),
                                "referentiel": verdict.get("referentiel")},
                               ensure_ascii=False).encode("utf-8")
            return h._send(409, "application/json; charset=utf-8", corps,
                           {"X-CV-Target": tag, "X-CV-Grounding": "blocked"})
        h._send(200, "application/pdf", pdf, {
            "Content-Disposition": 'attachment; filename="lettre.pdf"',
            "X-CV-Target": tag,
            "X-CV-Grounding": "ok",
            "X-CV-Degrade": "1" if ciblage_degrade(cfg) else "0",
        })
    except Exception:
        traceback.print_exc()
        h._send(500, "text/plain; charset=utf-8", _ERR_CLIENT.encode("utf-8"))


def handle_save(h, data):              # ex 1095-1123 ; `_PROFILE`, `_ROOT`, `save_profile_edit`, `_regen_bank`, `_git_commit` = globaux de CE module
    try:
        if data.get("govern"):
            import profile_pipeline
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            report = profile_pipeline.govern_save(
                str(data.get("json", "")), _PROFILE,
                _ROOT / "data" / "profile_history", _ROOT / "data" / "profile_graph.json",
                ts, do_rebuild=bool(data.get("rebuild", True)))
            return h._send(200, "application/json; charset=utf-8",
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
        h._send(200, "application/json; charset=utf-8",
               json.dumps(res, ensure_ascii=False).encode("utf-8"))
    except Exception:
        traceback.print_exc()   # idem : la trace va à la console, pas au client
        h._send(500, "application/json; charset=utf-8",
               json.dumps({"ok": False, "errors": [_ERR_CLIENT]},
                          ensure_ascii=False).encode("utf-8"))


def page_atelier(h) -> None:
    h._send(200, "text/html; charset=utf-8",
            _page(layout.render(_FORM, h.token(), page="atelier")).encode("utf-8"))


def page_edit(h) -> None:
    raw = _PROFILE.read_text(encoding="utf-8")
    h._send(200, "text/html; charset=utf-8", layout.render(_EDIT, h.token(), raw, page="edit").encode("utf-8"))


def page_cms(h) -> None:
    raw = _PROFILE.read_text(encoding="utf-8")
    h._send(200, "text/html; charset=utf-8", layout.render(_CMS, h.token(), raw, page="cms").encode("utf-8"))
