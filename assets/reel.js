/* reel.js: left and right arrows that turn between the software pages. Loaded in <head>, without
   defer, so the pagereveal listener is in place before the new page first renders.
   The order here is the order of the cards on /heliosoftware/. No dependencies. */
(function () {
  'use strict';
  var PAGES = [
    ['/heliogram/', 'Heliogram'],
    ['/heliofits/', 'HelioFITS Peek'],
    ['/heliofits-studio/', 'HelioFITS Studio'],
    ['/rhef/', 'RHEF']
  ];
  var here = location.pathname.replace(/index\.html$/, '');
  var i = PAGES.findIndex(function (p) { return p[0] === here; });
  if (i < 0) return;
  var KEY = 'reel-dir';
  var root = document.documentElement;

  function turn(dir) {
    root.classList.remove('reel-next', 'reel-prev');
    if (dir === 'next' || dir === 'prev') root.classList.add('reel-' + dir);
  }
  function remember(dir) { try { sessionStorage.setItem(KEY, dir); } catch (e) {} }

  // The arriving page learns which way the visitor turned.
  addEventListener('pagereveal', function (e) {
    var dir = null;
    try { dir = sessionStorage.getItem(KEY); sessionStorage.removeItem(KEY); } catch (err) {}
    turn(e.viewTransition ? dir : null);
    if (e.viewTransition) e.viewTransition.finished.finally(function () { turn(null); });
  });

  document.addEventListener('DOMContentLoaded', function () {
    var nav = document.createElement('nav');
    nav.setAttribute('aria-label', 'Previous and next software');
    var links = {};
    [['prev', -1, '‹', 'Previous'], ['next', 1, '›', 'Next']].forEach(function (d) {
      var page = PAGES[(i + d[1] + PAGES.length) % PAGES.length];
      var a = document.createElement('a');
      a.className = 'reel__arrow reel__arrow--' + d[0];
      a.href = page[0];
      a.rel = d[0];
      a.title = d[3] + ': ' + page[1];
      a.setAttribute('aria-label', a.title);
      a.setAttribute('data-no-blank', '');
      a.textContent = d[2];
      a.addEventListener('click', function () { remember(d[0]); turn(d[0]); });
      nav.appendChild(a);
      links[d[0]] = a;
    });
    (document.querySelector('main.product') || document.body).appendChild(nav);
    // Arrow keys turn the reel only when nothing else has the focus, so sliders, tabs and
    // code blocks keep their own arrow keys.
    document.addEventListener('keydown', function (e) {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if (document.activeElement && document.activeElement !== document.body) return;
      if (e.key === 'ArrowLeft') links.prev.click();
      if (e.key === 'ArrowRight') links.next.click();
    });
  });
})();
