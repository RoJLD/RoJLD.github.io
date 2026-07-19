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
            # La carte porte les DEUX chemins ; `applyLang` bascule le href, comme il
            # le fait déjà pour le PDF du CV via [data-cv]. Repli : si la traduction
            # n'existe pas, les deux attributs pointent le FR — un lecteur anglophone
            # atterrit sur du français plutôt que sur un 404.
            fr_url = a["url"]
            en_url = _article_en_url(fr_url)
            cards.append(f'<a class="blog-card" href="{esc(fr_url)}" '
                         f'data-article-fr="{esc(fr_url)}" data-article-en="{esc(en_url)}">'
                         f'{inner}</a>')
    return "\n    " + "\n    ".join(cards) + "\n"


def _article_en_url(fr_url):
    """'articles/x.html' -> 'articles/x.en.html' SI la page existe, sinon le FR.

    L'existence est vérifiée sur disque et non supposée : promettre une page absente
    produirait un 404 sur un lien public. Le fichier est écrit par build_articles,
    qui tourne AVANT cette fonction dans build()."""
    if not fr_url.endswith(".html"):
        raise BuildError(f"URL d'article inattendue : {fr_url!r}")
    en_url = fr_url[: -len(".html")] + ".en.html"
    return en_url if (ROOT / en_url).exists() else fr_url


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


# ── Section #education ────────────────────────────────────────────────────────
def _edu_courses(e, i):
    """Collapsible « cours clés » si l'entrée porte des cours ; '' sinon."""
    courses = e.get("courses") or []
    if not courses:
        return ""
    ps = "".join(f'<p data-i18n="edu{i}_c{k}">{esc(_bi(c, "fr"))}</p>'
                 for k, c in enumerate(courses, start=1))
    return (f'\n        <div style="margin-top:12px"><button class="stg" onclick="sub(this,event)">'
            f'<span class="ar">▸</span> '
            f'<span data-i18n="edu{i}_courses_label">{esc(_bi(e["courses_label"], "fr"))}</span></button>'
            f'<div class="sp">{ps}</div></div>')


def _edu_capstone(e, i):
    """Collapsible projet de fin d'études si l'entrée porte un capstone ; '' sinon."""
    cap = e.get("capstone")
    if not cap:
        return ""
    return (f'\n        <div style="margin-top:8px"><button class="stg" onclick="sub(this,event)">'
            f'<span class="ar">▸</span> '
            f'<span data-i18n="edu{i}_pfe_label">{esc(_bi(cap["label"], "fr"))}</span></button>'
            f'<div class="sp"><p><strong data-i18n="edu{i}_pfe_role">{esc(_bi(cap["role"], "fr"))}</strong> : '
            f'<span data-i18n="edu{i}_pfe_desc">{esc(_bi(cap["summary"], "fr"))}</span></p></div></div>')


def render_education(profile):
    """.tl (N cartes) depuis profile.education[] (bilingue ; NON lu par les tools CV → restructure sûre).
    Chaque carte : titre + org + période littérale ; collapsibles cours/PFE si présents.
    Réconciliation : le 1er cours gagne une clé data-i18n (bug latent EN corrigé) ; la Prépa remonte
    dans la donnée (était affichage-only) ; la carte montre capstone.summary (texte live court), la
    description longue reste en donnée pour SP1."""
    cards = []
    for i, e in enumerate(profile["education"], start=1):
        head = (f'<div class="tl-i"><div class="cd"><div class="cd-h"><div class="cd-info">'
                f'<h3 data-i18n="edu{i}_title">{esc(_bi(e["title"], "fr"))}</h3>'
                f'<span class="org" data-i18n="edu{i}_org">{esc(_bi(e["org"], "fr"))}</span>'
                f'<span class="per">{esc(e["period"])}</span></div></div>')
        body = _edu_courses(e, i) + _edu_capstone(e, i)
        tail = "\n    </div></div>" if body else "</div></div>"
        cards.append(head + body + tail)
    return '<div class="tl">\n    ' + "\n    ".join(cards) + "\n</div>"


def gen_i18n_edu(profile, lang):
    """Entrées CONTENU du dict i18n pour #education (les labels de section restent chrome)."""
    out = []
    for i, e in enumerate(profile["education"], start=1):
        out.append(f'        edu{i}_title: {js_str(_bi(e["title"], lang))}, '
                   f'edu{i}_org: {js_str(_bi(e["org"], lang))},')
        courses = e.get("courses") or []
        if courses:
            out.append(f'        edu{i}_courses_label: {js_str(_bi(e["courses_label"], lang))},')
            for k, c in enumerate(courses, start=1):
                out.append(f'        edu{i}_c{k}: {js_str(_bi(c, lang))},')
        cap = e.get("capstone")
        if cap:
            out.append(f'        edu{i}_pfe_label: {js_str(_bi(cap["label"], lang))}, '
                       f'edu{i}_pfe_role: {js_str(_bi(cap["role"], lang))},')
            out.append(f'        edu{i}_pfe_desc: {js_str(_bi(cap["summary"], lang))},')
    return "\n" + "\n".join(out) + "\n"


# ── Section #parcours (frise / journey) ───────────────────────────────────────
_HT_CLS = {"edu": "ht-item edu", "proj": "ht-item proj", "exp": "ht-item"}


def _ht_field(val, key, lang):
    """Champ frise : (attr data-i18n, texte échappé). Bilingue {fr,en} → traduit + clé ;
    str → langue-neutre, sans data-i18n (fidèle à l'existant : années/lieux/noms propres)."""
    if isinstance(val, dict):
        return f' data-i18n="{key}"', esc(_bi(val, lang))
    return "", esc(val)


def render_journey(profile):
    """.htl (N jalons) depuis profile.journey[] — frise éditoriale curée (mêle exp/edu/proj ;
    ELYSIUM n'est pas une expérience → journey est sa propre donnée, pas une projection).
    Chaque champ year/label/sub est statique (langue-neutre) OU bilingue (traduit)."""
    items = []
    for i, j in enumerate(profile["journey"], start=1):
        cls = _HT_CLS.get(j["kind"])
        if cls is None:
            raise BuildError(f"journey[{i}] kind inconnu : {j['kind']!r}")
        yi, year = _ht_field(j["year"], f"ht_j{i}_year", "fr")
        li, label = _ht_field(j["label"], f"ht_j{i}_label", "fr")
        si, sub = _ht_field(j["sub"], f"ht_j{i}_sub", "fr")
        ref = j.get("ref", "")
        click = (f' data-ref="{esc(ref)}" onclick="openModal({_ref_slug(ref)!r})" style="cursor:pointer"'
                 if ref else "")
        items.append(
            f'<div class="{cls}"{click}><span class="ht-year"{yi}>{year}</span><div class="ht-dot"></div>'
            f'<div class="ht-label"{li}>{label}</div><div class="ht-sub"{si}>{sub}</div></div>'
        )
    return "\n        " + "\n        ".join(items) + "\n    "


def gen_i18n_journey(profile, lang):
    """Entrées CONTENU du dict i18n pour #parcours (seuls les champs bilingues émettent une clé)."""
    out = []
    for i, j in enumerate(profile["journey"], start=1):
        parts = [f'ht_j{i}_{name}: {js_str(_bi(val, lang))}'
                 for name, val in (("year", j["year"]), ("label", j["label"]), ("sub", j["sub"]))
                 if isinstance(val, dict)]
        if parts:
            out.append("        " + ", ".join(parts) + ",")
    return "\n" + "\n".join(out) + "\n"


# ── Section #demos (teaser → /demos/ ; les widgets vivent sur la page /demos/) ─
def render_demos(profile):
    """Teaser #demos : cartes cliquables vers /demos/#<id> (galerie interactive SP2).
    desc bilingue réutilise les clés {id}_desc ; catégorie affichée."""
    cards = []
    for d in profile["demos"]:
        did = d["id"]
        cards.append(
            f'<a class="demo-card demo-teaser" href="/demos/#{esc(did)}">'
            f'<span class="demo-cat">{esc(d["category"])}</span>'
            f'<h4>{esc(d["title"])}</h4>'
            f'<p data-i18n="{did}_desc">{esc(_maybe_bi(d["desc"], "fr"))}</p>'
            f'<span class="demo-cta">Essayer la démo →</span></a>'
        )
    return "\n    " + "\n    ".join(cards) + "\n"


def gen_i18n_demos(profile, lang):
    """Entrées CONTENU du dict i18n pour #demos : {id}_desc (bilingue). Titres/liens
    sont statiques (dans le markup) ; labels widget (bs_vol/bs_mat) restent chrome."""
    out = [f'        {d["id"]}_desc: {js_str(_bi(d["desc"], lang))},' for d in profile["demos"]]
    return "\n" + "\n".join(out) + "\n"


# ── Modals détail (SP1 frise cliquable) ──────────────────────────────────────
def _maybe_bi(v, lang):
    """Champ str OU {fr,en} → la langue demandée (str renvoyé tel quel)."""
    return v[lang] if isinstance(v, dict) else ("" if v is None else v)


def _ref_slug(ref):
    return "modal-" + ref.replace(":", "-")


def _projkey(pid):
    """id projet → fragment de clé i18n valide (hyphen interdit dans une clé JS non-quotée)."""
    return pid.replace("-", "_")


def _exp_index(profile, eid):
    for i, e in enumerate(profile["experiences"], start=1):
        if e["id"] == eid:
            return i
    raise BuildError(f"experience {eid!r} absente")


def _edu_index(profile, eid):
    for i, e in enumerate(profile["education"], start=1):
        if e["id"] == eid:
            return i
    raise BuildError(f"education {eid!r} absente")


def _modal_experience(profile, eid):
    i = _exp_index(profile, eid)
    e = profile["experiences"][i - 1]
    lis = "".join(f'<li data-i18n="exp{i}_b{j}">{esc(b)}</li>'
                  for j, b in enumerate(_bi(e["bullets"], "fr"), start=1))
    return (f'<h3 data-i18n="exp{i}_title">{esc(_bi(e["title"], "fr"))}</h3>'
            f'<div class="modal-org" data-i18n="exp{i}_org">{esc(_org(e, "fr"))}</div>'
            f'<div class="modal-per" data-i18n="exp{i}_per">{esc(fmt_range(e["start"], e["end"], "fr"))}</div>'
            f'<ul class="modal-bullets">{lis}</ul>')


def _modal_education(profile, eid):
    i = _edu_index(profile, eid)
    e = profile["education"][i - 1]
    parts = [f'<h3 data-i18n="edu{i}_title">{esc(_bi(e["title"], "fr"))}</h3>',
             f'<div class="modal-org" data-i18n="edu{i}_org">{esc(_bi(e["org"], "fr"))}</div>',
             f'<div class="modal-per">{esc(e["period"])}</div>']
    courses = e.get("courses") or []
    if courses:
        lis = "".join(f'<li data-i18n="edu{i}_c{k}">{esc(_bi(c, "fr"))}</li>'
                      for k, c in enumerate(courses, start=1))
        parts.append(f'<div class="modal-sub" data-i18n="edu{i}_courses_label">'
                     f'{esc(_bi(e["courses_label"], "fr"))}</div><ul class="modal-bullets">{lis}</ul>')
    cap = e.get("capstone")
    if cap:
        parts.append(f'<p class="modal-cap"><strong data-i18n="edu{i}_pfe_role">{esc(_bi(cap["role"], "fr"))}</strong> : '
                     f'<span data-i18n="edu{i}_pfe_desc">{esc(_bi(cap["summary"], "fr"))}</span></p>')
    return "".join(parts)


def _modal_project(profile, pid):
    p = next(x for x in profile["projects"] if x["id"] == pid)
    k = _projkey(pid)
    stack = "".join(f'<span class="p-tag">{esc(s)}</span>' for s in p.get("stack") or [])
    tags = "".join(f'<span class="p-tag">{esc(t)}</span>' for t in p.get("tags") or [])
    links = "".join(f'<a class="p-link" href="{esc(u)}" target="_blank" rel="noopener">{esc(key)}</a>'
                    for key, u in (p.get("links") or {}).items())
    imp = _maybe_bi(p.get("impact", ""), "fr")
    imp_html = f'<div class="modal-impact" data-i18n="mproj_{k}_impact">{esc(imp)}</div>' if imp else ""
    return (f'<h3 data-i18n="mproj_{k}_name">{esc(_maybe_bi(p["name"], "fr"))}</h3>'
            f'<div class="modal-per">{esc(p.get("date", ""))}</div>'
            f'<p data-i18n="mproj_{k}_summary">{esc(_maybe_bi(p["summary"], "fr"))}</p>'
            f'{imp_html}'
            f'<div class="modal-chips">{stack}</div>'
            f'<div class="modal-chips">{tags}</div>'
            f'<div class="p-links">{links}</div>')


_MODAL_BUILDERS = {"experience": _modal_experience, "education": _modal_education, "project": _modal_project}


def _referenced_refs(profile):
    seen = []
    for j in profile["journey"]:
        r = j.get("ref")
        if r and r not in seen:
            seen.append(r)
    return seen


def render_modals(profile):
    """Un modal caché par entité référencée par la frise. exp/edu réutilisent les clés
    de section (exp{i}_*/edu{i}_*) ; project a des clés mproj_* bilingues."""
    out = []
    for ref in _referenced_refs(profile):
        typ, _, eid = ref.partition(":")
        builder = _MODAL_BUILDERS.get(typ)
        if builder is None:
            raise BuildError(f"journey ref type inconnu : {ref!r}")
        body = builder(profile, eid)
        out.append(
            f'<div class="modal-ov" id="{_ref_slug(ref)}" onclick="closeModal(event)">'
            f'<div class="modal-card" onclick="event.stopPropagation()">'
            f'<button class="modal-x" aria-label="Fermer" onclick="closeModal()">&times;</button>'
            f'<div class="modal-body">{body}</div></div></div>'
        )
    return "\n    " + "\n    ".join(out) + "\n"


def gen_i18n_modals(profile, lang):
    """i18n CONTENU des modals : seuls les projets (mproj_*). exp/edu réutilisent les clés section."""
    out = []
    for ref in _referenced_refs(profile):
        typ, _, pid = ref.partition(":")
        if typ != "project":
            continue
        p = next(x for x in profile["projects"] if x["id"] == pid)
        k = _projkey(pid)
        out.append(f'        mproj_{k}_name: {js_str(_maybe_bi(p["name"], lang))}, '
                   f'mproj_{k}_summary: {js_str(_maybe_bi(p["summary"], lang))},')
        imp = _maybe_bi(p.get("impact", ""), lang)
        if imp:
            out.append(f'        mproj_{k}_impact: {js_str(imp)},')
    return "\n" + "\n".join(out) + "\n"


# ── Registre des sections (extensible) ────────────────────────────────────────
# name section HTML -> fonction render (marqueur <!-- BUILD:name -->)
HTML_SECTIONS = {
    "blog": render_blog,
    "interests": render_interests,
    "testimonials": render_testimonials,
    "experience": render_experience,
    "education": render_education,
    "journey": render_journey,
    "modals": render_modals,
    "demos": render_demos,
}
# name région i18n -> fonction gen(profile, lang) (marqueur /* BUILD:i18n_name_<lang> */)
I18N_SECTIONS = {
    "blog": gen_i18n_blog,
    "langs": gen_i18n_langs,
    "ints": gen_i18n_ints,
    "testi": gen_i18n_testi,
    "exp": gen_i18n_exp,
    "edu": gen_i18n_edu,
    "journey": gen_i18n_journey,
    "modals": gen_i18n_modals,
    "demos": gen_i18n_demos,
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
    # Les pages d'articles sont générées AVANT index.html, et non après comme les
    # autres builders : `render_blog` teste l'existence de la version anglaise sur
    # disque pour décider si la carte peut y pointer. Dans l'ordre inverse, une
    # construction sur clone frais figerait des liens FR que seule une SECONDE
    # construction corrigerait — une sortie dépendante de l'ordre d'exécution.
    try:
        import build_articles
        build_articles.build_articles(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération des pages articles échouée : {exc}")
    out = build_html(html, profile)
    if write:
        idx_path.write_text(out, encoding="utf-8")
    # Génère aussi la page projets depuis la même source (profile.json).
    try:
        import build_projects
        build_projects.build_projects(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération page projets échouée : {exc}")
    # Génère aussi la galerie démos depuis la même source.
    try:
        import build_demos
        build_demos.build_demos(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération page démos échouée : {exc}")
    # Génère aussi la page Explorer (browse unifié) depuis la même source.
    try:
        import build_browse
        build_browse.build_browse(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération page explorer échouée : {exc}")
    # Génère aussi la page Highlights (pitch pondéré) depuis la même source.
    try:
        import build_highlights
        build_highlights.build_highlights(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération page highlights échouée : {exc}")
    # Génère aussi la page Academy (quiz + flashcards) depuis academy.json.
    try:
        import build_academy
        build_academy.build_academy(write=write)
    except Exception as exc:
        raise BuildError(f"génération page academy échouée : {exc}")
    # Génère aussi la page Graphe (visualisation du profil) depuis la même source.
    try:
        import build_graph
        build_graph.build_graph(profile, write=write)
    except Exception as exc:
        raise BuildError(f"génération page graphe échouée : {exc}")
    return out


if __name__ == "__main__":
    build()
    print("[build_site] OK — index.html généré depuis profile.json")
