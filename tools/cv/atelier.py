"""Σ-CV-ATELIER sous-projet C — atelier local (serveur privé, jamais exposé).

Colle une fiche de poste → CV ciblé en PDF. Réutilise tout le socle :
extract_cfg (LLM souverain) → select_experiences → render_html → Playwright PDF.

Lancer localement :  python tools/cv/atelier.py    (→ http://127.0.0.1:8010)

Non servi par GitHub Pages (stdlib http.server, single-user). Fondation du futur
CMS (sous-projet D). Le LLM passe par llm_client SIGIL-1674 (sibling ELYSIUM) ;
s'il est indisponible, extract_cfg retombe sur un cfg défaut (CV général) — loud.
"""
from __future__ import annotations

import http.server
import json
import pathlib
from typing import Any, Callable, Optional

import cv_pdf
import cv_render
import cv_target

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # repo site racine
_PROFILE = _ROOT / "profile.json"


def generate_pdf(job_posting: str, profile: dict, lang: str = "fr",
                 complete_fn: Optional[Callable[[str], str]] = None) -> tuple[dict, bytes]:
    """Pipeline ciblé complet → (cfg, pdf_bytes). Testable via complete_fn factice."""
    cfg, scv = cv_target.targeted_structured_cv(job_posting, profile, lang, complete_fn=complete_fn)
    pdf = cv_pdf.html_to_pdf_bytes(cv_render.render_html(scv))
    return cfg, pdf


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
    if validate_fn is None:
        validate_fn = _load_validate()
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [f"JSON invalide : {e}"]}
    if not isinstance(parsed, dict):
        return {"ok": False, "errors": ["Le profil doit être un objet JSON."]}
    errors = list(validate_fn(parsed))
    if errors:
        return {"ok": False, "errors": errors}
    tmp = profile_path.parent / (profile_path.name + ".tmp")
    tmp.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(profile_path)  # remplacement atomique
    return {"ok": True, "errors": []}


def _regen_bank() -> None:
    import build_cv_bank  # type: ignore
    build_cv_bank.main()


def _git_commit(repo_root: pathlib.Path, paths: list[str], message: str) -> None:
    import subprocess
    subprocess.run(["git", "-C", str(repo_root), "add", *paths], check=True)
    subprocess.run(["git", "-C", str(repo_root), "commit", "-m", message], check=True)


_FORM = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Atelier CV ciblé</title><style>
body{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#1a1a2e}
h1{font-size:22px}p.sub{color:#666}
textarea{width:100%;min-height:240px;border:1px solid #ccd;border-radius:8px;padding:12px;font-size:14px;font-family:inherit}
.row{display:flex;gap:12px;align-items:center;margin:12px 0}
select,button{padding:10px 14px;border-radius:8px;font-size:14px}
button{background:#4361ee;color:#fff;border:none;cursor:pointer}button:disabled{opacity:.5}
#status{color:#666;font-size:13px;margin-left:8px}
</style></head><body>
<h1>Atelier CV ciblé</h1>
<p style="font-size:13px"><a href="/edit" style="color:#4361ee">✎ Éditer le profil (profile.json)</a></p>
<p class="sub">Colle une fiche de poste : le CV est filtré vers les expériences les plus pertinentes puis rendu en PDF (texte réel, ATS-safe).</p>
<textarea id="job" placeholder="Colle la fiche de poste ici..."></textarea>
<div class="row">
  <select id="lang"><option value="fr">Français</option><option value="en">English</option></select>
  <button id="go" onclick="gen()">Générer le CV ciblé (PDF)</button>
  <span id="status"></span>
</div>
<script>
async function gen(){
  const btn=document.getElementById('go'),st=document.getElementById('status');
  const job=document.getElementById('job').value.trim();
  if(!job){st.textContent='Fiche vide.';return}
  btn.disabled=true;st.textContent='Génération...';
  try{
    const r=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({job:job,lang:document.getElementById('lang').value})});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const blob=await r.blob();
    const url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='cv_cible.pdf';a.click();URL.revokeObjectURL(url);
    st.textContent='PDF téléchargé. Ciblage: '+(r.headers.get('X-CV-Target')||'?');
  }catch(e){st.textContent='Erreur: '+e.message}
  btn.disabled=false;
}
</script></body></html>"""


_EDIT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Éditer le profil — Atelier CV</title><style>
body{font-family:-apple-system,"Segoe UI",Roboto,sans-serif;max-width:900px;margin:30px auto;padding:0 20px;color:#1a1a2e}
h1{font-size:20px}a{color:#4361ee}
textarea{width:100%;min-height:58vh;border:1px solid #ccd;border-radius:8px;padding:12px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
.row{display:flex;gap:16px;align-items:center;margin:12px 0;flex-wrap:wrap}
label.cb{font-size:13px}
button{background:#4361ee;color:#fff;border:none;border-radius:8px;padding:10px 16px;font-size:14px;cursor:pointer}button:disabled{opacity:.5}
#status{font-size:13px}#status.ok{color:#159957}
#errs{color:#c0392b;font-size:13px;white-space:pre-wrap;margin-top:8px}
</style></head><body>
<p><a href="/">← Atelier</a></p>
<h1>Éditer le profil (profile.json)</h1>
<p style="color:#666;font-size:13px">Validé (validate_profile) avant écriture atomique. Le site public s'hydrate de ce fichier.</p>
<textarea id="p" spellcheck="false"></textarea>
<div class="row">
  <button id="go" onclick="save()">Valider &amp; Enregistrer</button>
  <label class="cb"><input type="checkbox" id="regen"> Régénérer la banque préfab</label>
  <label class="cb"><input type="checkbox" id="commit"> Committer localement</label>
  <span id="status"></span>
</div>
<div id="errs"></div>
<script>
var P = __PROFILE__;
document.getElementById('p').value = P;
async function save(){
  var btn=document.getElementById('go'),st=document.getElementById('status'),er=document.getElementById('errs');
  er.textContent='';st.textContent='Validation...';st.className='';btn.disabled=true;
  try{
    var r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({json:document.getElementById('p').value,
        regen:document.getElementById('regen').checked,
        commit:document.getElementById('commit').checked})});
    var res=await r.json();
    if(res.ok){st.textContent='Enregistré. '+((res.actions||[]).join(', '));st.className='ok';}
    else{st.textContent='Refusé ('+res.errors.length+' erreur(s))';er.textContent=res.errors.join('\\n');}
  }catch(e){st.textContent='Erreur: '+e.message;}
  btn.disabled=false;
}
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencieux
        pass

    def _send(self, code: int, ctype: str, body: bytes, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, "text/html; charset=utf-8", _FORM.encode("utf-8"))
        elif self.path == "/edit":
            raw = _PROFILE.read_text(encoding="utf-8")
            page = _EDIT.replace("__PROFILE__", json.dumps(raw).replace("<", "\\u003c"))
            self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self._send(400, "text/plain", b"bad json")
        if self.path == "/generate":
            return self._handle_generate(data)
        if self.path == "/save":
            return self._handle_save(data)
        self._send(404, "text/plain", b"not found")

    def _handle_generate(self, data):
        try:
            job = str(data.get("job", "")); lang = "en" if data.get("lang") == "en" else "fr"
            profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
            cfg, pdf = generate_pdf(job, profile, lang)
            tag = f"{cfg.get('relevance_key')}~{cfg.get('min_relevance')}"
            self._send(200, "application/pdf", pdf, {
                "Content-Disposition": 'attachment; filename="cv_cible.pdf"',
                "X-CV-Target": tag,
            })
        except Exception as exc:  # atelier local : renvoie l'erreur lisible
            self._send(500, "text/plain; charset=utf-8", f"Erreur: {exc}".encode("utf-8"))

    def _handle_save(self, data):
        try:
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
        except Exception as exc:
            self._send(500, "application/json; charset=utf-8",
                       json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False).encode("utf-8"))


def main(port: int = 8010) -> int:
    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    print(f"[atelier] http://127.0.0.1:{port}  (Ctrl+C pour arrêter)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
