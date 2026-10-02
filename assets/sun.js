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

  // ---- Stage data: channel metadata, slot clock, id order (WS-15) -------------------------
  // Characteristic log T per AIA channel is copied from instruments/AIA.md section 4, table
  // "Channels" (lines 65-73 of that vault file), which cites the LMSAL AIA instrument page,
  // Table A1 (https://aia.lmsal.com/public/instrument.htm, retrieved 2026-08-19). Where a
  // channel lists several values it is multithermal and every value is kept. The WS-15 task
  // file carried a different table (131: 5.5, 7.1; 193: 7.2; 1600: 3.7); it disagreed with the
  // vault file, so the vault file wins. The three composite products have no single
  // temperature and say so rather than guess.
  const CHANNELS = {
    "94":   { instrument: "SDO/AIA", wavelength: "94 Å",   ions: "Fe XVIII",           logT: [6.8],          src: "instruments/AIA.md:65" },
    "131":  { instrument: "SDO/AIA", wavelength: "131 Å",  ions: "Fe VIII, XX, XXIII", logT: [5.6, 7.0, 7.2], src: "instruments/AIA.md:66" },
    "171":  { instrument: "SDO/AIA", wavelength: "171 Å",  ions: "Fe IX",              logT: [5.8],          src: "instruments/AIA.md:67" },
    "193":  { instrument: "SDO/AIA", wavelength: "193 Å",  ions: "Fe XII, XXIV",       logT: [6.1, 7.3],     src: "instruments/AIA.md:68" },
    "211":  { instrument: "SDO/AIA", wavelength: "211 Å",  ions: "Fe XIV",             logT: [6.3],          src: "instruments/AIA.md:69" },
    "304":  { instrument: "SDO/AIA", wavelength: "304 Å",  ions: "He II",              logT: [4.7],          src: "instruments/AIA.md:70" },
    "335":  { instrument: "SDO/AIA", wavelength: "335 Å",  ions: "Fe XVI",             logT: [6.4],          src: "instruments/AIA.md:71" },
    "1600": { instrument: "SDO/AIA", wavelength: "1600 Å", ions: "C IV and continuum", logT: [5.0],          src: "instruments/AIA.md:72" },
    "1700": { instrument: "SDO/AIA", wavelength: "1700 Å", ions: "continuum",          logT: [3.7],          src: "instruments/AIA.md:73" },
    "rainbow":      { instrument: "SDO/AIA", wavelength: "composite", ions: "", logT: [], src: "", note: "false-colour composite of several channels; no single temperature" },
    "composite_uv": { instrument: "SDO/AIA", wavelength: "composite", ions: "", logT: [], src: "", note: "composite product; no single temperature" },
    "dem":          { instrument: "SDO/AIA", wavelength: "DEM",       ions: "", logT: [], src: "", note: "differential emission measure map; a range of temperatures, not one" },
  };
  const AIA_IDS = ["94", "131", "171", "193", "211", "304", "335", "1600", "1700"];
  // The nine AIA channels from cool to hot by their first (lowest) characteristic log T.
  const CHANNEL_ORDER = AIA_IDS.slice().sort((a, b) => CHANNELS[a].logT[0] - CHANNELS[b].logT[0]);

  // The strip lists the temperature-ordered AIA channels first, then the remaining products
  // in the order the page gives them.
  function stageIds(productIds) {
    const have = new Set(productIds);
    return CHANNEL_ORDER.filter((id) => have.has(id)).concat(productIds.filter((id) => !CHANNEL_ORDER.includes(id)));
  }

  function tempText(id) {
    const c = CHANNELS[id];
    if (!c) return "unknown";
    if (!c.logT.length) return c.note || "unknown";
    return "characteristic log T " + c.logT.map((x) => x.toFixed(1)).join(", ") + (c.logT.length > 1 ? " (multithermal)" : "");
  }

  // Frames sit on a 20-minute grid (three per hour, 144 = 48 h). Until the producer writes
  // per-slot times (SB-14, not written yet) a slot's time is the newest frame's time minus
  // the grid step times its distance from the end: good to about one step, so exact is false.
  const SLOT_MIN = 20;
  function parseUtc(s) {
    if (typeof s !== "string" || !s) return NaN;
    return Date.parse(/(Z|[+-]\d\d:?\d\d)$/i.test(s) ? s : s + "Z");
  }
  function clampSlot(s) { return Math.max(0, Math.min(SLOTS - 1, Math.round(Number(s) || 0))); }
  function endMs(m) {
    if (!m) return NaN;
    const t = parseUtc(m.through);
    return isNaN(t) ? parseUtc(m.updated) : t;
  }
  function slotTime(m, slot) {
    const s = clampSlot(slot);
    if (m && Array.isArray(m.times) && typeof m.times[s] === "string") {
      const t = parseUtc(m.times[s]);
      if (!isNaN(t)) return { ms: t, exact: true };
    }
    const e = endMs(m);
    return { ms: isNaN(e) ? NaN : e - (SLOTS - 1 - s) * SLOT_MIN * 60000, exact: false };
  }
  // The slot of manifest `to` that shows the same moment as `slot` of manifest `from`.
  function alignSlot(from, to, slot) {
    const s = clampSlot(slot);
    const a = slotTime(from, s).ms;
    if (isNaN(a) || !to) return s;
    if (Array.isArray(to.times) && to.times.length) {
      let best = -1, bestD = Infinity;
      to.times.forEach((x, i) => { const d = Math.abs(parseUtc(x) - a); if (d < bestD) { bestD = d; best = i; } });
      if (best >= 0 && isFinite(bestD)) return clampSlot(best);
    }
    const e = endMs(to);
    return isNaN(e) ? s : clampSlot(SLOTS - 1 - (e - a) / (SLOT_MIN * 60000));
  }
  // Middle of the frame, so a seek never lands on the boundary between two frames.
  function slotVideoTime(slot) { return (clampSlot(slot) + 0.5) / FPS; }

  window.SunData = {
    BUCKET, u, loadManifest, loadAll, loadCaptureTime, freshness,
    FRESH_OK_MIN, FRESH_STALE_MIN, FPS, SLOTS, parseHash,
    CHANNELS, CHANNEL_ORDER, SLOT_MIN, stageIds, tempText, slotTime, alignSlot, slotVideoTime,
  };

  // ---- The Stage: one large 48 hour clip, a 144 step scrubber, a channel strip (WS-15) ----
  // Two stacked <video> layers: the next channel loads and seeks to the same moment in the
  // hidden layer, then fades in over the old one (a plain cut under reduced motion).
  // DOM comes from sun.html; this code never runs at load, only when init() is called.
  function createStage() {
    const FADE_MS = 400, WALK_MS = 3500, LOAD_MS = 20000, SEEK_MS = 8000;
    const reduced = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const saveData = () => !!(navigator.connection && navigator.connection.saveData);
    let root, layers, scrub, timeEl, infoEl, statusEl, strip, playBtn, walkBtn, noteEl;
    let ids = [], labels = {}, cur = null, slot = SLOTS - 1, front = 0;
    let playing = false, raf = 0, token = 0, walking = false, walkToken = 0, walkTimer = 0, walkWake = null;
    let lazy = false, urlTimer = 0;
    const manifests = {};

    function once(el, ev, ms) {
      return new Promise((resolve, reject) => {
        const finish = (fn, v) => { clearTimeout(t); el.removeEventListener(ev, ok); el.removeEventListener("error", bad); fn(v); };
        const ok = () => finish(resolve);
        const bad = () => finish(reject, new Error("video error"));
        const t = setTimeout(() => finish(reject, new Error("timed out waiting for " + ev)), ms);
        el.addEventListener(ev, ok);
        el.addEventListener("error", bad);
      });
    }
    const sleep = (ms) => new Promise((r) => { walkWake = r; walkTimer = setTimeout(r, ms); });

    function fmtTime(ms) {
      if (isNaN(ms)) return "time unknown";
      const d = new Date(ms);
      return d.toLocaleString("en-US", { timeZone: "UTC", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) + " UTC";
    }
    function label(id) { return labels[id] || (CHANNELS[id] && CHANNELS[id].wavelength) || id; }

    function render() {
      scrub.value = String(slot);
      const t = slotTime(manifests[cur], slot);
      const when = (t.exact || isNaN(t.ms) ? "" : "about ") + fmtTime(t.ms);
      timeEl.textContent = when + " (slot " + slot + " of " + (SLOTS - 1) + ")";
      scrub.setAttribute("aria-valuetext", when);
      infoEl.textContent = cur ? label(cur) + ": " + tempText(cur) + (CHANNELS[cur] && CHANNELS[cur].ions ? "; " + CHANNELS[cur].ions : "") : "";
      strip.querySelectorAll(".stage-btn").forEach((b) => {
        const on = b.dataset.stageId === cur;
        b.classList.toggle("is-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      playBtn.textContent = playing ? "Pause" : "Play 48 h";
      playBtn.setAttribute("aria-pressed", playing ? "true" : "false");
      walkBtn.textContent = reduced() ? "Next channel by temperature" : (walking ? "Stop temperature walk" : "Temperature walk");
      walkBtn.setAttribute("aria-pressed", walking ? "true" : "false");
    }
    function state() { return { id: cur, slot }; }
    function emit(user) {
      document.dispatchEvent(new CustomEvent("sun:stage", { detail: state() }));
      if (!user) return;
      clearTimeout(urlTimer);
      urlTimer = setTimeout(() => {
        try { history.replaceState(null, "", "#stage=" + cur + "@" + slot); } catch (e) { /* history blocked: the link just does not update */ }
      }, 150);
    }
    function setStatus(msg, retry) {
      statusEl.textContent = "";
      if (msg) {
        const span = document.createElement("span");
        span.textContent = msg;
        statusEl.appendChild(span);
      }
      if (retry) {
        const b = document.createElement("button");
        b.type = "button"; b.className = "sun-retry"; b.textContent = "Retry"; b.dataset.stageAction = "retry";
        b.addEventListener("click", retry);
        statusEl.appendChild(b);
      }
    }
    function busy(on) {
      root.querySelector(".stage-videos").classList.toggle("is-loading", on);
      root.setAttribute("aria-busy", on ? "true" : "false");
    }
    function seekTo(v, s) {
      let t = slotVideoTime(s);
      if (isFinite(v.duration) && v.duration > 0) t = Math.min(t, Math.max(0, v.duration - 0.001));
      v.currentTime = t;
    }

    // Load channel `id` into the hidden layer at `target`, then bring it to the front.
    async function bringToFront(m, id, target, my) {
      const back = layers[1 - front];
      back.pause();
      back.src = u(m.video, m.updated);
      back.load();
      await once(back, "loadedmetadata", LOAD_MS);
      if (my !== token) return false;
      const seeked = once(back, "seeked", SEEK_MS);
      seekTo(back, target);
      await seeked;
      if (my !== token) return false;
      const old = layers[front];
      if (old.classList.contains("is-front")) { old.classList.remove("is-front"); old.classList.add("is-under"); }
      back.classList.add("is-front");
      front = 1 - front;
      cur = id; slot = target;
      if (playing) back.play().catch(() => {});
      setTimeout(() => { old.classList.remove("is-under"); if (old !== layers[front]) old.pause(); }, reduced() ? 0 : FADE_MS);
      return true;
    }

    async function setChannel(id, opts) {
      opts = opts || {};
      if (!ids.includes(id)) return state();
      if (id === cur && !opts.force) return state();
      const my = ++token;
      setStatus("");
      busy(true);
      try {
        const m = await loadManifest(id);
        manifests[id] = m;
        const target = cur && manifests[cur] ? alignSlot(manifests[cur], m, slot) : clampSlot(opts.slot == null ? slot : opts.slot);
        if (lazy && !opts.force) {
          // Save-Data: show the still, load the clip only when asked.
          layers[front].poster = u(m.img1k, m.updated);
          layers[front].removeAttribute("src");
          layers[front].classList.add("is-front");
          cur = id; slot = target;
        } else if (!(await bringToFront(m, id, target, my))) {
          return state();
        }
        render();
        emit(!opts.silent);
      } catch (err) {
        if (my === token) setStatus(label(id) + " did not load (" + (err && err.message ? err.message : "error") + ").", () => setChannel(id, { force: true, slot }));
      } finally {
        if (my === token) busy(false);
      }
      return state();
    }

    function seek(s, opts) {
      opts = opts || {};
      slot = clampSlot(s);
      if (lazy && !opts.silent) { activate(); return state(); }
      const v = layers[front];
      if (v.getAttribute("src")) seekTo(v, slot);
      render();
      emit(!opts.silent);
      return state();
    }

    function activate() {
      if (!lazy) return;
      lazy = false;
      setChannel(cur, { force: true, silent: true });
    }

    function tick() {
      if (!playing) return;
      const v = layers[front];
      const s = Math.min(SLOTS - 1, Math.floor(v.currentTime * FPS));
      if (s !== slot) { slot = s; render(); }
      raf = requestAnimationFrame(tick);
    }
    function play() {
      if (playing) return;
      if (lazy) activate();
      playing = true;
      layers[front].play().catch(() => { playing = false; render(); });
      raf = requestAnimationFrame(tick);
      render();
    }
    function pause() {
      if (!playing) return;
      playing = false;
      cancelAnimationFrame(raf);
      layers[front].pause();
      render();
      emit(true);
    }

    function stopWalk() {
      walkToken++;
      walking = false;
      clearTimeout(walkTimer);
      if (walkWake) { walkWake(); walkWake = null; }
      render();
    }
    async function walk() {
      if (walking) { stopWalk(); return; }
      const order = CHANNEL_ORDER.filter((id) => ids.includes(id));
      if (!order.length) return;
      if (reduced()) {                      // no timers and no fades: one step per press
        const i = order.indexOf(cur);
        await setChannel(order[(i + 1) % order.length]);
        return;
      }
      walking = true;
      const my = ++walkToken;
      render();
      for (const id of order) {
        if (my !== walkToken) return;
        await setChannel(id);
        if (my !== walkToken) return;
        await sleep(WALK_MS);
      }
      if (my === walkToken) stopWalk();
    }

    function onKey(e) {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const step = e.shiftKey ? 12 : 1;      // 12 slots is four hours
      let handled = true;
      if (e.key === "ArrowLeft" && e.target !== scrub) seek(slot - step);
      else if (e.key === "ArrowRight" && e.target !== scrub) seek(slot + step);
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        const i = ids.indexOf(cur), j = e.key === "ArrowUp" ? i - 1 : i + 1;
        if (j >= 0 && j < ids.length) setChannel(ids[j]);
      } else handled = false;
      if (handled) e.preventDefault();
    }

    function applyHash() {
      const h = parseHash(location.hash);
      if (!h.stage || !ids.includes(h.stage.id)) return false;
      if (h.stage.id === cur) seek(h.stage.slot, { silent: true });
      else setChannel(h.stage.id, { slot: h.stage.slot, silent: true });
      return true;
    }

    function init(rootEl, idList, labelMap) {
      root = rootEl;
      ids = idList.slice();
      labels = labelMap || {};
      layers = [root.querySelector("#stage-a"), root.querySelector("#stage-b")];
      scrub = root.querySelector("#stage-scrub");
      timeEl = root.querySelector("#stage-time");
      infoEl = root.querySelector("#stage-info");
      statusEl = root.querySelector("#stage-status");
      strip = root.querySelector("#stage-strip");
      playBtn = root.querySelector("#stage-play");
      walkBtn = root.querySelector("#stage-walk");
      noteEl = root.querySelector("#stage-note");
      scrub.min = "0"; scrub.max = String(SLOTS - 1); scrub.step = "1";
      strip.textContent = "";
      ids.forEach((id) => {
        const b = document.createElement("button");
        b.type = "button"; b.className = "stage-btn"; b.dataset.stageId = id;
        b.textContent = label(id);
        b.setAttribute("aria-pressed", "false");
        b.addEventListener("click", () => setChannel(id));
        strip.appendChild(b);
      });
      scrub.addEventListener("input", () => seek(+scrub.value));
      playBtn.addEventListener("click", () => (playing ? pause() : play()));
      walkBtn.addEventListener("click", walk);
      root.addEventListener("keydown", onKey);
      root.addEventListener("pointerdown", () => { if (lazy) activate(); }, { once: true });
      window.addEventListener("hashchange", applyHash);
      lazy = saveData();
      noteEl.textContent = "The moment is matched by time: frames sit on a 20 minute grid, so a switch can be off by up to one frame.";
      const fromHash = parseHash(location.hash).stage;
      const first = fromHash && ids.includes(fromHash.id) ? fromHash : { id: ids.includes("171") ? "171" : ids[0], slot: SLOTS - 1 };
      slot = clampSlot(first.slot);
      render();
      return setChannel(first.id, { slot: first.slot, silent: !fromHash });
    }

    return { init, setChannel, seek, play, pause, walk, state };
  }

  window.SunStage = createStage();
})();
