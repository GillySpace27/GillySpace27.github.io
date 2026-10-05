/* product.js: fills data-release elements from the family release feed (suite SU-11).

   <span data-release="heliofits-studio" data-release-field="version">0.8.3</span>
   <a data-release="heliofits-studio" data-release-asset="macos-arm64" href="...">Download</a>
   <p data-release="heliofits" hidden>Version <span data-release-field="version"></span></p>

   The feed is /heliosoftware/feed/<product>.json (records appended by the release scripts).
   data-release-field = version | date | notes | url   sets text, or href for url.
   data-release-asset = <platform>                      sets href to that asset, only when it is confirmed.
   Static text and links in the page are the fallback: they stay when the fetch fails or the feed has
   no record. A hidden element is revealed, up to the data-release element, once it is filled.
   No dependencies. In Node (the tests) it exports its helpers and does not touch the DOM. */
(function (root) {
  'use strict';

  var FEED = '/heliosoftware/feed/';

  function versionKey(v) {
    var m = /\d+(?:\.\d+)*/.exec(v || '');
    return m ? m[0].split('.').map(Number) : [];
  }

  function cmp(a, b) {
    var n = Math.max(a.length, b.length);
    for (var i = 0; i < n; i++) {
      var x = a[i] || 0;
      var y = b[i] || 0;
      if (x !== y) return x < y ? -1 : 1;
    }
    return 0;
  }

  // Highest version; the later record wins a tie (a new build of the same version).
  function newest(feed) {
    var records = (feed && feed.records) || [];
    var best = null;
    for (var i = 0; i < records.length; i++) {
      if (!best || cmp(versionKey(records[i].version), versionKey(best.version)) >= 0) best = records[i];
    }
    return best;
  }

  // A platform's asset, only when a person has confirmed that build on real hardware.
  function assetFor(record, platform) {
    var list = (record && record.assets) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].platform === platform && list[i].confirmed === true) return list[i];
    }
    return null;
  }

  function reveal(el, stopAt) {
    for (var n = el; n; n = n.parentElement) {
      n.hidden = false;
      if (n === stopAt) break;
    }
  }

  function within(el, name) {
    var found = Array.prototype.slice.call(el.querySelectorAll('[' + name + ']'));
    return el.hasAttribute(name) ? [el].concat(found) : found;
  }

  function fill(el, record) {
    within(el, 'data-release-field').forEach(function (f) {
      var key = f.getAttribute('data-release-field');
      var value = record[key];
      if (value === undefined || value === null || value === '') return;
      if (key === 'url') f.setAttribute('href', value);
      else f.textContent = String(value);
      reveal(f, el);
    });
    within(el, 'data-release-asset').forEach(function (a) {
      var asset = assetFor(record, a.getAttribute('data-release-asset'));
      if (!asset) return;
      a.setAttribute('href', asset.url);
      ['aria-disabled', 'role', 'title'].forEach(function (k) { a.removeAttribute(k); });
      reveal(a, el);
    });
  }

  function run() {
    var nodes = document.querySelectorAll('[data-release]');
    if (!nodes.length || typeof fetch !== 'function') return;
    var cache = {};
    function feed(product) {
      if (!cache[product]) {
        cache[product] = fetch(FEED + encodeURIComponent(product) + '.json')
          .then(function (r) { return r.ok ? r.json() : null; })
          .catch(function () { return null; });
      }
      return cache[product];
    }
    Array.prototype.forEach.call(nodes, function (el) {
      feed(el.getAttribute('data-release')).then(function (f) {
        var rec = newest(f);
        if (!rec) return;
        try { fill(el, rec); } catch (e) { /* the static text stays */ }
      });
    });
  }

  var api = { versionKey: versionKey, cmp: cmp, newest: newest, assetFor: assetFor, fill: fill };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.HSRelease = api;
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
    else run();
  }
})(typeof window !== 'undefined' ? window : this);
