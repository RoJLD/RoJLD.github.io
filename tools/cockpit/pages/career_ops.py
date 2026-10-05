"""Page career-ops : ce que l'interface web de career-ops ne sait pas (entonnoir kpi.mjs, à faire
dans l'ordre de send-queue, alertes agent-inbox, file d'envoi, dossiers), les workflows sans LLM,
« J'ai postulé » et le copilote à la demande. Chaque panneau nomme son état (« lu à HH:MM »,
source vieille de N h, erreur) — spec § 8.
Recadrage 2026-10-05 : le web de career-ops (Pipeline, fiche d'offre, Follow-ups, CV, « Ask »)
est l'interface de travail des candidatures ; la page n'en garde qu'une synthèse et un bouton
qui l'ouvre sur la bonne route (`/followups`, `/pipeline`, `/pipeline/<n>`).
« À faire » suit l'ordre de send-queue (amendement 2026-10-03) : la priorité appartient à la file."""
from __future__ import annotations

import html
import json
from pathlib import Path

from tools.cockpit import career_ops as co, config, copilote, web
from tools.cockpit.pages import accueil, layout

_JS = """
function cheminValide(c){
  return typeof c==='string' && c.startsWith('/') && !c.includes('//') && !c.includes(':');
}
function joindre(url, chemin){ return (url.endsWith('/')?url.slice(0,-1):url)+chemin; }
async function envoyer(route, obj, chemin){
  const out=document.getElementById('sortie'); out.textContent='… en cours ('+route+')';
  const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json','X-Atelier-Token':TOKEN},body:JSON.stringify(obj)});
  let t=await r.text(); try{t=JSON.stringify(JSON.parse(t),null,2)}catch(e){}
  out.textContent=(r.ok?'OK ':'REFUS '+r.status+' ')+t;
  if(r.ok){ try{const j=JSON.parse(t); if(j.url){window.open(chemin?joindre(j.url,chemin):j.url,'_blank');}}catch(e){} }
}
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{
  const id=b.dataset.action, ecrit=b.dataset.ecrit;
  if(b.dataset.confirme==='1' && !confirm('Lancer '+id+' ? Il écrit : '+ecrit)) return;
  envoyer('/career-ops/action',{id:id,confirme:b.dataset.confirme==='1'});
});
document.querySelectorAll('[data-n]').forEach(b=>b.onclick=()=>{
  const n=parseInt(b.dataset.n,10), note=prompt('Note (optionnelle, une ligne) pour le rapport '+n+' :','')||'';
  if(!confirm('Enregistrer le rapport '+n+' comme candidature ENVOYÉE ? (set-status écrit le tracker)')) return;
  envoyer('/career-ops/postule',{n:n,note:note});
});
document.querySelectorAll('[data-route]').forEach(b=>b.onclick=()=>{
  const chemin=b.dataset.chemin;
  if(chemin!==undefined && !cheminValide(chemin)){
    document.getElementById('sortie').textContent='REFUS chemin invalide : '+chemin; return;
  }
  envoyer(b.dataset.route,{},chemin);
});
"""

_VIVACITE = {"active": "active", "expired": "disparue", "uncertain": "incertaine"}


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def md_vers_html(texte: str) -> str:
    """Markdown rendu si la lib est là (requirements.txt), sinon <pre> échappé. Jamais rien."""
    try:
        import markdown  # absent de l'image Kleos (requirements-atelier.txt) : repli visible
    except ImportError:
        return "<pre>" + html.escape(texte) + "</pre>"
    return markdown.markdown(texte, extensions=["tables", "fenced_code"])


def _panneau(titre: str, contenu: str, lu_a: str | None = None, age_h=None, erreur: str | None = None) -> str:
    meta = " · ".join(x for x in (f"lu à {lu_a}" if lu_a else "", f"source vieille de {age_h} h" if age_h is not None else "") if x)
    corps = f'<p class="ko">{html.escape(erreur)}</p>' if erreur else contenu
    return f'<section><h2>{html.escape(titre)} <span class="muet">{html.escape(meta)}</span></h2>{corps}</section>'


def _pouls(p: dict) -> str:
    f = p.get("followups") or {}
    morceaux = [f"conversations sur 28 j : {_e(p.get('conversations28'))}",
                f"envois 7 j / 28 j : {_e(p.get('sends7'))} / {_e(p.get('sends28'))}",
                f"entrantes sur 28 j : {_e(p.get('inbound28'))}",
                f"relances dues : {_e(f.get('due'))} (en retard : {_e(f.get('overdue'))})"]
    if f.get("next"):
        morceaux.append(f"prochaine : {_e(f.get('next'))}")
    return "<p>" + " · ".join(morceaux) + "</p>"


def _canaux(canaux: list[dict]) -> str:
    rows = "".join(f"<tr><td>{_e(c.get('label') or c.get('channel'))}</td><td>{_e(c.get('evaluated'))}</td>"
                   f"<td>{_e(c.get('aboveThreshold'))}</td><td>{_e(c.get('applied'))}</td><td>{_e(c.get('responded'))}</td>"
                   f"<td>{_e(c.get('interview'))}</td></tr>" for c in canaux)
    return ("<table><tr><th>Canal</th><th>Évaluées</th><th>Au-dessus du seuil</th><th>Envoyées</th><th>Réponses</th>"
            f"<th>Entretiens</th></tr>{rows}</table>")


def _pistes_kpi(pistes: list[dict]) -> str:
    rows = "".join(f"<tr><td>{_e(t.get('label') or t.get('id'))}</td><td>{_e(t.get('threshold'))}</td><td>{_e(t.get('evaluated'))}</td>"
                   f"<td>{_e(t.get('aboveThreshold'))}</td><td>{_e(t.get('applied'))}</td><td>{_e(t.get('conversations28'))}</td>"
                   f"<td>{_e(t.get('ready'))}</td><td>{_e(t.get('hours'))} h</td></tr>" for t in pistes)
    return ("<h3>Par piste</h3><table><tr><th>Piste</th><th>Seuil</th><th>Évaluées</th><th>Au-dessus</th><th>Envoyées</th>"
            f"<th>Conversations 28 j</th><th>Prêts</th><th>Heures</th></tr>{rows}</table>")


def _entonnoir(kpi: dict) -> str:
    lignes = []
    for k in kpi.get("kpis", []):
        if k["state"] == "computable":
            val = f'{k["numerator"]} / {k["denominator"]} ({k["value"]} %)'
        else:
            val = f'verrouillé — débloqué par : {k.get("unlock") or "?"}'
        lignes.append(f"<tr><td>{html.escape(k['label'])}</td><td>{html.escape(val)}</td></tr>")
    out = f'<table>{"".join(lignes)}</table><p class="muet">étape : {html.escape(str(kpi.get("stage")))} · seuil {kpi.get("threshold")}</p>'
    if kpi.get("pulse"):
        out += _pouls(kpi["pulse"])
    if kpi.get("channels"):
        out += _canaux(kpi["channels"])
    if kpi.get("tracks"):
        out += _pistes_kpi(kpi["tracks"])
    return out


def _ouvrir(chemin: str, libelle: str) -> str:
    """Bouton qui ouvre l'interface web de career-ops sur `chemin` (lancée au besoin, en loopback).
    `chemin` ne vient que de constantes ou d'un entier : jamais d'une donnée de career-ops."""
    return f'<button data-route="/career-ops/ouvrir-web" data-chemin="{_e(chemin)}">{html.escape(libelle)}</button>'


def _ouvrir_rapport(n: int | None) -> str:
    return _ouvrir(f"/pipeline/{int(n)}", "Ouvrir") if n else ""


def _vivacite(item: dict) -> str:
    l = item.get("liveness")
    if not l:
        return "jamais vérifiée"
    return f"{_VIVACITE.get(l.get('verdict'), l.get('verdict'))} ({l.get('date')})"


def _a_faire_file(items: list[dict]) -> str:
    rows = []
    for it in items:
        n = co.numero_item(it)
        bouton = (f'<button data-n="{n}">J\'ai postulé</button> ' + _ouvrir_rapport(n)) if n else ""
        feu = (it.get("decision") or {}).get("state")
        effort = (it.get("why") or {}).get("effort")
        rows.append(f"<tr><td>{_e(it.get('company'))}</td><td>{_e(it.get('role'))}</td><td>{_e(it.get('score'))}</td>"
                    f"<td>{_e(it.get('piste'))}</td><td>{_e(_vivacite(it))}</td><td>{_e(it.get('waitingDays'))} j</td>"
                    f"<td>{_e(effort)} h</td><td>{_e(feu or '')}</td><td>{bouton}</td></tr>")
    if not rows:
        return "<p>Aucun dossier prêt dans la file.</p>"
    return ('<p class="muet">Ordre de la file d\'envoi de career-ops (valeur × perte hebdomadaire ÷ effort).</p>'
            "<table><tr><th>Entreprise</th><th>Rôle</th><th>Note</th><th>Piste</th><th>Annonce</th><th>Attente</th>"
            f"<th>Effort</th><th>Feu vert</th><th></th></tr>{''.join(rows)}</table>")


def _a_faire_repli(lignes: list[dict], erreur: str) -> str:
    rows = []
    for l in co.a_faire(lignes):
        n = co.numero_rapport(l)
        bouton = (f'<button data-n="{n}">J\'ai postulé</button> ' + _ouvrir_rapport(n)) if n else ""
        rows.append(f"<tr><td>{_e(l.get('company'))}</td><td>{_e(l.get('role'))}</td>"
                    f"<td>{_e(l.get('score'))}</td><td>{bouton}</td></tr>")
    tete = f'<p class="ko">File d\'envoi illisible ({html.escape(erreur)}) : repli sur le tri par note, sans priorité.</p>'
    corps = (f'<table><tr><th>Entreprise</th><th>Rôle</th><th>Note</th><th></th></tr>{"".join(rows)}</table>'
             if rows else "<p>Rien au-dessus du seuil.</p>")
    return tete + corps


def _file_envoi(fj: dict) -> str:
    st = fj.get("stats") or {}
    out = (f"<p>{_e(st.get('ready'))} prêt(s) · {_e(st.get('hours'))} h pour vider la file · "
           f"plus ancien : {_e(st.get('oldest'))} ({_e(st.get('oldestDays'))} j) · "
           f"pertes attendues : {_e(st.get('expectedLostPerWeek'))} dossier(s) par semaine</p>")
    rows = []
    for p in fj.get("perTrack") or []:
        t, wip = p.get("track") or {}, p.get("wip") or {}
        depasse = " — limite dépassée" if wip.get("exceeded") else ""
        rows.append(f"<tr><td>{_e(t.get('label') or t.get('id'))}</td><td>{_e(wip.get('count'))} / {_e(wip.get('limit'))}{depasse}</td>"
                    f"<td>{_e(p.get('hours'))} h</td></tr>")
    if rows:
        out += f"<table><tr><th>Piste</th><th>Prêts / limite</th><th>Heures</th></tr>{''.join(rows)}</table>"
    morts = fj.get("dead") or []
    if morts:
        out += "<h3>Annonces disparues</h3><ul>" + "".join(
            f"<li>{_e(d.get('company'))} #{_e(d.get('num'))} — {_e(d.get('role'))} : {_e(_vivacite(d))}</li>" for d in morts) + "</ul>"
    return out


def _relances(rel: dict) -> str:
    """Synthèse seule (entrées = relances en retard, --overdue-only) : le suivi des relances se travaille dans l'onglet Follow-ups du web."""
    m = rel.get("metadata", {})
    dates = [str(e["nextFollowupDate"]) for e in rel.get("entries", []) if e.get("nextFollowupDate")]
    ancienne = f" · la plus ancienne en retard : {html.escape(min(dates))}" if dates else ""
    return (f"<p>{m.get('overdue', 0)} en retard · {m.get('urgent', 0)} urgentes · {m.get('waiting', 0)} en attente "
            f"(sur {m.get('totalTracked', 0)} suivies){ancienne}</p>"
            f"<p>{_ouvrir('/followups', 'Ouvrir les relances dans career-ops')}</p>")


def _candidatures(lignes: list[dict]) -> str:
    """Comptes par statut seuls : le pipeline se travaille dans le web de career-ops."""
    comptes: dict[str, int] = {}
    for l in lignes:
        comptes[str(l.get("status"))] = comptes.get(str(l.get("status")), 0) + 1
    tete = " · ".join(f"{html.escape(s)} : {n}" for s, n in sorted(comptes.items()))
    return f"<p>{tete}</p><p>{_ouvrir('/pipeline', 'Ouvrir le pipeline dans career-ops')}</p>"


def _workflows() -> str:
    b = []
    for c in co.COMMANDES.values():
        b.append(f'<button data-action="{c.id}" data-ecrit="{html.escape(c.ecrit)}" data-confirme="{1 if c.confirmation else 0}">'
                 f'{html.escape(c.id)}</button> <span class="muet">écrit : {html.escape(c.ecrit)} · {c.delai_s} s max</span><br>')
    return ("".join(b) + '<p>Candidatures, CV sur mesure, candidature assistée et assistant « Ask » : interface web de career-ops. '
            '<button data-route="/career-ops/ouvrir-web">Ouvrir career-ops (interface web)</button> '
            '<button data-route="/career-ops/copilote">Ouvrir une session copilote</button></p>')


def _dossiers(ds: list[dict]) -> str:
    rows = "".join(f"<tr><td>{html.escape(d['entreprise'])}</td><td>{html.escape(d['dossier'])}</td><td>{d['version']}</td>"
                   f"<td>{html.escape(', '.join(d['fichiers']))}</td></tr>" for d in ds)
    return f"<table>{rows}</table>" if rows else "<p>Aucun dossier dans output/.</p>"


def page_career_ops(h) -> None:
    pre = co.prerequis()
    # « Ergon » (ἔργον, l'œuvre) = la facette carrière d'Anthropos dans le canon (SIGIL-1707).
    # L'app Ergon est gelée (D10) ; le nom vit ici, sur l'espace qui fait ce travail (décision Robin 2026-09-29).
    if not pre["ok"]:
        corps = "<h1>Ergon · career-ops</h1>" + "".join(f'<p class="ko">{html.escape(p)}</p>' for p in pre["problemes"])
        return h._send(200, "text/html; charset=utf-8", layout.page("Ergon · career-ops", corps, h.token(), "career-ops").encode("utf-8"))
    root = Path(pre["career_ops_root"])
    kpi, tr, rel, fi = co.lire_kpi(root), co.lire_tracker(root), co.lire_relances(root), co.lire_file(root)
    inbox = co.lire_texte(root, "data/agent-inbox.md")
    if fi["ok"]:
        a_faire = _panneau("À faire maintenant", _a_faire_file(co.file_a_envoyer(fi["donnees"])), fi["lu_a"])
    else:
        a_faire = _panneau("À faire maintenant", _a_faire_repli(tr["donnees"] or [], fi["erreur"]), tr["lu_a"], erreur=tr["erreur"])
    corps = "<h1>Ergon · career-ops</h1><pre id=\"sortie\" class=\"muet\">(la sortie des actions s'affiche ici)</pre>"
    corps += _panneau("Entonnoir", _entonnoir(kpi["donnees"] or {}), kpi["lu_a"], erreur=kpi["erreur"])
    corps += a_faire
    corps += _panneau("Relances dues", _relances(rel["donnees"] or {}), rel["lu_a"], erreur=rel["erreur"])
    corps += _panneau("Candidatures (tracker)", _candidatures(tr["donnees"] or []), tr["lu_a"], erreur=tr["erreur"])
    corps += _panneau("Alertes (agent-inbox.md)", md_vers_html(inbox["texte"]), age_h=inbox["age_h"], erreur=inbox["erreur"])
    corps += _panneau("Workflows", _workflows())
    corps += _panneau("File d'envoi (send-queue)", _file_envoi(fi["donnees"] or {}), fi["lu_a"], erreur=fi["erreur"])
    corps += _panneau("Dossiers (output/)", _dossiers(co.lire_dossiers(root)))
    corps += f"<script>{_JS}</script>"
    h._send(200, "text/html; charset=utf-8", layout.page("Ergon · career-ops", corps, h.token(), "career-ops").encode("utf-8"))


def _json(h, code: int, obj: dict) -> None:
    h._send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def post_action(h, data: dict) -> None:
    cmd_id = str(data.get("id", ""))
    if cmd_id not in co.COMMANDES:   # refus à la frontière HTTP, avant tout appel
        return _json(h, 400, {"ok": False, "erreur": f"commande inconnue : {cmd_id!r}"})
    try:
        res = co.executer(cmd_id, confirme=data.get("confirme") is True)
    except ValueError as exc:
        return _json(h, 400, {"ok": False, "erreur": str(exc)})
    except co.ActionEnCours as exc:
        return _json(h, 409, {"ok": False, "erreur": f"action déjà en cours : {exc}"})
    except RuntimeError as exc:
        return _json(h, 503, {"ok": False, "erreur": str(exc)})
    return _json(h, 200, {"ok": res["code"] == 0 and not res["interrompu"], **res})


def post_postule(h, data: dict) -> None:
    n, note = data.get("n"), data.get("note", "")
    if not isinstance(n, int) or isinstance(n, bool) or not isinstance(note, str):
        return _json(h, 400, {"ok": False, "erreur": "n doit être un entier, note une chaîne"})
    try:
        res = co.postule(n, note)
    except ValueError as exc:
        return _json(h, 400, {"ok": False, "erreur": str(exc)})
    except co.ActionEnCours as exc:
        return _json(h, 409, {"ok": False, "erreur": f"action déjà en cours : {exc}"})
    except RuntimeError as exc:
        return _json(h, 503, {"ok": False, "erreur": str(exc)})
    return _json(h, 200, {"ok": res["code"] == 0, **res})


def _root_ou_503(h):
    root = config.career_ops_root()
    if root is None:
        _json(h, 503, {"ok": False, "problemes": ["career-ops non configuré"]})
    return root


def post_ouvrir_web(h, data: dict) -> None:
    root = _root_ou_503(h)
    if root is None:
        return
    try:
        with co.verrou_action("ouvrir-web"):
            res = web.ouvrir_web(root)
    except co.ActionEnCours as exc:
        return _json(h, 409, {"ok": False, "problemes": [f"action déjà en cours : {exc}"]})
    return _json(h, 200 if res["ok"] else 503, res)


def post_copilote(h, data: dict) -> None:
    root = _root_ou_503(h)
    if root is None:
        return
    res = copilote.ouvrir_copilote(root)
    return _json(h, 200 if res["ok"] else 503, res)


def carte_career_ops() -> dict:
    pre = co.prerequis()
    if not pre["ok"]:
        return {"titre": "Ergon · career-ops", "href": "/career-ops", "etat": "attention", "lignes": pre["problemes"]}
    kpi = co.lire_kpi(Path(pre["career_ops_root"]))
    if not kpi["ok"]:
        return {"titre": "Ergon · career-ops", "href": "/career-ops", "etat": "erreur", "lignes": [kpi["erreur"]]}
    app = next((k for k in kpi["donnees"].get("kpis", []) if k["key"] == "application_rate"), None)
    ligne = (f"Passage à la candidature : {app['numerator']} / {app['denominator']}" if app and app["state"] == "computable"
             else "Passage à la candidature : verrouillé")
    return {"titre": "Ergon · career-ops", "href": "/career-ops", "etat": "ok", "lignes": [ligne, f"lu à {kpi['lu_a']}"]}


carte_career_ops.titre, carte_career_ops.href = "Ergon · career-ops", "/career-ops"   # nom affiché si la carte sort du budget
accueil.CARTES.append(carte_career_ops)
