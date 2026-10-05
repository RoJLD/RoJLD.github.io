"""Page career-ops : chaque panneau nomme son état, chaque bouton appelle un outil de la
liste blanche, la chaîne de refus POST de l'atelier s'applique aux nouvelles routes.
« À faire » suit l'ordre de la file d'envoi de career-ops, jamais un tri maison par note."""
import copy, json, sys, threading, urllib.error, urllib.request
from pathlib import Path
import pytest

SITE = Path(__file__).resolve().parents[2]
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
from cockpit_fixtures import KPI, RELANCES, SEND_QUEUE, TRACKER  # noqa: E402
from tools.cockpit import career_ops as co, server, web  # noqa: E402
from tools.cockpit.pages import career_ops as page  # noqa: E402


class _Srv:
    def __enter__(self):
        self.srv = server.make_server(0)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        return self
    def __exit__(self, *a):
        self.srv.shutdown(); self.srv.server_close()
    def get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
    def post(self, path, obj, jeton=None):
        corps = json.dumps(obj).encode("utf-8")
        h = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}",
             server.CSRF_HEADER: server.csrf_token() if jeton is None else jeton}
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=corps, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")


def _lu(donnees):
    return lambda root, **k: {"ok": True, "donnees": donnees, "erreur": None, "lu_a": "10:00"}


@pytest.fixture
def configure(monkeypatch, tmp_path):
    monkeypatch.setattr(co, "prerequis", lambda **k: {"ok": True, "career_ops_root": str(tmp_path), "node": "node", "node_version": "25.2.1", "problemes": []})
    monkeypatch.setattr(co.config, "career_ops_root", lambda env=None, local_json=None: tmp_path)
    monkeypatch.setattr(co, "lire_kpi", _lu(KPI))
    monkeypatch.setattr(co, "lire_tracker", _lu(TRACKER))
    monkeypatch.setattr(co, "lire_relances", _lu(RELANCES))
    monkeypatch.setattr(co, "lire_file", _lu(SEND_QUEUE))
    return tmp_path


def test_non_configure_est_dit_pas_un_entonnoir_vide(monkeypatch):
    monkeypatch.setattr(co, "prerequis", lambda **k: {"ok": False, "career_ops_root": None, "node": None, "node_version": None,
                                                       "problemes": ["career-ops non configuré : poser CAREER_OPS_ROOT"]})
    with _Srv() as s:
        code, body = s.get("/career-ops")
    assert code == 200 and "non configuré" in body and "Passage" not in body


def test_la_page_montre_entonnoir_a_faire_file_d_envoi_et_boutons(configure):
    with _Srv() as s:
        code, body = s.get("/career-ops")
    assert code == 200
    assert "Passage à la candidature" in body and "0 / 24" in body and "Taux de réponse" in body and "1 candidature envoyée" in body
    assert "Acme" in body and 'data-n="23"' in body and 'data-n="5"' not in body      # Globex disparue : pas à faire
    assert "File d&#x27;envoi (send-queue)" in body and "agent-inbox.md : FileNotFoundError" in body  # inbox absente : dit
    assert "ENVOI.md" not in body                                                       # sortie de --write, peut dater
    for b in ("kpi", "watch", "scan", "sante", "pistes"):
        assert f'data-action="{b}"' in body
    assert 'data-action="verifier"' not in body
    assert 'data-route="/career-ops/ouvrir-web"' in body and 'data-route="/career-ops/copilote"' in body
    assert "lu à 10:00" in body


def test_a_faire_suit_l_ordre_de_la_file_pas_la_note(configure):
    """#024 (4.1) avant #023 (4.5) : la priorité de send-queue (valeur × perte ÷ effort)."""
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert body.index('data-n="24"') < body.index('data-n="23"')
    assert "repli" not in body


def test_sans_send_queue_a_faire_se_replie_sur_la_note_et_le_dit(configure, monkeypatch):
    monkeypatch.setattr(co, "lire_file", lambda root, **k: {"ok": False, "donnees": None, "lu_a": "10:00",
                                                             "erreur": "node send-queue.mjs --json → code 1 : boom"})
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert "repli" in body and "boom" in body
    assert body.index('data-n="23"') < body.index('data-n="24"')                       # tri par note, assumé et affiché


def test_la_file_d_envoi_montre_stats_pistes_et_disparues(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    file = body[body.index("File d&#x27;envoi (send-queue)"):]
    assert "2 prêt(s)" in file and "2.0 h" in file and "0.18" in file
    assert "Poste principal" in file and "2 / 3" in file
    assert "Globex" in file and "disparue" in file


def test_l_entonnoir_montre_le_pouls_et_les_canaux(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert "conversations sur 28 j : 1" in body and "scanner ATS" in body and "approche entrante" in body
    assert "Par piste" not in body                                                      # une seule piste : pas de tracks[]


def test_l_entonnoir_montre_les_pistes_quand_kpi_en_donne(configure, monkeypatch):
    kpi = copy.deepcopy(KPI)
    kpi["tracks"] = [{"id": "principal", "label": "Poste principal", "threshold": 4, "evaluated": 24, "aboveThreshold": 4,
                      "applied": 0, "conversations28": 1, "ready": 2, "oldestDays": 23, "hours": 2.0},
                     {"id": "week-end", "label": "Job du week-end", "threshold": 3.5, "evaluated": 0, "aboveThreshold": 0,
                      "applied": 0, "conversations28": 0, "ready": 0, "oldestDays": None, "hours": 0}]
    monkeypatch.setattr(co, "lire_kpi", _lu(kpi))
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert "Par piste" in body and "Job du week-end" in body


def test_une_donnee_piegee_ne_recoit_jamais_le_jeton(configure, monkeypatch):
    """Le tracker n'est plus recopié : le piège `__TOKEN__` voyage désormais dans un rôle de la
    file d'envoi, champ encore affiché par « À faire »."""
    fq = copy.deepcopy(SEND_QUEUE)
    fq["perTrack"][0]["items"][0]["role"] = "Quant __TOKEN__ piège"
    monkeypatch.setattr(co, "lire_file", _lu(fq))
    with _Srv() as s:
        code, body = s.get("/career-ops")
    assert "__TOKEN__ piège" in body and body.count(server.csrf_token()) == 1


def test_post_action_passe_par_la_liste_blanche(configure, monkeypatch):
    appels = []
    monkeypatch.setattr(co, "executer", lambda cid, **k: appels.append((cid, k)) or
                        {"id": cid, "argv": ["node", "kpi.mjs", "--json"], "code": 0, "sens": "fait", "stdout": "{}", "stderr": "",
                         "duree_s": 0.1, "interrompu": False, "json": {}, "ecrit": "rien"})
    with _Srv() as s:
        assert s.post("/career-ops/action", {"id": "kpi"})[0] == 200
        code, body = s.post("/career-ops/action", {"id": "rm -rf"})
        assert code == 400 and "inconnue" in body
        assert s.post("/career-ops/action", {"id": "kpi"}, jeton="faux")[0] == 403      # chaîne de refus de l'atelier
    assert appels[0][0] == "kpi" and appels[0][1]["confirme"] is False


def test_post_postule_refuse_les_types_laxistes_et_appelle_postule(configure, monkeypatch):
    vus = []
    monkeypatch.setattr(co, "postule", lambda n, note, **k: vus.append((n, note)) or
                        {"id": "postule", "argv": [], "code": 0, "sens": "enregistré", "stdout": "", "stderr": "", "duree_s": 0.1,
                         "interrompu": False, "json": {"newStatus": "Applied"}, "ecrit": "x"})
    with _Srv() as s:
        for mauvais in ("23", True, 23.5, None):
            assert s.post("/career-ops/postule", {"n": mauvais, "note": ""})[0] == 400
        code, body = s.post("/career-ops/postule", {"n": 23, "note": "ok"})
    assert code == 200 and json.loads(body)["ok"] is True and vus == [(23, "ok")]


def test_action_en_cours_repond_409(configure, monkeypatch):
    def _occupe(cid, **k):
        raise co.ActionEnCours("scan")
    monkeypatch.setattr(co, "executer", _occupe)
    with _Srv() as s:
        code, body = s.post("/career-ops/action", {"id": "kpi"})
    assert code == 409 and "scan" in body


def test_ouvrir_web_relaie_l_etat(configure, monkeypatch):
    monkeypatch.setattr(web, "ouvrir_web", lambda root, **k: {"ok": False, "deja": False, "url": web.URL_WEB, "problemes": ["web/node_modules absent"]})
    with _Srv() as s:
        code, body = s.post("/career-ops/ouvrir-web", {})
    assert code == 503 and "node_modules" in body


def test_md_vers_html_ne_se_tait_jamais():
    """Avec la lib markdown : un <h1> ; sans : un <pre> échappé. Jamais une chaîne vide."""
    out = page.md_vers_html("# Titre\n\n- a")
    assert "Titre" in out and ("<pre>" in out or "<h1>" in out)


def _panneau(body, titre):
    """Le HTML d'un panneau, de son <h2> au suivant."""
    debut = body.index(f"<h2>{titre}")
    return body[debut:body.index("</section>", debut)]


def test_le_panneau_candidatures_compte_par_statut_et_renvoie_au_pipeline(configure):
    """Le web de career-ops est l'interface des candidatures : le cockpit garde les comptes et
    renvoie au pipeline, il ne recopie plus le tracker ligne à ligne."""
    with _Srv() as s:
        code, body = s.get("/career-ops")
    p = _panneau(body, "Candidatures (tracker)")
    assert "Evaluated : 3" in p and "Discarded : 1" in p
    assert "<table" not in p and "Initech" not in p
    assert 'data-route="/career-ops/ouvrir-web"' in p and 'data-chemin="/pipeline"' in p
    assert "Ouvrir le pipeline dans career-ops" in p


def test_le_panneau_relances_resume_et_renvoie_aux_followups(configure, monkeypatch):
    """lire_relances passe --overdue-only : les entrées sont les relances EN RETARD, donc la date
    minimale est la plus ancienne en retard, jamais une « prochaine » échéance."""
    rel = copy.deepcopy(RELANCES)
    rel["metadata"].update({"overdue": 2, "urgent": 1, "waiting": 3, "totalTracked": 24})
    rel["entries"] = [{"company": "Relancia", "urgency": "overdue", "nextFollowupDate": "2026-10-03"},
                      {"company": "Autrefois", "urgency": "overdue", "nextFollowupDate": "2026-09-28"}]
    monkeypatch.setattr(co, "lire_relances", _lu(rel))
    with _Srv() as s:
        _, body = s.get("/career-ops")
    p = _panneau(body, "Relances dues")
    assert "2 en retard · 1 urgentes · 3 en attente (sur 24 suivies)" in p
    assert "la plus ancienne en retard : 2026-09-28" in p and "prochaine" not in p
    assert "<table" not in p and "Relancia" not in p and "Autrefois" not in p
    assert 'data-route="/career-ops/ouvrir-web"' in p and 'data-chemin="/followups"' in p
    assert "Ouvrir les relances dans career-ops" in p


def test_le_panneau_relances_sans_echeance_ne_montre_pas_de_prochaine_date(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    p = _panneau(body, "Relances dues")
    assert "0 en retard" in p and "prochaine" not in p and 'data-chemin="/followups"' in p


def test_chaque_ligne_a_faire_ouvre_son_rapport_dans_le_web(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    p = _panneau(body, "À faire maintenant")
    for n in (23, 24):
        assert f'data-chemin="/pipeline/{n}"' in p and f'data-n="{n}"' in p
    assert p.count('data-route="/career-ops/ouvrir-web"') == 2
    assert ">Ouvrir<" in p


def test_le_repli_a_faire_ouvre_aussi_son_rapport_dans_le_web(configure, monkeypatch):
    monkeypatch.setattr(co, "lire_file", lambda root, **k: {"ok": False, "donnees": None, "lu_a": "10:00", "erreur": "boom"})
    with _Srv() as s:
        _, body = s.get("/career-ops")
    p = _panneau(body, "À faire maintenant")
    assert 'data-chemin="/pipeline/23"' in p and 'data-chemin="/pipeline/24"' in p


def test_les_chemins_d_ouverture_sont_des_constantes_ou_un_entier(configure, monkeypatch):
    """Aucune donnée de career-ops (société, notes, rapport mal formé) n'entre dans un chemin."""
    tr = copy.deepcopy(TRACKER)
    tr[0]["report"] = '[23"><script>x</script>](../reports/023-acme.md)'
    monkeypatch.setattr(co, "lire_tracker", _lu(tr))
    monkeypatch.setattr(co, "lire_file", lambda root, **k: {"ok": False, "donnees": None, "lu_a": "10:00", "erreur": "boom"})
    with _Srv() as s:
        _, body = s.get("/career-ops")
    import re
    chemins = set(re.findall(r'data-chemin="([^"]*)"', body))
    assert chemins and all(re.fullmatch(r"/(followups|pipeline(/\d+)?)", c) for c in chemins), chemins
    assert "<script>x" not in body


def test_le_js_n_ouvre_qu_un_chemin_local_sans_double_barre_ni_deux_points(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    assert "function cheminValide" in body and "dataset.chemin" in body


def test_les_workflows_disent_ce_que_fait_le_web(configure):
    with _Srv() as s:
        _, body = s.get("/career-ops")
    p = _panneau(body, "Workflows")
    assert "Candidatures, CV sur mesure, candidature assistée et assistant « Ask » : interface web de career-ops" in p
    assert "Workflows agent (évaluer" not in p
