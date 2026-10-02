/* gilly.space: sun.js, the one shared loader for the Sun bucket (window.SunData).
   Plain script, no modules, no build. Loaded by sun.html before its inline script.
   The manifest fields it serves are pinned in contracts/sun-bucket.md. */
(function () {
  "use strict";

  const BUCKET = (location.hostname === "localhost" && new URLSearchParams(location.search).has("fixtures")) ? "/fixtures/sun/" : "https://the-sun-now.s3.us-east-2.amazonaws.com/";
  const u = (key, v) => BUCKET + key + (v ? "?v=" + encodeURIComponent(v) : "");
  const memo = new Map();

  // One request per id; repeat callers share it. A rejected promise is forgotten,
  // so the next call (a Retry) asks the network again.
  function loadManifest(id, { fresh = false } = {}) {
    if (!fresh && memo.has(id)) return memo.get(id);
    const p = fetch(u("manifest/" + id + ".json"), { cache: "no-store" }).then((r) => {
      if (!r.ok) throw new Error("manifest/" + id + ".json: HTTP " + r.status);
      return r.json();
    });
    memo.set(id, p);
    p.catch(() => { if (memo.get(id) === p) memo.delete(id); });
    return p;
  }

  function loadAll(ids) {
    return Promise.allSettled(ids.map((id) => loadManifest(id)));
  }

  // image_times.txt is one UTC time without a zone suffix, e.g. 2026-06-25T22:03:00.570
  function loadCaptureTime() {
    return fetch(u("image_times.txt"), { cache: "no-store" }).then((r) => {
      if (!r.ok) throw new Error("image_times.txt: HTTP " + r.status);
      return r.text();
    }).then((text) => {
      const raw = text.trim();
      const t = new Date(raw.endsWith("Z") ? raw : raw + "Z");
      if (isNaN(t.getTime())) throw new Error("image_times.txt: not a time");
      return t;
    });
  }

  // Thresholds in minutes, estimated from the 20-minute cadence and the 45-90 minute
  // GitHub cron throttling seen in 2026-06 (register WS-5 step 3). Gilly may tune them.
  const FRESH_OK_MIN = 60;
  const FRESH_STALE_MIN = 180;

  function freshness(updated, now = Date.now()) {
    if (typeof updated !== "string" || !updated) return "unknown";
    const zoned = /(Z|[+-]\d\d:?\d\d)$/i.test(updated) ? updated : updated + "Z";
    const t = Date.parse(zoned);
    if (isNaN(t)) return "unknown";
    const min = (now - t) / 60000;
    if (min < -5) return "unknown";     // a stamp from the future: say unknown, do not guess
    if (min <= FRESH_OK_MIN) return "ok";
    if (min <= FRESH_STALE_MIN) return "stale";
    return "old";
  }

  // Sunback production values: 18 fps timelapse, 144 slots = 48 h on a 20-minute grid.
  const FPS = 18;
  const SLOTS = 144;

  // "#stage=<id>@<slot>" -> {stage:{id, slot}}; "#<id>" -> {card:id}; anything else -> {}.
  // The caller checks the id against PRODUCTS.
  function parseHash(hash) {
    let h = String(hash || "").replace(/^#/, "");
    try { h = decodeURIComponent(h); } catch (e) { return {}; }
    let g = /^stage=([A-Za-z0-9_]+)@(\d+)$/.exec(h);
    if (g) return { stage: { id: g[1], slot: Math.min(SLOTS - 1, parseInt(g[2], 10)) } };
    g = /^([A-Za-z0-9_]+)$/.exec(h);
    return g ? { card: g[1] } : {};
  }

  window.SunData = {
    BUCKET, u, loadManifest, loadAll, loadCaptureTime, freshness,
    FRESH_OK_MIN, FRESH_STALE_MIN, FPS, SLOTS, parseHash,
  };
})();
