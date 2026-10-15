// RH-14: the RHEF Lab kernel (rhef/lab/index.html, <script id="rhef-kernel">) against the public
// conformance vectors (heliosoftware/spec/rhef/golden, convention sunkit-0.7), plus the FITS
// reader, the PNG tEXt writer and the stamp line. Only public expected values are read: the
// oRHEF 2.0 expectations stay withheld (suite Q18), so the lab's own Upsilon split at 0.5 is
// exercised by unit cases here, and its parity run uses the kernel's sunkit-0.7 mode.
// Run: node --test tools/tests/test_rhef_lab.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const LAB = path.join(ROOT, 'rhef', 'lab', 'index.html');
const GOLDEN = path.join(ROOT, 'heliosoftware', 'spec', 'rhef', 'golden');

function loadKernel() {
  const html = fs.readFileSync(LAB, 'utf8');
  const m = html.match(/<script id="rhef-kernel">([\s\S]*?)<\/script>/);
  assert.ok(m, 'no <script id="rhef-kernel"> in rhef/lab/index.html');
  const module = { exports: {} };
  vm.runInNewContext(m[1], { module, Math, Float64Array, Int32Array, Uint8Array, Uint32Array,
    DataView, ArrayBuffer, TextDecoder, TextEncoder, Number, Error, isNaN, Object, Array, String });
  return module.exports;
}
const K = loadKernel();

function props(dir) {
  const out = {};
  for (const line of fs.readFileSync(path.join(dir, 'case.properties'), 'utf8').split('\n')) {
    const t = line.trim();
    if (!t || t[0] === '#') continue;
    const i = t.indexOf('=');
    out[t.slice(0, i)] = t.slice(i + 1);
  }
  return out;
}
const f64 = (p) => { const b = fs.readFileSync(p); return new Float64Array(b.buffer, b.byteOffset, b.length / 8).slice(); };
const i32 = (p) => { const b = fs.readFileSync(p); return new Int32Array(b.buffer, b.byteOffset, b.length / 4).slice(); };

const cases = fs.readdirSync(GOLDEN).filter((d) => fs.existsSync(path.join(GOLDEN, d, 'case.properties'))).sort();

test('the public bundle has cases and withholds the oRHEF 2.0 expectations', () => {
  assert.ok(cases.length >= 4);
  for (const c of cases) {
    for (const f of fs.readdirSync(path.join(GOLDEN, c))) assert.ok(!f.includes('oRHEF'), f);
  }
});

for (const c of cases) {
  test(`parity with sunkit-0.7 on ${c}`, () => {
    const dir = path.join(GOLDEN, c);
    const p = props(dir);
    const input = f64(path.join(dir, 'input.f64'));
    const bins = i32(path.join(dir, 'bin_index.i32'));
    const want = f64(path.join(dir, 'expected_sunkit-0.7.f64'));
    const nbins = parseInt(p.nbins, 10);
    const ranks = K.rhefRanksFromBins(input, bins, nbins);
    let got = ranks;
    if (p.upsilon !== 'none') {
      const [lo, hi] = p.upsilon.split(',').map(Number);
      got = K.upsilonImage(ranks, bins, nbins, lo, hi, 'sunkit-0.7');
    }
    // Two allowances, both from conventions.md section 6: a pixel whose rank equals its bin's mean
    // rank to within rounding sits on the sunkit split and is counted apart (the branch there
    // depends on how the library sums the mean), and Math.pow may differ from numpy's power by
    // a few units in the last place (2^-50 here, about 8.9e-16).
    const tol = Math.max(Number(p.tol_f64) || 0, 2 ** -50);
    const mean = new Float64Array(nbins), cnt = new Float64Array(nbins);
    for (let i = 0; i < ranks.length; i++) if (bins[i] >= 0 && ranks[i] === ranks[i]) { mean[bins[i]] += ranks[i]; cnt[bins[i]]++; }
    for (let b = 0; b < nbins; b++) mean[b] /= cnt[b];
    let maxDiff = 0, compared = 0, onSplit = 0;
    for (let i = 0; i < want.length; i++) {
      if (bins[i] < 0) continue;
      if (p.upsilon !== 'none' && Math.abs(ranks[i] - mean[bins[i]]) <= 1e-12) { onSplit++; continue; }
      const a = want[i], b = got[i];
      if (Number.isNaN(a) && Number.isNaN(b)) continue;
      compared++;
      maxDiff = Math.max(maxDiff, Math.abs(a - b));
    }
    assert.ok(compared > 0);
    console.log(`RHEF-CONFORMANCE impl=rhef-lab-js case=${c} convention=sunkit-0.7 max_abs_diff=${maxDiff.toExponential(3)} on_split=${onSplit}`);
    assert.ok(maxDiff <= tol, `max |diff| ${maxDiff} > tol ${tol}`);
  });
}

test('the lab convention: Upsilon splits at 0.5 and keeps NaN', () => {
  assert.equal(K.applyUpsilon(0.25, 1, 1), 0.25);
  assert.equal(K.applyUpsilon(0.5, 0.35, 0.35), 0.5);
  assert.equal(K.applyUpsilon(0.25, 2, 2), 0.125);          // (2 * 0.25)^2 / 2
  assert.equal(K.applyUpsilon(0.75, 2, 2), 0.875);          // 1 - (2 - 1.5)^2 / 2
  assert.ok(Number.isNaN(K.applyUpsilon(NaN, 0.35, 0.35)));
  const ranks = new Float64Array([0.25, NaN, 1]);
  const out = K.upsilonImage(ranks, new Int32Array([0, 0, 0]), 1, 2, 2, 'oRHEF-2.0');
  assert.equal(out[0], 0.125);
  assert.ok(Number.isNaN(out[1]));
  assert.equal(out[2], 1);
});

test('ranks: ties share their average rank, NaN and no-bin pixels stay NaN', () => {
  const v = new Float64Array([5, 1, 5, NaN, 3]);
  const b = new Int32Array([0, 0, 0, 0, -1]);
  const r = K.rhefRanksFromBins(v, b, 1);
  assert.deepEqual(Array.from(r.slice(0, 3)), [2.5 / 3, 1 / 3, 2.5 / 3]);
  assert.ok(Number.isNaN(r[3]) && Number.isNaN(r[4]));
});

test('geometry: radii from a helioprojective header match the public geometry case', () => {
  const dir = path.join(GOLDEN, 'geometry_hpc_32');
  const header = JSON.parse(fs.readFileSync(path.join(dir, 'header.json'), 'utf8'));
  const want = f64(path.join(dir, 'expected_radii.f64'));
  const g = K.geometry(header, header.NAXIS1, header.NAXIS2);
  assert.equal(g.unit, 'R_sun');
  const r = K.radiiFor(header.NAXIS1, header.NAXIS2, g);
  let maxRel = 0;
  for (let i = 0; i < want.length; i++) maxRel = Math.max(maxRel, Math.abs(r[i] - want[i]) / want[i]);
  console.log(`geometry_hpc_32 max relative radius difference ${maxRel.toExponential(3)} (flat-sky approximation)`);
  assert.ok(maxRel < 1e-3, `max relative difference ${maxRel}`);
});

test('geometry: no solar radius in the header is said, not guessed', () => {
  const g = K.geometry({ NAXIS1: 10, NAXIS2: 10 }, 10, 10);
  assert.equal(g.unit, 'unknown');
  assert.match(g.note, /unknown/);
});

function card(k, v) { return (k.padEnd(8) + '= ' + String(v).padStart(20)).padEnd(80); }
function fitsFile(cards, bytes) {
  const h = cards.concat(['END'.padEnd(80)]).join('');
  const hlen = Math.ceil(h.length / 2880) * 2880;
  const dlen = Math.ceil(bytes.length / 2880) * 2880;
  const out = new Uint8Array(hlen + dlen);
  out.set(new TextEncoder().encode(h.padEnd(hlen)), 0);
  out.set(bytes, hlen);
  return out.buffer;
}

test('FITS: BITPIX 16 with BZERO, big-endian, first plane of the primary HDU', () => {
  const raw = new Uint8Array(2 * 3 * 2);
  const dv = new DataView(raw.buffer);
  [-32768, 0, 1, 2, 3, 32767].forEach((v, i) => dv.setInt16(2 * i, v, false));
  const buf = fitsFile([card('SIMPLE', 'T'), card('BITPIX', 16), card('NAXIS', 2), card('NAXIS1', 3),
    card('NAXIS2', 2), card('BZERO', 32768), card('BSCALE', 1)], raw);
  const f = K.parseFits(buf);
  assert.equal(f.width, 3);
  assert.equal(f.height, 2);
  assert.deepEqual(Array.from(f.data), [0, 32768, 32769, 32770, 32771, 65535]);
});

test('FITS: BITPIX -32 in an IMAGE extension after an empty primary', () => {
  const raw = new Uint8Array(4 * 4);
  const dv = new DataView(raw.buffer);
  [1.5, -2, NaN, 4].forEach((v, i) => dv.setFloat32(4 * i, v, false));
  const prim = fitsFile([card('SIMPLE', 'T'), card('BITPIX', 8), card('NAXIS', 0)], new Uint8Array(0));
  const ext = fitsFile([card('XTENSION', "'IMAGE   '"), card('BITPIX', -32), card('NAXIS', 2), card('NAXIS1', 2),
    card('NAXIS2', 2), card('RSUN_OBS', 960)], raw);
  const buf = new Uint8Array(prim.byteLength + ext.byteLength);
  buf.set(new Uint8Array(prim), 0);
  buf.set(new Uint8Array(ext), prim.byteLength);
  const f = K.parseFits(buf.buffer);
  assert.equal(f.hdu, 1);
  assert.equal(f.header.RSUN_OBS, 960);
  assert.deepEqual(Array.from(f.data).map(String), ['1.5', '-2', 'NaN', '4']);
});

test('FITS: a tile-compressed (RICE_1) image is refused with a plain message', () => {
  const prim = fitsFile([card('SIMPLE', 'T'), card('BITPIX', 8), card('NAXIS', 0)], new Uint8Array(0));
  const ext = fitsFile([card('XTENSION', "'BINTABLE'"), card('BITPIX', 8), card('NAXIS', 2), card('NAXIS1', 8),
    card('NAXIS2', 1), card('ZIMAGE', 'T'), card('ZCMPTYPE', "'RICE_1  '")], new Uint8Array(8));
  const buf = new Uint8Array(prim.byteLength + ext.byteLength);
  buf.set(new Uint8Array(prim), 0);
  buf.set(new Uint8Array(ext), prim.byteLength);
  assert.throws(() => K.parseFits(buf.buffer), /uncompressed FITS/);
});

test('PNG: tEXt chunk inserted before IEND with a valid CRC', () => {
  // smallest valid PNG: 1x1 grey
  const sig = [137, 80, 78, 71, 13, 10, 26, 10];
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'latin1'), Buffer.from(data)]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.from([0, 0, 0, 1, 0, 0, 0, 1, 8, 0, 0, 0, 0]);
  const png = Buffer.concat([Buffer.from(sig), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(Buffer.from([0, 128]))), chunk('IEND', Buffer.alloc(0))]);
  const out = Buffer.from(K.pngAddText(new Uint8Array(png), 'RHEF', 'RHEF oRHEF-2.0 via rhef-lab-js 1.0.0; upsilon=0.35,0.35; deviations=none'));
  let off = 8; const seen = [];
  while (off < out.length) {
    const n = out.readUInt32BE(off); const type = out.toString('latin1', off + 4, off + 8);
    const crc = out.readUInt32BE(off + 8 + n);
    assert.equal(crc, zlib.crc32(out.subarray(off + 4, off + 8 + n)), `${type} CRC`);
    seen.push(type);
    if (type === 'tEXt') assert.equal(out.toString('latin1', off + 8, off + 8 + n), 'RHEF\0RHEF oRHEF-2.0 via rhef-lab-js 1.0.0; upsilon=0.35,0.35; deviations=none');
    off += 12 + n;
  }
  assert.deepEqual(seen, ['IHDR', 'IDAT', 'tEXt', 'IEND']);
});

test('stamp line follows conventions.md section 5', () => {
  const re = /^RHEF (\S+) via (\S+) (\S+); upsilon=(none|[0-9.eE+-]+,[0-9.eE+-]+); deviations=(none|[A-Z0-9-]+(?:,[A-Z0-9-]+)*)(; ref=doi:\S+)?$/;
  const a = K.formatStamp('oRHEF-2.0', 'rhef-lab-js', K.VERSION, [0.35, 0.5], []);
  assert.match(a, re);
  assert.equal(a, `RHEF oRHEF-2.0 via rhef-lab-js ${K.VERSION}; upsilon=0.35,0.5; deviations=none`);
  assert.match(K.formatStamp('oRHEF-2.0', 'rhef-lab-js', K.VERSION, null, ['GEOM-GRID']), /upsilon=none; deviations=GEOM-GRID$/);
});

test('downsample halves each side and averages finite values', () => {
  const d = K.downsample2(new Float64Array([1, 3, 5, 7, NaN, 2, 9, 9]), 4, 2);
  assert.equal(d.width, 2); assert.equal(d.height, 1);
  assert.deepEqual(Array.from(d.data), [2, 7.5]);
});
