// Determinism golden test for the ensō engine (enso/enso-engine.js).
// Run from the repo root:   node --test tools/tests/test_enso_golden.mjs
// Rewrite the golden file:  UPDATE_GOLDEN=1 node tools/tests/test_enso_golden.mjs
// Test another engine file: ENSO_ENGINE=/path/to/enso-engine.js node --test tools/tests/test_enso_golden.mjs
//
// The engine is an IIFE that hangs renderEnso on `window`. This test loads its text in a
// vm context with an empty `window`, inserting one line before the closing `})(window);`
// to expose dateToEnso, getParams and the module-level render target. The engine file
// itself is never modified. No DOM is needed: render() only calls a few 2D-context
// methods, which a recording stub captures and hashes.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const ENGINE = process.env.ENSO_ENGINE || path.join(ROOT, 'enso', 'enso-engine.js');
const GOLDEN = path.join(ROOT, 'enso', 'golden.json');
const RENDER_SIZE = 96;

const DATES = [];
for (let m = 0; m < 12; m++) DATES.push(new Date(Date.UTC(2026, m, 1)).toISOString().slice(0, 10));

function loadEngine(file) {
  let src = fs.readFileSync(file, 'utf8');
  const tail = '})(window);';
  const at = src.lastIndexOf(tail);
  if (at < 0) throw new Error('closing "' + tail + '" not found in ' + file);
  const hook = "global.__enso = { dateToEnso: dateToEnso, getParams: getParams, " +
    "setSettings: function (s) { _S = s; }, " +
    "setTarget: function (c, sd) { canvas = c; ctx = c.getContext('2d'); seed = sd; }, " +
    "render: render };\n";
  const win = {};
  vm.runInNewContext(src.slice(0, at) + hook + src.slice(at), { window: win }, { filename: file });
  if (!win.__enso || typeof win.renderEnso !== 'function' || typeof win.renderEnsoWith !== 'function') {
    throw new Error('engine did not expose renderEnso, renderEnsoWith and the test hook');
  }
  return win;
}

function fmt(v) {
  return typeof v === 'number' ? v.toFixed(5) : String(v);
}

function recordingCanvas() {
  const log = [];
  const store = {};
  const ctx = new Proxy(store, {
    get(t, k) {
      if (k in t) return t[k];
      return (...args) => { log.push(String(k) + '(' + args.map(fmt).join(',') + ')'); };
    },
    set(t, k, v) { log.push(String(k) + '=' + fmt(v)); t[k] = v; return true; },
  });
  return { log, canvas: { width: 0, height: 0, getContext: () => ctx } };
}

function measure(win, ms) {
  const e = win.__enso;
  const { settings, seed } = e.dateToEnso(ms);
  e.setSettings(settings);
  const params = JSON.parse(JSON.stringify(e.getParams(1)));
  const rec = recordingCanvas();
  win.renderEnso(rec.canvas, ms, RENDER_SIZE);
  const sha = crypto.createHash('sha256').update(rec.log.join('\n')).digest('hex');
  return { params, seed, render: { calls: rec.log.length, sha256: sha } };
}

function compute(file) {
  const win = loadEngine(file);
  const out = { schema: 1, dates: DATES, params: {}, seeds: {}, render: {} };
  for (const d of DATES) {
    const r = measure(win, Date.parse(d + 'T00:00:00Z'));
    out.params[d] = r.params;
    out.seeds[d] = r.seed;
    out.render[d] = r.render;
  }
  return out;
}

if (process.env.UPDATE_GOLDEN === '1') {
  fs.writeFileSync(GOLDEN, JSON.stringify(compute(ENGINE), null, 2) + '\n');
  console.log('wrote ' + GOLDEN);
} else {
  const golden = JSON.parse(fs.readFileSync(GOLDEN, 'utf8'));
  const got = compute(ENGINE);

  test('golden file has schema 1 and the 12 first-of-month dates of 2026', () => {
    assert.equal(golden.schema, 1);
    assert.deepEqual(golden.dates, DATES);
  });

  for (const d of DATES) {
    test('settings and shape seed for ' + d, () => {
      assert.deepEqual(got.params[d], golden.params[d]);
      assert.equal(got.seeds[d], golden.seeds[d]);
    });
    test('2D-context call sequence for ' + d, () => {
      assert.deepEqual(got.render[d], golden.render[d]);
    });
  }

  test('no parameter is NaN or missing (JSON turns NaN into null)', () => {
    for (const d of DATES) {
      for (const [k, v] of Object.entries(got.params[d])) {
        assert.notEqual(v, null, d + ': getParams().' + k + ' is null');
      }
    }
  });
}
