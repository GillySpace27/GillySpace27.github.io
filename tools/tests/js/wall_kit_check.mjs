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
vm.runInNewContext(region("sun-wall.html", "wallOptions") + "\nthis.o=wallOptions;this.c=wallClockText;this.r=wallOrder;", wall);
const link = { URLSearchParams, Math, String };
vm.runInNewContext(region("wall/index.html", "wallLink") + "\nthis.l=wallLink;", link);

// a bare link changes nothing
assert.deepEqual(JSON.parse(JSON.stringify(wall.o(""))), { clock: null, caption: "brief", dome: false, attrib: null, ids: null });
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
console.log("wall kit: ok");
