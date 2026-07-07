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
        else:
            self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path != "/generate":
            return self._send(404, "text/plain", b"not found")
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
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
