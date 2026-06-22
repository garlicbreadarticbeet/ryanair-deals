/* Split-flap vertrekbord — progressive enhancement.
 * De <table> is server-gerenderd en zonder dit script volledig leesbaar; hier verven we er een
 * per-teken scramble-flip overheen (Web Animations API, alleen transform/opacity) die periodiek
 * één rij naar een andere voorbeelddeal wisselt. Pauzeert buiten beeld, in een verborgen tab, bij
 * hover en via een expliciete pauzeknop (WCAG 2.2.2); respecteert prefers-reduced-motion.
 */
(function () {
  "use strict";
  var board = document.getElementById("flapBoard");
  if (!board) return;
  var reduceMq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  if (reduceMq && reduceMq.matches) return; // stil, server-gerenderd bord

  var pool;
  try { pool = JSON.parse(board.getAttribute("data-pool")); } catch (e) { return; }
  if (!Array.isArray(pool) || pool.length < 8) return; // te weinig om zinnig te roteren

  var allRows = [].slice.call(board.querySelectorAll(".flap-row"));
  if (allRows.length < 2) return;

  var COLS = ["from", "to", "price", "nights", "via"];
  var DELAY = { from: 0, to: 150, nights: 300, via: 410, price: 550 }; // prijs flipt als laatste = payoff
  var GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  var FLIP = 130, TICKS = 2;

  var rows, shown, pointer, nextRow, STAGGER, CYCLE;
  var timer = null, paused = false, hovered = false, visible = false;
  var timers = [], anims = [], pending = [];

  function prune(arr, v) { var i = arr.indexOf(v); if (i >= 0) arr.splice(i, 1); }
  function setBlank(t, ch) { t.classList.toggle("is-blank", ch === " "); }

  // Stop al het lopende flip-werk en land elke tegel netjes op zijn eindteken.
  function halt() {
    while (timers.length) clearTimeout(timers.pop());
    while (anims.length) { var a = anims.pop(); try { a.cancel(); } catch (e) {} }
    pending.forEach(function (p) { p.tile.textContent = p.ch; setBlank(p.tile, p.ch); });
    pending = [];
    [].forEach.call(board.querySelectorAll(".flap-row.is-active"), function (r) { r.classList.remove("is-active"); });
  }

  function flipTile(tile, finalCh, delay) {
    var seq = [];
    for (var i = 0; i < TICKS; i++) seq.push(GLYPHS.charAt((Math.random() * GLYPHS.length) | 0));
    seq.push(finalCh);
    var rec = { tile: tile, ch: finalCh };
    pending.push(rec);
    var k = 0;
    function one() {
      if (tile.animate) {
        var a = tile.animate(
          [{ transform: "scaleY(1)", opacity: 1 }, { transform: "scaleY(.05)", opacity: .45, offset: .5 },
           { transform: "scaleY(1)", opacity: 1 }],
          { duration: FLIP, easing: "cubic-bezier(.3,.1,.3,1)" });
        anims.push(a);
        a.onfinish = a.oncancel = function () { prune(anims, a); };
      }
      var t = setTimeout(function () {
        prune(timers, t);
        tile.textContent = seq[k]; setBlank(tile, seq[k]); k++;
        if (k < seq.length) { var t2 = setTimeout(one, FLIP * 0.5); timers.push(t2); }
        else prune(pending, rec); // geland op eindteken
      }, FLIP * 0.48);
      timers.push(t);
    }
    var t0 = setTimeout(function () { prune(timers, t0); one(); }, delay);
    timers.push(t0);
  }

  function updateRow(rowEl, deal) {
    COLS.forEach(function (col) {
      var cell = rowEl.querySelector(".flap-cell--" + col);
      if (!cell || cell.offsetParent === null || !deal.tiles[col]) return; // sla verborgen/lege over
      var target = Array.from(deal.tiles[col]);
      var tiles = cell.querySelectorAll(".flap-tiles .flap");
      for (var i = 0; i < tiles.length; i++) {
        var ch = target[i] || " ";
        if (tiles[i].textContent !== ch) flipTile(tiles[i], ch, DELAY[col] + i * STAGGER);
      }
      var sr = cell.querySelector(".sr-only");
      if (sr && deal.read[col]) sr.textContent = deal.read[col]; // bijwerken zonder aria-live
    });
    rowEl.classList.add("is-active");
    var ta = setTimeout(function () { prune(timers, ta); rowEl.classList.remove("is-active"); }, 1000);
    timers.push(ta);
  }

  function tick() {
    var idx = pointer % pool.length, guard = 0;
    while (shown.indexOf(idx) !== -1 && guard < pool.length) { pointer++; idx = pointer % pool.length; guard++; }
    shown[nextRow] = idx; pointer++;
    updateRow(rows[nextRow], pool[idx]);
    nextRow = (nextRow + 1) % rows.length;
  }

  function recompute() {
    var want = visible && !document.hidden && !hovered && !paused;
    if (want && !timer) timer = setInterval(tick, CYCLE);
    else if (!want && timer) { clearInterval(timer); timer = null; }
  }

  // (Her)initialiseer voor de huidige breakpoint: zichtbare rijen, timing, rotatie-state.
  function setup() {
    if (timer) { clearInterval(timer); timer = null; }
    halt();
    rows = allRows.filter(function (r) { return r.offsetParent !== null; });
    if (rows.length < 2) return;
    var mobile = window.matchMedia("(max-width: 760px)").matches;
    STAGGER = mobile ? 22 : 32; CYCLE = mobile ? 5500 : 4500;
    shown = rows.map(function (r) { return parseInt(r.getAttribute("data-idx"), 10) || 0; });
    pointer = rows.length; nextRow = 0;
    recompute();
  }

  var btn = document.getElementById("flapPause");
  if (btn) btn.addEventListener("click", function () {
    paused = !paused;
    btn.setAttribute("aria-pressed", paused ? "true" : "false");
    btn.classList.toggle("is-paused", paused);
    recompute();
  });

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; recompute(); },
      { threshold: 0.25 }).observe(board);
  } else { visible = true; }
  document.addEventListener("visibilitychange", recompute);
  board.addEventListener("mouseenter", function () { hovered = true; recompute(); });
  board.addEventListener("mouseleave", function () { hovered = false; recompute(); });

  var mq = window.matchMedia("(max-width: 760px)");
  if (mq.addEventListener) mq.addEventListener("change", setup); else if (mq.addListener) mq.addListener(setup);
  if (reduceMq && reduceMq.addEventListener) reduceMq.addEventListener("change", function () {
    if (reduceMq.matches) { paused = true; recompute(); halt(); }
  });

  setup();
})();
