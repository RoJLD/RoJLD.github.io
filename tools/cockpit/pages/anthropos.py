"""Page Anthropos : le déclaré (hub) à côté du mesuré (sonde), et l'état du site public."""
from __future__ import annotations

import html

from tools.cockpit import anthropos as an, config
from tools.cockpit.pages import accueil, layout


def _ligne(r: dict) -> str:
    p = r["probe"]
    cls = {"repond": "ok", "erreur": "ko", "injoignable": "ko"}[p["etat"]]
    return (f"<tr><td>{html.escape(str(r['name']))}</td><td><a href=\"http://{html.escape(str(r['ingress_host']))}/\">{html.escape(str(r['ingress_host']))}</a></td>"
            f"<td>{html.escape(str(r['declared_status']))}</td><td class=\"{cls}\">{p['etat']} {p['code'] or ''} {html.escape(p['detail'])}</td><td>{p['ms']} ms</td></tr>")


def _site(e: dict) -> str:
    h, g, p = e["https"], e["git"], e["pages"]
    lignes = [f"HTTPS : {h['etat']} {h['code'] or ''} {html.escape(h['detail'])} ({h['ms']} ms)"]
    if g.get("ok"):
        lignes.append(f"git : local {g['head_local']} · distant {g['main_distant']} · " + ("à jour" if g["a_jour"] else "ÉCART"))
    else:
        lignes.append(f"git : {html.escape(g.get('erreur', '?'))}")
    if p.get("ok"):
        b = p["build"] or {}
        lignes.append(f"Pages : build {html.escape(str(b.get('status')))} sur {html.escape(str(b.get('commit', ''))[:9])} ({html.escape(str(b.get('updated_at')))}) · PR ouvertes : {len(p.get('pr_ouvertes') or [])}")
    else:
        lignes.append(f"Pages : {html.escape(str(p.get('erreur', '?')))}")
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lignes) + "</ul>"


def page_anthropos(h) -> None:
    apps = an.lire_apps()
    corps = f"<h1>Anthropos</h1><p class=\"muet\">hub : {html.escape(config.HUB_URL)}</p>"
    if not apps["ok"]:
        corps += f'<p class="ko">{html.escape(apps["erreur"])}</p>'
    else:
        if apps["repli"]:
            corps += '<p class="ko">le hub sert son manifeste de repli (satellite_version « ? ») : liste incomplète</p>'
        rows = "".join(_ligne(r) for r in an.sonder_apps(apps["apps"]))
        corps += f"<table><tr><th>app</th><th>hôte</th><th>déclaré</th><th>mesuré</th><th></th></tr>{rows}</table>"
    corps += "<h2>Site public</h2>" + _site(an.etat_site_public())
    h._send(200, "text/html; charset=utf-8", layout.page("Anthropos", corps, h.token(), "anthropos").encode("utf-8"))


def carte_anthropos() -> dict:
    s = an.sonder(config.HUB_URL.rstrip("/") + "/elysium/health")
    etat = "ok" if s["etat"] == "repond" else "erreur"
    return {"titre": "Anthropos", "href": "/anthropos", "etat": etat, "lignes": [f"hub : {s['etat']} {s['code'] or ''} ({s['ms']} ms)"]}


carte_anthropos.titre, carte_anthropos.href = "Anthropos", "/anthropos"   # nom affiché si la carte sort du budget
accueil.CARTES.append(carte_anthropos)
