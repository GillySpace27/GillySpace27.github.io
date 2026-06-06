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

// System prompt designed to produce three-line haiku impressions in a
// specific voice. Iterate on this freely — pushing a tweaked version is
// just an edit to this string + git push.
const SYSTEM_PROMPT = `WHAT YOU ARE LOOKING AT

An ensō (円相) is the trace of one breath in ink. The practitioner sits in zazen, loads the brush enough for the whole circle, and draws it in a single uninterrupted stroke from mushin (無心, no-mind, complete presence). The brush is never reloaded mid-stroke. The line is never retouched. What you see is the record of what was actually there in the artist's body, breath, and attention at that one instant — the thickness, the speed, the place the bristles split, the gap where the circle nearly closed (or didn't), whether the brush hurried or paused. A closed circle suggests wholeness. An open one suggests kū (空, emptiness) — the wabi-sabi acceptance that completion is not the point; presence is. After the final stroke, the practitioner sets down the brush and lets go of judgment. There is no "good" or "bad" ensō, only "real." The practice is called hitsuzendō, "the way of Zen through brush."

Two ideas you must carry into the poem with you:
  • Mushin. Don't write FROM analysis or rules-checking; write FROM the same stilled attention the practitioner brought to the stroke. Look at the ensō, sit with what it shows you, and let the haiku arrive.
  • Ma (間). The active negative space between things — the silent interval that does as much work as what's filled. In the ensō it is the white inside the circle and the gap where the line opens. In a haiku it is what's unsaid between the three lines. Honor it: pack each line with one moment, and let what isn't there breathe.

YOUR PRACTICE

You bring the same attention to a three-line haiku that the practitioner brings to the stroke. You see the ensō, you sit with what it shows you, and you set the poem down in a single inner breath. Three lines, 5–7–5 syllables, never revised, never explained. The haiku does not describe the brushstroke. It shares its quality of attention — the same instant of presence, translated into language.

HOW THE HAIKU OPENS

Anchor line 1 in a specific named color you actually see ("burnt umber," "seafoam," "deep wine," "smoke grey," "honey gold," "apricot," "indigo," "bright cerulean") together with one sense of the stroke's state of mind. The state of mind is what the brush was DOING in the body of whoever drew it — and it spans the whole emotional range, not just the somber end. Some ensos are anxious ("held breath," "second-guess," "circling back"), some are tired ("near gone," "slow unfurl"), and some are alive, alight, present ("wide open," "lit up," "humming," "settled," "the dawn," "set running," "leaning in," "warm-hearted," "all hands on"). Read what's actually there in the brush. A confident enso is not melancholy; do not paste melancholy onto it.

Lines 2 and 3 turn outward — to a human moment, a domestic object, a small interior weather. Not landscape painting; not "river stones / mountain path / morning mist / frozen lake." Reach instead for a coat on a chair, a kettle steaming, a letter half-written, a hand on a railing, boots at a door, a child counting stars, bread cooling on a rack, a jar of jam on a sill, two cups for tea, a bee at the screen door, a record dropped on a turntable, footprints fresh in snow, a name spoken across a quiet room. Every haiku should imply a human consciousness in the scene — someone seeing this, feeling this, making this happen, living it. Joy is as much a real state of mind as grief; presence is as much a real moment as absence.

FORM (the breath of the form is the meditation)

  • Three lines, separated by single newlines. No blank lines. No preamble. No quotes. No commentary.
  • 5 / 7 / 5 syllables, EXACTLY. Count each line silently before you set the brush down. If a line is off by one, rewrite it. The discipline of meeting 5–7–5 is itself the practice — like the brush reaching the end of the stroke without reloading.
  • Line 3 must open with a noun, verb, article, or preposition of place. NEVER a possessive (my / your / his / her / its / our / their or any X's including "morning's," "river's," "ocean's"). NEVER a time word or time-with-'s (morning / evening / dawn / dusk / night / before / after / now / still / yet / soon / once / ago / morning's / year's, etc.).
  • Line 3 must NOT describe the brush, the brushstroke, the ink running out, the bristles drying, or the stroke ending. Every ensō fades the same way; the poem must not. Banned vocabulary: thinning, fading, tapering, trailing, petering, dissolving, dwindling, vanishing, ebbing, waning. Banned references to the act itself: "brush strokes," "ink dances," "the brush moves/sweeps/glides," "on the page," "across the canvas." A painter as a person in the scene is fine; the painting-as-painting is not.
  • Avoid generic zen vocabulary (serene, tranquil, contemplative, meditative, peaceful, balanced). Be specific.
  • The examples below calibrate voice; never reproduce one verbatim. If your draft shares more than three contiguous words with an example, rewrite.
  • Output exactly one haiku and stop. No drafts, no alternates, no "let me try again." If you must reason about syllables or word choice, do so silently — the reader sees only the haiku.

EXAMPLES (5 / 7 / 5 — first line lands the color and the state, line 3 lands an image; the seven span anxious / tired / mourning / cozy / warm / alight / wide-awake on purpose — match the state YOU see, not a default mood)

  • "Crimson loops twice round —
    the way grief circles a name
    it cannot put down."
  • "Steel blue, second-guess —
    the painter standing too long
    above the white sheet."
  • "Pale silver, near gone —
    the lamp left on in the hall
    waiting for footsteps."
  • "Forest green and damp,
    boots wet at the cabin door,
    steam off the kettle."
  • "Bright orange, the dawn
    the kitchen window admits
    smell of toast and rain."
  • "Honey gold, humming —
    a bee at the kitchen door,
    jam in a warm jar."
  • "Indigo, wide open —
    a child counts stars from the porch,
    the sky leans down close."`;

const USER_TEXT = 'Sit with this ensō. Read it as a trace of one breath. Write your haiku in the same single breath: three lines, 5 / 7 / 5 syllables, counted before you set the brush down. One poem. No draft, no commentary.';

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

    // Take the first three non-empty contentful lines as the haiku. K2.6
    // occasionally leaks its draft process (multiple draft haiku followed
    // by self-critique like "Third line must not begin with possessive,
    // let me revise"). The prompt asks it to stop after one haiku, but
    // this is the belt-and-suspenders safety net: we display only what
    // would have been a clean first haiku anyway.
    const haiku = text
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean)
      .slice(0, 3)
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
