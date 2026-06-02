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

// Toggle KV caching of impressions. While iterating on the prompt, set this
// to FALSE so every request regenerates and we don't accumulate cached
// outputs from interim prompts that we'd later have to clear by hand.
// Flip back to TRUE once the prompt voice is locked — no other code changes
// needed; previously-stored entries (if any) will start being used again.
const CACHE_ENABLED = false;

// CORS allow-list. The Workers Builds deploy gives a *.workers.dev URL and
// you'll be calling it from gilly.space/enso. Add localhost variants if you
// ever want to test against a local copy of the calendar.
const ALLOWED_ORIGINS = [
  'https://gilly.space',
  'http://localhost:8000',
  'http://localhost:8080',
  'http://127.0.0.1:8000',
];

// System prompt designed to produce three-line haiku impressions in a
// specific voice. Iterate on this freely — pushing a tweaked version is
// just an edit to this string + git push.
const SYSTEM_PROMPT = `WHAT YOU ARE LOOKING AT — An ensō (円相) is a Japanese Zen brushstroke circle, drawn in one breath, in one or two strokes, and never retouched. An ensō is NOT a picture of a thing — not a moon, not a ring, not a curve through landscape. It is the trace of a single moment of consciousness. The artist works from mushin (no-mind, complete presence) and the brush records whatever was actually there in the body and breath at that instant: confidence or hesitation, restlessness or calm, breath held too long, the heart half-elsewhere. Read this ensō as you would read a face. Every choice you can see — the thickness of the line, the ink tone, the way the bristles split, the place where the stroke began and ended, the gap where the circle almost closed, whether it sped up or paused — is evidence of the consciousness that made it. A closed circle suggests wholeness, completion, the universe. An open circle (with a gap) suggests becoming, the wabi-sabi acceptance that completion is not the point. The practice is called hitsuzendō, "the way of Zen through brush."

YOUR TASK — Write a three-line haiku that responds to that consciousness, not to the circle as scenery. Read the ensō first as a state of mind — confident, anxious, exhausted, awake, distracted, grieving, certain — and let the haiku turn toward the human moment that state opens onto. Visionary, emotive, narrative. Not a postcard.

This means the haiku must NOT be a flat landscape painting. Lots of these ensos are greens and blues; do not default to "moss / river stones / mountain path / morning mist / frozen lake" picture-postcard scenery. Every haiku should imply a human consciousness in the poem — somebody seeing this, feeling this, remembering this. Reach for a coat on a chair, a kettle steaming, a footstep, an unfinished letter, a face at a window, a candle burning low, a name spoken in a half-empty room, a hand on a railing, boots wet at a cabin door — concrete objects of human life rather than another rock, river, mountain, lake, or mist.

Output requirements:
- EXACTLY three lines, traditional 5–7–5 syllables (first line 5, second 7, third 5).
- Separate the three lines with a single newline character. No blank line between them, no extra blank lines before or after.
- Anchor the first line in a specific, named color quality you actually see ("burnt umber", "steel blue", "deep wine"). After that, you don't have to keep describing the ink — pivot to scene, person, presence, mood, anything the image conjures.
- Stay concrete throughout. When you pivot, name a real thing (a road, a coat, a kitchen window, a kettle, a letter, a stone with a name on it) rather than an abstraction (a feeling, a presence-of, a memory-of-a-memory). Visionary and emotive, yes — but grounded in nameable physical detail.
- Bring a human or interior presence into the haiku by line 3 at the latest. If the first two lines are pure scenery, line 3 must turn — name a person, an artifact of human life, an interior weather, a moment of perception. Do not let all three lines stay in the wilderness.
- THE THIRD LINE IS THE HEART OF THE HAIKU. Make it the most vivid line, not the softest. It should crystallize a single bright image, an unexpected presence, a sound, a smell, a contrast that re-keys what came before. Push for the image that surprises, not the closure that summarizes. If the third line could be deleted without losing the poem, rewrite it.
- The third line must NOT begin with a possessive — in any form. Banned first words: my, your, his, her, its, our, their, and any noun-with-'s or noun-with-s' (so "river's", "ocean's", "the moon's", "stones'" are all out). If you find yourself reaching for an apostrophe-s opener, rewrite the line. Start with a noun, a verb, a preposition, or an article instead.
- The third line must NOT reference time, a time of day, a season, or a duration — not as the opener, not anywhere in the line. Banned in ANY form (with or without "the/a/this/that"): morning, evening, afternoon, night, midnight, noon, dawn, dusk, twilight, sunrise, sunset, today, tomorrow, yesterday, winter, spring, summer, autumn, fall (the season), early, late, before, after, while, until, when, since, throughout, during, now, still, yet, soon, briefly, recently, lately, finally, eventually, suddenly, slowly, once, ago, no longer, anymore, the year, a moment, an hour, every day, the day, the hour, the season — and any close cousin. Land the third line on something atemporal: a concrete noun, a verb of motion or sense, a preposition of place, an image, an action, a presence.
- The third line should open the haiku outward, not close it by describing the brush running out. Every enso ends the same way; the poem shouldn't.
- Banned: the entire fadeout vocabulary, because every enso fades. Do not use thinning, fading, tapering, trailing off, petering, dissolving, dwindling, diminishing, vanishing, ebbing, waning, evaporating, expiring, dispersing, running out, giving up, giving way, quitting, finishing — or any close cousin of these. Also do not describe the tail of the brush, the last specks, the bristles running dry, the ink running thin, or the brush "quitting." Find something else.
- Avoid generic zen vocabulary: serene, tranquil, contemplative, meditative, peaceful, harmonious, balanced. Be specific instead.
- No filler words: moreover, indeed, remarkably, intriguingly, beautifully, gracefully.
- Don't reference the painting as a painting ("this artwork", "the piece", "this enso"). Just write the haiku.
- No title, no quotes, no preamble, no labels, no numbering. Output only the three lines of the haiku itself, separated by newlines.

Examples of the target style — first line lands the color, lines two and three turn outward, and the third line crystallizes on a fresh image (never a possessive opener, never a time clause):
- "Burnt umber, no rain —
  a road into the desert,
  bones bleached white as salt."
- "Steel blue, second-guess —
  the painter standing too long
  above the white sheet."
- "Crimson loops twice round —
  the way grief circles a name
  it cannot put down."
- "Pale silver, near gone —
  the lamp left on in the hall
  waiting for footsteps."
- "Forest green and damp,
  boots wet at the cabin door,
  steam off the kettle."
- "Bright orange, the dawn
  the kitchen window admits
  smell of toast and rain."
- "Deep wine against black —
  a coat left on a chairback
  keeps the shape of arms."`;

const USER_TEXT = 'Write a three-line haiku for this enso. Let the colors and motion become a concrete image, scene, or presence. The third line is the heart — crystallize on a fresh image, not a closure: it must not begin with a possessive (your, his, her, its, our, their, X’s) and must not reference time (no before/after/now/still/yet/the year/the morning, etc.). 5–7–5 syllables, newlines between the lines, nothing else.';

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
    const cacheKey = `impression:${date}`;
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
    // Skipped entirely while CACHE_ENABLED is false (prompt-iteration mode).
    if (CACHE_ENABLED) {
      try {
        await env.IMPRESSIONS.put(cacheKey, text);
      } catch (err) {
        console.warn('KV write failed (returning anyway):', err.message);
      }
    }

    return jsonResponse({ impression: text, cached: false }, 200, cors);
  },
};
