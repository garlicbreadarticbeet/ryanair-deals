/* Lemon Squeezy checkout-overlay — progressive enhancement.
 * Zonder JS (of als lemon.js niet laadt) doet de upgrade-knop een gewone POST naar /upgrade,
 * die naar de hosted checkout redirect. Met lemon.js openen we de checkout als overlay op de
 * eigen site: we halen de checkout-URL via /billing/checkout-url op en geven 'm aan de overlay.
 */
(function () {
  "use strict";

  function ensureInit() {
    if (window.createLemonSqueezy && !(window.LemonSqueezy && window.LemonSqueezy.Url)) {
      try { window.createLemonSqueezy(); } catch (e) {}
    }
    return window.LemonSqueezy && window.LemonSqueezy.Url ? window.LemonSqueezy : null;
  }

  function openOverlay(url) {
    var inst = ensureInit();
    if (!inst) return false;
    inst.Url.Open(url + (url.indexOf("?") >= 0 ? "&" : "?") + "embed=1");
    return true;
  }

  function fetchUrl(plan) {
    return fetch("/billing/checkout-url", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "plan=" + encodeURIComponent(plan),
    }).then(function (r) { return r.ok ? r.json() : null; });
  }

  function init() {
    var inst = ensureInit();
    if (inst && inst.Setup) {
      try {
        inst.Setup({ eventHandler: function (ev) {
          // Na een geslaagde betaling terug naar het account; de webhook schaalt de tier op.
          if (ev && ev.event === "Checkout.Success") {
            setTimeout(function () { window.location.href = "/account?paid=1"; }, 700);
          }
        } });
      } catch (e) {}
    }

    var form = document.getElementById("upgradeForm");
    if (form) {
      form.addEventListener("submit", function (e) {
        if (!ensureInit()) return;          // geen lemon.js -> laat de normale POST (hosted) lopen
        e.preventDefault();
        var sel = form.querySelector('input[name="plan"]:checked');
        var plan = sel ? sel.value : "annual";
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        fetchUrl(plan).then(function (d) {
          if (d && d.url && openOverlay(d.url)) { if (btn) btn.disabled = false; }
          else { form.submit(); }            // terugval: hosted checkout
        }).catch(function () { form.submit(); });
      });
    }

    // Auto-open na e-mailbevestiging met premium-keuze (/account?start=plan).
    var auto = document.getElementById("lsAuto");
    if (auto && ensureInit()) {
      var plan = auto.getAttribute("data-plan") || "annual";
      fetchUrl(plan).then(function (d) { if (d && d.url) openOverlay(d.url); });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
