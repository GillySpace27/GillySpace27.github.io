// WS-13: the pure helpers in sun-wall.html (wallOptions, wallClockText, wallOrder) and the
// /wall/ builder's wallLink, extracted by their begin/end markers.
// Usage: node tools/tests/js/wall_kit_check.mjs <repo root>
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.argv[2] || ".";
const region = (file, name) => {
  const t = fs.readFileSync(path.join(root, file), "utf8");
  const m = new RegExp(`// ${name} begin\\n([\\s\\S]*?)// ${name} end`).exec(t);
  assert.ok(m, `${name} markers in ${file}`);
  return m[1];
};
const wall = { URLSearchParams, String };
vm.runInNewContext(region("sun-wall.html", "wallOptions") + "\nthis.o=wallOptions;this.c=wallClockText;this.r=wallOrder;this.s=wallStoreLink;", wall);
const link = { URLSearchParams, Math, String };
vm.runInNewContext(region("wall/index.html", "wallLink") + "\nthis.l=wallLink;", link);

// a bare link changes nothing
assert.deepEqual(JSON.parse(JSON.stringify(wall.o(""))), { clock: null, caption: "brief", dome: false, store: false, qr: false, attrib: null, ids: null });
// unknown values fall back to the default
const bad = wall.o("?clock=sundial&caption=loud&dome=yes&attrib=2&ids=,,");
assert.equal(bad.clock, null); assert.equal(bad.caption, "brief"); assert.equal(bad.dome, false); assert.equal(bad.attrib, null); assert.equal(bad.ids, null);
const o = wall.o("?clock=local&caption=stay&dome=1&attrib=0&ids=304, 171,304");
assert.equal(o.clock, "local"); assert.equal(o.caption, "stay"); assert.equal(o.dome, true); assert.equal(o.attrib, "0");
assert.deepEqual(Array.from(o.ids), ["304", "171", "304"]);

// clock text
const d = new Date(Date.UTC(2026, 9, 15, 3, 7, 59));
assert.equal(wall.c(d, "utc"), "03:07 UTC");
assert.match(wall.c(d, "local"), /^\d\d:\d\d$/);

// channel order follows ids; unknown and repeated ids drop out; none means everything
const fresh = [{ id: "171" }, { id: "193" }, { id: "304" }];
assert.equal(wall.r(fresh, null), fresh);
assert.deepEqual(Array.from(wall.r(fresh, ["304", "nope", "171", "304"]).map(m => m.id)), ["304", "171"]);
assert.equal(wall.r(fresh, ["nope"]).length, 0);

// builder links
const base = "https://gilly.space";
assert.equal(link.l({}, base), base + "/sun-wall.html?attrib=1");
assert.equal(link.l({ dome: true, clock: "utc", caption: "stay", attrib: false, ids: ["171", "304"], loops: "3", shuffle: true }, base),
  base + "/sun-wall.html?clock=utc&caption=stay&dome=1&attrib=0&ids=171,304&loops=3&shuffle=1");
assert.equal(link.l({ caption: "brief", loops: "0" }, base), base + "/sun-wall.html?attrib=1", "defaults stay out of the link");
// the builder's link round-trips through the wall's parser
const rt = wall.o("?" + link.l({ dome: true, clock: "local", caption: "0", attrib: true, ids: ["94"] }, base).split("?")[1]);
assert.equal(rt.dome, true); assert.equal(rt.clock, "local"); assert.equal(rt.caption, "0"); assert.equal(rt.attrib, "1"); assert.deepEqual(Array.from(rt.ids), ["94"]);
// SU-17: store=1 is opt-in and exact
assert.equal(wall.o("?store=1").store, true);
assert.equal(wall.o("?store=yes").store, false);
// SU-17 levels: store=1 is the text line; qr=1 is the text line plus the code; qr=0 and a bare link are neither
assert.equal(wall.o("?qr=1").qr, true); assert.equal(wall.o("?qr=1").store, true, "the code never stands without its text line");
assert.equal(wall.o("?qr=0").qr, false); assert.equal(wall.o("?qr=0").store, false);
assert.equal(wall.o("?store=1").qr, false); assert.equal(wall.o("?store=1").store, true);
assert.equal(wall.o("").qr, false);
assert.equal(link.l({ print: "text" }, base), base + "/sun-wall.html?store=1&attrib=1");
assert.equal(link.l({ print: "qr" }, base), base + "/sun-wall.html?qr=1&attrib=1");
assert.equal(link.l({ print: "" }, base), base + "/sun-wall.html?attrib=1");
// the wall's copy of the store link equals sun.js storeLink (utm_source wall)
const sunWin = {};
vm.runInNewContext(fs.readFileSync(path.join(root, "assets/sun.js"), "utf8"), { window: sunWin, location: { hostname: "gilly.space", search: "" }, URLSearchParams, fetch: () => Promise.reject(new Error("offline")), Date, Map, Promise, Math, isNaN, isFinite, parseInt, Number, Array, encodeURIComponent, decodeURIComponent, String, Set });
for (const [id, ms] of [["171", Date.UTC(2026, 8, 30, 14, 20)], ["rainbow", Date.UTC(2026, 0, 2, 3, 4)], ["94", NaN], ["dem", undefined]]) {
  assert.equal(wall.s(id, ms), sunWin.SunData.storeLink(id, ms, "wall"), id);
}
// matrix for the decode test: node tools/tests/js/wall_kit_check.mjs <root> --matrix <text>
console.log("wall kit: ok");

if (process.argv[3] === "--matrix") {
  const qsrc = fs.readFileSync(path.join(root, "assets/vendor/qrcode-generator/qrcode.js"), "utf8");
  const ctx = {}; vm.runInNewContext(qsrc + "\nthis.qrcode = qrcode;", ctx);
  const q = ctx.qrcode(0, "M"); q.addData(process.argv[4]); q.make();
  const n = q.getModuleCount(), rows = [];
  for (let r = 0; r < n; r++) { let line = ""; for (let c = 0; c < n; c++) line += q.isDark(r, c) ? "1" : "0"; rows.push(line); }
  console.log(JSON.stringify(rows));
}
