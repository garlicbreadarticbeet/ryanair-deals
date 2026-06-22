/* Lemon Squeezy checkout — overlay waar het betrouwbaar is, anders de hosted checkout.
 *
 * In Chrome/Firefox/Edge opent de betaling als overlay op de eigen site (lemon.js). In Safari
 * en op iOS valt de overlay terug op de hosted checkout: de embed-overlay loopt daar vast op
 * Safari's cross-origin-afscherming van de Stripe-iframe (bekende, niet-opgeloste LS-limitatie,
 * gaf een 404 bij afrekenen). Zonder JS doet de upgrade-knop sowieso een POST naar /upgrade.
 */
(function () {
  "use strict";

  function appleWebkit() {
    var ua = navigator.userAgent || "";
    var iOS = /iP(hone|ad|od)/.test(ua) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); // iPadOS meldt zich als Mac
    var safari = /^((?!chrome|crios|fxios|edg|android).)*safari/i.test(ua);
    return iOS || safari;
  }

  function ensureInit() {
    if (window.createLemonSqueezy && !(window.LemonSqueezy && window.LemonSqueezy.Url)) {
      try { window.createLemonSqueezy(); } catch (e) {}
    }
    return window.LemonSqueezy && window.LemonSqueezy.Url ? window.LemonSqueezy : null;
  }

  // Overlay waar het kan; anders (Safari/iOS of geen lemon.js) de hosted checkout in hetzelfde tab.
  function openCheckout(url) {
    if (appleWebkit()) { window.location.href = url; return; }
    var inst = ensureInit();
    if (!inst) { window.location.href = url; return; }
    inst.Url.Open(url + (url.indexOf("?") >= 0 ? "&" : "?") + "embed=1");
  }

  function fetchUrl(plan) {
    return fetch("/billing/checkout-url", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "plan=" + encodeURIComponent(plan),
    }).then(function (r) { return r.ok ? r.json() : null; });
  }

  function init() {
    // Event-handler alleen voor de overlay-browsers; Safari/iOS keert via redirect_url terug.
    if (!appleWebkit()) {
      var inst = ensureInit();
      if (inst && inst.Setup) {
        try {
          inst.Setup({ eventHandler: function (ev) {
            if (ev && ev.event === "Checkout.Success") {
              setTimeout(function () { window.location.href = "/account?paid=1"; }, 700);
            }
          } });
        } catch (e) {}
      }
    }

    var form = document.getElementById("upgradeForm");
    if (form) {
      form.addEventListener("submit", function (e) {
        // Safari/iOS of geen lemon.js: laat de normale POST -> hosted checkout lopen.
        if (appleWebkit() || !ensureInit()) return;
        e.preventDefault();
        var sel = form.querySelector('input[name="plan"]:checked');
        var plan = sel ? sel.value : "annual";
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        fetchUrl(plan).then(function (d) {
          if (d && d.url) { openCheckout(d.url); if (btn) btn.disabled = false; }
          else { form.submit(); }            // terugval: hosted checkout
        }).catch(function () { form.submit(); });
      });
    }

    // Auto-open na e-mailbevestiging met premium-keuze (/account?start=plan).
    var auto = document.getElementById("lsAuto");
    if (auto) {
      var plan = auto.getAttribute("data-plan") || "annual";
      fetchUrl(plan).then(function (d) {
        if (d && d.url) openCheckout(d.url);
        else if (form) form.submit();
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
