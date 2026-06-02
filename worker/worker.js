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

// Model. Llama 4 Scout is natively multimodal (single set of parameters
// handles text + vision), instruction-tuned, and free-tier eligible.
// Easy to swap for Kimi K2.5/2.6 or Gemma 4 if quality needs nudging.
const MODEL = '@cf/meta/llama-4-scout-17b-16e-instruct';
const MAX_TOKENS = 200;

// CORS allow-list. The Workers Builds deploy gives a *.workers.dev URL and
// you'll be calling it from gilly.space/enso. Add localhost variants if you
// ever want to test against a local copy of the calendar.
const ALLOWED_ORIGINS = [
  'https://gilly.space',
  'http://localhost:8000',
  'http://localhost:8080',
  'http://127.0.0.1:8000',
];

// System prompt designed to produce single-sentence emotional impressions
// in a specific voice. Iterate on this freely — pushing a tweaked version
// is just an edit to this string + git push.
const SYSTEM_PROMPT = `You write single-sentence emotional impressions of digital ensos — brushstroke circles inspired by Japanese zen ink practice — based on their visual character.

Output requirements:
- EXACTLY one sentence. No second sentence, no semicolons that chain two thoughts.
- 12 to 28 words.
- Sensory and evocative — connect color and texture to mood.
- Name specific color qualities you actually see ("burnt orange", "steel blue", "soft gray", "deep wine"), not hex codes and not just "blue" or "red".
- Don't explain what an enso is — assume the reader knows.
- Avoid generic zen vocabulary: serene, tranquil, contemplative, meditative, peaceful, harmonious, balanced. Be specific instead.
- Vary your openings. Some sentences start with mood, some with color, some with how the brush moves. Don't fall into a pattern.
- No filler words: moreover, indeed, remarkably, intriguingly, beautifully, gracefully.
- Don't reference the painting as a painting ("this artwork", "the piece", "this enso"). Just describe what you see.
- No quotes, no preamble, no labels. Output only the sentence itself.

Examples of the target style:
- "Bright and sunny, oranges and yellows blend into a warm, comfortable glow."
- "Steel blue and patient — the brush hesitates near the bottom before completing its arc."
- "A burnt umber stroke, dry and unhurried, fading into specks of dust at the tail."
- "Heavy crimson loops twice before catching itself, restless and unfinished."
- "Pale silver, almost ghostlike, drawn with the lightest possible hand."
- "Deep wine churning against black, the ink runs thin where the brush ran out."
- "Forest green, mossy and damp, with bristles that splay outward like wet grass."`;

const USER_TEXT = 'Write your one-sentence impression of this enso.';

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
    const cacheKey = `impression:${date}`;
    try {
      const cached = await env.IMPRESSIONS.get(cacheKey);
      if (cached) {
        return jsonResponse({ impression: cached, cached: true }, 200, cors);
      }
    } catch (err) {
      console.warn('KV read failed (continuing):', err.message);
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

    // Workers AI response shape varies by model. For Llama-family chat
    // models the binding returns `{ response: "..." }`; OpenAI-compat path
    // returns `{ choices: [{ message: { content: "..." } }] }`. Handle both.
    const text = (
      aiResult?.response ||
      aiResult?.choices?.[0]?.message?.content ||
      ''
    ).trim();

    if (!text) {
      console.error('Empty model response:', JSON.stringify(aiResult).slice(0, 500));
      return jsonResponse({ error: 'empty response from model' }, 502, cors);
    }

    // Cache the new impression. If KV write fails, still return — better
    // to serve the just-generated impression than fail the whole request.
    try {
      await env.IMPRESSIONS.put(cacheKey, text);
    } catch (err) {
      console.warn('KV write failed (returning anyway):', err.message);
    }

    return jsonResponse({ impression: text, cached: false }, 200, cors);
  },
};
