// Tests for worker/worker.js (the enso-impressions Worker).
// Run from the repo root: node --test tools/tests/test_worker.mjs
// worker/ is never written: any push under worker/ redeploys the Worker through
// Workers Builds. The test copies worker.js to a temp .mjs, appends an export list
// for the helpers it finds (the deployed file keeps only `export default`), and
// imports the copy. AI and KV bindings are stubbed; nothing touches the network.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SRC = fs.readFileSync(path.join(REPO, "worker", "worker.js"), "utf8");
const HELPERS = ["corsHeadersFor", "jsonResponse", "validDate", "DATE_MIN", "DAILY_AI_LIMIT"]
  .filter((n) => new RegExp("^(?:function|const) " + n + "\\b", "m").test(SRC));
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "ws6-worker-"));
fs.writeFileSync(path.join(TMP, "worker.mjs"), SRC + "\nexport { " + HELPERS.join(", ") + " };\n");
const W = await import(pathToFileURL(path.join(TMP, "worker.mjs")).href);
const worker = W.default;
const CACHE_ON = /^const CACHE_ENABLED = true;$/m.test(SRC);

const BASE = "https://enso-impressions.example.workers.dev";
const DAY = 86400000;
const utcDay = (ms) => new Date(ms).toISOString().slice(0, 10);
const TODAY = utcDay(Date.now());
const YESTERDAY = utcDay(Date.now() - DAY);
const IMAGE = "data:image/png;base64,iVBORw0KGgo=";
const HEALTH = "enso-impressions worker is alive (Workers AI / Llama 4 Scout / one-line evocation)";

function makeEnv({ kv = {}, ai = async () => ({ response: "Amber light over a quiet harbor" }) } = {}) {
  const store = new Map(Object.entries(kv));
  const calls = { ai: 0 };
  return {
    store, calls,
    IMPRESSIONS: {
      get: async (k) => (store.has(k) ? store.get(k) : null),
      put: async (k, v) => { store.set(k, String(v)); },
    },
    AI: { run: async (...args) => { calls.ai++; return ai(...args); } },
  };
}

function post(body, origin = "https://gilly.space") {
  return new Request(BASE + "/", {
    method: "POST",
    headers: { Origin: origin, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function call(req, env) {
  const res = await worker.fetch(req, env);
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* a text body */ }
  return { res, text, json };
}

test("the helpers are top-level names beside the default handler", () => {
  assert.equal(typeof worker.fetch, "function");
  assert.equal(typeof W.corsHeadersFor, "function");
  assert.equal(typeof W.jsonResponse, "function");
  assert.equal(typeof W.validDate, "function");
});

test("validDate keeps the YYYY-MM-DD shape check", () => {
  assert.equal(W.validDate(YESTERDAY), true);
  for (const bad of ["", "2026-1-01", "20261001", "2026/10/01", "2026-10-01T00:00", "abcd-ef-gh"]) {
    assert.equal(W.validDate(bad), false, bad);
  }
});

test("a malformed date is a 400 JSON error and never reaches AI", async () => {
  const env = makeEnv();
  const { res, json } = await call(post({ date: "2026/10/01", image: IMAGE }), env);
  assert.equal(res.status, 400);
  assert.match(json.error, /invalid date/);
  assert.equal(env.calls.ai, 0);
});

test("an allowed origin is echoed; any other falls back to https://gilly.space", () => {
  assert.equal(W.corsHeadersFor("http://localhost:8000")["Access-Control-Allow-Origin"], "http://localhost:8000");
  assert.equal(W.corsHeadersFor("https://evil.example")["Access-Control-Allow-Origin"], "https://gilly.space");
});

test("OPTIONS preflight answers 200 with the CORS headers", async () => {
  const req = new Request(BASE + "/", { method: "OPTIONS", headers: { Origin: "https://gilly.space" } });
  const { res } = await call(req, makeEnv());
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Access-Control-Allow-Origin"), "https://gilly.space");
  assert.equal(res.headers.get("Access-Control-Allow-Methods"), "POST, OPTIONS");
});

test("a cache hit returns the stored impression without calling AI", { skip: !CACHE_ON && "CACHE_ENABLED is false" }, async () => {
  const env = makeEnv({ kv: { [`impression-v2:${YESTERDAY}`]: "Storm light on slate" } });
  const { res, json } = await call(post({ date: YESTERDAY, image: IMAGE }), env);
  assert.equal(res.status, 200);
  assert.deepEqual(json, { impression: "Storm light on slate", cached: true });
  assert.equal(env.calls.ai, 0);
});

test("a cache miss calls AI once, keeps the first line, stores it under impression-v2", async () => {
  const env = makeEnv({ ai: async () => ({ response: "Honey in sunlight\nand a second thought" }) });
  const { res, json } = await call(post({ date: YESTERDAY, image: IMAGE }), env);
  assert.equal(res.status, 200);
  assert.deepEqual(json, { impression: "Honey in sunlight", cached: false });
  assert.equal(env.calls.ai, 1);
  if (CACHE_ON) assert.equal(env.store.get(`impression-v2:${YESTERDAY}`), "Honey in sunlight");
});

test("an AI failure is a 502 JSON error", async () => {
  const env = makeEnv({ ai: async () => { throw new Error("4006: daily free allocation used"); } });
  const quiet = console.error; console.error = () => {};
  try {
    const { res, json } = await call(post({ date: YESTERDAY, image: IMAGE }), env);
    assert.equal(res.status, 502);
    assert.equal(json.error, "inference failed");
    assert.match(json.detail, /4006/);
  } finally { console.error = quiet; }
});

test("a GET other than /status keeps the health string byte-identical", async () => {
  const { res, text } = await call(new Request(BASE + "/"), makeEnv());
  assert.equal(res.status, 200);
  assert.equal(text, HEALTH);
});
// ---- WS-6 Task 2: dates bounded to [DATE_MIN, tomorrow UTC] ----
test("validDate bounds: DATE_MIN to tomorrow UTC, real calendar dates only", () => {
  const now = Date.parse("2026-10-01T12:00:00Z");
  assert.equal(W.DATE_MIN, "2020-01-01");
  assert.equal(W.validDate("2020-01-01", now), true);
  assert.equal(W.validDate("2026-10-02", now), true);   // tomorrow UTC
  assert.equal(W.validDate("2024-02-29", now), true);   // leap day
  assert.equal(W.validDate("2019-12-31", now), false);
  assert.equal(W.validDate("1900-01-01", now), false);
  assert.equal(W.validDate("2026-10-03", now), false);
  assert.equal(W.validDate("2999-01-01", now), false);
  assert.equal(W.validDate("2026-02-31", now), false);  // not a real date
});

test("a far-past or far-future date is a 400 and never reaches AI", async () => {
  for (const date of ["1900-01-01", utcDay(Date.now() + 3 * DAY)]) {
    const env = makeEnv();
    const { res, json } = await call(post({ date, image: IMAGE }), env);
    assert.equal(res.status, 400, date);
    assert.match(json.error, /invalid date/);
    assert.equal(env.calls.ai, 0, date);
  }
});
// ---- WS-6 Task 3: a daily ceiling on Workers AI calls ----
test("cache misses count in quota:<UTC day>; at DAILY_AI_LIMIT the Worker answers 429", async () => {
  assert.equal(W.DAILY_AI_LIMIT, 500);
  const env = makeEnv();
  await call(post({ date: YESTERDAY, image: IMAGE }), env);
  assert.equal(env.store.get(`quota:${TODAY}`), "1");
  const full = makeEnv({ kv: { [`quota:${TODAY}`]: String(W.DAILY_AI_LIMIT) } });
  const { res, json } = await call(post({ date: YESTERDAY, image: IMAGE }), full);
  assert.equal(res.status, 429);
  assert.equal(json.error, "daily limit");
  assert.match(json.detail, /daily.*allocation/);   // the calendar's quota banner regex
  assert.equal(full.calls.ai, 0);
  assert.equal(full.store.get(`quota:${TODAY}`), String(W.DAILY_AI_LIMIT));
});

test("a cache hit does not count against the quota", { skip: !CACHE_ON && "CACHE_ENABLED is false" }, async () => {
  const env = makeEnv({ kv: { [`impression-v2:${YESTERDAY}`]: "cached", [`quota:${TODAY}`]: "500" } });
  const { res } = await call(post({ date: YESTERDAY, image: IMAGE }), env);
  assert.equal(res.status, 200);
  assert.equal(env.store.get(`quota:${TODAY}`), "500");
});

test("a KV failure on the counter fails open: the ceiling is soft", async () => {
  const env = makeEnv();
  env.IMPRESSIONS.get = async (k) => { if (k.startsWith("quota:")) throw new Error("kv down"); return null; };
  const quiet = console.warn; console.warn = () => {};
  try {
    const { res } = await call(post({ date: YESTERDAY, image: IMAGE }), env);
    assert.equal(res.status, 200);
    assert.equal(env.calls.ai, 1);
  } finally { console.warn = quiet; }
});
