// WS-15: the pure Stage helpers in assets/sun.js (channel table, temperature order, slot clock,
// same-moment alignment). Usage: node tools/tests/js/sun_stage_check.mjs <repo root>
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const root = process.argv[2] || ".";
const src = fs.readFileSync(path.join(root, "assets/sun.js"), "utf8");
const win = {};
vm.runInNewContext(src, { window: win, location: { hostname: "gilly.space", search: "" }, URLSearchParams, fetch: () => Promise.reject(new Error("offline")), Date, Map, Promise, Math, isNaN, isFinite, parseInt, Number, Array, encodeURIComponent, decodeURIComponent, String, Set });
const S = win.SunData;
const same = (a, b, msg) => assert.equal(JSON.stringify(a), JSON.stringify(b), msg);

// Values copied from instruments/AIA.md section 4 (lines 65-73), pinned here so a silent edit fails.
const LOGT = { 94: [6.8], 131: [5.6, 7.0, 7.2], 171: [5.8], 193: [6.1, 7.3], 211: [6.3], 304: [4.7], 335: [6.4], 1600: [5.0], 1700: [3.7] };
for (const [id, t] of Object.entries(LOGT)) same(S.CHANNELS[id].logT, t, "logT of " + id);
for (const id of ["rainbow", "composite_uv", "dem"]) { same(S.CHANNELS[id].logT, [], id); assert.ok(S.CHANNELS[id].note, id + " says why it has no temperature"); }
same(S.CHANNEL_ORDER, ["1700", "304", "1600", "131", "171", "193", "211", "335", "94"], "cool to hot by first log T");
assert.equal(S.CHANNEL_ORDER.length, 9);
const products = ["rainbow", "171", "193", "211", "304", "335", "94", "131", "1600", "1700", "composite_uv", "dem"];
same(S.stageIds(products), ["1700", "304", "1600", "131", "171", "193", "211", "335", "94", "rainbow", "composite_uv", "dem"]);
same(S.stageIds(["171", "dem"]), ["171", "dem"], "only the ids the page has");
assert.equal(S.tempText("171"), "characteristic log T 5.8");
assert.equal(S.tempText("1600"), "characteristic log T 5.0");
assert.equal(S.tempText("131"), "characteristic log T 5.6, 7.0, 7.2 (multithermal)");
assert.match(S.tempText("dem"), /not one/);
assert.equal(S.tempText("nope"), "unknown");

// Slot clock: 20 minute grid ending at `through` (else `updated`).
const m = { updated: "2026-10-01T15:20:00Z" };
assert.equal(new Date(S.slotTime(m, 143).ms).toISOString(), "2026-10-01T15:20:00.000Z");
assert.equal(new Date(S.slotTime(m, 142).ms).toISOString(), "2026-10-01T15:00:00.000Z");
assert.equal(new Date(S.slotTime(m, 0).ms).toISOString(), "2026-09-29T15:40:00.000Z", "48 h minus one step");
assert.equal(S.slotTime(m, 5).exact, false);
assert.equal(new Date(S.slotTime({ updated: "2026-10-01T15:20:00Z", through: "2026-10-01T15:00:00Z" }, 143).ms).toISOString(), "2026-10-01T15:00:00.000Z", "through wins");
assert.ok(isNaN(S.slotTime({}, 3).ms), "no time at all is NaN, not a guess");
assert.ok(isNaN(S.slotTime(null, 3).ms));
const exact = { updated: "2026-10-01T15:20:00Z", times: Array.from({ length: 144 }, (_, i) => new Date(Date.parse("2026-09-29T15:40:00Z") + i * 1200000).toISOString()) };
assert.equal(S.slotTime(exact, 10).exact, true, "per-slot times, when the producer writes them, are exact");
assert.equal(S.slotTime(exact, 10).ms, Date.parse("2026-09-29T19:00:00Z"));
assert.equal(S.slotTime(m, 999).ms, S.slotTime(m, 143).ms, "slot clamps");
assert.equal(S.slotTime(m, -4).ms, S.slotTime(m, 0).ms);

// Same moment across channels whose newest frames differ.
const a = { updated: "2026-10-01T15:20:00Z" }, b = { updated: "2026-10-01T15:20:00Z" };
assert.equal(S.alignSlot(a, b, 72), 72, "equal clocks keep the slot");
const later = { updated: "2026-10-01T16:00:00Z" };            // newest frame two steps later
assert.equal(S.alignSlot(a, later, 72), 70, "a later clip shows the same moment two slots earlier");
assert.equal(S.alignSlot(later, a, 72), 74);
assert.equal(S.alignSlot(a, later, 143), 141);
assert.equal(S.alignSlot(later, a, 143), 143, "clamped at the end");
assert.equal(S.alignSlot({}, b, 72), 72, "unknown time: keep the slot");
assert.equal(S.alignSlot(a, null, 72), 72);
assert.equal(S.alignSlot(a, exact, 100), 100, "per-slot times of the target are used when present");
assert.equal(S.alignSlot(later, exact, 100), 102, "nearest exact slot: the target ends two steps earlier");
assert.equal(S.slotVideoTime(0), 0.5 / 18);
assert.equal(S.slotVideoTime(72), 72.5 / 18);
assert.equal(S.slotVideoTime(500), 143.5 / 18, "clamped");
assert.equal(typeof win.SunStage.init, "function");
for (const k of ["setChannel", "seek", "play", "pause", "walk", "state"]) assert.equal(typeof win.SunStage[k], "function", k);
console.log("sun stage: ok");
