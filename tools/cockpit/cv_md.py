"""Rendu de cv.md (career-ops) depuis profile.json + complément privé (spec D8 § 5).

Pur : aucune lecture de fichier, aucune date du jour. Même entrée, même sortie, octet pour
octet. C'est ce qui rend stable l'empreinte de la garde de dérive (derive.py). La structure
reprend celle que career-ops lit aujourd'hui : titre, contact, `## English`, `---`,
`## Français`, et les mêmes rubriques `###` (cv.md mesuré le 2026-10-07)."""
from __future__ import annotations

import re

LANGUES = ("en", "fr")
NOM_LANGUE = {"en": "English", "fr": "Français"}
MOIS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "fr": ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]}
PRESENT = {"en": "Present", "fr": "Aujourd'hui"}
TYPE = {"stage": {"en": "Internship", "fr": "Stage"}, "alternance": {"en": "Apprenticeship", "fr": "Alternance"}}
TITRES = {
    "en": {"education": "Education", "experience": "Professional Experience", "academic": "Academic Projects",
           "personal": "Personal Projects", "other": "Other Projects (to be detailed later)",
           "skills": "Languages & Skills", "interests": "Activities & Interests",
           "languages": "Languages", "certifications": "Certifications", "coursework": "Coursework"},
    "fr": {"education": "Formation", "experience": "Expérience professionnelle", "academic": "Projets académiques",
           "personal": "Projets personnels", "other": "Autres projets (à détailler ultérieurement)",
           "skills": "Langues & Compétences", "interests": "Centres d'intérêt",
           "languages": "Langues", "certifications": "Certifications", "coursework": "Cours"},
}
DEUX_POINTS = {"en": ":", "fr": " :"}
_EMOJI_TETE = re.compile(r"^[^\w(]+\s*")   # « ♟️ Échecs » → « Échecs »


def t(v, lang: str) -> str:
    """Texte d'un champ bilingue ({fr, en}) ou unique (str) ; repli sur l'autre langue ; vide si absent."""
    if v is None:
        return ""
    if isinstance(v, dict):
        return str(v.get(lang) or v.get("en" if lang == "fr" else "fr") or "").strip()
    return str(v).strip()


def _mois(ym, lang: str) -> tuple[str, str]:
    annee, _, mois = str(ym).partition("-")
    return (MOIS[lang][int(mois) - 1] if mois else ""), annee


def periode(start, end, lang: str) -> str:
    """« Feb – Aug 2026 », « Sep 2025 – Feb 2026 », « Feb 2026 – Present »."""
    if not start:
        return ""
    m1, a1 = _mois(start, lang)
    debut = f"{m1} {a1}".strip()
    if not end:
        return f"{debut} – {PRESENT[lang]}"
    m2, a2 = _mois(end, lang)
    if a1 == a2 and m1 and m2:
        return f"{m1} – {m2} {a2}"
    return f"{debut} – {f'{m2} {a2}'.strip()}"


def annees(start, end) -> str:
    a1, a2 = str(start or "")[:4], str(end or "")[:4]
    return f"{a1}–{a2}" if a1 and a2 and a1 != a2 else (a1 or a2)


def lien_court(url) -> str:
    return re.sub(r"^https?://(www\.)?", "", str(url or "")).rstrip("/")


def _contact(profile: dict, comp: dict) -> str:
    ide = profile.get("identity", {})
    lieu = ide.get("location") or {}
    loc = t(comp.get("location"), "en") or ", ".join(x for x in (lieu.get("city"), lieu.get("country")) if x)
    liens = ide.get("links", {})
    morceaux = [loc, comp.get("phone", ""), ide.get("email", ""), lien_court(liens.get("portfolio")),
                lien_court(liens.get("github")), lien_court(liens.get("linkedin"))]
    return " · ".join(m for m in morceaux if m)


def _formation(profile: dict, lang: str) -> list[str]:
    lignes = []
    for e in profile.get("education", []):
        tete = f"- **{annees(e.get('start'), e.get('end'))} — {t(e.get('title'), lang)}**"
        suite = [x.rstrip(".") for x in (t(e.get("location"), lang), t(e.get("org"), lang)) if x]
        lignes.append(tete + (" — " + ". ".join(suite) + "." if suite else ""))
        cours = [t(c, lang) for c in e.get("courses") or [] if t(c, lang)]
        if cours:
            libelle = t(e.get("courses_label"), lang) or TITRES[lang]["coursework"]
            lignes.append(f"  {libelle}{DEUX_POINTS[lang]} {', '.join(cours)}.")
    return lignes


def _experiences(profile: dict, comp: dict) -> list[dict]:
    exps = list(profile.get("experiences", [])) + list(comp.get("experiences_cv", []))
    return sorted(exps, key=lambda e: str(e.get("start") or ""), reverse=True)


def _experience(e: dict, lang: str) -> list[str]:
    fin = None if e.get("current") else e.get("end")
    societe = ", ".join(y for y in (str(e.get("company") or ""), t(e.get("location"), lang)) if y)
    tete = " — ".join(x for x in (periode(e.get("start"), fin, lang), societe, t(e.get("title"), lang)) if x)
    typ = TYPE.get(str(e.get("type") or "").lower())
    if typ:
        tete += f" ({typ[lang]})"
    return [f"- **{tete}**"] + [f"  - {b}" for b in (e.get("bullets") or {}).get(lang, []) if str(b).strip()]


def _projets(profile: dict, groupe: str, lang: str) -> list[str]:
    lignes = []
    for p in profile.get("projects", []):
        cv = p.get("cv") or {}
        if cv.get("group") != groupe:
            continue
        titre = t(cv.get("title"), lang) or t(p.get("name"), lang)
        if groupe == "other":
            lignes.append(f"- {titre}")
            continue
        quand = periode(cv.get("start"), cv.get("end"), lang) if cv.get("start") else ""
        tete = " — ".join(x for x in (quand, titre, t(cv.get("role"), lang)) if x)
        resume = t(cv.get("summary"), lang)
        lignes.append(f"- **{tete}**" + (f" — {resume}" if resume else ""))
        lignes += [f"  - {b}" for b in (cv.get("bullets") or {}).get(lang, []) if str(b).strip()]
    return lignes


def _competences(profile: dict, lang: str) -> list[str]:
    dp, lignes = DEUX_POINTS[lang], []
    langues = []
    for item in profile.get("languages", []):
        nom, niveau = t(item.get("name"), lang), t(item.get("level"), lang)
        langues.append(f"{nom} ({niveau})" if niveau else nom)
    if langues:
        lignes.append(f"- **{TITRES[lang]['languages']}{dp}** {', '.join(langues)}")
    certs = [t(c, lang) for c in profile.get("certifications", []) if t(c, lang)]
    if certs:
        lignes.append(f"- **{TITRES[lang]['certifications']}{dp}** {', '.join(certs)}")
    for s in (profile.get("cv") or {}).get("skills", []):
        items = s.get("items")
        texte = ", ".join(t(i, lang) for i in items) if isinstance(items, list) else t(items, lang)
        if texte:
            lignes.append(f"- **{t(s.get('label'), lang)}{dp}** {texte}")
    return lignes


def _interets(profile: dict, lang: str) -> list[str]:
    propres = (profile.get("cv") or {}).get("interests")
    if propres:
        return [f"- {t(x, lang)}" for x in propres if t(x, lang)]
    items = [_EMOJI_TETE.sub("", t(x, lang)) for x in profile.get("interests", [])]
    items = [x for x in items if x]
    return [f"- {', '.join(items)}"] if items else []


def _section(titre: str, lignes: list[str]) -> str:
    return f"### {titre}\n" + "\n".join(lignes) if lignes else ""


def rendre(profile: dict, complement: dict) -> str:
    """Corps de cv.md, sans l'en-tête de la garde de dérive, en LF, terminé par un saut de ligne."""
    ide = profile.get("identity", {})
    nom = f"{ide.get('first_name', '')} {ide.get('last_name', '')}".strip()
    blocs = [f"# {nom} — CV", _contact(profile, complement), "---"]
    for i, lang in enumerate(LANGUES):
        if i:
            blocs.append("---")
        tt = TITRES[lang]
        exps = [ligne for e in _experiences(profile, complement) for ligne in _experience(e, lang)]
        sections = [_section(tt["education"], _formation(profile, lang)),
                    _section(tt["experience"], exps),
                    _section(tt["academic"], _projets(profile, "academic", lang)),
                    _section(tt["personal"], _projets(profile, "personal", lang)),
                    _section(tt["other"], _projets(profile, "other", lang)),
                    _section(tt["skills"], _competences(profile, lang)),
                    _section(tt["interests"], _interets(profile, lang))]
        blocs.append(f"## {NOM_LANGUE[lang]}")
        blocs += [s for s in sections if s]
    return "\n\n".join(blocs) + "\n"
