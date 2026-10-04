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
import secrets
import socket
import sys
import time
import urllib.parse
from typing import Optional

from tools.cockpit import config  # insère la racine du site, tools/ et tools/cv/ dans sys.path

_ROOT = config.SITE_ROOT

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


from tools.cockpit.pages import cv as pages_cv  # noqa: E402
from tools.cockpit.pages import accueil  # noqa: E402

ROUTES_GET = {
    "/": accueil.page_accueil,
    "/cv/": pages_cv.page_atelier,
    "/edit": pages_cv.page_edit,
    "/cms": pages_cv.page_cms,
}
ROUTES_POST = {
    "/generate": pages_cv.handle_generate,
    "/generate-docx": pages_cv.handle_generate_docx,
    "/generate-letter": pages_cv.handle_generate_letter,
    "/save": pages_cv.handle_save,
}

from tools.cockpit.pages import career_ops as pages_career_ops  # noqa: E402

ROUTES_GET["/career-ops"] = pages_career_ops.page_career_ops
ROUTES_POST.update({
    "/career-ops/action": pages_career_ops.post_action,
    "/career-ops/postule": pages_career_ops.post_postule,
    "/career-ops/ouvrir-web": pages_career_ops.post_ouvrir_web,
    "/career-ops/copilote": pages_career_ops.post_copilote,
})

from tools.cockpit.pages import anthropos as pages_anthropos  # noqa: E402

ROUTES_GET["/anthropos"] = pages_anthropos.page_anthropos


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
        chemin = urllib.parse.urlsplit(self.path).path
        route = ROUTES_GET.get(chemin)
        if route is not None:
            return route(self)
        if chemin in _STATIC_ALLOW:
            # urlsplit : `?v=1` (cache-busting) ne doit pas faire échouer l'allowlist
            return self._send(200, _STATIC_ALLOW[chemin], (_ROOT / chemin.lstrip("/")).read_bytes())
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
        route = ROUTES_POST.get(self.path)
        if route is None:
            return self._send(404, "text/plain", b"not found")
        return route(self, data)

    def token(self) -> str:
        return csrf_token()

    # Délégations gardées pour test_cv_render.py:111-114 (Handler.__new__ + _send factice)
    def _handle_generate(self, data):        return pages_cv.handle_generate(self, data)
    def _handle_generate_docx(self, data):   return pages_cv.handle_generate_docx(self, data)
    def _handle_generate_letter(self, data): return pages_cv.handle_generate_letter(self, data)
    def _handle_save(self, data):            return pages_cv.handle_save(self, data)


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
    sys.exit(main())
