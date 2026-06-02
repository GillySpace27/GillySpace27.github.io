// Builds enso/index.html by extracting the render engine (helpers + getParams
// + render) verbatim from enso/pixelated-enso.html. The only source transform
// is swapping document.getElementById( → EL( inside getParams; render is
// copied unchanged. A thin runtime shim lets us reassign canvas/ctx/seed per
// cell so one engine drives every thumbnail and the modal.
//
// We also extract the RANDOM_BOUNDS spec and RANDOM_COLORS list verbatim, so
// each day's enso here is byte-identical to what the tool would produce for
// that UTC date — same mulberry32 stream, same draw order.
//
// Run from the repo root:
//   node enso/build_calendar.js

const fs = require('fs');
const path = require('path');

// Resolve paths relative to this script's directory so it works regardless
// of cwd, as long as enso/ is the script's parent folder.
const ENSO_DIR = __dirname;
const TOOL = path.join(ENSO_DIR, 'pixelated-enso.html');
const OUT  = path.join(ENSO_DIR, 'index.html');

const src = fs.readFileSync(TOOL, 'utf8');
const lines = src.split('\n');
const slice = (a, b) => lines.slice(a - 1, b).join('\n');  // 1-indexed inclusive

// ── 1. Extract engine source pieces by TEXT ANCHOR (not line number) ──
// Each engine function lives at the script's base indentation (4 spaces),
// so the function body ends at the first line that is exactly `    }`.
// This is robust to any line-number shifts in the source — as long as the
// function signatures themselves don't change, extraction stays correct.
function extractFunction(headerNeedle) {
  const startIdx = lines.findIndex(l => l.includes(headerNeedle));
  if (startIdx === -1) throw new Error('Function not found: ' + headerNeedle);
  const indent = (lines[startIdx].match(/^(\s*)/) || ['',''])[1];
  const closer = new RegExp('^' + indent.replace(/ /g, ' ') + '\\}\\s*$');
  for (let i = startIdx + 1; i < lines.length; i++) {
    if (closer.test(lines[i])) return lines.slice(startIdx, i + 1).join('\n');
  }
  throw new Error('Closing brace not found for: ' + headerNeedle);
}
// Extract a contiguous run of functions from `firstHeader` through `lastHeader`
// (inclusive of lastHeader's body). Used for the helpers block which is a
// sequence of small functions we want to copy as one chunk.
function extractFunctionRange(firstHeader, lastHeader) {
  const startIdx = lines.findIndex(l => l.includes(firstHeader));
  const lastIdx  = lines.findIndex(l => l.includes(lastHeader));
  if (startIdx === -1) throw new Error('Function not found: ' + firstHeader);
  if (lastIdx  === -1) throw new Error('Function not found: ' + lastHeader);
  const indent = (lines[lastIdx].match(/^(\s*)/) || ['',''])[1];
  const closer = new RegExp('^' + indent.replace(/ /g, ' ') + '\\}\\s*$');
  for (let i = lastIdx + 1; i < lines.length; i++) {
    if (closer.test(lines[i])) return lines.slice(startIdx, i + 1).join('\n');
  }
  throw new Error('Closing brace not found for: ' + lastHeader);
}

const mulberry32Src = extractFunction('function mulberry32(a)');
const helpersSrc    = extractFunctionRange('function lerpColor', 'function logMap');
const getParamsRaw  = extractFunction('function getParams(scale)');
const renderSrc     = extractFunction('function render(size)');

// Swap DOM reads inside getParams for a shim that pulls from the current
// settings object (_S). Nothing else in getParams needs to change.
const domReadCount = (getParamsRaw.match(/document\.getElementById\(/g) || []).length;
if (domReadCount !== 52) throw new Error('Expected 52 DOM reads in getParams, found ' + domReadCount);
const getParamsSrc = getParamsRaw.replace(/document\.getElementById\(/g, 'EL(');

// ── 2. Extract RANDOM_BOUNDS and RANDOM_COLORS verbatim ──
const boundsBlock = src.match(/const RANDOM_BOUNDS = \{[\s\S]*?\};/)[0];
const colorsBlock = src.match(/const RANDOM_COLORS = \[[\s\S]*?\];/)[0];

// ── 3. Build a DEFAULTS map covering EVERY control getParams reads ──
// Range inputs: pull id+value attrs from the markup. Selects: take the
// option marked `selected` if present, else the first option. Color: the
// value= attribute on the color input.
const DEFAULTS = {};
for (const m of src.matchAll(/<input\s+type="range"\s+id="([^"]+)"[^>]*?\bvalue="([^"]+)"/g)) {
  DEFAULTS[m[1]] = m[2];
}
for (const m of src.matchAll(/<select\s+id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
  const id = m[1], body = m[2];
  const selected = body.match(/<option\s+[^>]*value="([^"]+)"[^>]*selected/);
  const first    = body.match(/<option\s+[^>]*value="([^"]+)"/);
  DEFAULTS[id] = (selected || first)[1];
}
for (const m of src.matchAll(/<input\s+type="color"\s+id="([^"]+)"[^>]*?\bvalue="([^"]+)"/g)) {
  DEFAULTS[m[1]] = m[2];
}

// Sanity: every id getParams touches must have a default so EL(...).value
// never returns undefined (which would NaN out the render).
const idsInGetParams = [...getParamsRaw.matchAll(/document\.getElementById\('([^']+)'\)/g)].map(m => m[1]);
const missing = [...new Set(idsInGetParams)].filter(id => !(id in DEFAULTS));
if (missing.length) throw new Error('No default extracted for: ' + missing.join(', '));

console.log('Extracted', Object.keys(DEFAULTS).length, 'control defaults;',
            'getParams touches', new Set(idsInGetParams).size, 'unique ids; all covered.');

// ── 4. Assemble the calendar HTML ──
const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Enso Calendar</title>
<script>
  // Pre-paint theme application — matches pixelated-enso.html's three-state
  // (system | light | dark) so the calendar styles correctly before first paint.
  (function () {
    try {
      var mode = localStorage.getItem('enso-theme') || 'system';
      var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (mode === 'dark' || (mode === 'system' && prefersDark)) {
        document.documentElement.classList.add('dark');
      }
    } catch (e) {}
  })();
<\/script>
<style>
  :root {
    --bg: #faf8f3;
    --text: #1a2a5a;
    --muted: #555;
    --card-bg: #ffffff;
    --card-border: #ddd;
    --cell-bg: #ffffff;
    --cell-border: #d8d0c2;
    --cell-future-bg: #f0ece2;
    --cell-future-text: #b8b0a0;
    --cell-today-border: #c89b3c;
    --cell-hover-border: #1a2a5a;
    --modal-backdrop: rgba(0, 0, 0, 0.55);
    --modal-bg: #ffffff;
    --btn-bg: #1a2a5a;
    --btn-text: #ffffff;
  }
  :root.dark {
    --bg: #1a1814;
    --text: #e8e2d0;
    --muted: #a8a094;
    --card-bg: #25221c;
    --card-border: #3a362c;
    --cell-bg: #2a2620;
    --cell-border: #4a4438;
    --cell-future-bg: #211e18;
    --cell-future-text: #5a5448;
    --cell-today-border: #d9a91a;
    --cell-hover-border: #d9a91a;
    --modal-backdrop: rgba(0, 0, 0, 0.78);
    --modal-bg: #25221c;
    --btn-bg: #d9a91a;
    --btn-text: #1a1814;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 24px 16px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
  }
  .wrap { max-width: 980px; margin: 0 auto; }
  .topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 12px; }
  h1 { margin: 0 0 4px 0; font-size: 28px; }
  .subtitle { color: var(--muted); margin: 0 0 24px 0; font-size: 14px; }
  .theme-toggle {
    background: transparent; border: 1px solid var(--card-border); color: var(--text);
    padding: 6px 12px; border-radius: 6px; font-size: 13px; cursor: pointer;
  }
  .theme-toggle:hover { opacity: 0.82; }
  .theme-toggle.active {
    background: var(--btn-bg);
    color: var(--btn-text);
    border-color: var(--btn-bg);
  }
  /* Small icon-only button for the theme switch — kept visually quiet. */
  .icon-btn {
    background: transparent;
    border: none;
    color: var(--muted);
    cursor: pointer;
    font-size: 16px;
    padding: 4px 6px;
    border-radius: 4px;
    opacity: 0.55;
    line-height: 1;
  }
  .icon-btn:hover { opacity: 1; background: var(--cell-bg); }
  .header-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 20px;
  }
  .month-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 18px;
    gap: 12px;
  }
  .month-nav h2 { margin: 0; font-size: 22px; font-weight: 600; }
  .nav-btn {
    background: transparent;
    border: 1px solid var(--card-border);
    color: var(--text);
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 16px;
    cursor: pointer;
    font-family: inherit;
  }
  .nav-btn:hover { background: var(--cell-bg); border-color: var(--cell-hover-border); }
  .nav-btn:disabled { opacity: 0.35; cursor: default; }
  .nav-btn:disabled:hover { background: transparent; border-color: var(--card-border); }
  .weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
    margin-bottom: 8px;
  }
  .weekdays div {
    text-align: center;
    font-size: 12px;
    color: var(--muted);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
  }
  .cell {
    aspect-ratio: 1 / 1;
    background: var(--cell-bg);
    border: 2px solid var(--cell-border);
    border-radius: 8px;
    padding: 6px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: default;
    overflow: hidden;
    transition: border-color 0.12s ease, transform 0.12s ease;
  }
  .cell.past { cursor: pointer; }
  .cell.past:hover { border-color: var(--cell-hover-border); transform: translateY(-1px); }
  .cell.today { border-color: var(--cell-today-border); border-width: 3px; }
  .cell.future { background: var(--cell-future-bg); border-style: dashed; cursor: default; }
  .cell.empty { background: transparent; border: none; pointer-events: none; }
  .cell canvas {
    position: absolute;
    inset: 6px;
    width: calc(100% - 12px);
    height: calc(100% - 12px);
    image-rendering: pixelated;
  }
  .day-num {
    position: absolute;
    bottom: 4px;
    right: 6px;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    background: var(--cell-bg);
    padding: 1px 5px;
    border-radius: 3px;
    z-index: 1;
    line-height: 1.3;
  }
  .cell.future .day-num { color: var(--cell-future-text); background: transparent; }
  .cell.today .day-num { color: var(--cell-today-border); }

  /* Modal */
  .modal-backdrop {
    position: fixed; inset: 0;
    background: var(--modal-backdrop);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 20px;
  }
  .modal-backdrop.open { display: flex; }
  .modal {
    background: var(--modal-bg);
    border-radius: 12px;
    padding: 20px;
    max-width: 95vw;
    max-height: 95vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
  }
  .modal-date { font-size: 18px; font-weight: 600; }
  .modal canvas {
    width: min(640px, 80vw, 80vh);
    height: min(640px, 80vw, 80vh);
    image-rendering: pixelated;
    border-radius: 8px;
  }
  .modal-actions {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  /* Vision-based AI impression line displayed between the canvas and the
     action buttons. Stays hidden when the feature isn't configured. */
  .modal-impression {
    font-style: italic;
    font-size: 14px;
    color: var(--muted);
    max-width: 580px;
    text-align: center;
    line-height: 1.55;
    display: none;          /* enabled by JS once a fetch begins */
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 22px;
    padding: 0 8px;
  }
  .modal-impression.visible { display: flex; }
  /* Banner state when Workers AI daily quota is exhausted. Non-italic,
     slightly smaller and dimmer than the haiku — reads as a status
     note rather than a poem. */
  .modal-impression.paused {
    font-style: normal;
    font-size: 13px;
    opacity: 0.85;
    letter-spacing: 0.02em;
    max-width: 70%;
  }
  .impression-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid var(--card-border);
    border-top-color: var(--text);
    border-radius: 50%;
    animation: enso-spin 0.7s linear infinite;
    flex-shrink: 0;
  }
  .impression-spinner.hidden { display: none; }
  @keyframes enso-spin { to { transform: rotate(360deg); } }
  .modal-close, .modal-download {
    background: var(--btn-bg);
    color: var(--btn-text);
    border: none;
    padding: 8px 18px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-family: inherit;
  }
  .modal-download { background: transparent; color: var(--text); border: 1px solid var(--card-border); }
  .modal-download:hover { border-color: var(--cell-hover-border); }
  .modal-download:disabled { opacity: 0.55; cursor: default; }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div>
      <h1>Enso Calendar</h1>
      <p class="subtitle">A new enso each day, deterministic from the UTC date — past days fill in, future days await.</p>
    </div>
    <div class="header-actions">
      <button id="themeToggle" type="button" class="icon-btn" aria-label="Toggle theme">🖥️</button>
    </div>
  </div>

  <div class="card">
    <div class="month-nav">
      <button id="prevMonth" type="button" class="nav-btn" aria-label="Previous month">←</button>
      <h2 id="monthLabel"></h2>
      <button id="nextMonth" type="button" class="nav-btn" aria-label="Next month">→</button>
    </div>
    <div class="weekdays">
      <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
    </div>
    <div class="grid" id="grid"></div>
  </div>
</div>

<div class="modal-backdrop" id="modalBackdrop">
  <div class="modal" id="modal">
    <div class="modal-date" id="modalDate"></div>
    <canvas id="modalCanvas" width="640" height="640"></canvas>
    <div class="modal-impression" id="modalImpression" style="display: none;">
      <span class="impression-spinner" id="impressionSpinner"></span>
      <span class="impression-text" id="impressionText"></span>
    </div>
    <div class="modal-actions">
      <button class="modal-download" id="modalDownload">⬇ Download PNG</button>
      <button class="modal-download" id="modalEdit" title="Open this enso in the editor with all its parameters preloaded">✎ Edit in tool</button>
      <button class="modal-close" id="modalClose">Close</button>
    </div>
  </div>
</div>

<script>
  // ════════════════════════════════════════════════════════════════════════
  //  ENSO RENDER ENGINE (extracted verbatim from pixelated-enso.html)
  //  Helpers + getParams + render are byte-identical to the tool's, save for
  //  swapping getParams' document.getElementById(...) calls for an EL(...)
  //  shim that reads from a current-settings object. canvas/ctx/seed are
  //  reassigned per render target by renderEnso() below.
  // ════════════════════════════════════════════════════════════════════════

  // Render target + seed are module-level so the copied render() can use them
  // unchanged — renderEnso() reassigns them per call.
  let canvas, ctx, seed;

  // Current settings object for the EL shim.
  let _S = {};
  const EL = id => ({ value: _S[id] });

  // Stub: render(size) only consults getRenderSize() when size is omitted; we
  // always pass size explicitly, but keep the symbol defined for safety.
  function getRenderSize() { return 470; }

${mulberry32Src}

${helpersSrc}

${getParamsSrc}

${renderSrc}

  // ════════════════════════════════════════════════════════════════════════
  //  DETERMINISTIC ENSO-OF-THE-DAY GENERATOR
  //  Same RANDOM_BOUNDS, same RANDOM_COLORS, same draw order as randomEnso()
  //  in the tool — so calendar(date) === tool's "Random enso of the day" for
  //  that UTC date.
  // ════════════════════════════════════════════════════════════════════════

  ${boundsBlock}

  ${colorsBlock}

  // Defaults for every control getParams reads. Most of these are inert in
  // bristle mode (brushFade, pixelStart/transitionWidth/pixelSize/fadeStart/
  // fadeCurve, the radial-bleed sliders), but getParams still parses them so
  // they need real numeric values to avoid NaN propagating into render.
  const DEFAULTS = ${JSON.stringify(DEFAULTS, null, 2)};

  // Produces { settings, seed } for the canonical enso of utcMidnightMs.
  // Draw order MUST match randomEnso(false) in the tool exactly — same
  // mulberry32 stream, same sequence of prng() calls — or outputs diverge.
  function dateToEnso(utcMidnightMs) {
    const prng = mulberry32(utcMidnightMs);
    const r = (mn, mx) => mn + prng() * (mx - mn);
    const snap = (v, step) => Math.round(v / step) * step;
    // First draw becomes the shape seed (matches the tool's first prng() draw assigned to _seed).
    const shapeSeed = prng();
    const overrides = { renderStyle: 'bristles' };
    for (const [id, [mn, mx, step]] of Object.entries(RANDOM_BOUNDS)) {
      overrides[id] = String(snap(r(mn, mx), step));
    }
    overrides.direction = prng() < 0.5 ? 'cw' : 'ccw';
    overrides.bg = 'transparent';
    if (prng() < 0.45) {
      overrides.color = RANDOM_COLORS[Math.floor(prng() * RANDOM_COLORS.length)];
    } else {
      overrides.color = hslToHex(prng(), 0.45 + prng() * 0.35, 0.28 + prng() * 0.24);
    }
    // Merge: defaults under randomized overrides. getParams reads from this.
    return { settings: { ...DEFAULTS, ...overrides }, seed: shapeSeed };
  }

  // Render the enso for utcMidnightMs into targetCanvas at size px.
  function renderEnso(targetCanvas, utcMidnightMs, size) {
    const { settings, seed: shapeSeed } = dateToEnso(utcMidnightMs);
    canvas = targetCanvas;
    ctx    = targetCanvas.getContext('2d');
    seed   = shapeSeed;
    _S     = settings;
    render(size);
  }

  // ════════════════════════════════════════════════════════════════════════
  //  CALENDAR UI
  // ════════════════════════════════════════════════════════════════════════

  const MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December'];

  // Today's UTC midnight — anchor for "future" classification.
  function todayUTC() {
    const n = new Date();
    return Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate());
  }
  function utcDate(year, month, day) { return Date.UTC(year, month, day); }

  // Cache of rendered cell bitmaps: key = utcMidnightMs, value = OffscreenCanvas
  // (or HTMLCanvasElement fallback). Each day's enso is immutable, so once
  // drawn we never re-render — paging back to a previously-viewed month just
  // blits the cached pixels in.
  const cellCache = new Map();
  const THUMB_SIZE = 180;   // internal canvas resolution (CSS shrinks it)

  // Render queue + idle scheduler. Drawing all 30 ensos at once would block
  // the main thread for a few hundred ms; we yield between cells so the page
  // stays responsive while the month fills in.
  let renderQueue = [];
  let queueRunning = false;
  function scheduleQueue() {
    if (queueRunning) return;
    queueRunning = true;
    function tick() {
      const start = performance.now();
      // Render a few cells per tick (budget ~8ms) before yielding.
      while (renderQueue.length && performance.now() - start < 8) {
        const job = renderQueue.shift();
        job();
      }
      if (renderQueue.length) {
        (window.requestIdleCallback || window.requestAnimationFrame)(tick);
      } else {
        queueRunning = false;
      }
    }
    (window.requestIdleCallback || window.requestAnimationFrame)(tick);
  }
  function enqueue(job) { renderQueue.push(job); scheduleQueue(); }

  // Build an offscreen render canvas for a given utc date, populate from cache
  // if available, else render and cache. Used by both the live cell and modal.
  function getOrRenderCell(utcMs, size) {
    const key = utcMs + ':' + size;
    if (cellCache.has(key)) return cellCache.get(key);
    const off = document.createElement('canvas');
    off.width = size;
    off.height = size;
    renderEnso(off, utcMs, size);
    cellCache.set(key, off);
    return off;
  }

  // Build the month grid for (year, monthIdx) where monthIdx is 0-11.
  function renderMonth(year, monthIdx) {
    const grid = document.getElementById('grid');
    grid.innerHTML = '';
    document.getElementById('monthLabel').textContent = MONTH_NAMES[monthIdx] + ' ' + year;

    // Disable next-month button if the next month is entirely in the future.
    const todayMs = todayUTC();
    const nextMonthFirst = utcDate(monthIdx === 11 ? year + 1 : year, (monthIdx + 1) % 12, 1);
    document.getElementById('nextMonth').disabled = nextMonthFirst > todayMs;

    // First day of month: UTC weekday (0 = Sun ... 6 = Sat). new Date(utcMs)
    // .getUTCDay() gives us a stable weekday regardless of local timezone.
    const firstUtc = utcDate(year, monthIdx, 1);
    const firstWeekday = new Date(firstUtc).getUTCDay();
    // Days in this month: day 0 of next month gives last day of this month.
    const daysInMonth = new Date(Date.UTC(monthIdx === 11 ? year + 1 : year,
                                          (monthIdx + 1) % 12, 0)).getUTCDate();

    // Leading blank cells for the first week.
    for (let i = 0; i < firstWeekday; i++) {
      const blank = document.createElement('div');
      blank.className = 'cell empty';
      grid.appendChild(blank);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const cellMs = utcDate(year, monthIdx, d);
      const cell = document.createElement('div');
      cell.className = 'cell';
      if (cellMs > todayMs) {
        cell.classList.add('future');
      } else {
        cell.classList.add('past');
        if (cellMs === todayMs) cell.classList.add('today');
        cell.dataset.utc = String(cellMs);
        cell.addEventListener('click', () => openModal(cellMs));
      }
      const num = document.createElement('div');
      num.className = 'day-num';
      num.textContent = String(d);
      cell.appendChild(num);

      if (cellMs <= todayMs) {
        // Schedule render — visible canvas in the cell.
        const cnv = document.createElement('canvas');
        cnv.width = THUMB_SIZE;
        cnv.height = THUMB_SIZE;
        cell.insertBefore(cnv, num);
        enqueue(() => {
          const cached = getOrRenderCell(cellMs, THUMB_SIZE);
          cnv.getContext('2d').drawImage(cached, 0, 0);
        });
      }
      grid.appendChild(cell);
    }
  }

  // Modal: render at higher resolution for the close-up view. We track the
  // open UTC date so the download button (rendered at full export size on
  // demand) knows which day it's saving.
  const MODAL_SIZE = 640;
  const DOWNLOAD_SIZE = 2400;   // print-quality (~8 in at 300 DPI); preserves bristle detail
  let currentModalUtcMs = null;

  // ── AI impression feature ───────────────────────────────────────────────
  // Set this to your deployed Cloudflare Worker URL after running
  // 'wrangler deploy' on the enso-impressions Worker. Leaving it empty
  // disables the impression UI silently — the modal just doesn't show the
  // line. See enso-impressions/README.md for the full setup.
  const IMPRESSIONS_WORKER_URL = '';

  // Session cache: dateStr → impression text. Prevents re-fetching when the
  // user reopens the same day's modal in the current tab session. The KV
  // cache on the Worker side handles the cross-session/cross-user case, so
  // each unique date is generated exactly once globally.
  const impressionCache = new Map();

  function openModal(utcMs) {
    currentModalUtcMs = utcMs;
    const dateStr = new Date(utcMs).toLocaleDateString(undefined, {
      timeZone: 'UTC', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    document.getElementById('modalDate').textContent = dateStr;
    const modalCnv = document.getElementById('modalCanvas');
    modalCnv.width = MODAL_SIZE;
    modalCnv.height = MODAL_SIZE;
    // Render directly (not via cache — modal is a one-off at higher res).
    renderEnso(modalCnv, utcMs, MODAL_SIZE);
    document.getElementById('modalBackdrop').classList.add('open');
    // Fire-and-forget the impression fetch. It owns its own UI lifecycle
    // (spinner → text or silent hide) and bails out if the modal closes
    // or changes date before the response arrives.
    loadImpression(utcMs);
  }
  function closeModal() {
    document.getElementById('modalBackdrop').classList.remove('open');
    currentModalUtcMs = null;
    // Reset impression block so a stale spinner from an in-flight request
    // doesn't briefly show next time the modal opens.
    const imp = document.getElementById('modalImpression');
    imp.classList.remove('visible');
    imp.classList.remove('paused');
    imp.style.display = 'none';
    document.getElementById('impressionText').textContent = '';
    document.getElementById('impressionSpinner').classList.remove('hidden');
  }
  // Fetches the AI impression for the current modal date from the Worker.
  // Owns the visibility of #modalImpression entirely: it shows the slot when
  // it starts work, hides it on error/disabled. All state transitions are
  // guarded by the currentModalUtcMs check so a slow response for an
  // already-closed modal can't blank the impression for a newer open.
  async function loadImpression(utcMs) {
    const imp = document.getElementById('modalImpression');
    const spinner = document.getElementById('impressionSpinner');
    const text = document.getElementById('impressionText');
    // Feature disabled (Worker URL not configured): keep slot hidden.
    if (!IMPRESSIONS_WORKER_URL) return;
    const dateStr = formatUtcDate(utcMs);
    // Session cache hit → show instantly, no spinner.
    if (impressionCache.has(dateStr)) {
      spinner.classList.add('hidden');
      text.textContent = impressionCache.get(dateStr);
      imp.classList.add('visible');
      imp.style.display = 'flex';
      return;
    }
    // First view this session: show spinner, fire request.
    spinner.classList.remove('hidden');
    text.textContent = 'reading the enso…';
    imp.classList.add('visible');
    imp.style.display = 'flex';
    const modalCnv = document.getElementById('modalCanvas');
    const dataUrl = modalCnv.toDataURL('image/png');
    try {
      const response = await fetch(IMPRESSIONS_WORKER_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: dateStr, image: dataUrl }),
      });
      // Parse the body even on non-2xx — Cloudflare's Workers AI quota
      // error (code 4006) arrives as a 502 with a structured error
      // body that we want to surface differently from a generic fail.
      let data = null;
      try { data = await response.json(); } catch (e) { /* non-JSON body */ }
      // Modal closed or moved on before the response landed — abandon.
      if (utcMs !== currentModalUtcMs) return;
      if (response.ok && data && data.impression) {
        impressionCache.set(dateStr, data.impression);
        spinner.classList.add('hidden');
        text.textContent = data.impression;
        return;
      }
      // Not ok, or no impression in body. Tell the two failure shapes
      // apart: Workers AI free-tier quota exhaustion is a temporary,
      // expected state (resets at UTC midnight) and deserves a kind
      // banner; everything else hides the slot as before.
      const detail = String((data && (data.detail || data.error)) || '');
      const quotaExhausted = /4006|free allocation|daily.*allocation|neurons/i.test(detail);
      spinner.classList.add('hidden');
      if (quotaExhausted) {
        imp.classList.add('paused');
        text.textContent = 'the brush is set down for today.\nfresh haiku tomorrow.';
      } else {
        // Generic failure — hide the whole slot rather than show an error.
        console.warn('[impressions] fetch failed:', response.status, detail);
        imp.classList.remove('visible');
        imp.style.display = 'none';
      }
    } catch (err) {
      console.warn('[impressions] fetch failed:', err && err.message);
      if (utcMs !== currentModalUtcMs) return;
      // Network error (worker unreachable, CORS rejection, etc.) —
      // treat as generic failure, hide the slot.
      imp.classList.remove('visible');
      imp.style.display = 'none';
    }
  }
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('modalBackdrop').addEventListener('click', e => {
    if (e.target.id === 'modalBackdrop') closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  // Download: re-render the current day's enso to a hidden offscreen canvas
  // at DOWNLOAD_SIZE and save as PNG. We render fresh rather than scaling the
  // visible 640px canvas — the engine's bristle/dot sizes scale with output
  // resolution, so a fresh render at 2400 produces genuinely more detail, not
  // a blown-up version of the modal view. We disable the button during render
  // because the 2400-size pass can take a few hundred ms on a busy preset.
  function formatUtcDate(utcMs) {
    const d = new Date(utcMs);
    return d.getUTCFullYear() + '-' +
           String(d.getUTCMonth() + 1).padStart(2, '0') + '-' +
           String(d.getUTCDate()).padStart(2, '0');
  }
  // Edit: opens the dashboard (pixelated-enso.html) in a new tab with
  // ?date=YYYY-MM-DD so it reproduces the same enso for editing. From the
  // user's perspective: "Edit takes me to the tool with this exact enso loaded."
  document.getElementById('modalEdit').addEventListener('click', () => {
    if (currentModalUtcMs === null) return;
    const url = 'pixelated-enso.html?date=' + formatUtcDate(currentModalUtcMs);
    window.open(url, '_blank', 'noopener');
  });
  document.getElementById('modalDownload').addEventListener('click', () => {
    if (currentModalUtcMs === null) return;
    const btn = document.getElementById('modalDownload');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Rendering…';
    // Defer one frame so the button visibly updates before the (blocking) render begins.
    requestAnimationFrame(() => {
      try {
        const off = document.createElement('canvas');
        off.width = DOWNLOAD_SIZE;
        off.height = DOWNLOAD_SIZE;
        renderEnso(off, currentModalUtcMs, DOWNLOAD_SIZE);
        off.toBlob(blob => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'dailyEnso_' + formatUtcDate(currentModalUtcMs) + '.png';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          // Revoke after the click handler so the browser has the URL long enough to start the download.
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          btn.disabled = false;
          btn.textContent = originalText;
        }, 'image/png');
      } catch (e) {
        console.error('Download render failed:', e);
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  });

  // Month navigation. Bounds: don't let the user page forward past the
  // current month (handled by the disabled state above), but allow paging
  // back arbitrarily — every past date has a canonical enso.
  let viewYear, viewMonth;
  function setView(year, monthIdx) {
    viewYear = year; viewMonth = monthIdx;
    // Clear pending renders from the previous month — they're no longer visible.
    renderQueue = [];
    renderMonth(year, monthIdx);
  }
  document.getElementById('prevMonth').addEventListener('click', () => {
    if (viewMonth === 0) setView(viewYear - 1, 11);
    else setView(viewYear, viewMonth - 1);
  });
  document.getElementById('nextMonth').addEventListener('click', () => {
    if (viewMonth === 11) setView(viewYear + 1, 0);
    else setView(viewYear, viewMonth + 1);
  });

  // Boot: show the current UTC month.
  const now = new Date();
  setView(now.getUTCFullYear(), now.getUTCMonth());

  // ── Theme toggle (mirrors pixelated-enso.html) ───────────────────────────
  // The theme button is intentionally small and quiet — just an icon in the
  // top right. Hover shows the current mode via the title attribute.
  (function () {
    const btn = document.getElementById('themeToggle');
    const order = ['system', 'light', 'dark'];
    const icons  = { system: '🖥️',         light: '☀️',        dark: '🌙' };
    const titles = { system: 'Theme: System (click to cycle)',
                     light:  'Theme: Light (click to cycle)',
                     dark:   'Theme: Dark (click to cycle)' };
    const mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    function getMode() {
      try { return localStorage.getItem('enso-theme') || 'system'; }
      catch (e) { return 'system'; }
    }
    function applyMode(mode) {
      const prefersDark = mq ? mq.matches : false;
      const dark = mode === 'dark' || (mode === 'system' && prefersDark);
      document.documentElement.classList.toggle('dark', dark);
      btn.textContent = icons[mode];
      btn.title = titles[mode];
    }
    btn.addEventListener('click', () => {
      const next = order[(order.indexOf(getMode()) + 1) % order.length];
      try { localStorage.setItem('enso-theme', next); } catch (e) {}
      applyMode(next);
    });
    if (mq) {
      const onChange = () => { if (getMode() === 'system') applyMode('system'); };
      if (mq.addEventListener) mq.addEventListener('change', onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
    applyMode(getMode());
  })();

<\/script>
</body>
</html>
`;

fs.writeFileSync(OUT, html);
console.log('Wrote', OUT, '—', (html.length / 1024).toFixed(1), 'KB');
