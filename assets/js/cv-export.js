/* Σ-CV-ATELIER sous-projet B2 — chooser de téléchargement CV.
 * Bouton « Télécharger » → modal : Complet | Par profil (préfabs PDF) | Composer (cases).
 * Complet/Composer = rendu client-side (cv-select + cv-render) → window.print() (texte réel,
 * ATS-safe). Par profil = lien direct vers cv/prefab/{id}_{lang}.pdf (généré au build).
 * Dépend de window.CVSelect + window.CVRender. UMD-light (navigateur uniquement). */
(function () {
  "use strict";

  var STYLE = "" +
    ".cvx-overlay{position:fixed;inset:0;background:rgba(10,12,30,.6);display:none;" +
    "align-items:center;justify-content:center;z-index:9999}" +
    ".cvx-overlay.cvx-open{display:flex}" +
    ".cvx-modal{background:#fff;color:#1a1a2e;border-radius:12px;max-width:520px;width:92%;" +
    "max-height:86vh;overflow:auto;padding:22px 24px;box-shadow:0 20px 60px rgba(0,0,0,.35)}" +
    ".cvx-modal h3{margin:0 0 4px;font-size:18px}" +
    ".cvx-sub{color:#666;font-size:13px;margin:0 0 16px}" +
    ".cvx-opt{display:block;width:100%;text-align:left;border:1px solid #e0e3f0;background:#f7f8ff;" +
    "border-radius:8px;padding:12px 14px;margin-bottom:8px;cursor:pointer;font-size:14px}" +
    ".cvx-opt:hover{border-color:#4361ee;background:#eef1ff}" +
    ".cvx-opt b{color:#16213e}.cvx-opt span{color:#666;font-size:12px;display:block;margin-top:2px}" +
    ".cvx-prefabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:6px 0 4px}" +
    ".cvx-prefabs a{border:1px solid #e0e3f0;border-radius:8px;padding:10px;text-align:center;" +
    "text-decoration:none;color:#16213e;font-size:13px;background:#f7f8ff}" +
    ".cvx-prefabs a:hover{border-color:#4361ee}" +
    ".cvx-bullets{border:1px solid #e0e3f0;border-radius:8px;padding:10px;max-height:38vh;overflow:auto;margin:6px 0}" +
    ".cvx-grp{font-weight:600;color:#4361ee;font-size:12px;margin:8px 0 4px}" +
    ".cvx-bl{display:flex;gap:8px;align-items:flex-start;font-size:13px;margin-bottom:4px;cursor:pointer}" +
    ".cvx-bl input{margin-top:3px}" +
    ".cvx-actions{display:flex;gap:8px;margin-top:12px}" +
    ".cvx-btn{flex:1;border:none;border-radius:8px;padding:11px;font-size:14px;cursor:pointer}" +
    ".cvx-primary{background:#4361ee;color:#fff}.cvx-ghost{background:#eee;color:#333}" +
    ".cvx-back{background:none;border:none;color:#4361ee;cursor:pointer;font-size:13px;padding:0;margin-bottom:10px}";

  var T = {
    fr: { title: "Télécharger le CV", sub: "Complet, ciblé par profil, ou composé sur mesure.",
          full: "CV complet", fullSub: "Toutes les expériences (PDF)",
          byProfile: "Par profil", byProfileSub: "CV ciblé pré-préparé (PDF)",
          compose: "Composer", composeSub: "Cocher les points à inclure",
          back: "← Retour", generate: "Générer le PDF", cancel: "Annuler",
          pickTitle: "Choisir un profil", composeTitle: "Composer mon CV" },
    en: { title: "Download CV", sub: "Full, targeted by profile, or custom-composed.",
          full: "Full CV", fullSub: "All experiences (PDF)",
          byProfile: "By profile", byProfileSub: "Pre-built targeted CV (PDF)",
          compose: "Compose", composeSub: "Tick the points to include",
          back: "← Back", generate: "Generate PDF", cancel: "Cancel",
          pickTitle: "Pick a profile", composeTitle: "Compose my CV" },
  };

  var state = { profile: null, prefabs: [], getLang: function () { return "fr"; }, cfg: {} };

  function h(tag, attrs, html) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (html != null) el.innerHTML = html;
    return el;
  }

  function lang() { return state.getLang() === "en" ? "en" : "fr"; }
  function t() { return T[lang()]; }

  function printCv(structuredCv) {
    // renderHtml échappe déjà tout le contenu (html.escape) ; on navigue vers un
    // Blob same-origin plutôt que document.write (évité : perf + XSS legacy).
    var html = window.CVRender.renderHtml(structuredCv);
    var url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    var w = window.open(url, "_blank");
    if (!w) { alert("Autorisez les pop-ups pour générer le PDF."); URL.revokeObjectURL(url); return; }
    w.focus();
    setTimeout(function () { try { w.print(); } catch (e) {} URL.revokeObjectURL(url); }, 500);
  }

  // ── vues du modal ──────────────────────────────────────────────────────────
  function viewMenu(body) {
    body.innerHTML = "";
    body.appendChild(h("h3", null, t().title));
    body.appendChild(h("p", { class: "cvx-sub" }, t().sub));
    var full = h("button", { class: "cvx-opt", type: "button" },
      "<b>" + t().full + "</b><span>" + t().fullSub + "</span>");
    full.onclick = function () {
      var lg = lang();
      // « Complet » = le CV ATS canonique (hand-crafted) si fourni, sinon fallback généré.
      if (state.cfg.fullPdf && state.cfg.fullPdf[lg]) {
        var a = document.createElement("a");
        a.href = (state.cfg.base || "") + state.cfg.fullPdf[lg]; a.target = "_blank";
        document.body.appendChild(a); a.click(); a.remove(); close();
        return;
      }
      var pf = findPrefab("full", lg);
      if (pf) { downloadPrefab(pf); return; }
      var exps = window.CVSelect.selectExperiences(state.profile, { relevance_key: "general", min_relevance: 0 });
      printCv(window.CVSelect.buildStructuredCv(state.profile, exps, lg));
    };
    var byp = h("button", { class: "cvx-opt", type: "button" },
      "<b>" + t().byProfile + "</b><span>" + t().byProfileSub + "</span>");
    byp.onclick = function () { viewProfiles(body); };
    var comp = h("button", { class: "cvx-opt", type: "button" },
      "<b>" + t().compose + "</b><span>" + t().composeSub + "</span>");
    comp.onclick = function () { viewCompose(body); };
    body.appendChild(full); body.appendChild(byp); body.appendChild(comp);
  }

  function findPrefab(id, lg) {
    return state.prefabs.filter(function (p) { return p.id === id && p.lang === lg; })[0];
  }
  function downloadPrefab(p) {
    var a = document.createElement("a");
    a.href = (state.cfg.base || "") + p.file;
    a.download = ""; document.body.appendChild(a); a.click(); a.remove();
    close();
  }

  function viewProfiles(body) {
    body.innerHTML = "";
    var back = h("button", { class: "cvx-back", type: "button" }, t().back);
    back.onclick = function () { viewMenu(body); };
    body.appendChild(back);
    body.appendChild(h("h3", null, t().pickTitle));
    var grid = h("div", { class: "cvx-prefabs" });
    var lg = lang();
    state.prefabs.filter(function (p) { return p.lang === lg && p.id !== "full"; }).forEach(function (p) {
      var a = h("a", { href: "#" });
      a.textContent = (p.label && (p.label[lg] || p.label.fr)) || p.id;  // contenu config → textContent
      a.onclick = function (e) { e.preventDefault(); downloadPrefab(p); };
      grid.appendChild(a);
    });
    body.appendChild(grid);
  }

  function viewCompose(body) {
    body.innerHTML = "";
    var back = h("button", { class: "cvx-back", type: "button" }, t().back);
    back.onclick = function () { viewMenu(body); };
    body.appendChild(back);
    body.appendChild(h("h3", null, t().composeTitle));
    var lg = lang();
    var items = window.CVSelect.listBullets(state.profile, lg);
    var box = h("div", { class: "cvx-bullets" });
    var lastCompany = null;
    items.forEach(function (it) {
      if (it.company !== lastCompany) {
        var grp = h("div", { class: "cvx-grp" }); grp.textContent = it.company;  // profil → textContent
        box.appendChild(grp);
        lastCompany = it.company;
      }
      var lbl = h("label", { class: "cvx-bl" });
      var cb = h("input", { type: "checkbox", value: it.id }); cb.checked = true;
      lbl.appendChild(cb);
      var sp = document.createElement("span"); sp.textContent = it.text;  // bullet profil → textContent
      lbl.appendChild(sp);
      box.appendChild(lbl);
    });
    body.appendChild(box);
    var actions = h("div", { class: "cvx-actions" });
    var gen = h("button", { class: "cvx-btn cvx-primary", type: "button" }, t().generate);
    gen.onclick = function () {
      var ids = Array.prototype.slice.call(box.querySelectorAll("input:checked")).map(function (c) { return c.value; });
      var exps = window.CVSelect.selectManual(state.profile, ids, lg);
      printCv(window.CVSelect.buildStructuredCv(state.profile, exps, lg));
    };
    var cancel = h("button", { class: "cvx-btn cvx-ghost", type: "button" }, t().cancel);
    cancel.onclick = close;
    actions.appendChild(gen); actions.appendChild(cancel);
    body.appendChild(actions);
  }

  var overlay, modalBody;
  function ensureDom() {
    if (overlay) return;
    var st = document.createElement("style"); st.textContent = STYLE; document.head.appendChild(st);
    overlay = h("div", { class: "cvx-overlay" });
    var modal = h("div", { class: "cvx-modal" });
    modalBody = h("div");
    modal.appendChild(modalBody);
    overlay.appendChild(modal);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay.classList.contains("cvx-open")) close();
    });
    document.body.appendChild(overlay);
  }
  function open() { ensureDom(); viewMenu(modalBody); overlay.classList.add("cvx-open"); }
  function close() { if (overlay) overlay.classList.remove("cvx-open"); }

  window.CVExport = {
    init: function (opts) {
      opts = opts || {};
      state.cfg = opts;
      state.getLang = opts.getLang || state.getLang;
      var base = opts.base || "";
      return Promise.all([
        fetch(base + (opts.profileUrl || "profile.json")).then(function (r) { return r.json(); }),
        fetch(base + (opts.prefabIndexUrl || "cv/prefab/index.json")).then(function (r) { return r.json(); }).catch(function () { return []; }),
      ]).then(function (res) {
        state.profile = res[0]; state.prefabs = res[1] || [];
        return window.CVExport;
      });
    },
    open: open,
    close: close,
  };
})();
