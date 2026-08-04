"""Smoke tests atelier local (cv_pdf + atelier.generate_pdf). Nécessite Playwright."""
from __future__ import annotations

import json
import pathlib
import re

import atelier
import cv_pdf
import cv_target


def test_html_to_pdf_bytes_smoke():
    pdf = cv_pdf.html_to_pdf_bytes("<!doctype html><html><body><h1>Hello Robin</h1></body></html>")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500


def test_generate_pdf_targeted_pipeline():
    profile = {
        "$updated": "2026-07-07",
        "identity": {"first_name": "Robin", "last_name": "Denis"},
        "skills": {"programming": [{"name": "Python"}]},
        "domains": [{"id": "quant", "label": {"fr": "Quant", "en": "Quant"}},
                    {"id": "risk", "label": {"fr": "Risk", "en": "Risk"}}],
        "experiences": [
            {"id": "a", "company": "ALTEN", "title": {"fr": "Quant", "en": "Quant"},
             "start": "2024", "current": True, "domains": ["quant"],
             "relevance": {"quant": 0.95, "risk": 0.3, "general": 0.6},
             "bullets": {"fr": ["Modèles Vasicek"], "en": ["Vasicek models"]}},
            {"id": "b", "company": "ManCo", "title": {"fr": "Risk", "en": "Risk"},
             "start": "2021", "current": False, "domains": ["risk"],
             "relevance": {"quant": 0.2, "risk": 0.9, "general": 0.4},
             "bullets": {"fr": ["Stress tests"], "en": ["Stress tests"]}},
        ],
    }
    fake = lambda _p: json.dumps({"relevance_key": "quant", "min_relevance": 0.9, "domains_in": ["quant"]})
    cfg, pdf = atelier.generate_pdf("Quant developer Python", profile, "en", complete_fn=fake)
    assert cfg["relevance_key"] == "quant"
    assert pdf[:4] == b"%PDF"
    # le PDF ciblé quant ne contient que ALTEN (quant>=0.9), pas ManCo
    from pypdf import PdfReader
    import io
    txt = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "ALTEN" in txt and "ManCo" not in txt
    assert "Vasicek models" in txt


# ── D : édition profile.json (save_profile_edit) — pas de Playwright ────────────

def test_save_valid_writes(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"old":1}', encoding="utf-8")
    res = atelier.save_profile_edit('{"$version":"1","new":2}', p, validate_fn=lambda d: [])
    assert res["ok"] and res["errors"] == []
    assert json.loads(p.read_text(encoding="utf-8"))["new"] == 2


def test_save_invalid_json_no_write(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"keep":1}', encoding="utf-8")
    res = atelier.save_profile_edit("{bad json", p, validate_fn=lambda d: [])
    assert not res["ok"] and any("JSON invalide" in e for e in res["errors"])
    assert p.read_text(encoding="utf-8") == '{"keep":1}'  # intact


def test_save_validation_errors_no_write(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"keep":1}', encoding="utf-8")
    res = atelier.save_profile_edit('{"x":1}', p, validate_fn=lambda d: ["missing domains", "bad radar"])
    assert not res["ok"] and res["errors"] == ["missing domains", "bad radar"]
    assert p.read_text(encoding="utf-8") == '{"keep":1}'  # intact


def test_save_rejects_non_dict(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text("{}", encoding="utf-8")
    res = atelier.save_profile_edit("[1,2,3]", p, validate_fn=lambda d: [])
    assert not res["ok"]


# ── Sous-projet D : routes du CMS (édition structurée) ────────────────────────

import contextlib
import http.server
import threading
import urllib.error
import urllib.request


@contextlib.contextmanager
def _server():
    """Lance LE serveur de l'atelier (`make_server`) sur un port éphémère.

    Volontairement `atelier.make_server` et non un `HTTPServer` reconstruit ici :
    la classe de serveur fait partie du correctif (un fil par connexion). Un
    fixture qui rebâtirait le sien validerait une version reconstituée.
    """
    srv = atelier.make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_cms_route_serves_page_with_real_profile_embedded():
    """Le CMS charge le profil ENTIER : c'est ce qui permet de le resoumettre
    entier et de ne perdre aucune clé non modélisée."""
    with _server() as base:
        code, body = _get(base, "/cms")
    assert code == 200
    assert "CMS" in body
    assert "experiences" in body and "ALTEN" in body   # vrai profile.json embarqué


def test_cms_model_asset_is_served():
    with _server() as base:
        code, body = _get(base, "/assets/js/cms-model.js")
    assert code == 200 and "CMSModel" in body


def test_static_allowlist_refuses_everything_else():
    """Allowlist stricte : aucun chemin arbitraire n'atteint le disque."""
    with _server() as base:
        for path in ("/assets/js/../../profile.json", "/profile.json",
                     "/assets/js/cv-render.js", "/../atelier.py"):
            code, _ = _get(base, path)
            assert code == 404, path


def test_le_cache_busting_ne_casse_pas_l_allowlist_statique():
    """L'allowlist porte sur le CHEMIN, pas sur l'URL brute.

    `_STATIC_ALLOW` est consultée après `urlsplit`, précisément pour qu'un
    `?v=<hash>` ne fasse pas échouer la correspondance. Personne ne le
    vérifiait : mesuré, comparer `self.path` directement rendait 404 sur
    `?v=1` — la page CMS perdait son script — et les 38 tests restaient VERTS.
    """
    with _server() as base:
        for suffixe in ("", "?v=1", "?v=deadbeef"):
            code, body = _get(base, "/assets/js/cms-model.js" + suffixe)
            assert code == 200, suffixe
            assert "CMSModel" in body, suffixe


def test_home_links_to_cms():
    with _server() as base:
        code, body = _get(base, "/")
    assert code == 200 and "/cms" in body


# ── I1 : durcissement anti-CSRF des routes mutantes ──────────────────────────
#
# L'atelier écoute sur 127.0.0.1, mais « local » ne veut pas dire « à l'abri » :
# un POST en `Content-Type: text/plain` est une *requête simple* au sens CORS —
# le navigateur l'émet SANS preflight depuis n'importe quelle page ouverte
# pendant que l'atelier tourne. Sans jeton ni contrôle d'origine, cette page
# tierce réécrit profile.json et peut déclencher un `git commit`.

import pathlib
import re
import socket
import time

_REAL_PROFILE = pathlib.Path(atelier.__file__).resolve().parents[2] / "profile.json"


def _port_of(base):
    return int(base.rsplit(":", 1)[1])


def _requete_brute(port, path, headers, body=b"", method="POST",
                   delai_lecture=0.0, fermer_ecriture=True, timeout=15):
    """Émet une requête brute et retourne les octets REÇUS (éventuellement zéro).

    Les erreurs de connexion sont rendues, jamais avalées : une réponse perdue
    doit rester visible pour l'appelant (c'est précisément ce que la régression
    du drainage doit interdire). Retourne `(octets, incident|None)`.
    """
    head = f"{method} {path} HTTP/1.1\r\n".encode("utf-8")
    for k, v in headers.items():
        head += f"{k}: {v}\r\n".encode("utf-8")
    head += b"\r\n"
    buf, incident = b"", None
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        try:
            s.sendall(head + body)
            if fermer_ecriture:
                # Signale la fin du corps. Best-effort : le serveur a pu refuser
                # et fermer avant — un `shutdown` nu lèverait alors ici et ferait
                # échouer le test pour une raison qui n'est pas la sienne.
                try:
                    s.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            if delai_lecture:
                time.sleep(delai_lecture)
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        except OSError as e:
            incident = f"{type(e).__name__}(WinError {getattr(e, 'winerror', '?')})"
    return buf, incident


def _tir(port, path, headers, body=b"", method="POST", **kw):
    """Un tir : `(code, incident)` — `code=None` quand la réponse est PERDUE.

    Ne lève pas : compter les pertes sur N tirs suppose de pouvoir en observer.
    """
    buf, incident = _requete_brute(port, path, headers, body, method, **kw)
    if not buf:
        return None, incident
    return int(buf.split(b" ", 2)[1]), incident


def _raw(port, path, headers, body=b"", method="POST", **kw):
    """Requête HTTP brute : contrôle total des en-têtes, `Host` compris.

    urllib impose son propre `Host` ; or c'est précisément l'en-tête que la garde
    doit filtrer. On parle donc au socket.
    """
    buf, incident = _requete_brute(port, path, headers, body, method, **kw)
    if not buf:
        raise AssertionError(
            f"aucune réponse reçue pour {method} {path} — incident={incident}. "
            "Le serveur a fermé la connexion avant que la réponse n'atteigne le "
            "client (corps non drainé → RST).")
    raw_head, _, raw_body = buf.partition(b"\r\n\r\n")
    return int(raw_head.split(b" ", 2)[1]), raw_body.decode("utf-8", "replace")


def _pointe_vers_une_copie(tmp_path, monkeypatch):
    """Fait viser à l'atelier une COPIE du vrai profil : le dépôt n'est jamais muté."""
    target = tmp_path / "profile.json"
    target.write_text(_REAL_PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(atelier, "_PROFILE", target)
    return target


def test_cross_origin_mutation_is_refused(tmp_path, monkeypatch):
    """RÉGRESSION I1 — la requête NON LÉGITIME doit être REFUSÉE.

    Rejoue l'exploit mesuré par l'audit : POST /save en `text/plain` (requête
    simple, aucun preflight), `Host` et `Origin` étrangers, aucun jeton, avec
    `commit: true` pour atteindre `_git_commit`. `_git_commit` est remplacé par
    un mouchard : si la garde manque, la trace le prouve sans toucher à git.
    """
    target = _pointe_vers_une_copie(tmp_path, monkeypatch)
    commits = []
    monkeypatch.setattr(atelier, "_git_commit", lambda *a, **k: commits.append(a))

    pwned = json.loads(target.read_text(encoding="utf-8"))
    pwned["identity"]["last_name"] = "PWNED"
    payload = json.dumps({"json": json.dumps(pwned), "commit": True}).encode("utf-8")

    with _server() as base:
        status, body = _raw(_port_of(base), "/save", {
            "Host": "cms.evil.example.com",
            "Origin": "https://evil.example.com",
            "Content-Type": "text/plain",
            "Content-Length": str(len(payload)),
            "Connection": "close",
        }, payload)

    apres = json.loads(target.read_text(encoding="utf-8"))["identity"]["last_name"]
    assert status == 403, f"mutation cross-origin ACCEPTÉE (HTTP {status}) : {body[:200]}"
    assert apres != "PWNED", "profile.json réécrit par une page tierce"
    assert commits == [], "un `git commit` a été déclenché par une requête cross-origin"


def _entetes_legitimes(port, **surcharges):
    """Les en-têtes qu'émet la page servie par l'atelier lui-même."""
    h = {"Host": f"127.0.0.1:{port}",
         "Origin": f"http://127.0.0.1:{port}",
         "Referer": f"http://127.0.0.1:{port}/cms",
         "Content-Type": "application/json",
         atelier.CSRF_HEADER: atelier.csrf_token(),
         "Connection": "close"}
    h.update(surcharges)
    return {k: v for k, v in h.items() if v is not None}


def _post(port, path, corps, **surcharges):
    payload = json.dumps(corps).encode("utf-8")
    h = _entetes_legitimes(port, **surcharges)
    h.setdefault("Content-Length", str(len(payload)))
    return _raw(port, path, h, payload)


# Chaque garde est éprouvée SEULE : une requête légitime sur toutes les autres
# dimensions. Sans cela, une seule garde efficace masquerait les trois inertes.

def test_missing_token_is_refused(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, **{atelier.CSRF_HEADER: None})
    assert code == 403


def test_wrong_token_is_refused(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, **{atelier.CSRF_HEADER: "x" * 43})
    assert code == 403


def test_seule_l_egalite_exacte_du_jeton_ouvre_les_routes_mutantes(tmp_path, monkeypatch):
    """Les faux jetons sont DÉRIVÉS du vrai, jamais écrits à la main.

    Mesuré 2026-07-29 : remplacer `secrets.compare_digest(given, csrf_token())` par
    `given.startswith(csrf_token()[:1])` — un préfixe d'UN caractère ouvre alors
    `/save` — laissait la suite VERTE, `test_wrong_token_is_refused` compris. Ce
    dernier n'essaie qu'un seul faux jeton, écrit à la main (`"x" * 43`) : il ne
    refuse que parce que le vrai ne commence pas par « x », soit 63 fois sur 64. Une
    liste écrite à la main dont le test est le seul lecteur ne voit pas cette classe
    de trous, et échoue à pile ou face plutôt que sur la propriété.

    Les faux sont donc fabriqués depuis le jeton RÉELLEMENT SERVI dans la page —
    la seule source qui suive le module quoi qu'il devienne : préfixe, moitié,
    troncature, rallonge, bruit autour, un caractère changé à chaque extrémité et au
    milieu. Toute comparaison plus laxiste que l'égalité (`startswith`, `in`, « les n
    premiers caractères ») rougit sur au moins l'un d'eux — et le vrai jeton doit
    continuer d'ouvrir : une garde qui mure la porte n'en est pas une.
    """
    cible = _pointe_vers_une_copie(tmp_path, monkeypatch)
    intact = cible.read_text(encoding="utf-8")
    with _server() as base:
        port = _port_of(base)
        code, page = _get(base, "/")
        assert code == 200
        m = re.search(r'const TOKEN="([^"]+)"', page)
        assert m, "la page d'accueil ne porte pas de jeton"
        jeton = m.group(1)

        def _un_caractere_change(t: str, i: int) -> str:
            return t[:i] + ("A" if t[i] != "A" else "B") + t[i + 1:]

        faux = {
            "chaîne vide": "",
            "préfixe d'un caractère": jeton[:1],
            "première moitié": jeton[:len(jeton) // 2],
            "tronqué d'un caractère": jeton[:-1],
            "privé de son premier caractère": jeton[1:],
            "rallongé d'un caractère": jeton + "A",
            "noyé dans du bruit": "A" + jeton + "A",
            "premier caractère changé": _un_caractere_change(jeton, 0),
            "caractère médian changé": _un_caractere_change(jeton, len(jeton) // 2),
            "dernier caractère changé": _un_caractere_change(jeton, len(jeton) - 1),
        }
        if jeton.swapcase() != jeton:
            faux["casse inversée"] = jeton.swapcase()
        assert jeton not in faux.values(), "un « faux » jeton est en fait le vrai"

        for nom, mauvais in faux.items():
            code, corps = _post(port, "/save", {"json": "{}"},
                                **{atelier.CSRF_HEADER: mauvais})
            assert code == 403, f"jeton ACCEPTÉ ({nom}) : {mauvais!r} → HTTP {code}"
        assert cible.read_text(encoding="utf-8") == intact, (
            "profile.json réécrit par une requête à jeton invalide")

        code, _ = _post(port, "/save", {"json": "{}"}, **{atelier.CSRF_HEADER: jeton})
        assert code == 200, "le jeton exact n'ouvre plus rien : porte murée"


def test_foreign_host_is_refused(tmp_path, monkeypatch):
    """DNS rebinding : la résolution pointe sur 127.0.0.1, le `Host` trahit."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, Host="cms.evil.example.com")
    assert code == 403


def test_host_on_another_port_is_refused(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, Host=f"127.0.0.1:{port + 1}")
    assert code == 403


def test_foreign_origin_is_refused(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, Origin="https://evil.example.com")
    assert code == 403


def test_null_origin_is_refused(tmp_path, monkeypatch):
    """`Origin: null` = iframe sandbox ou file:// — pas une origine locale."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"}, Origin="null")
    assert code == 403


def test_origin_locale_avec_un_schema_exotique_est_refusee(tmp_path, monkeypatch):
    """L'autorité peut être locale et l'origine rester illégitime.

    Ce test comble un trou MESURÉ : en mutant `_url_ok` pour supprimer le
    contrôle de schéma, les 30 tests restaient VERTS. `test_null_origin_is_refused`
    ne le défendait pas — `urlsplit("null")` rend `hostname=None`, donc `null`
    tombe sur la garde d'hôte. Sans contrôle de schéma, `ftp://127.0.0.1:<port>`
    (hôte et port corrects) passait."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        for origine in (f"ftp://127.0.0.1:{port}", f"file://127.0.0.1:{port}"):
            code, _ = _post(port, "/save", {"json": "{}"}, Origin=origine)
            assert code == 403, origine


def test_foreign_referer_is_refused(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _post(port, "/save", {"json": "{}"},
                        Origin=None, Referer="https://evil.example.com/x")
    assert code == 403


def test_non_json_content_type_is_refused(tmp_path, monkeypatch):
    """C'est cet en-tête qui faisait de l'attaque une « requête simple » : sans
    preflight. Exiger du JSON referme la fenêtre."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        for ct in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
            code, _ = _post(port, "/save", {"json": "{}"}, **{"Content-Type": ct})
            assert code == 415, ct


def test_oversized_body_is_refused(tmp_path, monkeypatch):
    """Le plafond s'applique AVANT la lecture : le corps annoncé n'est pas envoyé."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _raw(port, "/save", _entetes_legitimes(
            port, **{"Content-Length": str(atelier.MAX_BODY_BYTES + 1)}), b"{}")
    assert code == 413


# ── Un refus qui n'arrive pas n'est pas un refus ─────────────────────────────
#
# Le handler répondait puis fermait SANS avoir lu le corps. Sous Windows, fermer
# un socket qui porte des octets non lus fait émettre un RST : le RST purge le
# tampon de réception du client, qui perd la réponse pourtant déjà écrite. La
# garde bloquait bien, mais devenait muette — le navigateur voit une erreur
# réseau au lieu du motif. Mesuré avant correctif, client lisant à +0,3 s :
# 1/40 refus perdu avec un corps de la taille de `profile.json` (≈52 Kio),
# **15/15 perdus** à 3 Mio, 0/40 à 13 octets (ce corps-là tient déjà dans le
# tampon de `rfile`, donc rien ne reste côté noyau).

def _corps_taille_reelle():
    """Ce que poste réellement la page /cms : le profil ENTIER réencapsulé."""
    return json.dumps({"json": _REAL_PROFILE.read_text(encoding="utf-8"),
                       "commit": True}).encode("utf-8")


def test_refus_parvient_au_client_avec_un_corps_de_taille_reelle(tmp_path, monkeypatch):
    """Le cas PRODUIT exact : le corps qu'envoie /cms, 10 tirs.

    Honnêteté sur sa portée : la perte mesurée à cette taille est de l'ordre de
    2-5 %, donc 10 tirs ne la révèlent pas de façon fiable — ce test **documente
    et surveille** le scénario réel, il n'en est pas la garde. La garde
    déterministe est le test suivant (3 Mio, 15/15 perdus avant correctif)."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    payload = _corps_taille_reelle()
    assert len(payload) > 40_000, len(payload)   # la taille EST le déclencheur
    recus = []
    with _server() as base:
        port = _port_of(base)
        for _ in range(10):
            code, _ = _raw(port, "/save", {
                "Host": "cms.evil.example.com",
                "Origin": "https://evil.example.com",
                "Content-Type": "text/plain",
                "Content-Length": str(len(payload)),
                "Connection": "close",
            }, payload, delai_lecture=0.1)
            recus.append(code)
    assert recus == [403] * 10, recus


def test_refus_parvient_au_client_avec_un_gros_corps_sous_plafond(tmp_path, monkeypatch):
    """Même défaut, rendu déterministe : 3 Mio restent sous le plafond de 4 Mio,
    donc le corps DOIT être drainé. Avant correctif : 15/15 perdus."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    payload = b'{"json":"' + b"A" * (3 * 1024 * 1024) + b'"}'
    assert len(payload) < atelier.MAX_BODY_BYTES
    with _server() as base:
        code, _ = _raw(_port_of(base), "/save", {
            "Host": "cms.evil.example.com",
            "Origin": "https://evil.example.com",
            "Content-Type": "text/plain",
            "Content-Length": str(len(payload)),
            "Connection": "close",
        }, payload, delai_lecture=0.2)
    assert code == 403


def test_le_plafond_refuse_toujours_sans_lire_le_corps(tmp_path, monkeypatch):
    """La fermeture courtoise ne doit PAS rouvrir la porte que le plafond ferme.

    Au-delà de `MAX_BODY_BYTES`, aucun octet n'entre dans le traitement : on
    annonce un corps énorme, on n'en envoie rien et on garde le canal d'écriture
    OUVERT. Un serveur qui attendrait le corps resterait bloqué jusqu'au délai de
    garde ; ici la réponse doit être immédiate."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 5.0)
    with _server() as base:
        port = _port_of(base)
        t0 = time.monotonic()
        code, _ = _raw(port, "/save", _entetes_legitimes(
            port, **{"Content-Length": str(atelier.MAX_BODY_BYTES + 1)}),
            b"", fermer_ecriture=False)
        ecoule = time.monotonic() - t0
    assert code == 413
    assert ecoule < 2.0, f"le corps hors plafond a été lu ({ecoule:.1f}s)"


def _entetes_debut_de_reponse(port, taille_annoncee):
    return {"Host": f"127.0.0.1:{port}",
            "Origin": f"http://127.0.0.1:{port}",
            "Content-Type": "application/json",
            atelier.CSRF_HEADER: atelier.csrf_token(),
            "Content-Length": str(taille_annoncee),
            "Connection": "close"}


def _delai_premier_octet(port, headers, timeout=20):
    """Temps écoulé jusqu'au PREMIER octet de réponse, corps jamais envoyé.

    C'est la mesure qui distingue « je refuse sans lire » de « je refuse après
    avoir ingéré » : on garde le canal d'écriture ouvert et on n'émet rien.
    """
    t0 = time.monotonic()
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        head = b"POST /save HTTP/1.1\r\n"
        for k, v in headers.items():
            head += f"{k}: {v}\r\n".encode("utf-8")
        s.sendall(head + b"\r\n")
        premier = s.recv(65536)
    return time.monotonic() - t0, (int(premier.split(b" ", 2)[1]) if premier else None)


def test_le_refus_part_sans_attendre_le_corps(tmp_path, monkeypatch):
    """Le plafond n'a de sens que si le refus PRÉCÈDE l'ingestion.

    La fermeture courtoise lit-et-jette après coup ; il faut donc prouver
    séparément que la RÉPONSE, elle, part avant que le moindre octet de corps
    n'arrive. Mesure : temps jusqu'au premier octet, corps jamais émis."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 5.0)
    with _server() as base:
        port = _port_of(base)
        cas = [
            # hors plafond, client par ailleurs légitime → 413 avant tout octet
            (atelier.MAX_BODY_BYTES + 1, None, 413),
            # SOUS le plafond mais sans jeton → 403, également avant tout octet
            (4_000_000, "x" * 43, 403),
        ]
        for annonce, jeton, attendu in cas:
            h = _entetes_debut_de_reponse(port, annonce)
            if jeton is not None:
                h[atelier.CSRF_HEADER] = jeton
            ttfb, code = _delai_premier_octet(port, h)
            assert code == attendu, (annonce, code)
            # Sain : ~0,01 s. Le seul comportement à distinguer est « le serveur
            # a attendu le corps », qui coûte `REQUEST_TIMEOUT_S` (5 s). Le seuil
            # est placé au large, pour ne pas rougir sur une machine chargée.
            assert ttfb < 2.0, f"refus émis après {ttfb:.2f}s pour CL={annonce}"


def test_le_client_n_attend_pas_la_fin_du_nettoyage(tmp_path, monkeypatch):
    """Le `shutdown(SHUT_WR)` n'est pas décoratif : il DATE la fin de la réponse.

    On répond en HTTP/1.0 sans keep-alive : pour ce dialecte, la fermeture du
    canal EST le marqueur de fin, et un client qui lit jusqu'à EOF (l'idiome
    `Connection: close`) reste bloqué tant qu'il ne l'a pas. Sans le FIN, il paie
    donc TOUT le nettoyage qui suit le refus.

    Mesuré, `LINGER_IDLE_S` porté à 2 s, client qui garde son canal d'écriture
    ouvert : 0,002 s avec le FIN, 2,013 s sans. Ici la fenêtre de nettoyage est
    portée à 5 s pour que « sain » (~0,01 s) et « muet » (5 s) restent
    incomparables même sur une machine chargée."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "LINGER_IDLE_S", 5.0)
    monkeypatch.setattr(atelier, "LINGER_TOTAL_S", 30.0)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 30.0)
    with _server() as base:
        port = _port_of(base)
        t0 = time.monotonic()
        code, _ = _raw(port, "/save", _entetes_debut_de_reponse(
            port, atelier.MAX_BODY_BYTES + 1), b"", fermer_ecriture=False)
        ecoule = time.monotonic() - t0
    assert code == 413
    assert ecoule < 1.5, (
        f"le client a attendu {ecoule:.2f}s la fin du nettoyage : la fin de la "
        "réponse ne lui a pas été signalée (shutdown(SHUT_WR) manquant)")


# Les deux bornes de la fermeture courtoise ne s'observent PAS côté client : le
# `shutdown(SHUT_WR)` envoie le FIN tout de suite, donc le client voit la fin de
# la réponse immédiatement, borne ou pas. Ce qu'elles bornent réellement, c'est
# la rétention du FIL DE SERVICE — et c'est donc là qu'il faut mesurer, sans quoi
# la garde serait verte même sans borne du tout.

def _ouvre_et_fait_refuser(port, annonce):
    """Connexion refusée (413) dont le canal d'écriture reste OUVERT."""
    s = socket.create_connection(("127.0.0.1", port), timeout=30)
    head = b"POST /save HTTP/1.1\r\n"
    for k, v in _entetes_debut_de_reponse(port, annonce).items():
        head += f"{k}: {v}\r\n".encode("utf-8")
    s.sendall(head + b"\r\n")
    assert s.recv(65536).startswith(b"HTTP/1.0 413"), "refus attendu"
    return s


def _fil_rendu(base_fils, fenetre_s, goutte_a_goutte=None, pas=0.05):
    """Le serveur a-t-il relâché son fil de service dans la fenêtre ?"""
    fin = time.monotonic() + fenetre_s
    while time.monotonic() < fin:
        if goutte_a_goutte is not None:
            try:
                goutte_a_goutte.sendall(b"A")   # relance sans cesse l'inactivité
            except OSError:
                pass
        time.sleep(pas)
        if threading.active_count() <= base_fils:
            return True
    return False


def test_la_fermeture_courtoise_lache_un_client_silencieux(tmp_path, monkeypatch):
    """Borne d'INACTIVITÉ : rien n'arrive et le client ne ferme pas son canal
    d'écriture — le serveur ne peut pas attendre un EOF qui ne viendra jamais."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "LINGER_IDLE_S", 0.3)
    monkeypatch.setattr(atelier, "LINGER_TOTAL_S", 30.0)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 30.0)
    with _server() as base:
        port = _port_of(base)
        base_fils = threading.active_count()
        s = _ouvre_et_fait_refuser(port, atelier.MAX_BODY_BYTES + 1)
        try:
            rendu = _fil_rendu(base_fils, 3.0)
        finally:
            s.close()
    assert rendu, "fil de service retenu par un client silencieux (borne d'inactivité)"


def test_la_fermeture_courtoise_a_un_plafond_dur(tmp_path, monkeypatch):
    """Plafond DUR : un goutte-à-goutte relance indéfiniment l'inactivité.

    C'est le slowloris d'après-refus : un octet toutes les 50 ms suffit à rendre
    la borne d'inactivité inopérante. Seul `LINGER_TOTAL_S` rend le fil."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "LINGER_IDLE_S", 0.3)
    monkeypatch.setattr(atelier, "LINGER_TOTAL_S", 0.8)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 30.0)
    with _server() as base:
        port = _port_of(base)
        base_fils = threading.active_count()
        s = _ouvre_et_fait_refuser(port, atelier.MAX_BODY_BYTES + 1)
        try:
            rendu = _fil_rendu(base_fils, 4.0, goutte_a_goutte=s)
        finally:
            s.close()
    assert rendu, "fil de service retenu par un goutte-à-goutte (plafond dur absent)"


# ── DÉFAUT 1 : la réponse doit parvenir même quand le client lit tard ────────
#
# Le drainage AVANT réponse ne tenait qu'à délai de lecture nul. Mesuré avec un
# client réaliste (en-têtes légitimes, corps de 4 194 315 o RÉELLEMENT émis,
# plafond à 4 194 304) :
#     refus 413 — délai 0,00 s :  1/30 perdu  · 0,05 s : 30/30 · 0,30 s : 30/30
#     refus 403 — délai 0,00 s :  7/30 perdus · 0,05 s : 30/30 · 0,30 s : 30/30
# Autrement dit la réponse n'arrivait que si le client lisait dans la
# milliseconde. Aucun navigateur ne fait ça.

def _corps_hors_plafond():
    """Exactement la charge du protocole de mesure : 4 194 315 o émis."""
    corps = b'{"json":"' + b"A" * (4 * 1024 * 1024) + b'"}'
    assert len(corps) == 4_194_315 > atelier.MAX_BODY_BYTES, len(corps)
    return corps


_DELAIS_DE_LECTURE = (0.0, 0.05, 0.30)
_TIRS = 10


def _compte_pertes(port, mk_entetes, corps, attendu):
    """Rejoue le protocole de mesure et rend `{délai: (perdus, codes_inattendus)}`."""
    releve = {}
    for delai in _DELAIS_DE_LECTURE:
        perdus, autres = 0, []
        for _ in range(_TIRS):
            code, _inc = _tir(port, "/save", mk_entetes(port, len(corps)), corps,
                              delai_lecture=delai)
            if code is None:
                perdus += 1
            elif code != attendu:
                autres.append(code)
        releve[delai] = (perdus, autres)
    return releve


def _entetes_hors_plafond_legitimes(port, n):
    h = _entetes_legitimes(port)
    h["Content-Length"] = str(n)
    return h


def _entetes_hors_plafond_hostiles(_port, n):
    return {"Host": "cms.evil.example.com",
            "Origin": "https://evil.example.com",
            "Content-Type": "text/plain",
            "Content-Length": str(n),
            "Connection": "close"}


def test_le_413_hors_plafond_parvient_meme_si_le_client_lit_tard(tmp_path, monkeypatch):
    """Client LÉGITIME, corps hors plafond réellement émis → 413 reçu, 0 perte.

    Avant correctif : 30/30 perdus dès 0,05 s de délai de lecture."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    corps = _corps_hors_plafond()
    with _server() as base:
        releve = _compte_pertes(_port_of(base), _entetes_hors_plafond_legitimes, corps, 413)
    assert releve == {d: (0, []) for d in _DELAIS_DE_LECTURE}, releve


def test_le_403_hors_plafond_parvient_meme_si_le_client_lit_tard(tmp_path, monkeypatch):
    """Même chose sur le refus d'origine : un refus muet n'est pas un refus.

    Avant correctif : 30/30 perdus dès 0,05 s de délai de lecture."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    corps = _corps_hors_plafond()
    with _server() as base:
        releve = _compte_pertes(_port_of(base), _entetes_hors_plafond_hostiles, corps, 403)
    assert releve == {d: (0, []) for d in _DELAIS_DE_LECTURE}, releve


# ── DÉFAUT 2 : une connexion hostile ne doit pas affamer le client légitime ──
#
# Mesuré avant correctif : UNE connexion non authentifiée annonçant
# `Content-Length: 4000000` sans rien émettre occupait le serveur 5,01 s — et un
# `GET /` LÉGITIME lancé pendant ce blocage n'obtenait sa réponse qu'à 4,66 s.

def _duree_get_legitime(port, timeout=60):
    t0 = time.monotonic()
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                  f"Connection: close\r\n\r\n".encode("utf-8"))
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
    return time.monotonic() - t0, (int(buf.split(b" ", 2)[1]) if buf else None)


def test_une_connexion_hostile_qui_annonce_un_corps_n_affame_pas(tmp_path, monkeypatch):
    """Le scénario exact de la mesure : CL=4000000, rien émis, non authentifiée.

    DEUX assertions, parce que deux choses distinctes étaient cassées :
      · le serveur ne doit pas s'attarder sur cette connexion (mesuré 5,01 s —
        c'était le drainage AVANT réponse) ;
      · le `GET /` légitime concurrent ne doit pas attendre (mesuré 4,66 s).
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    mesure = {}

    with _server() as base:
        port = _port_of(base)

        def hostile():
            t0 = time.monotonic()
            code, _inc = _tir(port, "/save", {
                "Host": f"127.0.0.1:{port}", "Content-Type": "application/json",
                "Content-Length": "4000000", "Connection": "close"},
                b"", fermer_ecriture=False, timeout=60)
            mesure["hostile"] = (time.monotonic() - t0, code)

        th = threading.Thread(target=hostile, daemon=True)
        th.start()
        time.sleep(0.35)                 # la connexion hostile est établie
        duree_get, code_get = _duree_get_legitime(port)
        th.join(timeout=60)

    duree_hostile, code_hostile = mesure.get("hostile", (float("inf"), None))
    # Sain : 0,01 s et 0,04 s. Cassé : 5,01 s et 4,66 s. Le seuil est posé à
    # mi-chemin large — un facteur 100 de marge côté sain, 2,5 côté cassé.
    assert code_hostile == 403 and code_get == 200, (code_hostile, code_get)
    assert duree_hostile < 2.0, (
        f"le serveur s'attarde {duree_hostile:.2f}s sur une connexion qui n'émet "
        "rien (mesuré 5,01s avant correctif)")
    assert duree_get < 2.0, f"GET / légitime affamé ({duree_get:.2f}s) — 4,66s avant"


def test_une_connexion_muette_n_affame_pas(tmp_path, monkeypatch):
    """Variante plus dure : la connexion n'émet RIEN, pas même la ligne de requête.

    Borner le temps ne suffit pas ici — sur un serveur mono-fil, la borne devient
    la durée de la famine. Seul « un fil par connexion » y répond."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        s = socket.create_connection(("127.0.0.1", port), timeout=60)
        try:
            time.sleep(0.35)
            duree, code = _duree_get_legitime(port)
        finally:
            s.close()
    assert code == 200
    # Sain : 0,04 s. Mono-fil : le GET attend `REQUEST_TIMEOUT_S` entier (5 s).
    assert duree < 2.0, f"GET / légitime affamé par une connexion muette ({duree:.2f}s)"


def test_une_connexion_muette_est_relachee(tmp_path, monkeypatch):
    """…et la borne reste indispensable : sinon chaque connexion muette immobilise
    un fil pour toujours (épuisement du pool, la famine par un autre chemin)."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "REQUEST_TIMEOUT_S", 0.6)
    with _server() as base:
        port = _port_of(base)
        t0 = time.monotonic()
        # 4 s : ~7× la borne demandée. Sans borne, le serveur ne lâche jamais et
        # c'est le client qui expire — ce cas est compté comme « non relâchée ».
        with socket.create_connection(("127.0.0.1", port), timeout=4.0) as s:
            try:
                ferme = (s.recv(65536) == b"")   # EOF = le serveur a lâché
            except TimeoutError:
                ferme = False                    # le serveur, lui, n'a rien lâché
            except OSError:
                ferme = True                     # RST = lâchée aussi
        ecoule = time.monotonic() - t0
    assert ferme, f"le serveur garde une connexion muette ouverte ({ecoule:.1f}s)"


# ── DÉFAUT 3 : l'hypothèse « une requête par connexion » devient un invariant ─
#
# L'ancien `handle_one_request` réinitialisait un drapeau `_body_drained` par
# requête. La mutation qui neutralisait cette remise à zéro laissait la suite
# VERTE : le code était INERTE (`protocol_version = HTTP/1.0` → une instance de
# Handler par connexion, donc le drapeau partait déjà à False). Il est retiré.
# Ce qui restait tacite — et dont la conception dépend vraiment — est testé ici :
# répondre à un refus SANS lire le corps n'est correct que si la connexion se
# ferme ensuite ; en keep-alive, le corps non lu serait interprété comme la
# requête suivante.

def test_une_connexion_ne_sert_qu_une_requete(tmp_path, monkeypatch):
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
            requete = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n").encode("utf-8")
            s.sendall(requete)      # ni `Connection: close` : c'est le serveur qui tranche
            premiere = b""
            while b"\r\n\r\n" not in premiere:
                bloc = s.recv(65536)
                if not bloc:
                    break
                premiere += bloc
            assert premiere.startswith(b"HTTP/1.0 200"), premiere[:40]
            reste = b""
            try:
                s.sendall(requete)   # seconde requête sur la MÊME connexion
                while True:
                    bloc = s.recv(65536)
                    if not bloc:
                        break
                    reste += bloc
            except OSError:
                pass                 # connexion déjà fermée : c'est le résultat attendu
    assert b"HTTP/" not in reste, (
        "la connexion sert plusieurs requêtes (keep-alive) : un refus qui répond "
        "sans lire le corps laisserait alors des octets de corps être lus comme "
        "la requête suivante")


# ── La taille ANNONCÉE ne dit pas ce que le client ÉMET ─────────────────────
#
# Trou MESURÉ, et c'est le DÉFAUT 1 qui s'y rejouait : la fermeture courtoise
# n'était déclenchée que sur un refus, et seulement si `Content-Length` était
# lisible et > 0. Trois chemins y échappaient. Corps de 5 242 891 o réellement
# émis, 30 tirs par délai de lecture, AVANT le correctif :
#     CL négatif (-1)        0,00 s → 0/30 · 0,05 s → 22/30 · 0,30 s → 30/30
#     CL illisible (abc)     0,00 s → 0/30 · 0,05 s → 25/30 · 0,30 s → 30/30
#     CL absent, corps émis  0,00 s → 1/30 · 0,05 s → 26/30 · 0,30 s → 30/30
# Les 21 tests d'alors restaient VERTS. Les trois suivants sont leur garde ; le
# délai de lecture de 0,30 s N'EST PAS décoratif — à 0,00 s la perte est nulle,
# c'est-à-dire que la version cassée passerait.

_TIRS_TARDIFS = 5
_DELAI_TARDIF = 0.30


def _corps(taille_mio):
    return b'{"json":"' + b"A" * (taille_mio * 1024 * 1024) + b'"}'


def test_un_content_length_negatif_ne_contourne_pas_le_plafond(tmp_path, monkeypatch):
    """`Content-Length: -1` doit être refusé — et le refus doit PARVENIR.

    Deux défauts en un. Sans le contrôle `length < 0`, `-1 > MAX_BODY_BYTES` est
    faux, donc le plafond laisse passer, puis `rfile.read(-1)` lit **jusqu'à
    l'EOF** : le plafond est intégralement contourné. Mesuré sous mutation,
    25 165 835 o (6× le plafond) ont été ingérés et la requête a répondu 200.
    Et sans fermeture courtoise, le 400 lui-même se perdait (30/30 à 0,30 s).
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    corps = _corps(5)                       # > MAX_BODY_BYTES : toute acceptation
    assert len(corps) > atelier.MAX_BODY_BYTES     # est un contournement prouvé
    with _server() as base:
        port = _port_of(base)
        for _ in range(_TIRS_TARDIFS):
            code, motif = _raw(port, "/save", _entetes_legitimes(
                port, **{"Content-Length": "-1"}), corps, delai_lecture=_DELAI_TARDIF)
            assert (code, motif) == (400, "Content-Length invalide"), (code, motif[:120])


def test_un_content_length_illisible_est_refuse_franchement(tmp_path, monkeypatch):
    """Un cadrage illisible se refuse ; il ne se réinterprète pas en « corps vide ».

    Sous mutation (`except ValueError: length = 0`), les quatre valeurs testées
    répondaient 200 : le corps émis était ignoré et la requête traitée comme
    vide. Sur `/generate`, cela déclenche LLM + navigateur sur un en-tête bidon.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    corps = _corps(3)
    with _server() as base:
        port = _port_of(base)
        for valeur in ("abc", "1 2", "0x10", ""):
            code, motif = _raw(port, "/save", _entetes_legitimes(
                port, **{"Content-Length": valeur}), corps, delai_lecture=_DELAI_TARDIF)
            assert (code, motif) == (400, "Content-Length invalide"), (valeur, code)


def test_une_reponse_ordinaire_parvient_quand_le_client_emet_un_corps_non_annonce(
        tmp_path, monkeypatch):
    """Le troisième chemin n'était PAS un refus — et c'est ce qui l'avait caché.

    Sans `Content-Length`, le corps n'est pas lu et la réponse est un 200
    ordinaire. Elle se perdait exactement pareil (30/30 à 0,30 s) : la fermeture
    courtoise ne peut donc pas être une affaire de refus, elle doit être la
    façon dont le handler termine. Ce que ce test exige, c'est l'ARRIVÉE —
    `_raw` échoue de lui-même quand rien n'est reçu.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    corps = _corps(3)
    with _server() as base:
        port = _port_of(base)
        entetes = _entetes_legitimes(port)
        entetes.pop("Content-Length", None)
        for _ in range(_TIRS_TARDIFS):
            code, body = _raw(port, "/save", entetes, corps, delai_lecture=_DELAI_TARDIF)
            assert code == 200, (code, body[:120])
            assert json.loads(body)["ok"] is False


# ── Le preflight CORS ne doit RIEN accorder ─────────────────────────────────

def test_le_preflight_cors_n_est_pas_accorde():
    """C'est la clé de voûte de la garde `Content-Type`, et elle n'était pas testée.

    Exiger `application/json` ne referme la fenêtre de la « requête simple » que
    parce que le navigateur doit alors demander un preflight — auquel l'atelier
    ne répond pas. Qu'un `do_OPTIONS` complaisant apparaisse, et la garde tombe :
    mesuré, une réponse 204 portant `Access-Control-Allow-Origin: *` et
    `Access-Control-Allow-Headers: *` laissait les 38 tests VERTS.
    """
    with _server() as base:
        port = _port_of(base)
        buf, incident = _requete_brute(port, "/save", {
            "Host": f"127.0.0.1:{port}",             # le navigateur vise bien l'atelier
            "Origin": "https://evil.example.com",    # …depuis une page tierce
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"content-type,{atelier.CSRF_HEADER}",
            "Connection": "close"}, method="OPTIONS")
    assert buf, f"aucune réponse au preflight — incident={incident}"
    tete = buf.split(b"\r\n\r\n", 1)[0].decode("utf-8", "replace")
    assert int(tete.split(" ", 2)[1]) == 501, tete.splitlines()[0]
    accordes = re.findall(r"(?im)^access-control-allow-\S+:.*$", tete)
    assert not accordes, f"le preflight accorde des droits CORS : {accordes}"


# ── L'ordre d'injection dans les pages servies ──────────────────────────────

def test_un_profil_contenant_le_marqueur_du_jeton_est_servi_intact(tmp_path, monkeypatch):
    """Le jeton s'injecte AVANT le profil — jamais l'inverse.

    Trou MESURÉ : en inversant les deux lignes de `_render`, les 38 tests
    restaient VERTS, parce qu'aucun profil de test ne contenait le marqueur.
    L'inversion est pourtant doublement grave — mesuré sur un profil piégé :
      · la charge servie devient illisible (`"…\\"last_name\\": \\""JETON"\\"…"`) :
        guillemets non échappés au milieu du littéral, la page ne parse plus ;
      · le jeton apparaît DEUX fois, dont une dans le texte que /edit propose de
        réécrire dans profile.json — fichier PUBLIC (GitHub Pages).
    """
    piege = json.dumps({"identity": {"first_name": "Robin", "last_name": "__TOKEN__"}},
                       indent=2, ensure_ascii=False)
    cible = tmp_path / "profile.json"
    cible.write_text(piege, encoding="utf-8")
    monkeypatch.setattr(atelier, "_PROFILE", cible)
    with _server() as base:
        for chemin, motif in (("/edit", r"var P = (.*);\n"),
                              ("/cms", r"var profile = JSON\.parse\((.*)\);\n")):
            code, page = _get(base, chemin)
            assert code == 200, chemin
            m = re.search(motif, page)
            assert m, f"{chemin} : charge profil introuvable dans la page"
            try:
                servi = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                raise AssertionError(
                    f"{chemin} : la charge du profil n'est plus un littéral valide "
                    f"({e}) — {m.group(1)[:160]}")
            assert servi == piege, f"{chemin} : profil altéré à l'injection"
            assert page.count(atelier.csrf_token()) == 1, (
                f"{chemin} : le jeton apparaît {page.count(atelier.csrf_token())}× — "
                "il a fui dans les données du profil")


# ── Le point d'entrée réel ──────────────────────────────────────────────────

def test_main_tire_un_jeton_neuf_au_demarrage(monkeypatch):
    """`main` est le point d'entrée du produit, et il n'était pas exercé du tout.

    Ce qu'il garantit et que rien d'autre ne garantit : le jeton servi est neuf
    À CHAQUE DÉMARRAGE, pas celui hérité de l'import du module. Mesuré, mutation
    retirant `reset_csrf_token()` : la page servait le jeton d'import à
    l'identique, et les 38 tests restaient VERTS.
    """
    monkeypatch.setattr(atelier, "_TOKEN", atelier._TOKEN)   # rotation annulée au teardown
    avant = atelier.csrf_token()
    crees, vrai = [], atelier.make_server
    # `main` fixe le port ; on le force éphémère pour ne pas heurter un atelier
    # qui tournerait vraiment. Le serveur construit reste le VRAI `make_server`.
    monkeypatch.setattr(atelier, "make_server",
                        lambda port=0: (crees.append(vrai(0)), crees[-1])[1])
    threading.Thread(target=atelier.main, args=(0,), daemon=True).start()
    debut = time.monotonic()
    while not crees and time.monotonic() - debut < 10:
        time.sleep(0.02)
    assert crees, "main() n'a construit aucun serveur en 10 s"
    srv = crees[0]
    try:
        code, page = _get(f"http://127.0.0.1:{srv.server_address[1]}", "/")
        assert code == 200
        m = re.search(r'const TOKEN="([^"]+)"', page)
        assert m, "la page servie par main() ne porte pas de jeton"
        servi = m.group(1)
    finally:
        srv.shutdown()
        srv.server_close()
    assert servi != avant, (
        "main() a resservi le jeton hérité de l'import : aucune rotation au démarrage")
    assert servi == atelier.csrf_token(), "le jeton servi n'est pas celui qui sera exigé"
    assert len(servi) >= 40, servi


# ── Zero Masking, versant refus ─────────────────────────────────────────────

def test_tout_refus_est_journalise_en_console(tmp_path, monkeypatch, capfd):
    """Le client n'obtient qu'un motif sobre ; le contexte va à la console.

    Sans cette trace, un refus devient indiscernable d'une panne réseau pour le
    propriétaire — le motif rendu au client est volontairement laconique.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, motif = _post(port, "/save", {"json": "{}"}, Host="cms.evil.example.com")
    assert code == 403 and motif == "hote non autorise"
    err = capfd.readouterr().err
    assert "refus 403" in err, f"refus non journalisé : {err[-300:]!r}"
    assert "cms.evil.example.com" in err, "le Host refusé n'est pas dans la trace"
    assert "/save" in err, "la route refusée n'est pas dans la trace"


def test_generate_route_is_guarded_too(tmp_path, monkeypatch):
    """/generate lit le profil, appelle le LLM et lance un navigateur : une page
    tierce ne doit pas pouvoir le déclencher non plus."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        code, _ = _raw(port, "/generate", {
            "Host": "evil.example.com", "Content-Type": "text/plain",
            "Content-Length": "2", "Connection": "close"}, b"{}")
    assert code == 403


def test_get_with_foreign_host_is_refused():
    """/edit et /cms embarquent le profil ENTIER *et* le jeton : un rebinding DNS
    les rendrait lisibles par un tiers."""
    with _server() as base:
        port = _port_of(base)
        for path in ("/", "/edit", "/cms", "/assets/js/cms-model.js"):
            code, _ = _raw(port, path, {"Host": "evil.example.com",
                                        "Connection": "close"}, method="GET")
            assert code == 403, path


# ── L'usage LÉGITIME doit rester intact (pas de porte murée) ─────────────────

def test_served_pages_carry_and_send_the_token():
    with _server() as base:
        for path in ("/", "/edit", "/cms"):
            code, body = _get(base, path)
            assert code == 200, path
            assert atelier.csrf_token() in body, f"{path} ne porte pas le jeton"
            assert atelier.CSRF_HEADER in body, f"{path} n'envoie pas le jeton"


def test_legitimate_save_from_the_served_page_succeeds(tmp_path, monkeypatch):
    """ÉTAPE 3 : le propriétaire doit toujours pouvoir enregistrer."""
    target = _pointe_vers_une_copie(tmp_path, monkeypatch)
    prof = json.loads(target.read_text(encoding="utf-8"))
    prof["identity"]["last_name"] = "Denis-OK"
    with _server() as base:
        port = _port_of(base)
        code, body = _post(port, "/save", {"json": json.dumps(prof)})
    assert code == 200, body
    assert json.loads(body)["ok"] is True
    assert json.loads(target.read_text(encoding="utf-8"))["identity"]["last_name"] == "Denis-OK"


def test_legitimate_save_without_origin_header_succeeds(tmp_path, monkeypatch):
    """Certains clients locaux n'envoient ni Origin ni Referer : absent ≠ étranger."""
    target = _pointe_vers_une_copie(tmp_path, monkeypatch)
    prof = json.loads(target.read_text(encoding="utf-8"))
    prof["identity"]["last_name"] = "Denis-OK2"
    with _server() as base:
        port = _port_of(base)
        code, body = _post(port, "/save", {"json": json.dumps(prof)},
                           Origin=None, Referer=None)
    assert code == 200, body
    assert json.loads(target.read_text(encoding="utf-8"))["identity"]["last_name"] == "Denis-OK2"


# ── Les exceptions ne partent plus au client ────────────────────────────────

def test_internal_error_is_not_echoed_to_the_client(tmp_path, monkeypatch, capfd):
    """Zero Masking : la trace complète va à la console, jamais dans la réponse."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)

    def boum(*a, **k):
        raise RuntimeError("C:/chemin/secret/interne — jeton=DEADBEEF")

    monkeypatch.setattr(atelier, "save_profile_edit", boum)
    with _server() as base:
        code, body = _post(_port_of(base), "/save", {"json": "{}"})
    assert code == 500
    assert "secret" not in body and "DEADBEEF" not in body, body
    assert json.loads(body)["ok"] is False
    assert "DEADBEEF" in capfd.readouterr().err, "la trace n'a pas été journalisée"


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  PASSE 2 — les propriétés dont la passe 1 dépendait sans les tenir        ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# La passe 1 revendiquait « 28 mutations, 28 rouges, 0 garde inerte » — vrai sur
# SES 28, faux comme énoncé sur le fichier : un audit externe a rejoué 22
# mutations inédites, dont 11 laissaient la suite VERTE avec un écart de
# comportement MESURÉ sur le serveur en marche. Prouver ses gardes par mutation
# ne prouve que les mutations qu'on a pensé à faire : on ne mute pas une
# propriété dont on ignore qu'on en dépend.
#
# Les 12 gardes ci-dessous couvrent ces 11 écarts, plus un douzième trouvé en
# cherchant au-delà de la liste reçue (le plafond de corps, § MAX_BODY_BYTES).
# Aucune ligne d'`atelier.py` n'a eu besoin d'être touchée : les propriétés
# étaient correctement implémentées — c'est leur défense qui manquait.
#
# Règle appliquée ici, sans exception : l'ATTENDU de chaque assertion vient d'une
# source INDÉPENDANTE de l'implémentation — un second rendu de la même page, les
# octets réellement reçus sur le socket, le fichier profil relu sur le disque,
# un autre processus, ou une horloge. Aucune assertion ne compare une constante
# du module à elle-même, aucune liste écrite à la main n'est son propre unique
# lecteur (celles qui subsistent sont confrontées à ce que les pages déclarent).


def _reponse(port, path, headers=None, body=b"", method="GET", **kw):
    """Réponse BRUTE : `(code, en-têtes minuscules, corps en OCTETS)`.

    `_raw` décode et jette les en-têtes ; plusieurs propriétés de cette passe se
    mesurent précisément DANS les en-têtes (`Content-Length`, `Content-Type`) ou
    sur le nombre d'octets reçus.
    """
    h = dict(headers or {})
    h.setdefault("Host", f"127.0.0.1:{port}")
    h.setdefault("Connection", "close")
    buf, incident = _requete_brute(port, path, h, body, method, **kw)
    if not buf:
        raise AssertionError(f"aucune réponse pour {method} {path} — incident={incident}")
    tete, _, corps = buf.partition(b"\r\n\r\n")
    lignes = tete.decode("utf-8", "replace").split("\r\n")
    entetes = {}
    for ligne in lignes[1:]:
        if ":" in ligne:
            k, v = ligne.split(":", 1)
            entetes[k.strip().lower()] = v.strip()
    return int(lignes[0].split(" ")[1]), entetes, corps


# ── V20 : l'imprévisibilité du jeton — la clé de voûte de tout le lot I1 ─────
#
# Les quatre gardes (Host, Origin/Referer, Content-Type, jeton) ne referment la
# fenêtre de la « requête simple » que parce qu'une page tierce ne peut pas
# DEVINER le jeton. Mutation mesurée : `secrets.token_urlsafe(32)` remplacé par
# une constante littérale dans `reset_csrf_token()` → 46 tests VERTS, et
# `reset() == reset()`. `test_main_tire_un_jeton_neuf_au_demarrage` ne l'attrape
# pas : il compare le jeton servi à celui de l'IMPORT (resté aléatoire) et exige
# `len >= 40` — une constante de 43 caractères passe les deux.

def test_le_jeton_anti_csrf_est_imprevisible(monkeypatch):
    """La propriété, pas la ligne d'appel : deux tirages ne coïncident jamais.

    Trois façons de ne PAS être imprévisible sont couvertes d'un coup :
      · constante (un seul tirage distinct) ;
      · jeton trop court pour résister à une énumération ;
      · jeton dont l'aléa est concentré sur une poignée de caractères —
        « préfixe aléatoire + queue constante » est tout aussi devinable et
        passerait un simple `reset() != reset()`. D'où la mesure position par
        position.

    Ce qui est compté n'est PAS « toutes les positions varient » : un séparateur
    figé est légitime (un UUID a quatre tirets), ce serait rougir sur une forme
    plutôt que sur la propriété. C'est le NOMBRE de positions qui portent
    réellement de l'aléa.

    Aucun nombre n'est repris du module : les 64 tirages sont la mesure, et les
    seuils sont des PLANCHERS de sécurité (32 caractères, 20 positions portant
    ≥ 8 valeurs distinctes) volontairement très en dessous de ce que rend
    l'artefact livré (43 caractères, 43 positions à 16-45 valeurs) — pour rougir
    sur une dégénérescence, jamais sur un changement de forme légitime.
    """
    monkeypatch.setattr(atelier, "_TOKEN", atelier._TOKEN)   # rotation annulée au teardown
    tirs = [atelier.reset_csrf_token() for _ in range(64)]

    assert len(set(tirs)) == len(tirs), (
        f"{len(tirs) - len(set(tirs))} collision(s) sur {len(tirs)} tirages : "
        "le jeton anti-CSRF est prévisible, les quatre gardes du lot tombent")
    assert min(len(t) for t in tirs) >= 32, sorted({len(t) for t in tirs})
    for t in tirs:
        assert re.fullmatch(r"[A-Za-z0-9_-]+", t), (
            f"jeton non transmissible tel quel en en-tête HTTP : {t!r}")

    largeur = min(len(t) for t in tirs)
    vivantes = sum(1 for i in range(largeur) if len({t[i] for t in tirs}) >= 8)
    assert vivantes >= 20, (
        f"seules {vivantes} position(s) sur {largeur} portent de l'aléa sur "
        f"{len(tirs)} tirages : l'entropie du jeton est concentrée sur une "
        "poignée de caractères, le reste est devinable")


def test_le_jeton_d_une_session_precedente_n_ouvre_plus_rien(tmp_path, monkeypatch):
    """La CONSÉQUENCE observable de l'imprévisibilité, mesurée sur le serveur.

    Le jeton n'est pas lu dans le module mais dans la PAGE que sert un premier
    atelier — c'est exactement ce qu'une page tierce pourrait avoir vu une fois.
    Après redémarrage (nouveau tirage), il doit être refusé, et le jeton courant
    doit continuer d'ouvrir : une garde qui mure la porte n'en est pas une.

    Sous la mutation « constante littérale », l'ancien jeton reste valide pour
    toujours.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    monkeypatch.setattr(atelier, "_TOKEN", atelier._TOKEN)

    atelier.reset_csrf_token()
    with _server() as base:
        code, page = _get(base, "/")
        assert code == 200
        m = re.search(r'const TOKEN="([^"]+)"', page)
        assert m, "la page d'accueil ne porte pas de jeton"
        ancien = m.group(1)

    atelier.reset_csrf_token()          # redémarrage de l'atelier
    with _server() as base:
        port = _port_of(base)
        code_ancien, _ = _post(port, "/save", {"json": "{}"},
                               **{atelier.CSRF_HEADER: ancien})
        code_courant, _ = _post(port, "/save", {"json": "{}"})
    assert code_ancien == 403, (
        "le jeton d'une session précédente ouvre encore les routes mutantes")
    assert code_courant == 200, "le jeton courant n'ouvre plus rien : porte murée"


def test_deux_ateliers_lances_separement_ne_tirent_pas_le_meme_jeton():
    """Source indépendante : d'autres PROCESSUS.

    Tout jeton dérivé d'une source déterministe — constante, graine figée,
    valeur calculée depuis le code — est identique d'un interpréteur neuf à
    l'autre. Un jeton tiré de l'entropie du système ne l'est jamais. Cette
    mesure ne peut pas être satisfaite par accident depuis l'intérieur du module.

    Les DEUX jetons d'un interpréteur neuf sont relevés, car un serveur peut être
    servi avec l'un ou l'autre : `main()` appelle `reset_csrf_token()`, mais
    `make_server()` — le point d'entrée unique, celui qu'emploient ces tests et
    tout appelant qui embarque l'atelier — sert le jeton posé À L'IMPORT sans rien
    retirer. Mesuré 2026-07-29 : figer le `_TOKEN = secrets.token_urlsafe(32)` de
    niveau module en une constante littérale laissait la suite VERTE (61 tests) —
    un atelier lancé autrement que par `main` servait alors un jeton lisible dans
    le code source, et les quatre gardes du lot I1 tombaient avec lui.
    """
    import subprocess
    import sys as _sys
    dossier = str(pathlib.Path(atelier.__file__).resolve().parent)
    programme = ("import sys; sys.path.insert(0, r'" + dossier + "'); "
                 "import atelier; print(atelier.csrf_token()); "
                 "print(atelier.reset_csrf_token())")
    a_l_import, apres_reset = [], []
    for _ in range(3):
        r = subprocess.run([_sys.executable, "-c", programme],
                           capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-500:]
        lignes = r.stdout.split()
        assert len(lignes) == 2, r.stdout
        a_l_import.append(lignes[0])
        apres_reset.append(lignes[1])
    for quand, tirs in (("à l'import", a_l_import), ("après reset", apres_reset)):
        assert all(tirs), (quand, tirs)
        assert len(set(tirs)) == len(tirs), (
            f"des interpréteurs neufs servent le même jeton {quand} : {tirs}")


# ── V1 : le profil est une DONNÉE, jamais du balisage ────────────────────────

_PIEGES_BALISAGE = ["</script><script>alert(1)</script>",
                    "<img src=x onerror=alert(1)>",
                    "<svg/onload=alert(1)>",
                    "<!--"]


def _page_avec_ce_profil(tmp_path, monkeypatch, contenu, chemin, nom):
    """Sert `chemin` avec un profil donné et rend la page (source d'attendu)."""
    cible = tmp_path / f"profile_{nom}.json"
    cible.write_text(contenu, encoding="utf-8")
    monkeypatch.setattr(atelier, "_PROFILE", cible)
    with _server() as base:
        code, page = _get(base, chemin)
    assert code == 200, (chemin, nom, code)
    return page


def _balises(page):
    """La suite des balises de la page — ce que voit l'analyseur du navigateur."""
    return re.findall(r"</?[a-zA-Z][^>]*>", page)


def test_un_profil_qui_referme_le_bloc_script_ne_change_pas_la_structure_de_la_page(
        tmp_path, monkeypatch):
    """Trou MESURÉ : `.replace("<", "\\u003c")` retiré de `_render` → 46 verts.

    Avec `last_name = "</script><script>alert(1)</script>"`, /cms passe de 2 à 4
    balises `</script>` et /edit de 1 à 3, et la fermeture apparaît À L'INTÉRIEUR
    de la charge profil : la donnée referme le bloc `<script>` qui PORTE le jeton
    anti-CSRF, puis ouvre le sien. Le piège existant n'employait que `__TOKEN__`,
    jamais `<`.

    L'attendu n'est écrit nulle part : c'est la MÊME page rendue avec un profil
    anodin, dans le même processus (donc même jeton). La charge peut changer —
    la structure de balises, non.
    """
    anodin = json.dumps({"identity": {"first_name": "Robin", "last_name": "Denis"},
                         "notes": ["texte anodin"] * len(_PIEGES_BALISAGE)},
                        indent=2, ensure_ascii=False)
    piege = json.dumps({"identity": {"first_name": "Robin",
                                     "last_name": _PIEGES_BALISAGE[0]},
                        "notes": _PIEGES_BALISAGE},
                       indent=2, ensure_ascii=False)

    for chemin, motif in (("/edit", r"var P = (.*);\n"),
                          ("/cms", r"var profile = JSON\.parse\((.*)\);\n")):
        page_anodine = _page_avec_ce_profil(tmp_path, monkeypatch, anodin, chemin, "anodin")
        page_piegee = _page_avec_ce_profil(tmp_path, monkeypatch, piege, chemin, "piege")

        assert _balises(page_piegee) == _balises(page_anodine), (
            f"{chemin} : la donnée profil a modifié le balisage de la page "
            f"(`</script>` : {page_piegee.count('</script>')} contre "
            f"{page_anodine.count('</script>')} avec un profil anodin)")

        m = re.search(motif, page_piegee)
        assert m, f"{chemin} : charge profil introuvable"
        charge = m.group(1)
        # Dans un bloc `<script>`, l'analyseur HTML réagit au `<` LUI-MÊME
        # (script data less-than-sign state), quel que soit le contexte JS.
        assert "<" not in charge, (
            f"{chemin} : un `<` brut subsiste dans la charge servie — "
            f"{charge[max(0, charge.find('<') - 40):charge.find('<') + 40]!r}")
        assert json.loads(charge) == piege, (
            f"{chemin} : le profil a été ALTÉRÉ au lieu d'être échappé")


# ── V6 / V8 : les VALEURS LIVRÉES des bornes de temps ────────────────────────
#
# `test_une_connexion_muette_est_relachee` fixe `REQUEST_TIMEOUT_S` à 0,6 s et
# `test_la_fermeture_courtoise_a_un_plafond_dur` fixe `LINGER_TOTAL_S` à 0,8 s :
# tous deux gardent le MÉCANISME et laissent sans garde les deux nombres que ce
# mécanisme applique. Mutations mesurées, aucune borne monkeypatchée :
#     REQUEST_TIMEOUT_S 5.0 → 3600.0 : fil retenu > 8 s (plafonné à 1 h) — 46 verts
#     LINGER_TOTAL_S      3.0 →  600.0 : fil retenu > 20 s                — 46 verts
# C'est le DÉFAUT 2 qui revient par la constante. Les deux tests suivants ne
# monkeypatchent RIEN : ils mesurent l'artefact tel qu'il est expédié.
#
# Le seuil n'est pas la constante relue (ce serait la comparer à elle-même) :
# c'est une exigence de service — un atelier local doit rendre son fil en
# quelques secondes. Il est posé 2× au-dessus des valeurs livrées, pour rougir
# sur un ordre de grandeur, jamais sur un réglage fin.

_BORNE_DE_SERVICE_S = 10.0


def test_la_borne_de_temps_LIVREE_relache_une_connexion_muette(tmp_path, monkeypatch):
    """Valeur expédiée de `REQUEST_TIMEOUT_S`, mesurée à l'horloge."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        t0 = time.monotonic()
        with socket.create_connection(("127.0.0.1", port),
                                      timeout=_BORNE_DE_SERVICE_S + 2.0) as s:
            try:
                relachee = (s.recv(65536) == b"")   # EOF = le serveur a lâché
            except TimeoutError:
                relachee = False                    # il n'a rien lâché
            except OSError:
                relachee = True                     # RST = lâchée aussi
        ecoule = time.monotonic() - t0
    assert relachee, (
        f"une connexion muette immobilise un fil de service au-delà de "
        f"{_BORNE_DE_SERVICE_S:.0f}s : la valeur LIVRÉE de REQUEST_TIMEOUT_S "
        "n'a plus de rapport avec un atelier local")
    assert ecoule < _BORNE_DE_SERVICE_S, f"connexion muette relâchée après {ecoule:.1f}s"


def test_le_plafond_de_fermeture_LIVRE_rend_le_fil_face_a_un_goutte_a_goutte(
        tmp_path, monkeypatch):
    """Valeur expédiée de `LINGER_TOTAL_S` : slowloris d'après-refus, 1 octet /
    50 ms, aucune borne monkeypatchée."""
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    with _server() as base:
        port = _port_of(base)
        base_fils = threading.active_count()
        s = _ouvre_et_fait_refuser(port, atelier.MAX_BODY_BYTES + 1)
        t0 = time.monotonic()
        try:
            rendu = _fil_rendu(base_fils, _BORNE_DE_SERVICE_S, goutte_a_goutte=s)
        finally:
            s.close()
        ecoule = time.monotonic() - t0
    assert rendu, (
        f"fil de service retenu plus de {_BORNE_DE_SERVICE_S:.0f}s par un "
        "goutte-à-goutte : la valeur LIVRÉE de LINGER_TOTAL_S ne borne plus rien")
    assert ecoule < _BORNE_DE_SERVICE_S, f"fil rendu après {ecoule:.1f}s"


# La même famille, trouvée en cherchant au-delà des mutations déjà nommées : le
# PLAFOND de corps est lui aussi une valeur livrée que rien ne mesure.
# `test_oversized_body_is_refused` tire à `MAX_BODY_BYTES + 1` — il éprouve le
# plafond AVEC le plafond, donc il reste vert si le plafond passe à 4 Tio, ce qui
# rendrait la garde purement décorative. Mesuré : `4 * 1024 * 1024` → `4 * 1024**4`,
# les 59 autres tests restent VERTS et le serveur accepte d'ingérer 10 Mio.
# L'étalon ne peut donc pas être le plafond : c'est la charge RÉELLE que poste la
# page /cms, lue sur le profil du dépôt.

def test_le_plafond_de_corps_LIVRE_est_calibre_sur_la_charge_reelle_du_CMS(
        tmp_path, monkeypatch):
    """Deux bornes, toutes deux mesurées sur le serveur, toutes deux rapportées à
    la taille du vrai `profile.json` :
      · la charge réelle doit PASSER — un plafond trop bas mure l'atelier ;
      · 128 fois cette charge doit être REFUSÉE — au-delà, le plafond ne plafonne
        plus rien.
    """
    cible = _pointe_vers_une_copie(tmp_path, monkeypatch)
    reelle = len(_corps_taille_reelle())
    assert reelle > 40_000, reelle          # la charge produite, pas un jouet

    prof = json.loads(cible.read_text(encoding="utf-8"))
    prof["identity"]["last_name"] = "Denis-PLAFOND"
    charge = json.dumps({"json": json.dumps(prof)}).encode("utf-8")
    with _server() as base:
        port = _port_of(base)
        code_reel, corps = _raw(port, "/save", _entetes_legitimes(
            port, **{"Content-Length": str(len(charge))}), charge)
        # Corps ANNONCÉ seulement : le refus doit précéder toute ingestion.
        code_enorme, _ = _raw(port, "/save", _entetes_legitimes(
            port, **{"Content-Length": str(128 * reelle)}), b"")
    assert code_reel == 200 and json.loads(corps)["ok"] is True, (code_reel, corps[:200])
    assert json.loads(cible.read_text(encoding="utf-8"))["identity"]["last_name"] \
        == "Denis-PLAFOND", "la charge réelle du CMS ne passe plus : atelier muré"
    assert code_enorme == 413, (
        f"un corps de {128 * reelle} octets (128× la charge réelle du CMS) est "
        f"accepté : le plafond livré ne plafonne plus rien")


# ── V2 / V3 : Zero Masking sur l'AUTRE route mutante ─────────────────────────

def test_une_erreur_interne_de_generate_ne_part_pas_au_client_mais_a_la_console(
        tmp_path, monkeypatch, capfd):
    """La même propriété que sur /save, portée sur /generate.

    Deux mutations mesurées la laissaient verte, chacune sur un versant :
      · `_ERR_CLIENT` → `traceback.format_exc()` : le client reçoit le marqueur
        ET le chemin interne (46 verts) ;
      · `traceback.print_exc()` retiré : plus AUCUNE trace en console (46 verts),
        Zero Masking rompu — une panne de /generate devient indiscernable d'un
        problème réseau pour le propriétaire.
    /generate lit le profil, appelle le LLM et lance un navigateur : c'est la
    route qui a le plus de détails internes à laisser fuir.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    marqueur = "DEADBEEF42"

    def boum(*a, **k):
        raise RuntimeError(f"C:/chemin/secret/interne — jeton={marqueur}")

    monkeypatch.setattr(atelier, "generate_pdf", boum)
    with _server() as base:
        code, corps = _post(_port_of(base), "/generate", {"job": "x", "lang": "fr"})
    assert code == 500, corps[:200]
    for fuite in (marqueur, "secret", "Traceback", "atelier.py", "RuntimeError", "line "):
        assert fuite not in corps, (
            f"le client reçoit un détail interne ({fuite!r}) : {corps[:300]!r}")
    err = capfd.readouterr().err
    assert marqueur in err, "l'erreur de /generate n'est journalisée NULLE PART"
    assert "Traceback" in err, err[-400:]


# ── V4 : un cadrage indécodable se refuse, il ne se répare pas ───────────────

def test_un_corps_non_utf8_est_refuse_et_n_atteint_jamais_le_pipeline(
        tmp_path, monkeypatch):
    """Frère jumeau exact de `Content-Length` illisible, déjà gardé, lui.

    Mutation mesurée : `decode("utf-8")` → `decode("utf-8", "replace")` → sur
    `b'{"json":"\\xff\\xfe\\x80abc"}'` la réponse passe de 400 à 200 (46 verts) et
    des U+FFFD entrent dans le pipeline d'écriture. Le code retourné ne suffit
    donc pas : un MOUCHARD observe le pipeline, qui ne doit pas être appelé.
    """
    _pointe_vers_une_copie(tmp_path, monkeypatch)
    appels = []
    vrai = atelier.save_profile_edit
    monkeypatch.setattr(atelier, "save_profile_edit",
                        lambda *a, **k: (appels.append(a), vrai(*a, **k))[1])
    corps = b'{"json":"\xff\xfe\x80abc"}'
    with _server() as base:
        port = _port_of(base)
        code, motif = _raw(port, "/save", _entetes_legitimes(
            port, **{"Content-Length": str(len(corps))}), corps)
    assert code == 400, (code, motif[:160])
    assert "UTF-8" in motif, motif
    assert appels == [], (
        "des octets indécodables, réinterprétés en silence, ont atteint le "
        "pipeline d'écriture du profil")


# ── V19 : l'aiguillage des routes POST ───────────────────────────────────────

def _routes_mutantes_declarees(port):
    """Les routes POST que les PAGES de l'atelier appellent réellement.

    Source indépendante du serveur : les pages sont le contrat client. Ce qui y
    figure doit exister ; ce qui n'y figure pas ne doit rien déclencher.
    """
    routes = set()
    for chemin in ("/", "/edit", "/cms"):
        _, _, page = _reponse(port, chemin)
        html = page.decode("utf-8")
        routes |= set(re.findall(
            r"""fetch\(\s*["']([^"']+)["']\s*,\s*\{\s*method:\s*["']POST["']""", html))
        # Les trois générateurs partagent UN seul `fetch(route, …)` : dupliquer le
        # transport trois fois pour rester détectable par une regex serait laisser
        # le test dicter l'architecture. La route est donc DÉCLARÉE sur le bouton
        # (`data-route`) — et le bouton la lit (`this.dataset.route`), donc la
        # déclaration est utilisée, pas décorative : elle ne peut pas dériver.
        routes |= set(re.findall(r"""data-route=["']([^"']+)["']""", html))
    return routes


def test_seules_les_routes_declarees_par_les_pages_repondent_en_POST(
        tmp_path, monkeypatch):
    """Mutation mesurée : le `if self.path == "/save"` et le 404 final remplacés
    par un appel direct → `POST /n-importe-quoi` passe de 404 à 200 ET RÉÉCRIT
    profile.json, les 46 tests restant verts.

    La preuve du refus n'est donc pas le code retourné seul : ce sont les OCTETS
    du fichier profil, relus sur le disque avant et après la salve.
    """
    cible = _pointe_vers_une_copie(tmp_path, monkeypatch)
    avant = cible.read_bytes()
    modifie = json.loads(avant.decode("utf-8"))
    modifie["identity"]["last_name"] = "ROUTE-FANTOME"
    payload = json.dumps({"json": json.dumps(modifie)}).encode("utf-8")

    with _server() as base:
        port = _port_of(base)
        declarees = _routes_mutantes_declarees(port)
        # Confrontation, pas déclaration : si une route mutante est ajoutée aux
        # pages, ce test doit être revu — c'est précisément ce qu'on veut.
        assert declarees == {"/generate", "/generate-docx", "/generate-letter",
                             "/save"}, declarees
        for chemin in ("/", "/edit", "/cms", "/save/", "/save2", "/sauver",
                       "/n-importe-quoi", "/generate/x", "/generate-pdf",
                       "/generate-docx/", "/generatedocx", "/generate-letter2"):
            assert chemin not in declarees, chemin
            code, _, _ = _reponse(port, chemin, _entetes_legitimes(
                port, **{"Content-Length": str(len(payload))}), payload, "POST")
            assert code == 404, (chemin, code)

    assert cible.read_bytes() == avant, (
        "une route POST que personne ne déclare a réécrit profile.json")


# ── V9 : un script servi doit être EXÉCUTABLE par le navigateur ──────────────

# « JavaScript MIME type » au sens WHATWG (HTML Standard, §Scripting) : c'est le
# navigateur, pas nous, qui décide d'exécuter ou non. `text/plain` est refusé en
# mode strict — le CMS perdrait silencieusement son modèle.
_MIME_JAVASCRIPT = re.compile(r"^(?:text|application)/(?:x-)?(?:java|ecma)script$", re.I)


def test_les_scripts_declares_par_la_page_cms_sont_servis_avec_un_type_executable():
    """Mutation mesurée : `application/javascript` → `text/plain` dans
    `_STATIC_ALLOW` → 46 verts, et le CMS reçoit son modèle dans un type qu'un
    navigateur strict n'exécute pas. `test_cms_model_asset_is_served` ne vérifie
    que le code 200 et la présence de « CMSModel » dans le corps.

    Les chemins ne sont pas écrits ici : ils sont LUS dans la page servie, seule
    source qui dise ce dont le CMS a besoin pour fonctionner.
    """
    with _server() as base:
        port = _port_of(base)
        _, _, page_cms = _reponse(port, "/cms")
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', page_cms.decode("utf-8"))
        assert srcs, "la page /cms ne déclare aucun script externe"
        for src in srcs:
            code, entetes, corps = _reponse(port, src)
            assert code == 200, src
            assert corps, f"{src} servi vide"
            essence = entetes.get("content-type", "").split(";")[0].strip()
            assert _MIME_JAVASCRIPT.match(essence), (
                f"{src} servi en {essence!r} : un navigateur strict ne "
                "l'exécutera pas, et le CMS perd son modèle en silence")


# ── V12 : l'accueil survit à une query string ───────────────────────────────

def test_la_page_d_accueil_survit_a_une_query_string():
    """Un lien de suivi (`/?utm=…`), un rechargement forcé (`/?v=2`) : le
    navigateur ajoute des query strings et l'accueil doit rester l'accueil.

    Mutation mesurée : `self.path.startswith("/?")` retiré → `GET /?utm=x` passe
    de 200 à 404, 46 tests verts — la branche n'était jamais exercée.

    L'attendu n'est pas écrit à la main : c'est la réponse de `/` lui-même,
    obtenue du MÊME serveur. Le test ne suppose donc rien du contenu de la page.
    """
    with _server() as base:
        port = _port_of(base)
        code_ref, _, corps_ref = _reponse(port, "/")
        assert code_ref == 200 and corps_ref
        for suffixe in ("?utm=newsletter", "?v=2", "?"):
            code, _, corps = _reponse(port, "/" + suffixe)
            assert code == 200, (suffixe, code)
            assert corps == corps_ref, f"/{suffixe} ne sert pas la page d'accueil"


# ── V13 : une réponse déclare la taille RÉELLE de son corps ──────────────────

def test_toute_reponse_declare_la_taille_reelle_de_son_corps(tmp_path, monkeypatch):
    """Mutation mesurée : `Content-Length` retiré de `_send` → l'en-tête
    disparaît de TOUTES les réponses, 46 tests verts.

    L'attendu n'est pas la valeur émise relue à elle-même : c'est le nombre
    d'octets de corps RÉELLEMENT reçus sur le socket. Un en-tête absent comme un
    en-tête faux rougissent donc de la même façon. Les cinq familles de réponse
    passent toutes par `_send` : page, actif, 404, refus, succès JSON.
    """
    cible = _pointe_vers_une_copie(tmp_path, monkeypatch)
    payload = json.dumps({"json": cible.read_text(encoding="utf-8")}).encode("utf-8")
    hostile = {"Host": "cms.evil.example.com", "Content-Type": "application/json",
               "Content-Length": str(len(payload))}
    with _server() as base:
        port = _port_of(base)
        legitimes = _entetes_legitimes(port, **{"Content-Length": str(len(payload))})
        plafond = _entetes_legitimes(
            port, **{"Content-Length": str(atelier.MAX_BODY_BYTES + 1)})
        cas = [("GET", "/", None, b"", 200),
               ("GET", "/assets/js/cms-model.js", None, b"", 200),
               ("GET", "/inconnu", None, b"", 404),
               ("POST", "/save", hostile, payload, 403),
               ("POST", "/save", plafond, b"", 413),
               ("POST", "/save", legitimes, payload, 200)]
        for methode, chemin, entetes_req, corps_req, attendu in cas:
            code, entetes, corps = _reponse(port, chemin, entetes_req, corps_req, methode)
            assert code == attendu, (methode, chemin, code)
            assert corps, f"{methode} {chemin} : corps vide, la mesure serait vide de sens"
            assert "content-length" in entetes, (
                f"{methode} {chemin} : réponse sans Content-Length")
            assert int(entetes["content-length"]) == len(corps), (
                f"{methode} {chemin} : Content-Length annoncé "
                f"{entetes['content-length']}, {len(corps)} octets reçus")


# ── un ciblage dégradé doit être visible DANS LE PRODUIT (mesuré 2026-08-03) ───
#
# Premier usage réel de la chaîne : le tier LLM a expiré, `extract_cfg` est retombé
# sur le cfg défaut, et un CV GÉNÉRIQUE est parti sous le nom `cv_cible.pdf` avec
# le statut « Ciblage: general~0.0 ». Le WARNING existait bel et bien — dans la
# console du serveur, pendant que le PDF partait chez le recruteur.
#
# Les deux cfg ci-dessous sortent du VRAI chemin `cv_target.extract_cfg` et ne sont
# jamais écrits à la main : un cfg recopié depuis la structure attendue ne pourrait
# pas diverger de l'implémentation qu'il prétend surveiller.

def _profil_reel():
    import pathlib
    chemin = pathlib.Path(__file__).resolve().parents[2] / "profile.json"
    return json.loads(chemin.read_text(encoding="utf-8"))


def _cfg_repli(profil):
    def expire(_p):
        raise RuntimeError("litellm.Timeout after 120.0s")   # l'erreur réellement vue
    return cv_target.extract_cfg("Ingénieur quantitatif chez Amundi.", profil,
                                 complete_fn=expire)


def _cfg_extrait(profil):
    rendu = json.dumps({"relevance_key": "quant", "min_relevance": 0.75,
                        "domains_in": ["quant"], "keywords": ["machine learning"],
                        "company": "Amundi", "job_title": "Ingénieur quantitatif",
                        "requirements": ["machine learning"], "register": "formel",
                        "market": None})
    return cv_target.extract_cfg("Ingénieur quantitatif chez Amundi.", profil,
                                 complete_fn=lambda _p: rendu)


def test_a_fallback_cfg_is_detected_as_degraded():
    assert atelier.ciblage_degrade(_cfg_repli(_profil_reel())) is True


def test_a_real_extraction_is_not_flagged_as_degraded():
    """Le garde doit MORDRE le repli sans mordre un vrai ciblage : un garde qui
    refuse tout est inutile de la même façon qu'un garde qui laisse tout passer."""
    assert atelier.ciblage_degrade(_cfg_extrait(_profil_reel())) is False


# ── exposition réseau : opt-in explicite, jamais par défaut ───────────────────

def test_par_defaut_l_atelier_reste_loopback_et_refuse_tout_autre_hote(monkeypatch):
    """Le durcissement d'origine EST le défaut. Un déploiement k8s doit le lever
    exprès ; l'oublier ne doit jamais ouvrir la page qui sert le profil entier."""
    monkeypatch.delenv("ATELIER_HOSTS", raising=False)
    monkeypatch.delenv("ATELIER_BIND", raising=False)
    assert atelier._bind() == "127.0.0.1"
    assert atelier._hostport_ok("kleos.elysium.local", 8010) is False


def test_un_hote_declare_est_accepte_sans_jamais_fermer_le_loopback(monkeypatch):
    """L'allowlist s'ÉTEND, elle ne se remplace pas : un déploiement qui ajoute son
    hôte ne doit pas couper l'accès local par lequel on le diagnostique."""
    monkeypatch.setenv("ATELIER_HOSTS", "kleos.elysium.local")
    assert atelier._hostport_ok("kleos.elysium.local", 8010) is True
    assert atelier._hostport_ok("127.0.0.1:8010", 8010) is True
    assert atelier._hostport_ok("localhost:8010", 8010) is True
    # Un voisin de domaine n'hérite de rien : l'allowlist compare des noms entiers.
    assert atelier._hostport_ok("kleos.elysium.local.evil.tld", 8010) is False
    assert atelier._hostport_ok("evil-kleos.elysium.local", 8010) is False


def test_the_degraded_verdict_renames_the_artefact():
    """La vérité doit voyager AVEC le fichier : l'écran se ferme, le PDF reste."""
    profil = _profil_reel()
    degrade = atelier.verdict_ciblage(_cfg_repli(profil))
    normal = atelier.verdict_ciblage(_cfg_extrait(profil))
    assert degrade["nom"] != normal["nom"], "les deux CV portent le même nom"
    assert "cible" not in degrade["nom"], f"un CV non ciblé nommé {degrade['nom']!r}"
    assert degrade["message"] != normal["message"]


def test_le_pilote_playwright_suit_le_chromium_de_l_image():
    """Le paquet pip et l'image de base DOIVENT porter la même version.

    Le paquet `playwright` n'est qu'un pilote ; les navigateurs sont cuits dans
    l'image `mcr.microsoft.com/playwright/python:vX-noble`. Un décalage ne se voit
    NI à la construction NI au démarrage — il tue le premier rendu PDF, en
    production, sur « Executable doesn't exist at /ms-playwright/... ».

    Mesuré le 2026-08-04 : une contrainte `>=1.58,<2` a installé 1.62.0 sur une base
    v1.58.0-noble, et Kleos a rendu 500 sur son bouton principal. Un commentaire
    « garder ces deux valeurs égales » ne garde rien — il n'est lu que par qui a déjà
    décidé de changer la ligne. Ce test, lui, échoue au moment du bump.
    """
    ici = pathlib.Path(__file__).resolve().parent
    epingle = re.search(r"^playwright==(\S+)",
                        (ici / "requirements-atelier.txt").read_text(encoding="utf-8"),
                        re.M)
    assert epingle, "playwright doit être épinglé avec ==, jamais borné par une plage"

    base = re.search(r"^FROM mcr\.microsoft\.com/playwright/python:v(\S+?)-",
                     (ici / "Dockerfile.kleos").read_text(encoding="utf-8"), re.M)
    assert base, "image de base playwright introuvable dans Dockerfile.kleos"

    assert epingle.group(1) == base.group(1), (
        f"pilote pip {epingle.group(1)} vs chromium de l'image {base.group(1)} — "
        "le rendu PDF mourra en production, pas ici")
