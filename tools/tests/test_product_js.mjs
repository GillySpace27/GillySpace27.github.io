// Tests for assets/product.js (suite SU-11). Run: node --test tools/tests/test_product_js.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const P = require('../../assets/product.js');

// Just enough DOM for fill(): attributes, children, parent, text, hidden.
class El {
  constructor(attrs = {}, kids = []) {
    this.attrs = { ...attrs };
    this.kids = kids;
    this.textContent = '';
    this.hidden = false;
    this.parentElement = null;
    kids.forEach((k) => { k.parentElement = this; });
  }
  hasAttribute(n) { return n in this.attrs; }
  getAttribute(n) { return n in this.attrs ? this.attrs[n] : null; }
  setAttribute(n, v) { this.attrs[n] = v; }
  removeAttribute(n) { delete this.attrs[n]; }
  querySelectorAll(sel) {
    const name = sel.slice(1, -1);
    const out = [];
    const walk = (e) => e.kids.forEach((k) => { if (k.hasAttribute(name)) out.push(k); walk(k); });
    walk(this);
    return out;
  }
}

const REC = {
  version: '0.8.3', date: '2026-09-24', url: 'https://github.com/o/r/releases/tag/v0.8.3', notes: 'Things.',
  assets: [
    { platform: 'macos-arm64', url: 'https://example.test/mac.dmg', confirmed: true },
    { platform: 'windows', url: 'https://example.test/win.zip', confirmed: false },
  ],
};

test('newest takes the highest version and the later record wins a tie', () => {
  const feed = { records: [{ version: '0.8.3', n: 1 }, { version: '0.10.0', n: 2 }, { version: '0.10.0', n: 3 }, { version: '0.9.9', n: 4 }] };
  assert.equal(P.newest(feed).n, 3);
  assert.equal(P.newest({ records: [] }), null);
  assert.equal(P.newest(null), null);
});

test('assetFor links only a confirmed asset', () => {
  assert.equal(P.assetFor(REC, 'macos-arm64').url, 'https://example.test/mac.dmg');
  assert.equal(P.assetFor(REC, 'windows'), null);
  assert.equal(P.assetFor(REC, 'linux'), null);
});

test('fill sets text and href and reveals a hidden chip up to the product element', () => {
  const field = new El({ 'data-release-field': 'version' });
  const link = new El({ 'data-release-field': 'url', href: 'fallback' });
  const chip = new El({ 'data-release': 'x' }, [field, link]);
  chip.hidden = true;
  const outer = new El({}, [chip]);
  outer.hidden = true;                      // above the product element: must stay hidden
  field.textContent = 'old';
  P.fill(chip, REC);
  assert.equal(field.textContent, '0.8.3');
  assert.equal(link.getAttribute('href'), REC.url);
  assert.equal(chip.hidden, false);
  assert.equal(outer.hidden, true);
});

test('fill links a confirmed asset, removes the disabled marks, and skips an unconfirmed one', () => {
  const mac = new El({ 'data-release-asset': 'macos-arm64', 'aria-disabled': 'true', role: 'link', title: 'x' });
  const win = new El({ 'data-release-asset': 'windows', 'aria-disabled': 'true' });
  const root = new El({ 'data-release': 'x' }, [mac, win]);
  P.fill(root, REC);
  assert.equal(mac.getAttribute('href'), 'https://example.test/mac.dmg');
  assert.equal(mac.hasAttribute('aria-disabled'), false);
  assert.equal(mac.hasAttribute('role'), false);
  assert.equal(win.hasAttribute('href'), false);
  assert.equal(win.hasAttribute('aria-disabled'), true);
});

test('an element that is its own product root works, and a missing field leaves the static text', () => {
  const a = new El({ 'data-release': 'x', 'data-release-asset': 'macos-arm64', href: 'static' });
  P.fill(a, REC);
  assert.equal(a.getAttribute('href'), 'https://example.test/mac.dmg');
  const f = new El({ 'data-release': 'x', 'data-release-field': 'nope' });
  f.textContent = 'static';
  P.fill(f, REC);
  assert.equal(f.textContent, 'static');
});
