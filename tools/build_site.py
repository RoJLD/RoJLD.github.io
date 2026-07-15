#!/usr/bin/env python3
"""build_site.py — Vitrine SP0 keystone : génère la homepage depuis profile.json.

Modèle (SIGIL vitrine SP0, réframé) : profile.json est l'UNIQUE source. Le build
génère (a) le markup FR des cartes (fallback pré-JS + clés data-i18n stables) et
(b) les entrées CONTENU du dict i18n (fr ET en) depuis les champs bilingues de
profile.json. Les clés CHROME du dict i18n (nav, titres de section…) restent à la
main. Injection entre marqueurs : HTML (`<!-- BUILD:x -->`) pour le body, JS
(`/* BUILD:x */`) pour le dict i18n (commentaires HTML illégaux dans un <script>).

Pilote SP0 = section #blog (articles). Extensible section par section.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BuildError(Exception):
    pass


# ── I/O ───────────────────────────────────────────────────────────────────────
def load_profile(path=None):
    p = Path(path) if path else ROOT / "profile.json"
    return json.loads(p.read_text(encoding="utf-8"))


def inject(text, open_m, close_m, content):
    """Remplace ce qui est entre open_m et close_m (inclus, bornes conservées).
    Fail-loud si un marqueur manque. Idempotent."""
    if open_m not in text or close_m not in text:
        raise BuildError(f"marqueur absent : {open_m!r} / {close_m!r}")
    pat = re.compile(re.escape(open_m) + r".*?" + re.escape(close_m), re.DOTALL)
    return pat.sub(lambda _: open_m + content + close_m, text, count=1)


# ── Helpers ───────────────────────────────────────────────────────────────────
def esc(s):
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def js_str(s):
    """Encode une string pour un littéral JS double-quote (dict i18n)."""
    return json.dumps("" if s is None else str(s), ensure_ascii=False)


_MONTHS = {
    "fr": ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"],
    "en": ["", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
}


def fmt_date(iso, lang):
    """'2026-03' -> 'Mars 2026' (fr) / 'March 2026' (en). Fail-loud si mal formé."""
    m = re.match(r"^(\d{4})-(\d{2})$", str(iso or ""))
    if not m:
        raise BuildError(f"date attendue 'YYYY-MM', reçu {iso!r}")
    year, month = m.group(1), int(m.group(2))
    if not 1 <= month <= 12:
        raise BuildError(f"mois hors bornes : {iso!r}")
    return f"{_MONTHS[lang][month]} {year}"


def _bi(field, lang):
    """Champ bilingue {fr,en} → la langue demandée. Fail-loud si absent."""
    if not isinstance(field, dict) or lang not in field:
        raise BuildError(f"champ bilingue attendu {{fr,en}}, reçu {field!r}")
    return field[lang]


# ── Section #blog ─────────────────────────────────────────────────────────────
def render_blog(profile):
    """Markup FR de .blog-grid depuis profile.articles[]. Fallback = fr ; clés
    data-i18n = blog{N}_*. Réconciliation : status=soon → carte non-cliquable +
    badge blog_soon ; sinon <a href=url>."""
    cards = []
    for i, a in enumerate(profile["articles"], start=1):
        soon = a.get("status") == "soon"
        date_fr = fmt_date(a["date"], "fr")
        title_fr, desc_fr = _bi(a["title"], "fr"), _bi(a["desc"], "fr")
        tags = "".join(f'<span class="blog-tag">{esc(t)}</span>' for t in a.get("tags", []))
        if soon:
            tags += ('<span class="blog-tag" data-i18n="blog_soon" '
                     'style="background:var(--warm-g);color:var(--warm)">À venir</span>')
        inner = (f'<div class="blog-date" data-i18n="blog{i}_date">{esc(date_fr)}</div>'
                 f'<h4 data-i18n="blog{i}_title">{esc(title_fr)}</h4>'
                 f'<p data-i18n="blog{i}_desc">{esc(desc_fr)}</p>'
                 f'<div class="blog-tags">{tags}</div>')
        if soon:
            cards.append(f'<div class="blog-card" style="opacity:.55;cursor:default">{inner}</div>')
        else:
            cards.append(f'<a class="blog-card" href="{esc(a["url"])}">{inner}</a>')
    return "\n    " + "\n    ".join(cards) + "\n"


def gen_i18n_blog(profile, lang):
    """Lignes d'entrées CONTENU du dict i18n pour #blog, langue `lang`."""
    out = []
    for i, a in enumerate(profile["articles"], start=1):
        out.append(f'        blog{i}_date: {js_str(fmt_date(a["date"], lang))}, '
                   f'blog{i}_title: {js_str(_bi(a["title"], lang))},')
        out.append(f'        blog{i}_desc: {js_str(_bi(a["desc"], lang))},')
    return "\n" + "\n".join(out) + "\n"


# ── Section #interests (langues + centres d'intérêt) ──────────────────────────
def render_interests(profile):
    """Markup .langs + label + .ints depuis profile.languages[] et profile.interests[].
    Clés data-i18n : lang_<code>/lang_<code>_lvl (langues), int_<N> (intérêts).
    lbl_interests reste une clé CHROME (label de sous-section)."""
    langs = "\n        ".join(
        f'<div class="lang"><span class="lf">{L["flag"]}</span>'
        f'<div><div class="ln" data-i18n="lang_{L["code"]}">{esc(_bi(L["name"], "fr"))}</div>'
        f'<div class="ll" data-i18n="lang_{L["code"]}_lvl">{esc(_bi(L["level"], "fr"))}</div>'
        f'</div></div>'
        for L in profile["languages"]
    )
    ints = "\n        ".join(
        f'<span class="int" data-i18n="int_{i}">{esc(_bi(it, "fr"))}</span>'
        for i, it in enumerate(profile["interests"], start=1)
    )
    return (f'\n    <div class="langs">\n        {langs}\n    </div>\n'
            f'    <div class="label" data-i18n="lbl_interests">Centres d\'intérêt</div>\n'
            f'    <div class="ints">\n        {ints}\n    </div>\n')


def gen_i18n_langs(profile, lang):
    out = [f'        lang_{L["code"]}: {js_str(_bi(L["name"], lang))}, '
           f'lang_{L["code"]}_lvl: {js_str(_bi(L["level"], lang))},'
           for L in profile["languages"]]
    return "\n" + "\n".join(out) + "\n"


def gen_i18n_ints(profile, lang):
    out = [f'        int_{i}: {js_str(_bi(it, lang))},'
           for i, it in enumerate(profile["interests"], start=1)]
    return "\n" + "\n".join(out) + "\n"


# ── Section #testimonials (recommandations) ───────────────────────────────────
_DOC_STYLE = ("font-size:12px;color:var(--accent);text-decoration:none;"
              "display:inline-flex;align-items:center;gap:5px")


def render_testimonials(profile):
    """Markup .testi-grid depuis profile.recommendations[]. Modèle docs[{path,label}]
    (corrige le bug pré-existant : lien 'académique' écrasé par testi_pdf). Clés
    data-i18n : testi{N}(text), testi{N}_name, testi{N}_role, testi{N}_doc{M}."""
    cards = []
    for i, r in enumerate(profile["recommendations"], start=1):
        docs = r["docs"]
        links = "".join(
            f'<a href="{esc(d["path"])}" target="_blank" style="{_DOC_STYLE}" '
            f'data-i18n="testi{i}_doc{m}">{esc(_bi(d["label"], "fr"))}</a>'
            for m, d in enumerate(docs, start=1)
        )
        wrap = "margin-top:14px;display:flex;gap:10px" if len(docs) > 1 else "margin-top:14px"
        cards.append(
            f'<div class="testi"><p class="testi-text" data-i18n="testi{i}">{esc(_bi(r["text"], "fr"))}</p>'
            f'<div class="testi-author"><div class="testi-avatar">{esc(r["initials"])}</div>'
            f'<div><div class="testi-name" data-i18n="testi{i}_name">{esc(r["author"])}</div>'
            f'<div class="testi-role" data-i18n="testi{i}_role">{esc(_bi(r["role"], "fr"))}</div>'
            f'</div></div><div style="{wrap}">{links}</div></div>'
        )
    grid = "\n        ".join(cards)
    return f'\n    <div class="testi-grid">\n        {grid}\n    </div>\n'


def gen_i18n_testi(profile, lang):
    out = []
    for i, r in enumerate(profile["recommendations"], start=1):
        out.append(f'        testi{i}: {js_str(_bi(r["text"], lang))},')
    for i, r in enumerate(profile["recommendations"], start=1):
        out.append(f'        testi{i}_name: {js_str(r["author"])},')
        out.append(f'        testi{i}_role: {js_str(_bi(r["role"], lang))},')
        for m, d in enumerate(r["docs"], start=1):
            out.append(f'        testi{i}_doc{m}: {js_str(_bi(d["label"], lang))},')
    return "\n" + "\n".join(out) + "\n"


# ── Section #experience ───────────────────────────────────────────────────────
def fmt_range(start, end, lang):
    """'2026-02','2026-08' -> 'Février – Août 2026' (en-dash U+2013). Même année → une seule."""
    ms, me = re.match(r"^(\d{4})-(\d{2})$", str(start or "")), re.match(r"^(\d{4})-(\d{2})$", str(end or ""))
    if not ms or not me:
        raise BuildError(f"plage attendue YYYY-MM, reçu {start!r}–{end!r}")
    ys, mos, ye, moe = ms.group(1), int(ms.group(2)), me.group(1), int(me.group(2))
    M = _MONTHS[lang]
    if ys == ye:
        return f"{M[mos]} – {M[moe]} {ye}"
    return f"{M[mos]} {ys} – {M[moe]} {ye}"


def _org(exp, lang):
    """company[, division, ville] — ville seulement si division présente (fidèle à l'existant)."""
    parts = [exp["company"]]
    div = exp.get("division")
    if div:
        parts.append(_bi(div, lang) if isinstance(div, dict) else div)
        city = (exp.get("location") or "").split(",")[0].strip()
        if city:
            parts.append(city)
    return ", ".join(parts)


def render_experience(profile):
    """.tl (3 cartes) depuis profile.experiences[] (déjà bilingue, CV-consommé via _loc → additif).
    Clés data-i18n systématiques exp{i}_title/org/per/b{j}."""
    cards = []
    for i, e in enumerate(profile["experiences"], start=1):
        lis = "\n        ".join(
            f'<li data-i18n="exp{i}_b{j}">{esc(b)}</li>'
            for j, b in enumerate(_bi(e["bullets"], "fr"), start=1)
        )
        cards.append(
            f'<div class="tl-i"><div class="cd"><div class="cd-h"><div class="cd-info">'
            f'<h3 data-i18n="exp{i}_title">{esc(_bi(e["title"], "fr"))}</h3>'
            f'<span class="org" data-i18n="exp{i}_org">{esc(_org(e, "fr"))}</span>'
            f'<span class="per" data-i18n="exp{i}_per">{esc(fmt_range(e["start"], e["end"], "fr"))}</span>'
            f'</div></div><div class="cd-b"><ul>\n        {lis}\n    </ul></div></div></div>'
        )
    return '<div class="tl">\n    ' + "\n    ".join(cards) + "\n</div>"


def gen_i18n_exp(profile, lang):
    out = []
    for i, e in enumerate(profile["experiences"], start=1):
        out.append(f'        exp{i}_title: {js_str(_bi(e["title"], lang))},')
        out.append(f'        exp{i}_org: {js_str(_org(e, lang))},')
        out.append(f'        exp{i}_per: {js_str(fmt_range(e["start"], e["end"], lang))},')
        for j, b in enumerate(_bi(e["bullets"], lang), start=1):
            out.append(f'        exp{i}_b{j}: {js_str(b)},')
    return "\n" + "\n".join(out) + "\n"


# ── Registre des sections (extensible) ────────────────────────────────────────
# name section HTML -> fonction render (marqueur <!-- BUILD:name -->)
HTML_SECTIONS = {
    "blog": render_blog,
    "interests": render_interests,
    "testimonials": render_testimonials,
    "experience": render_experience,
}
# name région i18n -> fonction gen(profile, lang) (marqueur /* BUILD:i18n_name_<lang> */)
I18N_SECTIONS = {
    "blog": gen_i18n_blog,
    "langs": gen_i18n_langs,
    "ints": gen_i18n_ints,
    "testi": gen_i18n_testi,
    "exp": gen_i18n_exp,
}


def build_html(index_html, profile):
    out = index_html
    for name, render in HTML_SECTIONS.items():
        out = inject(out, f"<!-- BUILD:{name} -->", f"<!-- /BUILD:{name} -->", render(profile))
    for name, gen in I18N_SECTIONS.items():
        for lang in ("fr", "en"):
            out = inject(out, f"/* BUILD:i18n_{name}_{lang} */",
                         f"/* /BUILD:i18n_{name}_{lang} */", gen(profile, lang))
    return out


def build(profile_path=None, index_path=None, write=True):
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from validate_profile import validate  # gate pré-build
    except Exception:
        validate = None
    profile = load_profile(profile_path)
    if validate:
        errs = validate(profile)
        if errs:
            raise BuildError("profile.json invalide : " + " ; ".join(errs[:5]))
    idx_path = Path(index_path) if index_path else ROOT / "index.html"
    html = idx_path.read_text(encoding="utf-8")
    out = build_html(html, profile)
    if write:
        idx_path.write_text(out, encoding="utf-8")
    return out


if __name__ == "__main__":
    build()
    print("[build_site] OK — index.html généré depuis profile.json")
