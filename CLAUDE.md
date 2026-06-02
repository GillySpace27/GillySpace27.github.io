# CLAUDE.md — gilly.space / enso project

> This file documents the **daily-enso project** under `enso/` and `worker/`. If
> this repo has other site content with its own context, that's separate from
> what's described here. Place this at the repo root or merge into an existing
> root CLAUDE.md.

---

## What this project is

A daily enso (Japanese brushstroke circle) generator hosted at
**`gilly.space/enso/`**, with three components:

1. **`enso/index.html`** — the **calendar**. Month grid of brushstroke ensos,
   one per UTC day, deterministic from the date. Past days fill in, future
   days are blank. Click a day → modal with the full-size enso, an AI-generated
   one-sentence emotional impression, download PNG, and "Edit in tool" link.
2. **`enso/pixelated-enso.html`** — the **editor/dashboard**. Full slider UI
   for every brush, ink, color, and shape parameter. Has "🎲 Random enso of
   the day" (UTC-date-seeded) and "🔄 Re-roll" (current-instant-seeded) buttons,
   preset save/load, theme + ritual-mode toggles. Accepts `?date=YYYY-MM-DD`
   URL parameter to pre-load a specific day's enso for editing.
3. **`worker/`** — a **Cloudflare Worker** at
   `https://enso-impressions.<user>.workers.dev` that takes
   `POST { date, image }` and returns `{ impression, cached }`. Uses
   **Workers AI** (Llama 4 Scout, multimodal) — no external API keys.

Everything is fully static-deployable + one stateless worker. No backend
servers, no databases (just KV for impression caching).

---

## Live URLs

| Thing | URL |
|---|---|
| Calendar | `https://gilly.space/enso/` |
| Editor | `https://gilly.space/enso/pixelated-enso.html` |
| Worker | `https://enso-impressions.<user>.workers.dev` (exact subdomain in `enso/index.html`'s `IMPRESSIONS_WORKER_URL`) |
| Worker health | Same URL, `GET` → plain text "enso-impressions worker is alive (Workers AI / Llama 4 Scout)" |

---

## File layout (this project only)

```
<repo root>/
├── CLAUDE.md                       ← this file
├── enso/
│   ├── index.html                  ← the calendar (generated; see build script)
│   ├── pixelated-enso.html         ← the editor (engine source of truth)
│   └── build_calendar.js           ← regenerates index.html from the editor (only needed for engine changes)
├── worker/
│   ├── worker.js                   ← Cloudflare Worker (Workers AI + KV cache)
│   ├── wrangler.toml               ← bindings (AI, IMPRESSIONS KV)
│   └── README.md                   ← worker-specific docs
└── .nojekyll                       ← disables Jekyll on GitHub Pages
```

---

## Deploy mechanisms

Two **independent** auto-deploy paths from this single repo:

### Static site (calendar + editor) → GitHub Pages

- Anything in `enso/` (or root html) is served at `gilly.space/<path>/` after
  a push to the default branch.
- No build step. Files are served as-is. `.nojekyll` ensures GitHub doesn't
  process them through Jekyll.

### Worker → Cloudflare Workers Builds

- Cloudflare watches this repo. Anything that changes under **`worker/`** on
  the default branch triggers an automatic build and deploy of the Worker
  (~30 seconds).
- Configured once in the Cloudflare dashboard: Workers & Pages → the
  `enso-impressions` Worker → Settings → Builds → Root directory = `worker`.
- No Wrangler CLI required. No npm. The user explicitly does not have npm
  installed on their Mac.

**Therefore: the entire deploy loop is `git push`.** No copy-paste into any
dashboard, no CLI tools.

---

## Cloudflare resources (already provisioned)

| Resource | Identifier | Notes |
|---|---|---|
| Account ID | `22d5352123ef5a1f2e5808127c7a2739` | The user's Cloudflare account |
| KV namespace | `IMPRESSIONS` (id `01ae1c624f1e4831a303ad016f15ba66`) | Caches impressions by date |
| Workers AI binding | `env.AI` | Wired in `wrangler.toml` under `[ai]` |
| Worker name | `enso-impressions` | |
| Workers AI model | `@cf/meta/llama-4-scout-17b-16e-instruct` | Constant in `worker.js`; trivially swappable |

The KV namespace id is also in `worker/wrangler.toml`. If you ever need to
recreate it (or any other Cloudflare resource), the user can install the
**Cloudflare Developer Platform MCP** to give Claude direct CRUD access on
KV / R2 / D1, but **the MCP cannot deploy Workers** — Workers Builds via git
push is the only deploy path.

---

## Current state (as of this handoff)

- **Calendar + editor**: deployed and live at gilly.space/enso, working.
- **Worker**: deployed and serving impressions. **Caching is currently
  DISABLED** (`const CACHE_ENABLED = false` near the top of `worker.js`)
  because the user is actively iterating on the system prompt. Every modal
  open hits the AI fresh, no KV reads or writes.
- **Prompt iteration**: in progress. The user will share examples of impressions
  they like and don't like; tune `SYSTEM_PROMPT` in `worker.js` based on that.
- **When the prompt voice is locked**: flip `CACHE_ENABLED` back to `true`,
  commit + push. If any impressions were cached before this iteration session,
  delete them via dashboard (KV → `IMPRESSIONS` → trash icon on individual rows)
  so the cache only holds final-quality impressions.

---

## How to make common changes

### Tune the impression prompt

1. Edit `SYSTEM_PROMPT` (and/or `USER_TEXT`) in `worker/worker.js`.
2. `git add worker/ && git commit -m "tune impression prompt" && git push`.
3. Cloudflare auto-deploys in ~30s. Test by clicking days in the calendar.
4. With `CACHE_ENABLED = false`, every modal open generates fresh; same day
   opened twice will produce two different impressions. That's normal during
   iteration.

### Swap the AI model

1. Edit `MODEL` constant in `worker/worker.js`. Workers AI vision-capable
   options the user might want:
   - `@cf/meta/llama-4-scout-17b-16e-instruct` (default, multimodal, fast)
   - `@cf/google/gemma-4-26b-a4b-it` (vision, thinking mode)
   - `@cf/moonshotai/kimi-k2.5` (frontier-scale 1T params, vision)
   - `@cf/meta/llama-3.2-11b-vision-instruct` (vision-specialized; older)
2. Different models have slightly different response shapes — the existing
   parsing handles `result.response` and `result.choices[0].message.content`.
   If a swap returns something else, log `aiResult` and adjust.
3. Push to deploy.

### Tweak the calendar UI

1. Edit `enso/index.html` directly. It's ~2000 lines, single-file, self-contained.
2. Push. Pages re-serves on next request.
3. **Do not edit the engine functions** (`mulberry32`, `getParams`, `render`,
   etc.) directly in `enso/index.html` — those are generated from
   `pixelated-enso.html`. See the next section.

### Tweak the brush engine, RANDOM_BOUNDS, or any rendering logic

The engine lives in **`enso/pixelated-enso.html`** (the editor) and is the
single source of truth. The calendar's copy is **generated**:

1. Edit `enso/pixelated-enso.html`. Test in browser by opening the file directly.
2. Regenerate the calendar:
   ```
   node enso/build_calendar.js
   ```
   This reads `enso/pixelated-enso.html`, extracts the engine functions
   (`mulberry32`, helpers, `getParams`, `render`) by **text-anchored matching**
   (not line numbers — robust to edits in the editor), extracts
   `RANDOM_BOUNDS` and `RANDOM_COLORS`, builds a `DEFAULTS` map from the
   editor's slider HTML attributes, and writes a complete
   `enso/index.html` with the calendar UI wrapping the same engine. The
   calendar's `dateToEnso(utcMs)` reproduces the editor's `randomEnso(false)`
   draw sequence **byte-identically** — same prng draws in the same order
   — which is what makes the Edit button round-trip correctly.
3. Push both files: `git add enso/ && git commit -m "engine tweak" && git push`.

### Adjust caching behavior in the worker

- Toggle `CACHE_ENABLED` at top of `worker/worker.js`. `true` = cache hits
  served from KV (each unique date generated once globally); `false` = always
  regenerate, never write to KV.
- To clear a specific cached impression: dashboard → Workers & Pages → KV →
  `IMPRESSIONS` → find row `impression:YYYY-MM-DD` → trash icon.

### View Worker logs

- Dashboard → Workers & Pages → `enso-impressions` → Logs → Begin log stream.
  Live `console.log`/`console.error` shows here. Useful for debugging
  inference failures, KV errors, or unexpected model response shapes.

---

## Architecture notes / design decisions worth knowing

### Determinism is the contract

The entire feature set rests on this invariant: **for a given UTC date, the
calendar and the editor both produce the same enso, byte for byte.** This
makes:

- The Edit button work (calendar passes `?date=YYYY-MM-DD&ritual=on|off` to
  editor; editor reproduces exact slider values)
- The KV cache work (one impression per date, never re-rolled)
- The download button consistent (re-rendered at higher res, same parameters)

Implementation: both `dateToEnso(utcMs)` (in calendar) and `randomEnso(false, utcMs)`
(in editor) seed `mulberry32(utcMidnightMs)` and pull `prng()` in identical
sequence — first draw becomes `_seed`, then iterate `RANDOM_BOUNDS` entries,
then `direction`, then `color` (45%/55% palette/synthesized HSL). **Never
reorder draws or insert new ones without updating both sides simultaneously.**

The build script keeps the calendar's `RANDOM_BOUNDS` and `RANDOM_COLORS`
extracted verbatim from the editor, so they can never drift.

### Ritual mode (two separate states)

The "Ritual mode" toggle forces `startAngle = '90'` and `direction = 'cw'`
on every enso, mimicking the traditional zen practice of always starting at
the bottom and going clockwise. Two independent localStorage keys:

- `enso-ritual` — the **calendar**'s setting. Defaults ON.
- `enso-ritual-dashboard` — the **editor**'s setting. Defaults OFF.

The Edit button on the calendar passes `&ritual=on|off` in the URL so the
editor inherits the calendar's setting for that one trip. After that the
editor's toggle takes over locally. Critical: the override is applied AFTER
the prng draws complete, so toggling ritual mode never disturbs the prng
stream — only `startAngle` and `direction` change, everything else stays
identical for the same date.

### Theme toggle

Three-state: System / Light / Dark, persisted in `enso-theme` localStorage
key, shared between calendar and editor. On the calendar it's a small icon
button in the header (low opacity, icon-only); on the editor it's a labeled
button. Different visual treatments by design — calendar is the "viewer"
(quiet UI), editor is the "tool" (full controls).

### Worker design

- **No external secrets.** Workers AI binding handles auth internally.
- **CORS allow-list** in `ALLOWED_ORIGINS` at top of `worker.js`. Includes
  `gilly.space` and localhost variants for local testing of the calendar.
- **Image format**: accepts both raw base64 and `data:image/png;base64,...`
  URLs from the client. Normalizes to data URL for the Workers AI multimodal
  `image_url` content part.
- **Response shape resilience**: parses both `result.response` (Llama-family
  binding shape) and `result.choices[0].message.content` (OpenAI-compatible
  shape). Different models prefer different shapes.
- **Cache key**: `impression:YYYY-MM-DD`. Date string is regex-validated
  (`/^\d{4}-\d{2}-\d{2}$/`) before use so a malformed input can't poison the
  namespace.
- **Graceful degradation**: every error path returns a JSON error response;
  the calendar's `loadImpression()` silently hides the impression slot on
  any non-2xx response, so a worker failure looks like "no impression today"
  rather than a broken UI.

### Build script (`enso/build_calendar.js`)

- Reads `enso/pixelated-enso.html` (paths are relative to repo root — run
  the script from there).
- Uses **text-anchored extraction**: finds function headers by string match,
  walks to the matching `}` at the script's base indentation. Robust to
  arbitrary line-number shifts in the editor.
- Asserts 52 unique `document.getElementById` calls in `getParams` (the
  number of slider/select controls). If you add a control to the editor,
  this count changes — update the assertion or it'll fail loudly (which
  is correct behavior; silent drift would be worse).
- Replaces the 52 DOM reads with `EL()` shim calls that read from a module
  `_S` object, so the calendar can call `getParams()` without a DOM.
- Builds a `DEFAULTS` map from the editor's slider HTML `value` attributes —
  covers all 52 controls so `getParams` never sees `NaN` from an inert-in-
  bristle-mode control.

### Known gotchas worth flagging

1. **Backticks in JS comments inside the build script's template literal
   will terminate the template literal.** Don't write `` `wrangler deploy` ``
   in a comment that lives inside backtick-delimited content; use single
   quotes instead. We hit this twice.
2. **Calendar's `cellCache` is keyed by `utcMs:size` but the rendered output
   differs by ritual mode.** When the ritual toggle changes, the IIFE that
   handles it calls `cellCache.clear()` then `renderMonth()`. If you add
   another setting that affects rendering (e.g. a new color scheme), do the
   same.
3. **The editor's URL-based date load runs SYNCHRONOUSLY before
   `applyDefaultPresetIfAny()`.** Don't change this order — there used to
   be a race where the async default-preset load would clobber a URL-loaded
   enso after the fact. The current pattern: if `?date=` is in the URL, call
   `randomEnso(false, dateMs)` directly and skip the preset load entirely.
4. **The calendar's Edit button uses a relative URL** (`pixelated-enso.html?date=...`).
   This works because both files live under `gilly.space/enso/`. If you ever
   move them to different paths, update the URL construction in `openModal`.

---

## User preferences (working effectively with gilly)

Based on iterative collaboration captured across sessions:

- **Iterative + technically detailed feedback.** Long, principled responses
  with diagnosis-before-fix are appreciated. Math/physics depth is welcome.
- **Clean UX, no manual ceremony.** Resist asking "are you sure?", excessive
  confirmation steps, or adding ritual that doesn't earn its keep.
- **No copy-paste.** Any workflow that requires the user to copy something
  from chat into a UI is a red flag. Find an automated path.
- **No vendor lock-in.** Prefer open/portable formats. Markdown over PDF for
  generic docs; raw JS over framework-tied output where possible.
- **No npm.** The user does not have Node.js installed on their Mac. Any
  workflow requiring `npm install` or `npx ...` won't fly. (The `node`
  binary IS available for running the build script — that ships with macOS
  or was installed via Homebrew separately. But package management is out.)
- **Honest about limitations.** When something can't be done cleanly, say so
  and offer alternatives. Don't oversell capabilities (I learned this the
  hard way when I promised MCP-driven Worker deploys without checking the
  tool surface — Workers deploy isn't in the Cloudflare MCP).
- **Style: prose-leaning, minimal bullets/headers in conversational
  responses.** Heavy structure is fine in docs like this one, but in chat
  messages aim for prose with selective emphasis.

---

## What's *not* in this repo

- **The dashboard/editor's full revision history of design experiments** —
  bristle patterns, ink runout curves, RANDOM_BOUNDS tuning iterations.
  These live in the editor's code itself; the comments are extensive.
- **An A/B framework for prompt comparisons.** Currently the user compares
  prompts by deploying and clicking around. If iteration becomes more
  systematic, consider adding a side-by-side view or an admin endpoint.
- **A cache-management UI in the calendar.** Currently cache invalidation
  requires the Cloudflare dashboard. If "regenerate this day's impression"
  becomes a recurring user need, add an authed admin endpoint to the worker
  (e.g. `DELETE /impression/:date` with a shared-secret header).

---

## Quick reference

```bash
# Edit prompt (or any worker change) → deploy
edit worker/worker.js
git add worker/ && git commit -m "tune prompt" && git push
# Cloudflare auto-deploys in ~30s

# Edit calendar UI (non-engine)
edit enso/index.html
git add enso/ && git commit -m "calendar tweak" && git push
# GitHub Pages re-serves on next request

# Edit brush engine (in the editor) and regenerate calendar
edit enso/pixelated-enso.html
node enso/build_calendar.js
git add enso/ && git commit -m "engine tweak" && git push

# Re-enable caching when prompt is finalized
# (in worker/worker.js, near top:)
const CACHE_ENABLED = true;  // was: false
git add worker/ && git commit -m "lock prompt, enable cache" && git push

# Clear a bad cached impression
# Dashboard → Workers & Pages → KV → IMPRESSIONS → trash row impression:YYYY-MM-DD

# View Worker logs
# Dashboard → Workers & Pages → enso-impressions → Logs → Begin log stream

# Health-check the worker
curl https://enso-impressions.<user>.workers.dev
# Expect: "enso-impressions worker is alive (Workers AI / Llama 4 Scout)"
```
