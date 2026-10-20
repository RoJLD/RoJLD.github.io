#!/usr/bin/env python3
"""build_404.py — génère `404.html`, la page que GitHub Pages sert à toute adresse absente.

LE DÉFAUT, mesuré en ligne le 2026-10-20 : `https://robin-denis.com/nexiste-pas`
rendait le statut 404 et la page générique « Page not found · GitHub Pages »
(9 379 octets) — sans la nav du site, sans son thème, sans retour. Un recruteur
qui suivait un lien périmé quittait le site sans issue.

CE QUI DISTINGUE CETTE PAGE DES AUTRES, et pourquoi :

  * TOUT CHEMIN EST INDÉPENDANT DE L'ADRESSE SERVIE. GitHub Pages sert ce même
    fichier à `/x`, à `/a/b/c/d/e`, à `/projects/nexiste` : servi à
    `/a/b/c/nexiste`, un lien `projects/` viserait `/a/b/c/projects/` — une autre
    404 — et une feuille `style.css` ne chargerait pas. La nav est donc rendue en
    mode sous-page par `nav.render_nav("404")`, qui écrit des destinations
    absolues (`/#experience`, `/projects/`) ; la feuille de style est embarquée ;
    les polices et l'icône sont des URL complètes. Garde :
    `test_liens_internes.py::test_aucun_chemin_de_la_page_404_ne_depend_de_l_adresse_servie`.
  * LE THÈME EST POSÉ DANS `<head>`, avant que le `<body>` n'existe. Les autres
    pages le restaurent dans `<body>` ; la page d'erreur n'a aucune raison
    de risquer, pour un visiteur en thème clair, un premier rendu sombre. Seul
    ce script lit `getItem('theme')` — le harnais du thème
    (`theme_boot_harness.extract_script`) exige qu'un seul script le fasse.
    Garde, qui lit la structure du document (le script est dans `<head>`, en
    ligne et classique, et écrit `data-theme`) :
    `test_liens_internes.py::test_la_page_404_pose_le_theme_dans_head_avant_le_corps`.
  * LES DEUX LANGUES SONT LIVRÉES, donc le bouton de langue est là. Chaque texte
    visible porte `data-fr` et `data-en`, `<title>` compris, et la bascule écrit
    `lang` sur le document en même temps qu'elle remplace les textes : la langue
    annoncée est celle du contenu (WCAG 3.1.1, l'erreur que #40 a corrigée sur
    `/projects/` et `/demos/`). Garde :
    `test_lang_switch_behaviour.py::test_la_langue_annoncee_est_celle_du_contenu`,
    qui juge cette page dès qu'elle existe.
  * `noindex`, et HORS DU SITEMAP (`build_sitemap.PAS_DES_PAGES_D_ATTERRISSAGE`) :
    une page qui dit « introuvable » ne doit pas être proposée comme résultat.

MESURÉ AU NAVIGATEUR le 2026-10-20 (Chromium 145), la page servie par un serveur
qui imite GitHub Pages — `404.html` rendue avec le statut 404 à toute adresse
absente — à `/x`, `/a/b`, `/a/b/c/`, `/a/b/c/d/e` et `/projects/nexiste`, en
thème sombre et clair, en français et en anglais, à 390 et 1280 px, soit 40
chargements : les 11 destinations de la nav résolues comme celles de l'accueil
et toutes atteignables au pointeur, aucune requête en 404 hors le document,
aucune erreur JavaScript, aucun débordement horizontal ; `data-theme` posé entre
24 et 167 ms, le premier rendu entre 172 et 1 896 ms ; `lang` et les textes
anglais posés avant le premier rendu dans les 20 chargements en anglais. Ce
dernier point n'a PAS la garantie du thème : la bascule de langue vit en fin de
`<body>`, comme sur les autres pages. Sur trois passages de la même mesure, 10,
1 puis 9 chargements anglais sur 20 ont vu un premier rappel
`requestAnimationFrame` AVANT la bascule ; aucune image n'était peinte à ce
moment-là (`first-paint` est venu après elle dans les 20 cas), mais c'est une
observation, pas une construction.

Ce que cette page ne touche PAS : la 404 de `/academy/`. GitHub Pages sert
`/academy/` et tout ce qui est dessous depuis le dépôt-projet RoJLD/academy
(cf. `tools/servi_ailleurs.py`), qui a sa propre `404.html` — une copie de son
`index.html`, pour que les liens profonds de l'application se rechargent.
Mesuré en ligne le 2026-10-20 : `/academy/nexiste-pas` rend 404 avec le titre
« Academy ». Ce dépôt ne sert rien sous `/academy/`, donc cette page non plus.

Appelé par `build_site.build()`, comme ses frères : la porte « Publier » du
cockpit lance `build_site.py` et rien d'autre, et un fichier dérivé sans
écrivain dans cette porte dérive (leçon du 2026-10-15).
"""
from __future__ import annotations

import html
import pathlib

import nav

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "404.html"

# Le nom de cette page pour `nav.py` (cf. `nav._PAGES`).
PAGE = "404"

# Les raccourcis sous le bouton de retour : trois entrées de la nav, désignées par
# leur CLÉ de `site_texts.json`. Ni cible ni libellé n'est écrit ici — les cibles
# viennent de `nav.ENTREES`, les libellés de `site_texts.json`, comme pour la
# barre elle-même. Une entrée retirée de la nav fait échouer la construction au
# lieu de laisser ici un lien que la barre n'a plus. Le choix des trois est
# éditorial : le profil orienté (Highlights), le travail (Projets), et le but du
# site (Contact).
RACCOURCIS = ("nav_highlights", "nav_projects", "nav_contact")


class Build404Error(Exception):
    pass


TEMPLATE = """<!DOCTYPE html>
<html lang="fr" data-theme="dark" data-lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title data-fr="Page introuvable — Robin Denis" data-en="Page not found — Robin Denis">Page introuvable — Robin Denis</title>
<script>
  /* Thème mémorisé, posé AVANT le premier rendu : ce script s'exécute avant que
     le corps de la page n'existe. Cf. tools/build_404.py. */
  (function () {
    var t = localStorage.getItem('theme');
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
  })();
</script>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧭</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--serif:'Instrument Serif',Georgia,serif;--sans:'DM Sans',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;--ease:cubic-bezier(.4,0,.2,1)}
[data-theme="dark"]{--bg-0:#060a12;--bg-2:#111a2e;--border:#1a2847;--border-hi:#253a68;--tx-1:#e6eaf3;--tx-2:#8b9aba;--tx-3:#54678a;--accent:#3b82f6;--glass:rgba(10,16,32,.75)}
[data-theme="light"]{--bg-0:#f5f7fa;--bg-2:#ffffff;--border:#d8dfe9;--border-hi:#c2cbda;--tx-1:#1a2035;--tx-2:#546178;--tx-3:#8594ad;--accent:#2563eb;--glass:rgba(245,247,250,.8)}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:var(--bg-0);color:var(--tx-1);line-height:1.7;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden;transition:background .5s var(--ease),color .5s var(--ease)}
.blob{position:fixed;border-radius:50%;filter:blur(140px);pointer-events:none;z-index:0}.b1{width:700px;height:700px;top:-300px;right:-200px;background:var(--accent);opacity:.04}
nav{position:fixed;top:0;width:100%;z-index:100;padding:12px 0;background:var(--glass);backdrop-filter:blur(24px) saturate(1.4);border-bottom:1px solid var(--border)}
.nav-i{max-width:none;margin:0;padding:0 24px 0 max(24px,calc(50% - 468px));display:flex;align-items:center;position:relative}
.nav-brand{font-family:var(--serif);font-size:19px;color:var(--tx-1);letter-spacing:-.03em;text-decoration:none;white-space:nowrap;flex-shrink:0;margin-right:28px}.nav-brand b{color:var(--accent)}
.nav-r{display:flex;align-items:center;gap:18px;flex:1 1 auto;min-width:0;padding-block:6px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;-ms-overflow-style:none;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain;scroll-padding-inline:8px}
.nav-r::-webkit-scrollbar{display:none}
.nav-r>a{flex-shrink:0}
.nav-r a{color:var(--tx-3);text-decoration:none;font-size:12px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;transition:color .3s var(--ease);min-height:24px;padding-block:3px}
.nav-r a:hover{color:var(--tx-1)}.nav-r a.on{color:var(--accent)}
.ctrl-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--border);background:var(--bg-2);cursor:pointer;display:grid;place-items:center;font-size:16px;transition:all .3s var(--ease)}
.ctrl-btn:hover{border-color:var(--accent);transform:scale(1.1)}
.nav-btns{display:flex;align-items:center;gap:8px;flex-shrink:0;margin-left:16px;position:relative}
.nav-btns::before{content:'';position:absolute;top:-12px;bottom:-12px;left:-40px;width:40px;pointer-events:none;background:linear-gradient(to right,rgba(0,0,0,0),var(--glass))}
.ctrl-btn.lang-btn{font-size:12px;font-weight:700;font-family:var(--mono);color:var(--tx-2)}
.wrap{max-width:720px;margin:0 auto;padding:150px 32px 80px;position:relative;z-index:1;text-align:center}
.code{font-family:var(--serif);font-size:clamp(76px,16vw,128px);line-height:1;letter-spacing:-.04em;color:var(--accent);margin-bottom:10px}
h1{font-family:var(--serif);font-size:clamp(32px,5vw,44px);font-weight:400;letter-spacing:-.02em;line-height:1.2;margin-bottom:14px}
.lead{color:var(--tx-2);font-size:16px;font-weight:300;max-width:560px;margin:0 auto 18px}
.asked{display:flex;flex-wrap:wrap;justify-content:center;align-items:baseline;gap:8px;color:var(--tx-2);font-size:13px;margin-bottom:32px}
.asked[hidden]{display:none}
.asked code{font-family:var(--mono);font-size:12.5px;color:var(--tx-1);background:var(--bg-2);border:1px solid var(--border);border-radius:6px;padding:2px 8px;max-width:100%;overflow-wrap:anywhere}
.ctas{display:flex;flex-wrap:wrap;justify-content:center;gap:10px}
.cta{display:inline-flex;align-items:center;min-height:44px;padding:10px 20px;border-radius:100px;border:1px solid var(--border);background:var(--bg-2);color:var(--tx-1);font-size:14px;font-weight:600;text-decoration:none;transition:border-color .25s var(--ease),transform .25s var(--ease)}
.cta:hover{border-color:var(--border-hi);transform:translateY(-2px)}
.cta.main{background:var(--tx-1);border-color:var(--tx-1);color:var(--bg-0)}
@media(max-width:1620px){.nav-r{gap:14px}.nav-r a{font-size:11px;letter-spacing:.02em;padding-block:4px}.nav-brand{font-size:18px;margin-right:20px}.nav-i{padding-left:max(20px,calc(50% - 468px));padding-right:20px}.nav-btns{margin-left:12px}.ctrl-btn{width:34px;height:34px}}
@media(max-width:1150px){.nav-r{gap:11px}.nav-r a{font-size:10.5px;letter-spacing:.01em;padding-block:4px}.nav-brand{font-size:17px;margin-right:14px}.nav-i{padding-left:max(14px,calc(50% - 468px));padding-right:14px}.nav-btns{margin-left:8px}.ctrl-btn{width:32px;height:32px}}
@media(max-width:1023px){/* AUCUN `order:` ici : sous ce seuil l'ordre visuel doit rester celui du DOM (WCAG 2.4.3, niveau A). Mesures, hauteurs et contre-exemple : tools/nav.py, section « ordre de tabulation sous 1024 px ». */nav{position:static;padding:10px 0}.nav-i{flex-wrap:wrap;row-gap:6px;padding:0 18px}.nav-brand{font-size:19px}.nav-btns{margin-left:auto}.nav-btns::before{display:none}.ctrl-btn{width:38px;height:38px}.nav-r{flex:1 1 100%;flex-wrap:wrap;row-gap:2px;column-gap:14px;overflow:visible;padding-block:0}.nav-r a{font-size:11px;letter-spacing:.02em;padding-block:5px}.wrap{padding:48px 18px 64px}}
</style>
</head>
<body>
<div class="blob b1"></div>
@@NAV@@

<main class="wrap">
  <p class="code" aria-hidden="true">404</p>
  <h1 data-fr="Page introuvable" data-en="Page not found">Page introuvable</h1>
  <p class="lead" data-fr="Cette adresse ne mène à aucune page du site : le lien est peut-être ancien, ou la page a changé de place." data-en="This address leads to no page on this site: the link may be outdated, or the page may have moved.">Cette adresse ne mène à aucune page du site : le lien est peut-être ancien, ou la page a changé de place.</p>
  <p class="asked" id="asked" hidden><span data-fr="Adresse demandée" data-en="Requested address">Adresse demandée</span><code id="chemin"></code></p>
  <div class="ctas">
    <a class="cta main" href="/" data-fr="Retour à l'accueil" data-en="Back home">Retour à l'accueil</a>
@@RACCOURCIS@@
  </div>
</main>

<script>
  const root = document.documentElement;
  function applyBrowseLang(lang) {
    document.querySelectorAll('[data-fr][data-en]').forEach(function (el) {
      el.textContent = lang === 'en' ? el.dataset.en : el.dataset.fr;
    });
    root.setAttribute('data-lang', lang); root.setAttribute('lang', lang);
    document.getElementById('langBtn').textContent = lang === 'en' ? 'EN' : 'FR';
  }
  function toggleLang() {
    const next = root.getAttribute('data-lang') === 'en' ? 'fr' : 'en';
    localStorage.setItem('lang', next);
    applyBrowseLang(next);
  }
  function tgTheme() {
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('themeBtn').textContent = next === 'light' ? '☀️' : '🌙';
  }
  (function () {
    document.getElementById('themeBtn').textContent =
      root.getAttribute('data-theme') === 'light' ? '☀️' : '🌙';
    /* L'adresse demandée, telle que le visiteur l'a suivie : textContent, jamais
       innerHTML. decodeURI lève sur une séquence %-codée invalide ; l'adresse
       brute reste alors lisible, et c'est elle qui est montrée. */
    let chemin = location.pathname;
    try { chemin = decodeURI(chemin); } catch (e) { chemin = location.pathname; }
    document.getElementById('chemin').textContent = chemin;
    document.getElementById('asked').hidden = false;
    if (localStorage.getItem('lang') === 'en') applyBrowseLang('en');
  })();
</script>
</body>
</html>
"""


def render_raccourcis(libelles: dict[str, dict[str, str]] | None = None) -> str:
    """Les liens secondaires, cibles et libellés tirés de la nav. Fail-loud."""
    lib = libelles if libelles is not None else nav.charger_libelles()
    cibles = dict(nav.ENTREES)
    lignes = []
    for cle in RACCOURCIS:
        if cle not in cibles:
            raise Build404Error(
                f"raccourci {cle!r} absent de nav.ENTREES : la page 404 pointerait "
                "une destination que la barre ne porte plus")
        fr = html.escape(lib["fr"][cle], quote=True)
        en = html.escape(lib["en"][cle], quote=True)
        texte = html.escape(lib["fr"][cle], quote=False)
        lignes.append(f'    <a class="cta" href="{nav.href(cibles[cle], PAGE)}"'
                      f' data-fr="{fr}" data-en="{en}">{texte}</a>')
    return "\n".join(lignes)


def render_404() -> str:
    return (TEMPLATE
            .replace("@@NAV@@", nav.render_nav(PAGE))
            .replace("@@RACCOURCIS@@", render_raccourcis()))


def build_404(write: bool = True) -> str:
    out = render_404()
    if write:
        OUT.write_text(out, encoding="utf-8")
    return out


def main() -> int:
    out = build_404()
    print(f"[build_404] OK - {out.count('<a ')} liens -> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
