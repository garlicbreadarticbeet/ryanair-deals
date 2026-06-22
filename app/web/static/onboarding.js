/* Onboarding-wizard — progressive enhancement.
 * De <form> werkt volledig zonder JS (alle stappen onder elkaar, echte form-controls).
 * Met JS tonen we één stap tegelijk, met voortgang, validatie, een premium-nudge, een
 * voorbeeld-deals-stap afgestemd op de antwoorden, en een korte 'processing'-pauze.
 */
(function () {
  "use strict";
  var form = document.getElementById("obForm");
  if (!form) return;
  var steps = [].slice.call(form.querySelectorAll(".ob-step"));
  if (steps.length < 2) return;
  var bar = document.getElementById("obBar");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  form.classList.add("js-steps");
  var idx = 0;

  // Onzichtbare live-region: kondigt 'Stap X van Y' aan voor screenreaders bij elke stapwissel.
  var live = document.createElement("div");
  live.className = "sr-only";
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  form.parentNode.insertBefore(live, form);

  function selectedOrigins() {
    return [].slice.call(form.querySelectorAll('input[name="origins"]:checked')).map(function (c) { return c.value; });
  }
  function val(name) {
    var el = form.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : "";
  }

  function show(i) {
    i = Math.max(0, Math.min(steps.length - 1, i));
    steps[idx].classList.remove("is-active");
    idx = i;
    var step = steps[idx];
    step.classList.add("is-active");
    if (bar) bar.style.width = Math.round(((idx + 1) / steps.length) * 100) + "%";
    live.textContent = "Stap " + (idx + 1) + " van " + steps.length +
      (step.dataset.title ? ": " + step.dataset.title : "");
    // focus de kop voor screenreaders/toetsenbord
    var head = step.querySelector("h1, h2");
    if (head) { head.setAttribute("tabindex", "-1"); head.focus({ preventScroll: true }); }
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    onEnter(step);
  }

  function onEnter(step) {
    var name = step.getAttribute("data-step");
    if (name === "rekenen") {
      var ms = parseInt(step.getAttribute("data-auto"), 10) || 1800;
      var msg = document.getElementById("obProcessing");
      if (msg) {
        var o = selectedOrigins().length;
        msg.textContent = o > 1
          ? "We zetten je " + o + " vertrekvelden, je drempel en je reisduur klaar."
          : "We zetten je vertrekveld, je drempel en je reisduur klaar.";
      }
      setTimeout(function () { if (steps[idx] === step) next(); }, reduce ? 600 : ms);
    } else if (name === "voorbeelden") {
      renderDeals();
    } else if (name === "plan") {
      tunePlanCopy();
    }
  }

  // ---- voorbeelddeals afgestemd op de antwoorden ----
  var DEALS = [];
  try { DEALS = JSON.parse(form.getAttribute("data-deals")) || []; } catch (e) { DEALS = []; }

  function renderDeals() {
    var box = document.getElementById("obDeals");
    if (!box || !DEALS.length) return;
    var origins = selectedOrigins();
    var max = parseFloat(val("threshold")) || 9999;
    var pick = DEALS.filter(function (d) { return (!origins.length || origins.indexOf(d.origin) !== -1) && d.price <= max; });
    if (pick.length < 2) pick = DEALS.filter(function (d) { return !origins.length || origins.indexOf(d.origin) !== -1; });
    if (pick.length < 2) pick = DEALS.slice();
    pick = pick.sort(function (a, b) { return a.price - b.price; }).slice(0, 4);

    box.textContent = "";
    pick.forEach(function (d) {
      var card = document.createElement("div"); card.className = "ob-deal";
      var top = document.createElement("div"); top.className = "ob-deal__top";
      var route = document.createElement("span"); route.className = "ob-deal__route"; route.textContent = d.city;
      var price = document.createElement("span"); price.className = "ob-deal__price"; price.textContent = "€" + d.price;
      top.appendChild(route); top.appendChild(price);
      var meta = document.createElement("div"); meta.className = "ob-deal__meta";
      meta.textContent = d.country + " · " + d.nights + " nachten · retour";
      card.appendChild(top); card.appendChild(meta);
      box.appendChild(card);
    });
    var sub = document.getElementById("obDealsSub");
    if (sub) {
      sub.textContent = origins.length
        ? "Voorbeelden vanaf jouw veld" + (origins.length > 1 ? "en" : "") + " onder €" + (parseInt(max, 10) || "") + ". Prijzen kunnen wijzigen."
        : "Voorbeelden van retours die met jouw instellingen voorbijkomen. Prijzen kunnen wijzigen.";
    }
  }

  function tunePlanCopy() {
    var sub = document.getElementById("obPlanSub");
    if (!sub) return;
    var o = selectedOrigins().length;
    if (o > 1) {
      sub.innerHTML = "Je koos <strong>" + o + " vertrekvelden</strong>. Met Premium staan ze allemaal aan " +
        "én ben je met directe seintjes als eerste bij de scherpste prijs. Liever gratis? Ook prima.";
    } else {
      sub.textContent = "De scherpste prijzen zijn vaak het eerst weg. Begin gratis of wees er met Premium meteen bij. Je kiest zelf.";
    }
  }

  // ---- premium-nudge op de velden-stap ----
  var nudge = document.getElementById("obFieldNudge");
  var airports = document.getElementById("obAirports");
  if (airports && nudge) {
    airports.addEventListener("change", function () {
      nudge.hidden = selectedOrigins().length <= 1;
    });
  }

  // ---- navigatie ----
  function next() {
    var btn = steps[idx].querySelector("[data-next][data-require]");
    var req = btn && btn.getAttribute("data-require");
    if (req === "origins" && !selectedOrigins().length) {
      flashRequire(steps[idx], "Kies minstens één vertrekveld om verder te gaan.");
      var first = form.querySelector('input[name="origins"]');
      if (first) first.focus();
      return;
    }
    show(idx + 1);
  }
  function back() { show(idx - 1); }

  function flashRequire(step, text) {
    var el = step.querySelector(".ob-require");
    if (!el) {
      el = document.createElement("p");
      el.className = "ob-nudge ob-require";
      el.setAttribute("role", "alert");
      var nav = step.querySelector(".ob-nav");
      step.insertBefore(el, nav);
    }
    el.textContent = text;
  }

  form.addEventListener("click", function (e) {
    var n = e.target.closest("[data-next]");
    var b = e.target.closest("[data-back]");
    if (n) { e.preventDefault(); next(); }
    else if (b) { e.preventDefault(); back(); }
  });

  // Enter in het e-mailveld verstuurt (laatste stap). Op radio/checkbox NIET kapen (native
  // selectie via spatie blijft), maar wél per-ongeluk-submitten van de hele form voorkomen.
  form.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var t = e.target;
    if (t && t.tagName === "INPUT" && t.type === "email") return; // submit toestaan
    if (t && t.tagName === "INPUT" && (t.type === "radio" || t.type === "checkbox")) {
      e.preventDefault(); // geen onbedoelde submit; spatie selecteert nog steeds
    }
  });

  show(0);
})();
