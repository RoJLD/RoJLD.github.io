"""Les pages publiques ne mentent plus : plus de /life-architect/ (bêta morte), plus de
cv/*.html (persona Founder figée), et l'URL canonique du site est robin-denis.com.
Mesuré le 2026-09-28 : /life-architect/ pointait un formulaire vers un Render éteint et
un dépôt privé en 404 ; cv/*.html n'avaient aucun lien entrant."""
import json
import re
import subprocess
from pathlib import Path

SITE = Path(__file__).resolve().parents[2]


def _suivis():
    out = subprocess.run(["git", "-C", str(SITE), "ls-files"], capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def test_les_pages_mortes_ne_sont_plus_suivies():
    f = _suivis()
    assert not [p for p in f if p.startswith("life-architect/")]
    assert not [p for p in f if re.match(r"^cv/[^/]+\.html$", p)]
    assert "cv/prefab/full_fr.pdf" in f                      # les PDF vivants restent


def test_aucune_page_ne_mene_plus_a_ces_chemins():
    for p in _suivis():
        if p.endswith(".html"):
            t = (SITE / p).read_text(encoding="utf-8", errors="replace")
            assert "life-architect/" not in t, p
            assert not re.search(r'href="[^"]*cv/(index|ai_ml_engineer|solo_founder|software_architect|compiler_engineer|devops_platform|quality_sre)\.html', t), p


def test_l_url_du_portfolio_est_canonique():
    p = json.loads((SITE / "profile.json").read_text(encoding="utf-8"))
    assert p["identity"]["links"]["portfolio"] == "https://robin-denis.com"
