"""Formes RÉELLES des sorties career-ops, mesurées le 2026-09-29 et le 2026-10-03 (données anonymisées)."""
import subprocess

TRACKER = [
    {"id": 23, "date": "2026-09-10", "company": "Acme", "role": "Quantitative Developer", "score": "4.5/5",
     "status": "Evaluated", "pdf": "✅", "report": "[23](../reports/023-acme.md)", "notes": "Apply now"},
    {"id": 24, "date": "2026-09-11", "company": "?", "role": "Quant Developer Python", "score": "4.1/5",
     "status": "Evaluated", "pdf": "✅", "report": "[024](../reports/024-agence.md)", "notes": "email __TOKEN__ piège"},
    {"id": 5, "date": "2026-08-06", "company": "Globex", "role": "Quantitative Developer", "score": "4.3/5",
     "status": "Discarded", "pdf": "✅", "report": "[5](../reports/005-globex.md)", "notes": "morte"},
    {"id": 1, "date": "2026-08-06", "company": "Initech", "role": "OSS ML Engineer", "score": "3.3/5",
     "status": "Evaluated", "pdf": "❌", "report": "[1](../reports/001-initech.md)", "notes": ""},
]
KPI = {"stage": "entry", "threshold": 4,
       "kpis": [{"key": "scan_yield", "stage": "entry", "label": "Rendement de scan", "help": "", "state": "computable",
                 "value": 0.8, "numerator": 24, "denominator": 2928, "smallSample": False, "unlock": None, "owner": None},
                {"key": "application_rate", "stage": "entry", "label": "Passage à la candidature", "help": "", "state": "computable",
                 "value": 0.0, "numerator": 0, "denominator": 24, "smallSample": False, "unlock": None, "owner": None},
                {"key": "response_rate", "stage": "conversion", "label": "Taux de réponse", "help": "", "state": "locked",
                 "value": None, "numerator": None, "denominator": None, "smallSample": False, "unlock": "1 candidature envoyée", "owner": None}],
       "nextUnlock": {"key": "response_rate", "label": "Taux de réponse", "unlock": "1 candidature envoyée"},
       # Ajouts career-ops du 2026-10-02 (kpi.mjs : pouls hebdomadaire, entonnoir par canal).
       "pulse": {"conversations28": 1, "sends7": 0, "sends28": 0, "inbound28": 1,
                 "followups": {"due": 0, "overdue": 0, "next": "2026-10-08 (Globex)"},
                 "ready": 2, "oldestDays": 23, "oldest": "Acme #023", "expectedLostPerWeek": 0.18,
                 "hazardPerDay": 0.0139, "hazardMeasured": True,
                 "wip": [{"track": "principal", "label": "Poste principal", "count": 2, "limit": 3, "exceeded": False, "hours": 2.0}]},
       "channels": [{"channel": "scan", "label": "scanner ATS", "evaluated": 17, "aboveThreshold": 4, "applied": 0, "responded": 0, "interview": 0},
                    {"channel": "inbound", "label": "approche entrante", "evaluated": 1, "aboveThreshold": 1, "applied": 0, "responded": 1, "interview": 0}]}
RELANCES = {"metadata": {"analysisDate": "2026-09-29", "totalTracked": 24, "actionable": 0, "overdue": 0, "urgent": 0,
                         "cold": 0, "waiting": 0, "retired": 0}, "entries": [], "cadenceConfig": {}, "cadenceDefaults": {}}
WATCH = {"checked": 24, "liveness": 15, "findings": [{"type": "dead", "report": "005", "company": "Globex", "detail": "l'annonce n'est plus en ligne"}],
         "added": 0, "dryRun": True, "skippedForUrl": 0, "skippedForUrlReports": []}
# send-queue.mjs --json (2026-10-03). L'ordre de perTrack[].items est la priorité de la file
# (valeur × perte hebdomadaire ÷ effort) : #024 (4.1) passe avant #023 (4.5), comme mesuré.
SEND_QUEUE = {
    "today": "2026-10-03",
    "hazard": {"hazardPerDay": 0.0139, "measured": True, "deaths": 8, "exposureDays": 576},
    "perTrack": [{
        "track": {"id": "principal", "label": "Poste principal", "threshold": 4, "wipLimit": 3},
        "items": [
            {"num": "024", "company": "?", "role": "Quant Developer Python", "score": 4.1, "priority": 0.1949,
             "waitingDays": 22, "liveness": {"verdict": "active", "via": "api", "date": "2026-10-01"},
             "incomplete": False, "why": {"effort": 0.5, "weeklyLoss": 0.09}, "decision": {"state": "due"}},
            {"num": "023", "company": "Acme", "role": "Quantitative Developer", "score": 4.5, "priority": 0.0879,
             "waitingDays": 23, "liveness": {"verdict": "active", "via": "api", "date": "2026-10-01"},
             "incomplete": False, "why": {"effort": 1.5, "weeklyLoss": 0.09}},
        ],
        "hours": 2.0, "hazardPerDay": 0.0139, "wip": {"count": 2, "limit": 3, "exceeded": False}}],
    "dead": [{"num": "005", "company": "Globex", "role": "Quantitative Developer", "score": 4.3,
              "liveness": {"verdict": "expired", "via": "api", "date": "2026-09-20"}}],
    "below": [], "parked": [], "overdue": [],
    "stats": {"ready": 2, "incomplete": 0, "oldestDays": 23, "oldest": "Acme #023", "expectedLostPerWeek": 0.18,
              "hours": 2.0, "overdue": 0, "parked": 0},
}


class FauxProc:
    """Un Popen factice : sortie fixée, ou délai dépassé si `lent`."""
    pid = 4242

    def __init__(self, out="", err="", code=0, lent=False):
        self.out, self.err, self.returncode, self.lent, self.tue = out, err, code, lent, False

    def communicate(self, timeout=None):
        if self.lent:
            self.lent = False
            raise subprocess.TimeoutExpired(cmd="node", timeout=timeout)
        return self.out, self.err

    def wait(self, timeout=None):
        return self.returncode


def faux_popen(reponses):
    """reponses : dict {premier argument après node → FauxProc}. Journalise les appels."""
    appels = []

    def _popen(argv, **kw):
        appels.append({"argv": argv, "cwd": kw.get("cwd"), "env": kw.get("env")})
        cle = argv[1] if len(argv) > 1 else argv[0]
        return reponses[cle]
    _popen.appels = appels
    return _popen
