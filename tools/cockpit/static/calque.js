/* Calque d'édition du site (cockpit, édition du site A1). Servi par l'aperçu 127.0.0.1:8011,
 * jamais publié. Cœur pur (testé sous node) + branchement DOM (navigateur seulement).
 * Aucune donnée n'est insérée en HTML : textContent partout. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Calque = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function texteSain(s) {
    return String(s == null ? "" : s).replace(/\s+/g, " ").trim();
  }

  function langCourante(attr) {
    return attr === "en" ? "en" : "fr";
  }

  function requeteSource(source, lang, valeur, jeton) {
    return {
      url: "/__cockpit/source",
      init: {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Atelier-Token": String(jeton || "") },
        body: JSON.stringify({ source: String(source), lang: langCourante(lang), valeur: texteSain(valeur) })
      }
    };
  }

  function messageErreur(statut, corps) {
    var detail = "";
    try {
      var j = JSON.parse(corps);
      detail = j.erreur || (j.rapport && j.rapport.errors && j.rapport.errors.join(" ; ")) || "";
    } catch (e) {
      detail = String(corps || "").slice(0, 300);
    }
    return "Refusé (" + statut + ")" + (detail ? " : " + detail : "");
  }

  function alertesEtapes(corps) {
    var etapes;
    try {
      etapes = ((JSON.parse(corps) || {}).rapport || {}).stages || {};
    } catch (e) {
      return [];
    }
    return Object.keys(etapes).filter(function (k) {
      return etapes[k] && etapes[k].ok === false;
    }).map(function (k) {
      var s = etapes[k];
      return k + " : " + (s.error || s.message || "en échec");
    });
  }

  function resumeEtat(rep) {
    var e = (rep && rep.etat) || {};
    return {
      fichiers: (e.fichiers || []).map(function (f) { return f.statut + " " + f.chemin; }),
      horsPerimetre: e.hors_perimetre || [],
      refus: (rep && rep.refus) || []
    };
  }

  function peutPublier(rep, verifs) {
    return !!(rep && (rep.refus || []).length === 0 && verifs && verifs.ok === true);
  }

  function demarrer(win, doc) {
    var jeton = (win.__COCKPIT__ || {}).jeton || "";
    var style = doc.createElement("style");
    style.textContent =
      ".cockpit-barre{position:fixed;right:16px;bottom:16px;z-index:2147483647;display:flex;gap:8px;" +
      "font:13px system-ui,sans-serif}" +
      ".cockpit-barre button{padding:6px 12px;border-radius:6px;border:1px solid #4361ee;background:#fff;" +
      "color:#1a1a2e;cursor:pointer}" +
      ".cockpit-barre button[aria-pressed=true]{background:#4361ee;color:#fff}" +
      ".cockpit-edition [data-src]{outline:1px dashed #4361ee;outline-offset:2px;cursor:text}" +
      ".cockpit-edition [data-src][contenteditable=true]{outline:2px solid #4361ee;background:rgba(67,97,238,.06)}" +
      ".cockpit-bulle{position:fixed;left:16px;bottom:16px;z-index:2147483647;max-width:60vw;padding:8px 12px;" +
      "border-radius:6px;background:#1a1a2e;color:#fff;font:13px system-ui,sans-serif}" +
      ".cockpit-bulle.ko{background:#c0392b}";
    doc.head.appendChild(style);

    var barre = doc.createElement("div");
    barre.className = "cockpit-barre";
    var bEditer = doc.createElement("button");
    bEditer.type = "button";
    bEditer.textContent = "Éditer";
    bEditer.setAttribute("aria-pressed", "false");
    barre.appendChild(bEditer);
    doc.body.appendChild(barre);

    var bulle = null;
    function dire(texte, ko) {
      if (!bulle) { bulle = doc.createElement("div"); doc.body.appendChild(bulle); }
      bulle.className = "cockpit-bulle" + (ko ? " ko" : "");
      bulle.textContent = texte;
    }

    var enCours = null;
    var envoi = false;   // une sauvegarde est en vol : aucune autre action d'édition jusqu'à sa réponse
    var MSG_EN_COURS = "Modification en cours : Entrée pour enregistrer, Échap pour annuler";
    function modifie() {
      return !!enCours && texteSain(enCours.el.textContent) !== texteSain(enCours.avant);
    }
    function quitter(restaurer) {
      if (!enCours) return;
      if (restaurer) enCours.el.textContent = enCours.avant;
      enCours.el.removeAttribute("contenteditable");
      enCours = null;
    }

    function enregistrer() {
      if (envoi || !enCours) return;
      var el = enCours.el;
      var valeur = texteSain(el.textContent);
      if (valeur === texteSain(enCours.avant)) { quitter(false); return; }
      var lang = langCourante(doc.documentElement.getAttribute("data-lang"));
      var r = requeteSource(el.getAttribute("data-src"), lang, valeur, jeton);
      dire("Enregistrement…", false);
      el.removeAttribute("contenteditable");
      envoi = true;
      win.fetch(r.url, r.init).then(function (rep) {
        return rep.text().then(function (corps) {
          if (rep.ok) {
            var alertes = alertesEtapes(corps);
            var garde = true;
            try {
              win.sessionStorage.setItem("cockpit-defilement", String(win.scrollY));
              win.sessionStorage.setItem("cockpit-edition", "1");
              if (alertes.length) win.sessionStorage.setItem("cockpit-alerte", "Enregistré, mais : " + alertes.join(" ; "));
            } catch (e) {
              garde = false;
            }
            if (alertes.length && !garde) {
              envoi = false; quitter(false); dire("Enregistré, mais : " + alertes.join(" ; "), true); return;
            }
            win.location.reload();
          } else {
            envoi = false;
            dire(messageErreur(rep.status, corps), true);
            el.setAttribute("contenteditable", "true");
            el.focus();
          }
        });
      }).catch(function (e) {
        envoi = false;
        dire("Échec réseau : " + e, true);
        el.setAttribute("contenteditable", "true");
        el.focus();
      });
    }

    function basculer(actif) {
      if (envoi) { dire("Enregistrement en cours…", false); return; }
      if (!actif && modifie()) { dire(MSG_EN_COURS, true); return; }
      doc.body.classList.toggle("cockpit-edition", actif);
      bEditer.setAttribute("aria-pressed", actif ? "true" : "false");
      if (!actif) quitter(true);
    }

    bEditer.addEventListener("click", function () {
      basculer(!doc.body.classList.contains("cockpit-edition"));
    });

    doc.addEventListener("click", function (ev) {
      if (!doc.body.classList.contains("cockpit-edition") || barre.contains(ev.target)) return;
      var el = ev.target && ev.target.closest ? ev.target.closest("[data-src]") : null;
      if (!el) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (enCours && enCours.el === el) return;
      if (envoi) { dire("Enregistrement en cours…", false); return; }
      if (modifie()) { dire(MSG_EN_COURS, true); return; }
      quitter(true);
      enCours = { el: el, avant: el.textContent };
      el.setAttribute("contenteditable", "true");
      el.focus();
    }, true);

    doc.addEventListener("keydown", function (ev) {
      if (!enCours || envoi) return;
      if (ev.key === "Enter") { ev.preventDefault(); enregistrer(); }
      else if (ev.key === "Escape") { ev.preventDefault(); quitter(true); dire("Modification annulée", false); }
    }, true);

    try {
      var y = win.sessionStorage.getItem("cockpit-defilement");
      if (win.sessionStorage.getItem("cockpit-edition") === "1") basculer(true);
      var alerte = win.sessionStorage.getItem("cockpit-alerte");
      win.sessionStorage.removeItem("cockpit-defilement");
      win.sessionStorage.removeItem("cockpit-edition");
      win.sessionStorage.removeItem("cockpit-alerte");
      if (alerte) dire(alerte, true);
      if (y) win.scrollTo(0, parseInt(y, 10) || 0);
    } catch (e) { /* stockage indisponible : rien à restaurer */ }

    var bPublier = doc.createElement("button");
    bPublier.type = "button";
    bPublier.textContent = "Publier";
    barre.appendChild(bPublier);
    var panneau = null;

    function ligne(parent, texte, classe) {
      var p = doc.createElement("p");
      p.textContent = texte;
      if (classe) p.style.color = classe === "ko" ? "#c0392b" : "#159957";
      parent.appendChild(p);
      return p;
    }

    function appel(methode, url, corps) {
      var init = { method: methode, headers: { "X-Atelier-Token": jeton } };
      if (corps !== undefined) {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(corps);
      }
      return win.fetch(url, init).then(function (r) {
        return r.text().then(function (t) {
          var j = {};
          try { j = JSON.parse(t); } catch (e) { j = { erreur: t }; }
          return { ok: r.ok, statut: r.status, json: j };
        });
      });
    }

    function suivre(sha, zone, essais) {
      appel("GET", "/__cockpit/publication/pages?sha=" + encodeURIComponent(sha)).then(function (r) {
        var s = r.json.statut || "inconnu";
        zone.textContent = "GitHub Pages : " + s + (r.json.erreur ? " — " + r.json.erreur : "");
        if (s === "built") { zone.textContent += " — en ligne : " + (r.json.url || ""); return; }
        if (s === "errored" || essais <= 0) return;
        win.setTimeout(function () { suivre(sha, zone, essais - 1); }, 5000);
      });
    }

    function ouvrirPanneau() {
      if (panneau) { panneau.remove(); panneau = null; return; }
      panneau = doc.createElement("div");
      panneau.style.cssText = "position:fixed;right:16px;bottom:60px;z-index:2147483647;width:min(560px,90vw);" +
        "max-height:70vh;overflow:auto;background:#fff;color:#1a1a2e;border:1px solid #4361ee;border-radius:8px;" +
        "padding:12px;font:13px system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.2)";
      doc.body.appendChild(panneau);
      ligne(panneau, "Chargement de l'état…");
      appel("GET", "/__cockpit/publication").then(function (r) {
        panneau.textContent = "";
        var rep = r.json, res = resumeEtat(rep), verifs = null;
        ligne(panneau, "Fichiers à publier : " + (res.fichiers.length || "aucun"));
        res.fichiers.forEach(function (f) { ligne(panneau, "• " + f); });
        res.refus.forEach(function (m) { ligne(panneau, "Refus : " + m, "ko"); });
        Object.keys(rep.diffs || {}).forEach(function (c) {
          var pre = doc.createElement("pre");
          pre.style.cssText = "background:#f6f7fb;padding:8px;overflow:auto;max-height:200px";
          pre.textContent = c + "\n" + rep.diffs[c];
          panneau.appendChild(pre);
        });
        var message = doc.createElement("input");
        message.type = "text";
        message.value = rep.message || "";
        message.style.cssText = "width:100%;margin:6px 0";
        panneau.appendChild(message);
        var zone = ligne(panneau, "");
        var bVerifier = doc.createElement("button");
        bVerifier.type = "button";
        bVerifier.textContent = "Vérifier";
        var bEnvoyer = doc.createElement("button");
        bEnvoyer.type = "button";
        bEnvoyer.textContent = "Publier sur main";
        bEnvoyer.disabled = true;
        panneau.appendChild(bVerifier);
        panneau.appendChild(bEnvoyer);
        bVerifier.addEventListener("click", function () {
          zone.textContent = "Vérifications en cours (≈ 30 s)…";
          appel("POST", "/__cockpit/publication/verifier", {}).then(function (rv) {
            verifs = rv.json;
            zone.textContent = "";
            (verifs.verifications || []).forEach(function (v) {
              ligne(panneau, (v.ok ? "✓ " : "✗ ") + v.nom + (v.detail ? " — " + v.detail : ""), v.ok ? "ok" : "ko");
            });
            if (verifs.erreur) ligne(panneau, verifs.erreur, "ko");
            bEnvoyer.disabled = !peutPublier(rep, verifs);
          });
        });
        bEnvoyer.addEventListener("click", function () {
          bEnvoyer.disabled = true;
          zone.textContent = "Publication…";
          appel("POST", "/__cockpit/publication/publier", { message: message.value }).then(function (rp) {
            var j = rp.json;
            if (j.ok) {
              zone.textContent = "Poussé : " + j.commit;
              suivre(j.commit, ligne(panneau, "GitHub Pages : en attente"), 60);
            } else {
              zone.textContent = "Non publié : " + ((j.refus || []).join(" ; ") || j.erreur || ("étape " + j.etape))
                + (j.commit_local ? " (commit local conservé : relancer « Publier » pour le pousser)" : "");
            }
          });
        });
      });
    }

    bPublier.addEventListener("click", ouvrirPanneau);

    return { barre: barre, dire: dire, basculer: basculer };
  }

  return {
    texteSain: texteSain, langCourante: langCourante, requeteSource: requeteSource,
    messageErreur: messageErreur, alertesEtapes: alertesEtapes, demarrer: demarrer,
    resumeEtat: resumeEtat, peutPublier: peutPublier
  };
});

if (typeof window !== "undefined" && window.__COCKPIT__ && window.Calque) {
  window.Calque.instance = window.Calque.demarrer(window, document);
}
