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

  /* ---- 0: scroll-reveal. Armed synchronously (this script is parser-blocking
       at end of <body>, so it runs before first paint → no flash). Skipped
       entirely under reduced-motion or without IntersectionObserver, so content
       is never hidden when it can't be revealed. ---- */
  (function armReveal() {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!('IntersectionObserver' in window) || reduce) return;
    var targets = document.querySelectorAll('main .card, main figure, main .embed-16x9');
    if (!targets.length) return;
    document.documentElement.classList.add('js-reveal');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.04 });
    targets.forEach(function (t) { t.classList.add('reveal'); io.observe(t); });
    document.querySelectorAll('main .grid').forEach(function (g) {
      var i = 0;
      Array.prototype.forEach.call(g.children, function (c) {
        if (c.classList.contains('reveal')) { c.style.transitionDelay = (Math.min(i, 5) * 70) + 'ms'; i++; }
      });
    });
  })();

  /* ---- 1 & 2: inject shared header/footer, then mark the active nav link ---- */
  function norm(p) { return p.replace(/index\.html$/, '').replace(/\/$/, '') || '/'; }

  function markActive(root) {
    var here = norm(location.pathname);
    root.querySelectorAll('.site-nav a').forEach(function (a) {
      var url = new URL(a.getAttribute('href'), location.origin);
      if (url.hash) return;                 // in-page anchors (e.g. /#about) are never "the page"
      var path = norm(url.pathname);
      if (path === '/') return;             // no "Home" nav item; the wordmark covers home
      if (here === path || here.indexOf(path + '/') === 0) {
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
    Promise.all(jobs).then(function () { initThemeToggle(); externalizeLinks(); });
  }

  /* ---- New tabs by default: every link opens in a new tab EXCEPT the primary
       top-nav (so moving around the site doesn't spawn endless tabs), the
       wordmark, the skip link, and same-page / mail / tel links. ---- */
  function externalizeLinks() {
    document.querySelectorAll('a[href]').forEach(function (a) {
      if (a.hasAttribute('target')) return;                       // respect explicit target
      var href = a.getAttribute('href') || '';
      if (/^(#|mailto:|tel:|javascript:)/i.test(href)) return;
      if (a.closest('.site-nav') || a.classList.contains('brand') || a.classList.contains('skip-link')) return;
      a.target = '_blank';
      a.rel = (a.rel ? a.rel + ' ' : '') + 'noopener noreferrer';
    });
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
