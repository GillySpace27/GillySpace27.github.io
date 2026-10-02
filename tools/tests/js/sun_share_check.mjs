// WS-16: SunData.share and shareUrl in assets/sun.js, with stub navigator and document objects.
// Usage: node tools/tests/js/sun_share_check.mjs <repo root>
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.argv[2] || ".";
const src = fs.readFileSync(path.join(root, "assets/sun.js"), "utf8");

function load(navigator, document) {
  const win = {};
  vm.runInNewContext(src, { window: win, navigator, document, location: { hostname: "gilly.space", search: "" }, URLSearchParams, fetch: () => Promise.reject(new Error("offline")), Date, Map, Promise, Math, isNaN, isFinite, parseInt, Number, Array, encodeURIComponent, decodeURIComponent, String, Set });
  return win.SunData;
}
const doc = (copyOk, log) => ({
  createElement: () => ({ style: {}, setAttribute() {}, select() {} }),
  body: { appendChild() { log.push("append"); }, removeChild() { log.push("remove"); } },
  execCommand: (c) => { log.push("exec " + c); return copyOk; },
});
const opts = { title: "The Sun: AIA 171", url: "https://gilly.space/s/171/" };

assert.equal(load({}, doc(true, [])).shareUrl("171"), "https://gilly.space/s/171/");
assert.equal(load({}, doc(true, [])).shareUrl("Composite_UV"), "https://gilly.space/s/composite_uv/", "always lowercase");

// 1. native sheet
let seen;
let S = load({ share: async (d) => { seen = d; } }, doc(true, []));
assert.equal(await S.share(opts), "shared");
assert.deepEqual(JSON.parse(JSON.stringify(seen)), { title: opts.title, url: opts.url });

// 2. canShare says no: use the clipboard
let copied;
S = load({ share: async () => { throw new Error("must not be called"); }, canShare: () => false, clipboard: { writeText: async (t) => { copied = t; } } }, doc(true, []));
assert.equal(await S.share(opts), "copied");
assert.equal(copied, opts.url);

// 3. the person closes the sheet: cancelled, and the clipboard is not touched
S = load({ share: async () => { const e = new Error("x"); e.name = "AbortError"; throw e; }, clipboard: { writeText: async () => { throw new Error("must not be called"); } } }, doc(true, []));
assert.equal(await S.share(opts), "cancelled");

// 4. share throws something else: fall back to the clipboard
copied = null;
S = load({ share: async () => { throw new Error("NotAllowedError"); }, clipboard: { writeText: async (t) => { copied = t; } } }, doc(true, []));
assert.equal(await S.share(opts), "copied");
assert.equal(copied, opts.url);

// 5. no share, clipboard refuses: the old execCommand route
let log = [];
S = load({ clipboard: { writeText: async () => { throw new Error("denied"); } } }, doc(true, log));
assert.equal(await S.share(opts), "copied");
assert.deepEqual(log, ["append", "exec copy", "remove"]);

// 6. nothing works: failed (the page then shows the link itself)
log = [];
S = load({}, doc(false, log));
assert.equal(await S.share(opts), "failed");
S = load({}, { createElement() { throw new Error("no dom"); } });
assert.equal(await S.share(opts), "failed");
console.log("sun share: ok");
