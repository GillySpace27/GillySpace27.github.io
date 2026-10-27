/* sun-compare.js: a before/after compare slider for the HelioSoftware pages (suite SU-20).

   <figure data-compare="halves" data-before="Standard display" data-after="RHEF">
     <img src="/assets/sw/rhef-compare.jpg" width="1320" height="660" alt="...">
     <figcaption>...</figcaption>
   </figure>

   data-compare="halves": one side-by-side image; its left half is "before", its right half "after".
   data-compare="" (or any other value) with two <img>: the first is "before", the second "after".
   The images stay in the page as the fallback: without this script, or when an image fails, the
   visitor sees them as written. With it, one stage shows "before" left of a divider and "after"
   right of it. The divider is a keyboard slider: Left and Right (or Down and Up) move it 5 percent,
   Page Up and Page Down 25, Home and End to either edge, Enter back to the middle. Nothing moves on
   its own, so there is no motion to switch off. No dependencies. In Node (the tests) it exports
   its helpers and does not touch the DOM. */
(function (root) {
  'use strict';

  function clamp(v) { return Math.max(0, Math.min(100, Math.round(v))); }

  // The divider position after a key, or null when the key is not ours.
  function keyValue(key, value) {
    switch (key) {
      case 'ArrowLeft': case 'ArrowDown': return clamp(value - 5);
      case 'ArrowRight': case 'ArrowUp': return clamp(value + 5);
      case 'PageDown': return clamp(value - 25);
      case 'PageUp': return clamp(value + 25);
      case 'Home': return 0;
      case 'End': return 100;
      case 'Enter': return 50;
      default: return null;
    }
  }

  function el(tag, cls, parent) {
    var n = document.createElement(tag);
    n.className = cls;
    if (parent) parent.appendChild(n);
    return n;
  }

  function build(fig) {
    var imgs = fig.querySelectorAll('img');
    var halves = fig.getAttribute('data-compare') === 'halves';
    if (!imgs.length || (!halves && imgs.length < 2)) return;
    var first = imgs[0];
    var before = fig.getAttribute('data-before') || 'Before';
    var after = fig.getAttribute('data-after') || 'After';
    var w = first.naturalWidth, h = first.naturalHeight;
    if (!w || !h) return;

    var stage = el('div', 'compare__stage');
    stage.style.aspectRatio = (halves ? w / 2 : w) + ' / ' + h;
    var a = el('div', 'compare__layer', stage);
    var b = el('div', 'compare__layer compare__layer--after', stage);
    a.style.backgroundImage = 'url("' + first.currentSrc + '")';
    b.style.backgroundImage = 'url("' + (halves ? first.currentSrc : imgs[1].currentSrc) + '")';
    if (halves) {
      a.style.backgroundSize = b.style.backgroundSize = '200% 100%';
      a.style.backgroundPosition = '0 0';
      b.style.backgroundPosition = '100% 0';
    }
    el('span', 'compare__label', stage).textContent = before;
    el('span', 'compare__label compare__label--after', stage).textContent = after;
    var handle = el('div', 'compare__handle', stage);
    handle.setAttribute('role', 'slider');
    handle.setAttribute('tabindex', '0');
    handle.setAttribute('aria-label', 'Compare ' + before + ' with ' + after + ': drag, or use the arrow keys');
    handle.setAttribute('aria-valuemin', '0');
    handle.setAttribute('aria-valuemax', '100');
    var value = 50;

    function set(v) {
      value = clamp(v);
      b.style.clipPath = 'inset(0 0 0 ' + value + '%)';
      handle.style.left = value + '%';
      handle.setAttribute('aria-valuenow', String(value));
      handle.setAttribute('aria-valuetext', value + ' percent ' + before + ', ' + (100 - value) + ' percent ' + after);
    }
    function fromPointer(e) {
      var r = stage.getBoundingClientRect();
      if (r.width) set((e.clientX - r.left) / r.width * 100);
    }
    stage.addEventListener('pointerdown', function (e) {
      fromPointer(e);
      if (stage.setPointerCapture) stage.setPointerCapture(e.pointerId);
      handle.focus({ preventScroll: true });
    });
    stage.addEventListener('pointermove', function (e) {
      if (stage.hasPointerCapture && stage.hasPointerCapture(e.pointerId)) fromPointer(e);
    });
    handle.addEventListener('keydown', function (e) {
      var v = keyValue(e.key, value);
      if (v === null) return;
      e.preventDefault();
      set(v);
    });
    set(50);

    Array.prototype.forEach.call(imgs, function (i) { i.hidden = true; });
    fig.insertBefore(stage, fig.firstChild);
    fig.classList.add('compare--live');
  }

  function init(fig) {
    var first = fig.querySelector('img');
    if (!first) return;
    if (first.complete && first.naturalWidth) build(fig);
    else first.addEventListener('load', function () { build(fig); }, { once: true });
  }

  var api = { clamp: clamp, keyValue: keyValue };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.SunCompare = api;
    var run = function () { Array.prototype.forEach.call(document.querySelectorAll('[data-compare]'), init); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
    else run();
  }
})(typeof window !== 'undefined' ? window : this);
