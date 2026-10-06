// WS-5 scratch check: load assets/sun.js in a stub window and exercise window.SunData.
// Usage: node tools/tests/js/sun_js_check.mjs <repo root>   (run by tools/tests/test_sun_js.py)
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.argv[2] || ".";
// Objects made inside the vm context have other prototypes: compare them as JSON.
const same = (a, b, msg) => assert.equal(JSON.stringify(a), JSON.stringify(b), msg);
const src = fs.readFileSync(path.join(root, "assets/sun.js"), "utf8");

function load(hostname, search, responses) {
  const calls = [];
  const fetch = (url, opts) => {
    calls.push({ url, opts });
    const r = responses(url, calls.length);
    return Promise.resolve({ ok: r.status === 200, status: r.status,
      json: async () => JSON.parse(r.body), text: async () => r.body });
  };
  const win = {};
  const ctx = { window: win, location: { hostname, search }, URLSearchParams, fetch, Date, Map, Promise, Math, isNaN, parseInt, encodeURIComponent, decodeURIComponent, String };
  vm.runInNewContext(src, ctx);
  return { S: win.SunData, calls };
}

const S3 = "https://the-sun-now.s3.us-east-2.amazonaws.com/";
let n171 = 0;
const { S, calls } = load("gilly.space", "?fixtures", (url) => {
  if (url.endsWith("manifest/171.json")) { n171++; return n171 === 1 ? { status: 503, body: "" } : { status: 200, body: '{"updated":"2026-10-01T15:00:00Z"}' }; }
  if (url.endsWith("image_times.txt")) return { status: 200, body: "2026-10-01T15:03:02.081\n" };
  return { status: 200, body: '{"updated":"2026-10-01T15:00:00Z","id":"' + url.split("/").pop().replace(".json", "") + '"}' };
});

assert.equal(S.BUCKET, S3, "fixtures must be ignored off localhost");
assert.equal(S.u("1k/x.png", "2026-10-01T15:00:00Z"), S3 + "1k/x.png?v=2026-10-01T15%3A00%3A00Z");
assert.equal(S.u("1k/x.png"), S3 + "1k/x.png");
assert.equal(load("localhost", "?fixtures", () => ({ status: 404, body: "" })).S.BUCKET, "/fixtures/sun/");
assert.equal(load("localhost", "", () => ({ status: 404, body: "" })).S.BUCKET, S3);

const res = await S.loadAll(["171", "193", "94"]);
same(res.map((r) => r.status), ["rejected", "fulfilled", "fulfilled"]);
assert.equal(res[2].value.id, "94", "loadAll keeps the order of ids");
assert.ok(calls.every((c) => c.opts && c.opts.cache === "no-store"), "every fetch uses cache: no-store");
assert.ok(calls.every((c) => !/[?&]v=\d{12,}/.test(c.url)), "no Date.now() cache-buster on manifests");
await S.loadManifest("193");
assert.equal(calls.filter((c) => c.url.endsWith("193.json")).length, 1, "manifest requests are memoized");
const retried = await S.loadManifest("171");                  // rejected promise was forgotten
assert.equal(retried.updated, "2026-10-01T15:00:00Z");
await S.loadManifest("193", { fresh: true });
assert.equal(calls.filter((c) => c.url.endsWith("193.json")).length, 2, "fresh: true refetches");

const t = await S.loadCaptureTime();
assert.equal(t.toISOString(), "2026-10-01T15:03:02.081Z", "Z appended to image_times.txt");

const now = Date.parse("2026-10-01T16:00:00Z");
assert.equal(S.freshness("2026-10-01T15:30:00Z", now), "ok");
assert.equal(S.freshness("2026-10-01T15:00:00Z", now), "ok");
assert.equal(S.freshness("2026-10-01T14:00:00Z", now), "stale");
assert.equal(S.freshness("2026-10-01T12:00:00Z", now), "old");
assert.equal(S.freshness("2026-10-01T15:30:00", now), "ok", "a time without a zone is read as UTC");
assert.equal(S.freshness("garbage", now), "unknown");
assert.equal(S.freshness(undefined, now), "unknown");
assert.equal(S.freshness("2026-10-02T16:00:00Z", now), "unknown");
assert.equal(S.FRESH_OK_MIN, 60); assert.equal(S.FRESH_STALE_MIN, 180);
assert.equal(S.FPS, 18); assert.equal(S.SLOTS, 144);

same(S.parseHash("#stage=171@37"), { stage: { id: "171", slot: 37 } });
same(S.parseHash("#stage=171@999"), { stage: { id: "171", slot: 143 } });
same(S.parseHash("#composite_uv"), { card: "composite_uv" });
same(S.parseHash("#about-sun"), {});
same(S.parseHash(""), {});
same(S.parseHash("#%E0%A4%A"), {});
console.log("sun.js: ok");
