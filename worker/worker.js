// Cloudflare Worker: enso impressions (Workers AI version)
// ─────────────────────────────────────────────────────────────────────────
// Accepts POST { date, image } where:
//   • date  = "YYYY-MM-DD" (UTC, the canonical key for each daily enso)
//   • image = PNG data URL (canvas.toDataURL()) OR raw base64 string
//
// Returns JSON { impression, cached }.
//
// Architecture:
//   1. Cache lookup in KV by date — if cached, return immediately.
//   2. Otherwise, call Workers AI (env.AI.run) with the image + system prompt.
//      Native binding, no external API key, runs in the same datacenter as
//      the Worker. Free up to 100,000 requests/day per the Workers AI tier.
//   3. Cache the new impression, return it.
//
// Bindings required (configured in wrangler.toml):
//   • env.AI           — Workers AI binding
//   • env.IMPRESSIONS  — KV namespace for caching
// No secrets required. The whole stack is internal to Cloudflare.
// ─────────────────────────────────────────────────────────────────────────

// Model. Llama 4 Scout — Meta's 17B-parameter mixture-of-experts model,
// natively multimodal, free-tier eligible on Workers AI. We swapped
// back from Llama 4 Scout after a single afternoon of heavy iteration
// burned through the 10K-neurons/day free allocation; K2.6's 1T
// params cost many more neurons per call than Llama. Llama's haiku
// quality is the weaker side of the trade, but the new meditative
// prompt + diversified examples carry most of the gravity, and
// staying on free tier means the project just runs.
// Easy upgrades when ready: '@cf/moonshotai/kimi-k2.6' (1T params,
// Workers Paid plan needed) or '@cf/google/gemma-4-26b-a4b-it'.
const MODEL = '@cf/meta/llama-4-scout-17b-16e-instruct';
const MAX_TOKENS = 200;

// Toggle KV caching of impressions. While iterating on the prompt, set this
// to FALSE so every request regenerates and we don't accumulate cached
// outputs from interim prompts. Flip to TRUE once the prompt voice is
// locked — each unique date is then generated exactly once globally and
// served instantly forever after, also dropping inference cost to near
// zero for repeat visitors. Previously-stored entries (if any) start
// being used again, so make sure the namespace is clean for the
// current prompt before re-enabling.
const CACHE_ENABLED = true;

// CORS allow-list. The Workers Builds deploy gives a *.workers.dev URL and
// you'll be calling it from gilly.space/enso. Add localhost variants if you
// ever want to test against a local copy of the calendar.
const ALLOWED_ORIGINS = [
  'https://gilly.space',
  'http://localhost:8000',
  'http://localhost:8080',
  'http://127.0.0.1:8000',
];

// System prompt: produces a single-line evocative image that captures the
// ensō's color, saturation, and distribution of ink. Not a haiku, not a
// poem — one vivid phrase or sentence the color reminds you of. Iterate
// freely; a push is just an edit to this string.
const SYSTEM_PROMPT = `You are looking at an ensō (円相) — a Japanese Zen brushstroke circle drawn in one breath. Do not treat it as a symbolic object. Read it as a distribution of color, saturation, and gesture, and write ONE short evocative image that its palette and brushwork remind you of.

The image is not a haiku, not a poem, and not a description of the ensō. It is a single vivid phrase or sentence — a place, a mood, an object, a landscape, an atmosphere, a slice-of-life scene, a wry association — that a real human might blurt out on seeing the color pattern. Ground it in what the ink is actually doing: bright or muted, saturated or washed, warm or cool, dense or sparse, hurried or calm, clean-edged or broken. If the ensō is amber and gold, someone might think of honey in sunlight; if it is a nervous grey-green, someone might think of storm light on slate; if it is a wet, wine-dark red, someone might think of a bottle of port on a fisherman's wharf. Let the color make the association.

Length: six to fifteen words. One line. No line breaks. Capitalize the first letter. A trailing period is optional. No quotes, no preamble, no explanation, no "this image evokes," no "the ensō suggests" — just the phrase itself.

Range of tone: the examples span literary to playful on purpose. Match what you actually see; do not default to one register.

Examples:
  • Bright blue sky over a turbulent ocean
  • Amber and honey basking in the sunlight
  • A chilly day in Oslo
  • A bottle of ruby port on a fisherman's wharf
  • Wheat fields and solar feels
  • Dusk in a copper-domed cathedral
  • Storm light on a slate roof after rain
  • Cough-syrup pink at a kids' craft night
  • The green of pond scum on a July afternoon
  • Sunday in the vineyards, no phone service

Write one such line for THIS ensō. Nothing else.`;

const USER_TEXT = 'Look at this ensō. In one short evocative image — six to fifteen words on one line — say what its color, saturation, and distribution remind you of. No haiku, no line breaks, no commentary.';

// Build CORS headers for the request's origin (echoes if allowed, else
// default to gilly.space so the browser's preflight at least succeeds).
function corsHeadersFor(origin) {
  const allowed = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allowed,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

function jsonResponse(body, status, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...cors },
  });
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    const cors = corsHeadersFor(origin);

    // CORS preflight.
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }

    // Light health-check for "is the worker live?" testing.
    if (request.method === 'GET') {
      return new Response('enso-impressions worker is alive (Workers AI / Llama 4 Scout)', {
        headers: { 'Content-Type': 'text/plain', ...cors },
      });
    }

    if (request.method !== 'POST') {
      return jsonResponse({ error: 'method not allowed' }, 405, cors);
    }

    // Parse body. Strict shape: date must look like a real UTC date so a
    // typo can't poison the cache with a garbage key.
    let body;
    try { body = await request.json(); }
    catch { return jsonResponse({ error: 'invalid JSON body' }, 400, cors); }

    const date = String(body.date || '');
    const image = String(body.image || '');

    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return jsonResponse({ error: 'invalid date format (need YYYY-MM-DD)' }, 400, cors);
    }
    if (!image) {
      return jsonResponse({ error: 'missing image' }, 400, cors);
    }

    // Cache lookup. Each unique date is generated exactly once across all
    // visitors. KV is eventually consistent globally (~60s), which is fine
    // here — even a duplicate generation is free on the Workers AI tier.
    // Skipped entirely while CACHE_ENABLED is false (prompt-iteration mode).
    // Key prefix versioned so a substantive change in the prompt (e.g.
    // three-line haiku → one-line evocative image) invalidates every
    // prior cached entry without needing a KV dashboard trip. Old
    // "impression:YYYY-MM-DD" keys sit as dead weight; new entries
    // land under the new prefix and everyone sees the new format.
    const cacheKey = `impression-v2:${date}`;
    if (CACHE_ENABLED) {
      try {
        const cached = await env.IMPRESSIONS.get(cacheKey);
        if (cached) {
          return jsonResponse({ impression: cached, cached: true }, 200, cors);
        }
      } catch (err) {
        console.warn('KV read failed (continuing):', err.message);
      }
    }

    // Normalize image: accept either a raw base64 string or a data URL.
    // The Workers AI multimodal format wants a data URL (image_url.url).
    const imageDataUrl = image.startsWith('data:')
      ? image
      : `data:image/png;base64,${image}`;

    // Crude size guard. Modal canvas at 640px renders to ~80–200 KB base64
    // (~110–280 KB as a data URL). 4 MB is well above that ceiling.
    if (imageDataUrl.length > 5_500_000) {
      return jsonResponse({ error: 'image too large' }, 413, cors);
    }

    // Call Workers AI. OpenAI-compatible multimodal content format: the
    // user message's `content` is an array of structured parts (one for
    // the image, one for the text). Llama 4 Scout natively handles both.
    let aiResult;
    try {
      aiResult = await env.AI.run(MODEL, {
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          {
            role: 'user',
            content: [
              { type: 'image_url', image_url: { url: imageDataUrl } },
              { type: 'text', text: USER_TEXT },
            ],
          },
        ],
        max_tokens: MAX_TOKENS,
      });
    } catch (err) {
      console.error('Workers AI call failed:', err && (err.stack || err.message || err));
      return jsonResponse({ error: 'inference failed', detail: String(err?.message || err) }, 502, cors);
    }

    // Workers AI response shape varies by model. Known shapes:
    //   • Llama-family: { response: "..." }
    //   • OpenAI-compat: { choices: [{ message: { content: "..." } }] }
    //   • Kimi K2.x:    { result: { response: "..." } } per observed runs,
    //                    or sometimes { result: { choices: [...] } }
    //   • Some models:  { output: "..." } or { text: "..." }
    // Try each in order; first non-empty wins.
    const text = (
      aiResult?.response ||
      aiResult?.choices?.[0]?.message?.content ||
      aiResult?.result?.response ||
      aiResult?.result?.choices?.[0]?.message?.content ||
      aiResult?.output ||
      aiResult?.text ||
      aiResult?.message?.content ||
      ''
    ).trim();

    if (!text) {
      console.error('Empty model response:', JSON.stringify(aiResult).slice(0, 1000));
      // Echo the raw shape back to the client so the calling page can show
      // it in DevTools — much faster than chasing it through the dashboard
      // log stream. Safe because the worker is only callable from our own
      // origin (CORS allow-list).
      return jsonResponse({
        error: 'empty response from model',
        rawShape: aiResult,
      }, 502, cors);
    }

    // Take just the first non-empty line as the impression. The prompt
    // asks for one line, but Llama sometimes tacks on a second thought
    // or a "— this evokes..." elaboration; the trimmer clips it silently.
    const haiku = text
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean)
      .slice(0, 1)
      .join('\n');

    // Cache the new impression. If KV write fails, still return — better
    // to serve the just-generated impression than fail the whole request.
    // Skipped entirely while CACHE_ENABLED is false (prompt-iteration mode).
    if (CACHE_ENABLED) {
      try {
        await env.IMPRESSIONS.put(cacheKey, haiku);
      } catch (err) {
        console.warn('KV write failed (returning anyway):', err.message);
      }
    }

    return jsonResponse({ impression: haiku, cached: false }, 200, cors);
  },
};
