/* ============================================================================
   gilly.space — site.js
   ----------------------------------------------------------------------------
   Zero-build, no-dependency progressive enhancement for the whole site.
   Everything here is additive: the site works fully with JS disabled and with
   prefers-reduced-motion. Modules are individually guarded so one failing never
   takes down the others.

   Modules: shared header/footer injection · active nav · 3-state theme toggle ·
   new-tab links · scroll-reveal · scroll progress bar · back-to-top · animated
   starfield (dark mode) · card 3D tilt · image lightbox · reading time ·
   command palette (⌘K / Ctrl-K) · Konami solar-flare easter egg · service worker.
   ========================================================================== */
(function () {
  'use strict';

  var REDUCE = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var FINE = window.matchMedia && window.matchMedia('(pointer: fine)').matches;
  var safe = function (fn) { try { fn(); } catch (e) { /* never let one module break the rest */ } };

  /* ---- Scroll-reveal: armed synchronously (script is parser-blocking at end of
       <body> → runs before first paint, no flash). Skipped under reduced-motion
       or without IntersectionObserver so content is never hidden when it can't
       be revealed. ---- */
  safe(function () {
    if (!('IntersectionObserver' in window) || REDUCE) return;
    var targets = document.querySelectorAll('main .card, main figure, main .embed-16x9');
    if (!targets.length) return;
    document.documentElement.classList.add('js-reveal');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var el = e.target; el.classList.add('in'); io.unobserve(el);
        // after the reveal finishes, drop the classes so the base (fast) card
        // transition takes over for hover/tilt.
        setTimeout(function () { el.classList.remove('reveal', 'in'); el.style.transitionDelay = ''; }, 780);
      });
    }, { rootMargin: '0px 0px -6% 0px', threshold: 0.04 });
    targets.forEach(function (t) { t.classList.add('reveal'); io.observe(t); });
    document.querySelectorAll('main .grid').forEach(function (g) {
      var i = 0;
      Array.prototype.forEach.call(g.children, function (c) {
        if (c.classList.contains('reveal')) { c.style.transitionDelay = (Math.min(i, 5) * 70) + 'ms'; i++; }
      });
    });
  });

  /* ---- Shared header/footer injection + active nav ---- */
  function norm(p) { return p.replace(/index\.html$/, '').replace(/\/$/, '') || '/'; }
  function markActive(root) {
    var here = norm(location.pathname);
    root.querySelectorAll('.site-nav a').forEach(function (a) {
      var url = new URL(a.getAttribute('href'), location.origin);
      if (url.hash) return;
      var path = norm(url.pathname);
      if (path === '/') return;
      if (here === path || here.indexOf(path + '/') === 0) a.setAttribute('aria-current', 'page');
    });
  }
  var HEADER_FALLBACK = '<a class="skip-link" href="#main">Skip to content</a><header class="site-header"><div class="site-header__inner"><a class="brand" href="/">gilly<span class="dot">.</span>space</a><nav class="site-nav" aria-label="Primary"><a href="/Research.html">Research</a> <a href="/sun.html">The Sun</a> <a href="/RecordedPublicTalks.html">Outreach</a> <a href="/play/">Play</a> <a href="/shop.html">Store</a> <a href="/about.html">About / CV</a></nav></div></header>';
  var FOOTER_FALLBACK = '<footer class="site-footer"><div class="site-footer__inner"><span>&copy; Gilly &middot; gilly.space &middot; <a href="/">home</a></span></div></footer>';
  function inject(name, target, fallback) {
    var done = false;
    var to = setTimeout(function () { if (!done) { done = true; target.innerHTML = fallback; } }, 4000); // never hang headless/offline
    return fetch('/partials/' + name + '.html', { cache: 'no-cache' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (html) { if (!done) { done = true; clearTimeout(to); target.innerHTML = html || fallback; } })
      .catch(function () { if (!done) { done = true; clearTimeout(to); target.innerHTML = fallback; } });
  }
  function boot() {
    var jobs = [];
    var header = document.querySelector('[data-include="header"]');
    var footer = document.querySelector('[data-include="footer"]');
    if (header) jobs.push(inject('header', header, HEADER_FALLBACK).then(function () { markActive(header); }));
    if (footer) jobs.push(inject('footer', footer, FOOTER_FALLBACK));
    Promise.all(jobs).then(function () {
      safe(initThemeToggle);
      safe(externalizeLinks);
      safe(buildCommandPalette);   // needs the injected theme toggle
    });
    // these don't depend on the injected partials
    safe(scrollProgress);
    safe(backToTop);
    safe(starfield);
    safe(cardTilt);
    safe(lightbox);
    safe(readingTime);
    safe(konami);
    safe(respectVideos);
    safe(loadAnalytics);
    safe(registerSW);
  }

  /* ---- New tabs by default (except primary nav, wordmark, anchors, mail/tel) ---- */
  function externalizeLinks() {
    document.querySelectorAll('a[href]').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      if (/^(#|mailto:|tel:|javascript:)/i.test(href)) return;
      var skip = a.closest('.site-nav') || a.classList.contains('brand') || a.classList.contains('skip-link') || a.closest('[data-no-blank]');
      if (!skip && !a.hasAttribute('target')) a.target = '_blank';
      if (/_blank/i.test(a.target || '')) {
        a.rel = (a.rel ? a.rel + ' ' : '') + 'noopener noreferrer';   // also repairs hand-authored target=_blank links
        if (!a.closest('.icon-row') && !/opens in new tab/i.test(a.getAttribute('aria-label') || '')) {
          var name = (a.getAttribute('aria-label') || a.textContent || '').trim();
          if (name) a.setAttribute('aria-label', name + ' (opens in new tab)');
        }
      }
    });
  }

  /* ---- Reduced-motion: pause/neutralize auto-playing videos ---- */
  function respectVideos() {
    if (!REDUCE) return;
    document.querySelectorAll('video[autoplay]').forEach(function (v) {
      v.removeAttribute('autoplay'); v.setAttribute('controls', ''); try { v.pause(); } catch (e) {}
    });
  }

  /* ---- Three-state theme toggle (mirrors the enso toys; shared enso-theme key) ---- */
  function initThemeToggle() {
    var btn = document.getElementById('themeToggle');
    if (!btn) return;
    var order = ['system', 'light', 'dark'];
    var icons = { system: '🖥️', light: '☀️', dark: '🌙' };
    var titles = { system: 'Theme: System (click to cycle)', light: 'Theme: Light (click to cycle)', dark: 'Theme: Dark (click to cycle)' };
    var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    function getMode() { try { return localStorage.getItem('enso-theme') || 'system'; } catch (e) { return 'system'; } }
    function applyMode(mode) {
      var dark = mode === 'dark' || (mode === 'system' && mq && mq.matches);
      document.documentElement.classList.toggle('dark', dark);
      btn.textContent = icons[mode]; btn.title = titles[mode];
      btn.setAttribute('aria-label', titles[mode]);   // expose current state to AT
      window.dispatchEvent(new CustomEvent('themechange', { detail: { dark: dark } }));
    }
    btn.addEventListener('click', function () {
      var next = order[(order.indexOf(getMode()) + 1) % order.length];
      try { localStorage.setItem('enso-theme', next); } catch (e) {}
      applyMode(next);
    });
    if (mq) { var on = function () { if (getMode() === 'system') applyMode('system'); }; mq.addEventListener ? mq.addEventListener('change', on) : mq.addListener(on); }
    applyMode(getMode());
  }

  /* ---- Scroll progress bar (gold, top of viewport) ---- */
  function scrollProgress() {
    var bar = document.createElement('div');
    bar.className = 'scroll-progress'; bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    var ticking = false;
    function update() {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, h.scrollTop / max) : 0) + ')';
      ticking = false;
    }
    addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  /* ---- Back-to-top button ---- */
  function backToTop() {
    var b = document.createElement('button');
    b.className = 'to-top'; b.type = 'button'; b.setAttribute('aria-label', 'Back to top'); b.innerHTML = '↑';
    document.body.appendChild(b);
    b.addEventListener('click', function () { scrollTo({ top: 0, behavior: REDUCE ? 'auto' : 'smooth' }); });
    addEventListener('scroll', function () { b.classList.toggle('show', scrollY > 600); }, { passive: true });
  }

  /* ---- Animated starfield (dark mode only, not under reduced-motion) ---- */
  function starfield() {
    if (REDUCE) return;
    var cv = document.createElement('canvas');
    cv.className = 'starfield'; cv.setAttribute('aria-hidden', 'true');
    document.body.appendChild(cv);
    var ctx = cv.getContext('2d'), stars = [], shoot = null, W = 0, H = 0, dpr = Math.min(devicePixelRatio || 1, 2), raf = 0, on = false;
    // Theme palette: white twinkling stars by night; warm gold sun-motes that
    // gently rise by day — same engine, different mood.
    var PAL;
    function setPalette() {
      var dark = document.documentElement.classList.contains('dark');
      PAL = dark
        ? { color: '255,255,255', base: 0.40, amp: 0.45, vyMul: 0, rMul: 1,   shoot: '217,169,26' }
        : { color: '171,120,14',  base: 0.46, amp: 0.26, vyMul: 1, rMul: 1.5, shoot: '201,150,20' };
    }
    function resize() {
      W = innerWidth; H = innerHeight; cv.width = W * dpr; cv.height = H * dpr;
      cv.style.width = W + 'px'; cv.style.height = H + 'px'; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.min(170, Math.round(W * H / 9000));
      stars = []; for (var i = 0; i < n; i++) stars.push(mkStar());
    }
    function mkStar() {
      var depth = Math.random();
      return { x: Math.random() * W, y: Math.random() * H, r: 0.4 + depth * 1.3, vx: -(0.01 + depth * 0.03), vy: -(0.004 + depth * 0.012), tw: Math.random() * Math.PI * 2, ts: 0.005 + Math.random() * 0.015 };
    }
    function frame() {
      if (!on) return;
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i]; s.x += s.vx; s.y += s.vy * PAL.vyMul; s.tw += s.ts;
        if (s.x < -2) { s.x = W + 2; s.y = Math.random() * H; }
        if (s.y < -2) { s.y = H + 2; s.x = Math.random() * W; }
        var a = PAL.base + PAL.amp * Math.sin(s.tw);
        if (a <= 0.01) continue;
        ctx.globalAlpha = a; ctx.fillStyle = 'rgb(' + PAL.color + ')';
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r * PAL.rMul, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      // occasional shooting star
      if (!shoot && Math.random() < 0.0008) shoot = { x: Math.random() * W * 0.7, y: Math.random() * H * 0.4, len: 0, sp: 7 + Math.random() * 6, life: 1 };
      if (shoot) {
        shoot.x += shoot.sp; shoot.y += shoot.sp * 0.5; shoot.len = Math.min(160, shoot.len + shoot.sp); shoot.life -= 0.012;
        var g = ctx.createLinearGradient(shoot.x, shoot.y, shoot.x - shoot.len, shoot.y - shoot.len * 0.5);
        g.addColorStop(0, 'rgba(' + PAL.shoot + ',' + Math.max(0, shoot.life) + ')'); g.addColorStop(1, 'rgba(' + PAL.shoot + ',0)');
        ctx.strokeStyle = g; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(shoot.x, shoot.y); ctx.lineTo(shoot.x - shoot.len, shoot.y - shoot.len * 0.5); ctx.stroke();
        if (shoot.life <= 0 || shoot.x > W) shoot = null;
      }
      raf = requestAnimationFrame(frame);
    }
    function start() { if (on) return; on = true; raf = requestAnimationFrame(frame); }
    function stop() { on = false; cancelAnimationFrame(raf); ctx.clearRect(0, 0, W, H); }
    function sync() {
      setPalette();
      // canvas-stars only matters in dark (it hides the CSS tiled stars); the day
      // motes draw straight onto the paper backdrop. Run in BOTH themes.
      document.documentElement.classList.toggle('canvas-stars', document.documentElement.classList.contains('dark'));
      if (!document.hidden) start(); else stop();
    }
    var rt; addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { resize(); }, 200); }, { passive: true });
    addEventListener('themechange', sync);
    document.addEventListener('visibilitychange', sync);
    resize(); sync();
  }

  /* ---- Subtle 3D tilt on cards (fine pointers only, not reduced-motion) ---- */
  function cardTilt() {
    if (REDUCE || !FINE) return;
    document.querySelectorAll('main .card').forEach(function (card) {
      card.addEventListener('pointermove', function (e) {
        var r = card.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = 'perspective(800px) rotateY(' + (px * 5).toFixed(2) + 'deg) rotateX(' + (-py * 5).toFixed(2) + 'deg) translateY(-2px)';
      });
      card.addEventListener('pointerleave', function () { card.style.transform = ''; });
    });
  }

  /* ---- Lightbox: click any zoomable image/figure to view it large ---- */
  function lightbox() {
    var imgs = document.querySelectorAll('main figure img, main .prose img, img[data-zoom]');
    if (!imgs.length) return;
    var ov = document.createElement('div');
    ov.className = 'lightbox'; ov.setAttribute('aria-hidden', 'true');
    ov.innerHTML = '<button class="lightbox__close" aria-label="Close">✕</button><img alt="">';
    document.body.appendChild(ov);
    var big = ov.querySelector('img');
    function open(src, alt) { big.src = src; big.alt = alt || ''; ov.classList.add('open'); ov.setAttribute('aria-hidden', 'false'); }
    function close() { ov.classList.remove('open'); ov.setAttribute('aria-hidden', 'true'); big.src = ''; }
    imgs.forEach(function (im) {
      if (im.closest('a')) return; // don't hijack images that are already links
      im.classList.add('zoomable');
      im.addEventListener('click', function () { open(im.currentSrc || im.src, im.alt); });
    });
    ov.addEventListener('click', function (e) { if (e.target === ov || e.target.classList.contains('lightbox__close')) close(); });
    addEventListener('keydown', function (e) { if (e.key === 'Escape' && ov.classList.contains('open')) close(); });
  }

  /* ---- Reading time on prose-heavy pages ---- */
  function readingTime() {
    var prose = document.querySelector('main .prose');
    var h1 = document.querySelector('main h1');
    if (!prose || !h1) return;
    var words = (document.querySelector('main').innerText || '').trim().split(/\s+/).length;
    if (words < 220) return;
    var mins = Math.max(1, Math.round(words / 220));
    var tag = document.createElement('p');
    tag.className = 'reading-time'; tag.textContent = mins + ' min read';
    h1.insertAdjacentElement('afterend', tag);
  }

  /* ---- Command palette (⌘K / Ctrl-K): jump anywhere, toggle theme ---- */
  function buildCommandPalette() {
    var ITEMS = [
      { t: 'Home', u: '/', k: 'home start' },
      { t: 'Research', u: '/Research.html', k: 'papers ghosts punch' },
      { t: 'Publications', u: '/publications.html', k: 'papers thesis ads' },
      { t: 'Earlier research', u: '/PastResearch.html', k: 'student kelvin voyager' },
      { t: 'The Sun, right now', u: '/sun.html', k: 'solar live rhe images' },
      { t: 'Solar resources', u: '/resources.html', k: 'links directory' },
      { t: 'Outreach & talks', u: '/RecordedPublicTalks.html', k: 'video planetarium' },
      { t: 'Space Is Full (essay)', u: '/Space-Is-Full.html', k: 'asimov parker' },
      { t: 'Music & Theater', u: '/Music-and-Theater.html', k: 'songs plays' },
      { t: 'Play — the toys', u: '/play/', k: 'enso sudoku games' },
      { t: 'Ensō calendar', u: '/enso/', k: 'brushstroke daily' },
      { t: 'Ensō editor', u: '/enso/pixelated-enso.html', k: 'sliders' },
      { t: 'Spectrum Sudoku', u: '/sudoku/', k: 'puzzle color' },
      { t: 'Store — Solar Archive', u: '/shop.html', k: 'prints buy' },
      { t: 'About & CV', u: '/about.html', k: 'bio resume contact' },
      { t: 'Email Gilly', u: 'mailto:Gilly@NWRA.com', k: 'contact' },
      { t: 'Toggle theme', u: '#theme', k: 'dark light mode' }
    ];
    var pal = document.createElement('div');
    pal.className = 'cmdk'; pal.setAttribute('aria-hidden', 'true'); pal.setAttribute('role', 'dialog'); pal.setAttribute('aria-label', 'Command palette');
    pal.innerHTML = '<div class="cmdk__box"><input class="cmdk__input" type="text" placeholder="Jump to…  (try “sun”, “play”, “theme”)" aria-label="Search pages and actions" autocomplete="off"><ul class="cmdk__list" role="listbox"></ul><div class="cmdk__hint">↑↓ navigate · ↵ open · esc close</div></div>';
    document.body.appendChild(pal);
    var input = pal.querySelector('.cmdk__input'), list = pal.querySelector('.cmdk__list'), sel = 0, shown = [];
    function render(q) {
      q = (q || '').toLowerCase().trim();
      shown = ITEMS.filter(function (it) { return !q || (it.t + ' ' + it.k).toLowerCase().indexOf(q) >= 0; });
      list.innerHTML = shown.map(function (it, i) { return '<li role="option" class="' + (i === sel ? 'on' : '') + '" data-i="' + i + '">' + it.t + '</li>'; }).join('');
    }
    function open() { pal.classList.add('open'); pal.setAttribute('aria-hidden', 'false'); input.value = ''; sel = 0; render(''); setTimeout(function () { input.focus(); }, 30); }
    function close() { pal.classList.remove('open'); pal.setAttribute('aria-hidden', 'true'); }
    function go(it) {
      if (!it) return;
      if (it.u === '#theme') { close(); var tb = document.getElementById('themeToggle'); if (tb) tb.click(); return; }
      close(); location.href = it.u;
    }
    input.addEventListener('input', function () { sel = 0; render(input.value); });
    list.addEventListener('click', function (e) { var li = e.target.closest('li'); if (li) go(shown[+li.dataset.i]); });
    addEventListener('keydown', function (e) {
      var meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === 'k') { e.preventDefault(); pal.classList.contains('open') ? close() : open(); return; }
      if (e.key === '/' && !/^(input|textarea|select)$/i.test((document.activeElement || {}).tagName) && !pal.classList.contains('open')) { e.preventDefault(); open(); return; }
      if (!pal.classList.contains('open')) return;
      if (e.key === 'Escape') { close(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); render(input.value); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); render(input.value); }
      else if (e.key === 'Enter') { e.preventDefault(); go(shown[sel]); }
    });
    pal.addEventListener('click', function (e) { if (e.target === pal) close(); });
    // optional opener button in the nav tools, if present
    var opener = document.getElementById('cmdkOpen'); if (opener) opener.addEventListener('click', open);
  }

  /* ---- Konami code → a brief solar flare across the screen ---- */
  function konami() {
    var seq = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'], pos = 0;
    addEventListener('keydown', function (e) {
      pos = (e.key.toLowerCase() === seq[pos].toLowerCase()) ? pos + 1 : 0;
      if (pos === seq.length) { pos = 0; flare(); }
    });
    function flare() {
      var f = document.createElement('div'); f.className = 'solar-flare'; document.body.appendChild(f);
      setTimeout(function () { f.remove(); }, 1800);
    }
  }

  /* ---- Analytics: one shared source (assets/analytics.js) injected on every shell page ---- */
  function loadAnalytics() {
    if (document.getElementById('site-analytics')) return;
    var s = document.createElement('script');
    s.id = 'site-analytics'; s.defer = true; s.src = '/assets/analytics.js';
    document.head.appendChild(s);
  }

  /* ---- Service worker: offline cache + faster repeat visits ---- */
  function registerSW() {
    if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
      navigator.serviceWorker.register('/sw.js').catch(function () {});
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
