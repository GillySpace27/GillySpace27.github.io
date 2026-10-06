# enso-impressions worker

Cloudflare Worker that produces a one-sentence emotional impression of each
day's enso, using Workers AI (Llama 4 Scout). Deployed via Cloudflare's
Workers Builds (auto-deploy from GitHub).

## Files

- `worker.js`       — request handler, KV cache, Workers AI inference
- `wrangler.toml`   — bindings (AI, IMPRESSIONS KV)

## One-time setup (~3 min, in browser)

The KV namespace gets created by Claude via MCP — you just need to do the
git-to-Cloudflare connection once.

1. **Connect this directory to Cloudflare Workers Builds:**
   - dash.cloudflare.com → Workers & Pages → **Create application**
   - **Import a repository** → authorize the Cloudflare Workers & Pages GitHub App
     on your gilly.space repo
   - Select the repo, set **Root directory** to `worker`
   - Save and Deploy. Cloudflare clones the repo, reads `wrangler.toml`, builds
     and deploys the worker.

2. **Note the Worker URL.** After the first successful build, the worker's
   overview page shows the URL — something like
   `https://enso-impressions.<your-account>.workers.dev`.

3. **Wire the calendar to use it:** done. `enso/index.html:1838` sets
   `IMPRESSIONS_WORKER_URL` to `https://enso-impressions.gilly-22d.workers.dev`.
   The generator template `enso/build_calendar.js:619` still writes an empty
   URL, so do not run `node enso/build_calendar.js` until WS-12 adds
   `--check`: it would silently turn impressions off. The calendar hides the
   impression UI while the URL is empty.

## How updates work after that

Every push to the `master` branch that touches anything in `worker/` triggers
an auto-rebuild and redeploy by Cloudflare (~30 seconds). So the loop is:

1. Tell Claude what to change (prompt tweak, model swap, etc.)
2. Claude updates `worker.js`
3. You `git add worker/ && git commit -m "tune prompt" && git push`
4. Cloudflare deploys it. Calendar starts using new prompts on next request.

## Cost

Workers AI free tier: **100,000 requests/day** (way more than you'll need).
KV reads/writes also free on the standard tier. Total ongoing cost: $0 for
any realistic personal-site traffic level.

## Operations

- **Force-regenerate a bad impression:** dash → Workers & Pages → KV →
  `IMPRESSIONS` namespace → find the row `impression-v2:YYYY-MM-DD` → trash icon
  (Gilly only; agents never delete KV rows).
  Next view of that date generates a fresh impression.
- **See logs:** dash → Workers & Pages → `enso-impressions` → Logs → Begin
  log stream. Live `console.log`/`console.error` from the worker shows here.
- **Swap models:** edit the `MODEL` constant at the top of `worker.js`,
  commit + push. Workers AI options: `@cf/meta/llama-4-scout-17b-16e-instruct`
  (default, multimodal, fast), `@cf/google/gemma-4-26b-a4b-it` (alternative
  vision), `@cf/moonshotai/kimi-k2.5` (frontier-scale, vision). See
  `https://developers.cloudflare.com/workers-ai/models/` for the full catalog.

## Guards and tests

- `GET /status` returns JSON `{model, cacheEnabled, today, aiCallsToday}`;
  any other GET returns the health string unchanged.
  `curl -s https://enso-impressions.gilly-22d.workers.dev/status`
- Dates: a POST `date` must be a real `YYYY-MM-DD` from `DATE_MIN`
  (`2020-01-01`) to tomorrow UTC; anything else is a 400.
- Daily ceiling: each cache miss increments KV `quota:<UTC day>` before the
  Workers AI call. At `DAILY_AI_LIMIT` (500) the Worker answers 429
  `{"error": "daily limit", "detail": "daily allocation of AI calls reached; ..."}`,
  which the calendar shows as its paused message. Both numbers are estimates;
  change them in `worker.js`. The counter is not atomic (a soft ceiling) and its
  keys stay in KV.
- Tests: `node --test tools/tests/test_worker.mjs` from the repo root, with
  stubbed AI and KV and no network. They live outside `worker/` because any push
  under `worker/` redeploys the Worker. CI runs them in
  `.github/workflows/check.yml`.
- A merge to `master` that touches `worker/` is a production deploy: merge only
  on a green check and with Gilly's yes for that merge.
