/* Vriendelijke /preferences: luchthaven zoek-en-kies, klikbare nachten, landen-kiezer.
   Vanilla JS (geen build-stap). Vult verborgen formuliervelden die de server al kent. */
(function () {
  'use strict';
  var PREFS = window.__PREFS__ || {};
  var COUNTRIES = window.__COUNTRIES__ || [];

  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    return e;
  }
  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }

  /* ---------- Luchthaven-picker (origins / whitelist / blacklist) ---------- */
  function setupPicker(picker) {
    var max = parseInt(picker.getAttribute('data-max') || '99', 10);
    var chipsBox = picker.querySelector('[data-chips]');
    var input = picker.querySelector('[data-input]');
    var list = picker.querySelector('[data-list]');
    var note = picker.querySelector('[data-note]');
    var hidden = picker.parentElement.querySelector('[data-hidden]');
    var selected = [];

    function syncHidden() { hidden.value = selected.map(function (s) { return s.iata; }).join(' '); }
    function updateNote() {
      if (selected.length >= max) {
        if (note) { note.hidden = false; note.textContent = max === 1
          ? 'Met gratis kies je één luchthaven. Upgrade naar Premium voor meer.'
          : 'Je hebt het maximum van ' + max + ' bereikt.'; }
        input.disabled = true; input.placeholder = '';
      } else if (note) { note.hidden = true; input.disabled = false; }
      else { input.disabled = false; }
    }
    function renderChips() {
      chipsBox.innerHTML = '';
      selected.forEach(function (s, idx) {
        var chip = el('span', 'chip');
        chip.appendChild(el('span', null, s.label));
        var x = el('button', 'chip-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Verwijderen');
        x.addEventListener('click', function () { selected.splice(idx, 1); renderChips(); syncHidden(); updateNote(); });
        chip.appendChild(x);
        chipsBox.appendChild(chip);
      });
    }
    function hideList() { list.hidden = true; list.innerHTML = ''; }
    function add(item) {
      if (selected.length >= max) return;
      if (selected.some(function (s) { return s.iata === item.iata; })) return;
      var label = item.label || (item.name ? item.name + ' (' + item.iata + ')' : item.iata);
      selected.push({ iata: item.iata, label: label });
      renderChips(); syncHidden(); updateNote();
      input.value = ''; hideList();
    }
    function renderList(items) {
      list.innerHTML = '';
      var avail = items.filter(function (it) { return !selected.some(function (s) { return s.iata === it.iata; }); });
      if (!avail.length) { hideList(); return; }
      avail.forEach(function (it, i) {
        var row = el('button', 'picker-item' + (i === 0 ? ' is-active' : '')); row.type = 'button';
        row.appendChild(el('strong', null, it.name));
        if (it.city && it.city !== it.name) row.appendChild(el('span', 'picker-city', ' ' + it.city));
        row.appendChild(el('span', 'picker-code', it.iata));
        row.addEventListener('click', function () { add(it); input.focus(); });
        list.appendChild(row);
      });
      list.hidden = false;
    }
    var search = debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { hideList(); return; }
      fetch('/api/airports?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); }).then(renderList).catch(hideList);
    }, 180);
    input.addEventListener('input', search);
    input.addEventListener('keydown', function (e) {
      var items = Array.prototype.slice.call(list.querySelectorAll('.picker-item'));
      var active = list.querySelector('.picker-item.is-active');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!items.length) return; e.preventDefault();
        var idx = items.indexOf(active);
        idx = e.key === 'ArrowDown' ? Math.min(items.length - 1, idx + 1) : Math.max(0, idx - 1);
        items.forEach(function (it) { it.classList.remove('is-active'); });
        items[idx].classList.add('is-active'); items[idx].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter') {
        if (!list.hidden && active) { e.preventDefault(); active.click(); }
      } else if (e.key === 'Escape') { hideList(); }
    });
    document.addEventListener('click', function (e) { if (!picker.contains(e.target)) hideList(); });

    (PREFS[picker.getAttribute('data-picker')] || []).forEach(function (s) { selected.push(s); });
    renderChips(); syncHidden(); updateNote();
  }

  /* ---------- Nachten (klikbare chips + eigen aantal) ---------- */
  function setupDays() {
    var box = document.querySelector('[data-daychips]');
    if (!box) return;
    var hidden = document.querySelector('[data-triphidden]');
    var base = [1, 2, 3, 4, 5, 6, 7, 10, 14];
    var selected = new Set((PREFS.tripLengths || []).map(Number));
    function sync() { hidden.value = Array.from(selected).sort(function (a, b) { return a - b; }).join(' '); }
    function render() {
      box.innerHTML = '';
      var all = Array.from(new Set(base.concat(Array.from(selected)))).sort(function (a, b) { return a - b; });
      all.forEach(function (n) {
        var b = el('button', 'day-chip' + (selected.has(n) ? ' is-on' : ''), n + (n === 1 ? ' nacht' : ' nachten'));
        b.type = 'button';
        b.addEventListener('click', function () { selected.has(n) ? selected.delete(n) : selected.add(n); render(); sync(); });
        box.appendChild(b);
      });
    }
    var custom = document.querySelector('[data-daycustom]');
    var addBtn = document.querySelector('[data-dayadd]');
    function addCustom() { var v = parseInt(custom.value, 10); if (v >= 1 && v <= 60) { selected.add(v); custom.value = ''; render(); sync(); } }
    if (addBtn) addBtn.addEventListener('click', addCustom);
    if (custom) custom.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); addCustom(); } });
    render(); sync();
  }

  /* ---------- Landen-kiezer ---------- */
  function setupCountries() {
    var box = document.querySelector('[data-countries]');
    if (!box) return;
    var hidden = document.querySelector('[data-countryhidden]');
    var selected = new Set((PREFS.countries || []).map(function (c) { return String(c).toLowerCase(); }));
    function sync() { hidden.value = Array.from(selected).join(' '); }
    COUNTRIES.forEach(function (c) {
      var b = el('button', 'country-chip' + (selected.has(c.code) ? ' is-on' : ''), c.name); b.type = 'button';
      b.addEventListener('click', function () {
        if (selected.has(c.code)) { selected.delete(c.code); b.classList.remove('is-on'); }
        else { selected.add(c.code); b.classList.add('is-on'); }
        sync();
      });
      box.appendChild(b);
    });
    sync();
  }

  /* ---------- Bestemmings-modus (toon juiste sub-blok) ---------- */
  function setupDestMode() {
    var radios = document.querySelectorAll('[data-destmode] input[type=radio]');
    var subs = document.querySelectorAll('[data-destsub]');
    function update() {
      var val = 'all';
      radios.forEach(function (r) { if (r.checked) val = r.value; });
      subs.forEach(function (s) { s.hidden = s.getAttribute('data-destsub') !== val; });
    }
    radios.forEach(function (r) { r.addEventListener('change', update); });
    var mode = PREFS.destMode || 'all';
    radios.forEach(function (r) { r.checked = (r.value === mode); });
    update();
  }

  document.querySelectorAll('.picker').forEach(setupPicker);
  setupDays();
  setupCountries();
  setupDestMode();
})();
