"""Le bundle navigateur des templates CV.

Le bundle ne porte que de la DONNÉE : la machinerie (`buildCss`) est du vrai JS
écrit à la main dans assets/js/cv-render.js, aux côtés de son jumeau `renderHtml`.
C'est le harnais de parité — un cas CSS par template — qui interdit aux deux
implémentations de diverger, comme il le fait déjà pour le rendu.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "cv"))
import build_cv_templates as bct  # noqa: E402
import build_site as bs  # noqa: E402
import cv_templates  # noqa: E402


def test_bundle_contient_tous_les_templates():
    js = bct.build_cv_templates(write=False)
    for t in cv_templates.lister():
        assert f'"{t["id"]}"' in js


def test_bundle_idempotent():
    """Un builder non idempotent ferait bouger l'artefact généré à chaque
    construction : tout diff deviendrait illisible et le bundle ne pourrait plus
    servir de témoin de fraîcheur."""
    assert bct.build_cv_templates(write=False) == bct.build_cv_templates(write=False)


def test_bundle_sans_fetch():
    """Le site doit fonctionner hors ligne : les templates sont INLINÉS, jamais
    récupérés par le réseau."""
    js = bct.build_cv_templates(write=False)
    for interdit in ("fetch(", "XMLHttpRequest", "import(", "require("):
        assert interdit not in js


def test_bundle_porte_le_style_entier_pas_un_css_prerendu():
    """Le navigateur CALCULE le CSS depuis `style` ; il ne reçoit pas un CSS déjà
    rendu. Sinon `buildCss` côté JS ne serait jamais exercé en production et la
    parité ne garderait plus rien de réel."""
    js = bct.build_cv_templates(write=False)
    for cle in ("section_gap", "bullet_gap", "accent", "margin"):
        assert f'"{cle}"' in js
    assert "@page" not in js


def test_bundle_sur_disque_est_a_jour():
    """L'artefact commité doit correspondre à la donnée courante.

    Un bundle périmé sert au navigateur un template que plus personne n'édite,
    et aucun test de logique ne peut le voir — seul l'artefact lui-même le dit.
    """
    disque = (ROOT / "assets" / "js" / "cv-templates.js").read_text(encoding="utf-8")
    assert disque == bct.build_cv_templates(write=False)


def test_echec_du_builder_templates_remonte(monkeypatch):
    """Zero Masking, même leçon que pour les articles : un builder dont l'échec est
    avalé laisse la construction verte avec un artefact périmé."""
    import pytest

    def _boum(*a, **k):
        raise RuntimeError("boum")

    monkeypatch.setattr(bct, "build_cv_templates", _boum)
    with pytest.raises(bs.BuildError, match="templates"):
        bs.build(write=False)
