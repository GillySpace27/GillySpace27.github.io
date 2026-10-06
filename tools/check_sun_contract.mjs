// Consumer test for the imagery contract (suite SU-9): the Sun pages agree with the pinned fixture.
//   node tools/check_sun_contract.mjs [--fixtures DIR] [--root DIR]
// Checks: the fixture folder matches its SHA256SUMS; every id and label in sun.html PRODUCTS and every
// id in sun-wall.html IDS is in the fixture index; when assets/sun.js exists, its loadSunIndex and the
// copy in sun-wall.html are the same text and behave as specified against the fixture (one request when
// the index is usable, the per-product requests otherwise). Exit 1 when any check fails.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf(name); return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt; };
const root = path.resolve(opt("--root", path.join(here, "..")));
const fixtures = path.resolve(opt("--fixtures", path.join(root, "tools", "tests", "fixtures", "contract-v1")));

let checks = 0, failed = 0;
function check(ok, where, msg) {
  checks++;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"} ${where}: ${msg}`);
}
const readRel = (rel) => fs.readFileSync(path.join(root, rel), "utf8");
const exists = (rel) => fs.existsSync(path.join(root, rel));

// 1. The fixture folder is the pinned one.
let index = null;
try {
  const sums = fs.readFileSync(path.join(fixtures, "SHA256SUMS"), "utf8").split("\n").filter(Boolean);
  check(sums.length > 0, "SHA256SUMS", `${sums.length} entries`);
  for (const line of sums) {
    const m = /^([0-9a-f]{64})  (\S+)$/.exec(line);
    if (!m) { check(false, "SHA256SUMS", `bad line ${JSON.stringify(line)}`); continue; }
    let actual = null;
    try { actual = crypto.createHash("sha256").update(fs.readFileSync(path.join(fixtures, m[2]))).digest("hex"); } catch (e) { /* missing */ }
    check(actual === m[1], m[2], actual === null ? "missing" : actual === m[1] ? "matches SHA256SUMS" : "differs from SHA256SUMS");
  }
  index = JSON.parse(fs.readFileSync(path.join(fixtures, "index.json"), "utf8"));
} catch (e) {
  check(false, "fixture", `cannot read ${fixtures}: ${e.message}`);
}

if (index && Array.isArray(index.products)) {
  const byId = new Map(index.products.map((p) => [p.id, p]));

  // 2. sun.html PRODUCTS: ids and labels.
  const sun = readRel("sun.html");
  const block = /const PRODUCTS = \[([\s\S]*?)\n\s*\];/.exec(sun);
  check(!!block, "sun.html", "PRODUCTS literal found");
  if (block) {
    const pairs = [...block[1].matchAll(/\[\s*"([^"]+)"\s*,\s*"([^"]*)"\s*\]/g)].map((m) => [m[1], m[2]]);
    check(pairs.length > 0, "sun.html", `${pairs.length} products parsed`);
    for (const [id, label] of pairs) {
      const p = byId.get(id);
      check(!!p, `sun.html PRODUCTS ${id}`, p ? "is in the fixture index" : "is absent from the fixture index");
      if (p) check(p.label === label, `sun.html PRODUCTS ${id}`, p.label === label ? "label matches" : `label ${JSON.stringify(label)} differs from ${JSON.stringify(p.label)}`);
    }
  }

  // 3. sun-wall.html IDS.
  const wall = readRel("sun-wall.html");
  const ids = /const IDS = \[([\s\S]*?)\];/.exec(wall);
  check(!!ids, "sun-wall.html", "IDS literal found");
  if (ids) {
    for (const id of [...ids[1].matchAll(/"([^"]+)"/g)].map((m) => m[1])) {
      check(byId.has(id), `sun-wall.html IDS ${id}`, byId.has(id) ? "is in the fixture index" : "is absent from the fixture index");
    }
  }

  // 4. The loader: same text in both places, specified behaviour against the fixture.
  const fn = (text) => {
    const m = /\/\/ loadSunIndex begin\n([\s\S]*?)\/\/ loadSunIndex end/.exec(text);
    return m ? m[1].split("\n").map((l) => l.trim()).join("\n") : null;
  };
  const wallFn = fn(wall);
  check(!!wallFn, "sun-wall.html", "loadSunIndex markers found");
  check(wall.includes("loadSunIndex(BUCKET)"), "sun-wall.html", "refresh() calls loadSunIndex(BUCKET)");
  if (exists("assets/sun.js")) {
    const sunJs = readRel("assets/sun.js");
    const jsFn = fn(sunJs);
    check(!!jsFn, "assets/sun.js", "loadSunIndex markers found");
    check(jsFn !== null && jsFn === wallFn, "loadSunIndex", "the two copies are the same text");

    const generated = Date.parse(index.generated);
    const S3 = "https://the-sun-now.s3.us-east-2.amazonaws.com/";
    function load(respond) {
      const calls = [];
      const fetch = (url, opts) => {
        calls.push(url.replace(S3, ""));
        const r = respond(url.replace(S3, ""));
        return Promise.resolve({ ok: r.status === 200, status: r.status, json: async () => JSON.parse(r.body), text: async () => r.body });
      };
      class FakeDate extends Date {}
      FakeDate.now = () => generated + 60000;      // one minute after the fixture was captured
      const win = {};
      const ctx = { window: win, location: { hostname: "gilly.space", search: "" }, URLSearchParams, fetch, Date: FakeDate, Map, Promise, Math, isNaN, parseInt, encodeURIComponent, decodeURIComponent, String };
      vm.runInNewContext(sunJs, ctx);
      return { S: win.SunData, calls };
    }
    const fragmentBody = (id) => JSON.stringify(byId.get(id));
    const withIndex = (body, status = 200) => (key) => key === "manifest/index.json" ? { status, body }
      : key.startsWith("manifest/") ? { status: 200, body: fragmentBody(key.slice(9, -5)) } : { status: 404, body: "" };
    const allIds = index.products.map((p) => p.id);

    const a = load(withIndex(JSON.stringify(index)));
    const resA = await a.S.loadAll(allIds);
    check(resA.every((r) => r.status === "fulfilled") && resA.map((r) => r.value.id).join() === allIds.join(), "loader", "a usable index fills every product in order");
    check(a.calls.length === 1 && a.calls[0] === "manifest/index.json", "loader", `one request in all (${a.calls.join(", ")})`);
    const again = await a.S.loadManifest("171", { fresh: true });
    check(again.id === "171" && a.calls[a.calls.length - 1] === "manifest/171.json", "loader", "fresh: true bypasses the index");

    const b = load(withIndex("", 404));
    const resB = await b.S.loadAll(allIds);
    check(resB.every((r) => r.status === "fulfilled") && b.calls.length === allIds.length + 1, "loader", `a 404 index falls back to ${allIds.length} per-product requests (${b.calls.length} in all)`);

    for (const [name, body] of [["not JSON", "<html>"], ["no products", JSON.stringify({ generated: index.generated })], ["products not a list", JSON.stringify({ generated: index.generated, products: 3 })]]) {
      const c = load(withIndex(body));
      check((await c.S.loadSunIndex(S3, generated + 60000)) === null, "loadSunIndex", `${name} gives null`);
    }
    const stale = load(withIndex(JSON.stringify(index)));
    check((await stale.S.loadSunIndex(S3, generated + 7 * 3600 * 1000)) === null, "loadSunIndex", "an index over 6 hours old gives null");
    const fresh = load(withIndex(JSON.stringify(index)));
    const got = await fresh.S.loadSunIndex(S3, generated + 3600 * 1000);
    check(got !== null && got.generated === index.generated && got.products.length === allIds.length, "loadSunIndex", "a one-hour-old index is returned whole");

    const partial = JSON.stringify({ generated: index.generated, products: index.products.filter((p) => p.id !== "dem") });
    const d = load(withIndex(partial));
    const resD = await d.S.loadAll(allIds);
    check(resD.every((r) => r.status === "fulfilled") && d.calls.length === 2 && d.calls[1] === "manifest/dem.json", "loader", "a product the index lacks is fetched on its own");
  } else {
    console.log("SKIP assets/sun.js: not present (WS-5 has not landed)");
  }
}

console.log(`check_sun_contract: ${checks} checks, ${failed} failed`);
process.exit(failed ? 1 : 0);
