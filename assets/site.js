/* ============================================================================
   gilly.space — site.js
   ----------------------------------------------------------------------------
   Zero-build, no-jQuery shared-shell loader + theme toggle.

   1. Injects partials/header.html and partials/footer.html into placeholders:
        <div data-include="header"></div>
        <div data-include="footer"></div>
   2. Marks the active nav link with aria-current="page".
   3. Wires the three-state (system | light | dark) theme toggle, using the SAME
      `enso-theme` localStorage key as the enso toys — so a preference set in
      the calendar carries across the whole site, and vice-versa.

   The pre-paint <script> that sets .dark before first paint lives INLINE in each
   page's <head> (see partials/head.html); it must run before paint, so it can't
   wait on this fetch. This file only handles injection + the toggle interaction.

   GROUNDWORK: not referenced by any page yet. Pages opt in during the redesign.
   ========================================================================== */
(function () {
  'use strict';

  /* ---- 1 & 2: inject shared header/footer, then mark the active nav link ---- */
  function markActive(root) {
    var here = location.pathname.replace(/index\.html$/, '').replace(/\/$/, '') || '/';
    var links = root.querySelectorAll('.site-nav a');
    links.forEach(function (a) {
      var path = a.getAttribute('href').split('#')[0].replace(/index\.html$/, '').replace(/\/$/, '') || '/';
      if (path !== '/' && (here === path || here.indexOf(path) === 0)) {
        a.setAttribute('aria-current', 'page');
      } else if (path === '/' && here === '/') {
        a.setAttribute('aria-current', 'page');
      }
    });
  }

  function inject(name, target) {
    return fetch('/partials/' + name + '.html', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (html) { if (html) { target.innerHTML = html; } })
      .catch(function () { /* leave the <noscript>/static fallback in place */ });
  }

  function boot() {
    var jobs = [];
    var header = document.querySelector('[data-include="header"]');
    var footer = document.querySelector('[data-include="footer"]');
    if (header) jobs.push(inject('header', header).then(function () { markActive(header); }));
    if (footer) jobs.push(inject('footer', footer));
    Promise.all(jobs).then(initThemeToggle);
  }

  /* ---- 3: theme toggle (mirrors enso/index.html exactly) ---- */
  function initThemeToggle() {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    var order  = ['system', 'light', 'dark'];
    var icons  = { system: '🖥️', light: '☀️', dark: '🌙' };
    var titles = {
      system: 'Theme: System (click to cycle)',
      light:  'Theme: Light (click to cycle)',
      dark:   'Theme: Dark (click to cycle)'
    };
    var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function getMode() {
      try { return localStorage.getItem('enso-theme') || 'system'; }
      catch (e) { return 'system'; }
    }
    function applyMode(mode) {
      var prefersDark = mq ? mq.matches : false;
      var dark = mode === 'dark' || (mode === 'system' && prefersDark);
      document.documentElement.classList.toggle('dark', dark);
      btn.textContent = icons[mode];
      btn.title = titles[mode];
    }
    btn.addEventListener('click', function () {
      var next = order[(order.indexOf(getMode()) + 1) % order.length];
      try { localStorage.setItem('enso-theme', next); } catch (e) {}
      applyMode(next);
    });
    if (mq) {
      var onChange = function () { if (getMode() === 'system') applyMode('system'); };
      if (mq.addEventListener) mq.addEventListener('change', onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
    applyMode(getMode());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
