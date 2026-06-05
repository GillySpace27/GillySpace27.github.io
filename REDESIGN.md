# gilly.space — Redesign Proposal: **Heliostatic**

*One ink-on-paper design system, one persistent nav, every page reachable —
promoting the site's own best work to be its house style.*

> Produced 2026-06-05 by a multi-agent analysis of the whole repository
> (6 inventory auditors → 4 independent creative directors → synthesis →
> adversarial verification). Three other directions were considered and folded
> in or set aside: **Heliosphere** (the scientist's portfolio), **The Observable
> Universe** (a navigable cosmos of the toys), and **Currents of Space** (a
> scrollytelling home). Heliostatic is the recommended synthesis.
>
> **One caveat on §5:** the analysis sandbox had no `node` on its PATH, so the
> proposal hedges toward a zero-build approach. Your project `CLAUDE.md` says
> `node` *is* installed on your Mac (it runs `enso/build_calendar.js`), so the
> build-time path in §5/§7.5 is likely viable — treated here as your call, not
> a hard blocker.

---

## 1. The big idea

The strongest design decision for gilly.space has already been made — it's just trapped inside three toys. The enso calendar, the enso editor, and Spectrum Sudoku independently converged on the same modern, hand-built, dependency-free recipe: CSS custom properties as the single source of styling truth, a paired light/dark palette, a pre-paint inline bootstrap that kills the flash-of-wrong-theme, the system font stack, gold-on-ink restraint, and tasteful interaction states. Meanwhile the legacy Strata pages are frozen in 2015, riding a dead jQuery/skel.js/poptrox stack, IE8 polyfills, and a Google Analytics property that stopped collecting data in July 2023. The site is two stacks pretending to be one.

The recommended direction, **Heliostatic**, is therefore an act of *recognition, not invention*. A heliostat is the instrument that holds a steady image of a moving Sun; this redesign holds one steady visual identity across a site that has accreted for a decade. We extract the enso palette — warm paper `#faf8f3`, deep ink-navy `#1a2a5a`, a single gold accent `#d9a91a`, and the proven dark twin `#1a1814` — into one hand-authored stylesheet, give the whole site a real persistent navigation bar for the first time in its history, and re-skin every legacy page on top of that system. The aesthetic isn't borrowed from a template; it's *Gilly's own taste, already shipped and already loved*, finally applied past the toys. The register it lands in — ink on good paper, one accent, generous whitespace — is exactly where serious typography-first academic homepages live, which is what the front door needs to be.

What makes this more than a reskin is that it solves the site's two structural failures at once: there is no site-wide navigation anywhere (you reach a subpage only by clicking a homepage tile and return only via the avatar), and the genuinely impressive work — the live RHE/RHEF Sun viewer that is Gilly's own published science, the daily AI-haiku enso, the **live Solar Archive print store**, the never-linked 79 MB thesis, the commented-out GHOSTS paper — is buried, orphaned, or unreachable from the front door. Heliostatic builds **one nav, one palette, one head**, surfaces every hidden gem, gives the live store a real home, and gathers the genuinely-dead artifacts into an honest linked archive so the no-delete promise is met literally. The pun the domain has been quietly making for ten years — *a heliophysicist, fittingly, at gilly.SPACE* — finally gets to be the identity instead of an accident in the CNAME file.

*(Where this synthesis draws a line: it adopts the maintainability spine and unified-token discipline as the backbone, grafts the "Scientist's Portfolio" content priorities, takes the tasteful heliophysics framing and the "promote the toys" thesis, and deliberately drops a full-site immersive scroll — that's more bespoke code to own and worse for the program-officer-scanning-for-a-CV use case an academic front door must serve.)*

---

## 2. What's there now

The honest diagnosis is that the **content is strong and the shell is broken**. Every page hand-copies its own `<head>` and header because the intended shared-header mechanism — `navbar.shtml` and `headerScript.ssi` — relied on Server-Side Includes, which GitHub Pages does not process. Those files are inert, unreferenced, and have already drifted out of sync with the pages that were supposed to inherit from them. The result is per-page copy-paste that has diverged: footers alternate between "© Dr. Gilly" and "© Chris R. Gilly," the email is `chris.gilly@colorado.edu` (a grad-student address he's years past, now at NWRA), and the affiliation throughout still says CU Boulder / LASP. `sun.html` literally calls him a "Graduate Researcher" at LASP and cites his own RHE method as "Gilly & Cranmer 2024, in prep" — a method that now ships in sunpy's `sunkit-image` as `rhef`.

The technical floor is dead weight: jQuery 1.11.3 (2015, with published XSS advisories), the discontinued skel.js framework, poptrox, Font Awesome 4, IE8 conditional-comment shims (html5shiv, respond.js, PIE.htc), and the `UA-82880034-1` analytics tag — all loaded on the legacy pages, none of it doing anything useful. There's no `<meta name="description">`, no Open Graph beyond a single *relative* `og:image` (which breaks every social-card preview), no canonical link despite the site serving identical content on **four hostnames** (`gilly.space`, `www.gilly.space`, `chrisgilbert.space`, `www.chrisgilbert.space`), and no sitemap or robots.txt. There are 90-plus images with empty `alt=""`, invalid markup (a bare text node inside `<ul class="icons">`), and `shineVideo.html` has no `<title>` at all.

One important nuance the audit must get right: **not everything that looks like a stub is dead.** `shop.html` was deliberately retargeted **three days ago** (the single most recent content change in the entire repo) to point at the **live, actively-maintained Solar Archive print store** at `solar-archive.onrender.com` — a real product with its own Render-hosted feedback-admin backend. It still drags the old AWS-SDK Sun-viewer chrome and the dead analytics tag before it bounces, but its *destination is current and revenue-relevant*. It is **not** cruft and must not be treated as such (see §3). By contrast, the genuinely-orphaned siblings are: `index_withvideo.html` (a dead grad-era alternate homepage), `shineVideo.html` (a byte-identical clone of `Kelvin.html`), and `evan/` (a colleague's stale page).

The real treasures are hidden: `Kelvin.html` (genuinely good KH-instability science writing) sits three clicks deep; `Space-Is-Full.html` (the Asimov/Parker essay that is the conceptual heart of the whole pun) is reachable only from the Talks page; the GHOSTS paper PDF exists at `papers/Gilly&Cranmer2020.pdf` but its only link is **commented out** at `Research.html` line 60; the 79 MB thesis is committed but **never linked** (visitors are sent to a ProQuest paywall instead); and the enso calendar, enso editor, and sudoku are **not reachable from the homepage at all**. Add a duplicate CV (`CV.pdf` and `CV_2024.pdf` are byte-for-byte identical, MD5-confirmed, and the "Complete CV" shown is actually the *oldest* of the live ones), plus the orphaned media (`files/quad.mp4`, `files/windowPlot3.mp4` — real MP4 blobs, not linked from any page), plus committed cruft, and you have a site whose problems are entirely in presentation and plumbing, never in substance.

A subtle but verified plumbing contradiction deserves its own callout, because it's silently corrupting the repo today:

- **`.gitignore` is a no-op against everything it lists.** Its lines (`*.mov`, `*.mp4`, `*.config`, `*.scss`, `.DS_Store`) are all dead — every file they name is *already tracked* and committed: `.DS_Store`, both MP4s, all six `.scss` sources, the `.vs/` config, the two Dropbox "conflicted copy" files, `Website.code-workspace`, `websiteSolution.sln`, and three zips. Adding rules without untracking the files means the rules do nothing.
- **Git LFS is declared but inactive.** `.gitattributes` routes `*.mov`/`*.mp4` through `filter=lfs`, but `git lfs ls-files` is empty and `files/quad.mp4` is a real binary blob in history, not a pointer. The LFS attribute and the `*.mp4` gitignore line are *mutually contradictory and both inert* — any new MP4 today would be mis-handled by both. This is a present-tense correctness bug, not a someday-maybe.

The one bright spot — and the whole basis of this plan — is the modern cluster: the enso toys and the single Cloudflare Worker (`enso-impressions`, Workers AI haiku + KV cache) are clean, vanilla, zero-dependency, git-push-to-deploy, and beautifully made. They prove the legacy stack is fully isolable and removable page by page.

---

## 3. Proposed information architecture

The central fix is **one persistent top nav, identical on every page**, so lateral movement (Research → The Sun → Play) finally works and nothing is an island. Six primary slots absorb every existing page. The wordmark returns home; a theme toggle and the academic-icon row (arXiv / ORCID / ADS / GitHub / LinkedIn / email) dock to the right and — crucially — *stop disappearing on subpages*.

**Top nav:** `gilly.space` (wordmark → home) · **Research** · **The Sun** · **Outreach** · **Play** · **Store** · **About / CV** · [theme toggle] · [icon row]

> **Note on "Store":** this is the single most important IA correction. The live Solar Archive print store is a current, maintained product tied directly to the `sun.html` RHE imagery, and it gets a **real first-class destination**, not the attic. It can ride as its own top-nav slot (shown above) or, if six items feels heavy, nest as a prominent card *inside* "The Sun" — Gilly's call (Open Choices §7.6). Either way it is **featured**, and `shop.html` is **rebuilt**, not archived: stripped of the AWS-SDK chrome and dead analytics, re-skinned onto `site.css`, kept as the clean on-site landing that links out to `solar-archive.onrender.com`. (Its existing favicon/manifest/verification head set, which is currently the *most complete* in the repo, is preserved through the migration — see §5.)

Here is exactly where every current file lands. **Every page keeps its existing filename and URL** so inbound links, bookmarks, and Search Console entries never 404 — the redesign re-skins in place.

**Home** — `index.html` (rewritten; content preserved). Identity, research statement, the credential row promoted into the persistent header, a small set of "selected highlights" cards (Sun viewer, latest paper, the store, a toy), and quiet links into all sections.

**Research** — a hub linking:
- `Research.html` ("Current Research," refreshed to NWRA / PUNCH / RHEF / GHOSTS / DKIST / AIA-desaturation; **the GHOSTS PDF link at line 60 is uncommented**).
- `PastResearch.html` ("Earlier & student work"). **`Kelvin.html` is single-sourced here as its one canonical home** (URL `Kelvin.html`, owned by PastResearch). Research links to it by URL only — never a copied teaser — so there is exactly one place to maintain. Its byte-identical clone `shineVideo.html` is archived (§ Archive) *after* confirming Kelvin is the kept copy, closing the duplicate-maintenance trap for good.
- A new lightweight **`publications.html`** — the single biggest missing credibility asset. Reverse-chronological static list with DOI / ADS / arXiv / *local-PDF* links: GHOSTS (`papers/Gilly&Cranmer2020.pdf`, finally linked), the **thesis** (`files/thesis/Chris_R__Gilly_Thesis_Full-protected.pdf`, finally linked beside ProQuest), RHEF/sunkit-image, in-prep RHE.
- The conference posters in `files/` (AGU 2018/19, SHINE 17/18/19, AAS SPD 2020, Belfast SOLARNET) and `Overview_PUNCH.pdf` get a tidy responsive "Talks & Posters" subsection. As part of this pass, the two orphaned MP4s (`files/quad.mp4`, `files/windowPlot3.mp4`) are **checked against the science pages** — if either is a figure animation for GHOSTS/RHE/Kelvin work it gets embedded in a responsive wrapper here; if neither has a home, they are explicitly re-homed into the Archive with a provenance note rather than left floating. They do not stay orphaned after the redesign.

**The Sun** — `sun.html` (the live RHE/RHEF S3 viewer; AWS-SDK/Cognito logic untouched, only re-skinned, affiliation corrected to NWRA, "in prep" citation fixed) as the flagship. `resources.html` (the solar-links directory) lives here too **but as a clearly-labeled sub-tab / secondary "Solar resources" link, not co-equal with the viewer** — it's a utility link list, so it sits one notch below the signature interactive gem rather than diluting the section's identity. Top-level because "a heliophysicist at gilly.SPACE" *is* the brand. If the store nests here rather than taking its own nav slot, it sits beside the viewer as a featured "Prints" card.

**Outreach** — `RecordedPublicTalks.html` (the four Fiske/NASA videos in responsive `16:9` wrappers) + `Space-Is-Full.html` **promoted to a featured banner** — the essay that is the site's whole pun, currently buried.

**Play** *(new hub, `play/index.html`)* — the toys finally get a front door: the **enso calendar** (`enso/index.html`), the **enso editor** (`enso/pixelated-enso.html`), **Spectrum Sudoku** (`sudoku/index.html`), and a cross-link to the live Sun viewer. Each gets a real card, description, and OG image. This single page fixes the largest discoverability gap in the audit.

**About / CV** — bio + current NWRA affiliation + the CV cluster *de-duplicated by labeling, not deletion*: **Research CV** (`CV_Research_2025.pdf`), **Teaching CV** (`CV_Teaching_2025.pdf`), and **Complete CV** (newest), with a transparent note that `CV.pdf`/`CV_2024.pdf` are the 2024 vintage and `CV.docx` is the editable source. Plus `Music-and-Theater.html` (SoundCloud, `Plays.pdf`, the skit) and `skitPage.html` under a "beyond the science" note. A short **Colophon** tells the no-npm / one-Worker story, **carries the HTML5 UP CCA-3.0 attribution** the Strata template requires (see §5), and surfaces two genuine hidden gems: the enso worker's ~50-line haiku system prompt (a meditation on *ensō / mushin / ma*), and the **byte-identical determinism contract** — that the calendar and editor reproduce the same daily enso from the same PRNG draw sequence, the most impressive engineering story on the site and exactly the kind of technical depth worth showing.

**Archive** *(new, `archive/index.html`)* — the no-delete safety valve for genuinely-historical files: `index_withvideo.html` ("Archived 2023 homepage"), `shineVideo.html` ("Early duplicate of the Kelvin page — superseded; Kelvin.html is canonical"), `evan/index.html` ("Collaborator's page — Evan Anders," broken `posters/` link flagged), the older `CV_2024.pdf` and `Gilly&Cranmer2020-old.pdf`, any unembeddable orphaned MP4, and a provenance note for `README.txt` and the dead SSI files. **`shop.html` is NOT here** — it is a live store and lives in the nav (above). To keep the Archive genuinely reachable on a no-delete site, it is linked **both** from the shared footer **and** from a small "Archive" link in the About/CV hub body — not footer-only — and because the shared header/footer are baked into static HTML (see §5), the Archive's inbound links are crawlable, not JS-gated.

> **One thing to surface, not decide silently:** `evan/index.html` hosts another person's stale page (with their contact details) under Gilly's domain. The no-delete rule means we *preserve* it by default, but this is flagged explicitly for Gilly to choose — keep hosting it, or replace it with a one-line "page retired, contact Evan at …" stub — rather than quietly re-homing someone else's personal data.

The net: from any page you reach any other page in one or two clicks; every one of the ~19 pages plus all PDFs, CVs, posters, MP4s, and toys has exactly one obvious home; the live store is a featured destination; and the buried gems move from orphaned to featured.

---

## 4. Visual & interaction design

**The token system is the design.** One `:root` block holds the canon — lifted verbatim from the enso calendar so the toys and the site share a single source of truth and a single dark mode:

```
Light:  --bg #faf8f3 (warm paper)  --text #1a2a5a (ink-navy)  --muted #555
        --card-bg #fff  --card-border #ddd  --accent #d9a91a (gold)
Dark:   --bg #1a1814   --text #e8e2d0       --card #25221c     --accent #d9a91a
```

Every legacy hardcoded hex collapses into these tokens. Gold is used sparingly and with intent: links, the active nav item, the focus-visible ring, section rules. The effect is "ink on good paper" by day, "deep space" by night.

**Typography** is the enso/sudoku system stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui`) for body and UI — zero webfont fetch, which also kills the current mixed-content bug where `main.css` `@import`s Source Sans Pro over insecure `http://`. A fluid `clamp()` type scale (the sudoku title trick — `clamp(26px, 5vw, 38px)`) gives responsive headings with no breakpoints. Prose pages (Space-Is-Full, Kelvin) get a real `~68ch` reading measure instead of inline `margin:5%`. A self-hosted display serif is offered as an *opt-in* personality lever in §7, not a default — keeping the baseline zero-new-asset.

**Layout** replaces skel's `6u 12u$(xsmall)` classes with plain CSS Grid — the same `repeat(auto-fit, minmax(min(100%, 260px), 1fr))` auto-fit pattern the enso editor already uses. One `.card` component (12px radius, 1px border, the enso shadow, a `translateY(-1px)` hover lift) serves the work tiles, poster wall, talk embeds, store card, and toy cards. A single `.embed-16x9 { aspect-ratio: 16/9 }` utility fixes the four fixed-`560×315` YouTube iframes and the `1000px`-wide Kelvin GIFs that currently overflow phones.

**Dark mode** is the proven cross-page contract already shared by the calendar and editor: the same `enso-theme` localStorage key, the same three-state `system | light | dark` model, the same ~10-line pre-paint inline bootstrap that sets `.dark` on `<html>` before first paint. Promoted into the shared head, *every* page gets flash-free dark mode for free, and a dark preference set on the calendar carries to the homepage and back.

**Motion** is restrained and borrowed from what's shipped: 0.15s hover/focus transitions, the calendar's blurred-backdrop modal with ESC/click-out (replacing poptrox), the calendar's spinner. No skel parallax (it scroll-janks on mobile). `prefers-reduced-motion` is respected as a hard requirement.

**Signature moves that make it memorable** (heliophysics-forward, but disciplined): a single hairline brushstroke — the enso motif — as the section divider, tying the science home to the generative-art wing with zero heavy assets; a live "the Sun, right now" RHE thumbnail and/or today's deterministic enso on the homepage so the front door is literally *alive*; and the gold accent as a quiet corona color throughout. Accessibility is baked into the system, not bolted on: a skip-link, real `<main>`/`<nav>` landmarks (none exist today), `aria-current` on the active nav item, `lang="en"`, required `alt` slots on the card component, `title` on the YouTube/S3 iframes, valid `<ul><li>` icon lists, and the sudoku-grade colorblind sensibility as the bar to clear.

---

## 5. Technical plan

Everything stays static on GitHub Pages, npm-free, vanilla, with the **one existing Worker untouched**. New hand-authored assets do all the work.

### (1) `assets/site.css` (~500–600 lines, hand-written, no Sass/build)

The token block (light + dark), the type scale, and the grid / card / button / nav / footer / embed / prose components. This becomes the source of truth for re-skinned pages, *replacing* the template `main.css`. Per the no-delete rule, `main.css`, the whole `assets/sass/` tree, and `bkk/main.css` stay on disk — pages simply stop linking the old CSS as they migrate, so any not-yet-migrated page still renders exactly as today.

### (2) The shared header/footer — the no-SSI answer

The dead `navbar.shtml`/`headerScript.ssi` approach failed because Pages can't run SSI. There are two no-npm replacements, and the honest tradeoff must be stated plainly:

> **You cannot have BOTH zero-build AND fully-crawlable shared nav on GitHub Pages.** A build step that bakes nav into static HTML is crawlable; a client-side `fetch()` that injects nav at runtime is JS-dependent and largely invisible to crawlers. Pick one with eyes open.

- **Option A — zero-build, JS-injected partials.** A small `assets/site.js` (~40 lines, no jQuery) `fetch()`-injects `partials/header.html` and `partials/footer.html` into placeholder elements on each page and marks the active link. No `node` ever required; every header/footer/meta edit is a plain text edit. The cost — nav is JS-dependent and crawlers may not follow fetch-injected lateral links — is mitigated three ways: (a) every page keeps a real `<noscript>` home link and its own `<title>`/`<meta description>`/canonical baked into static HTML, so each page is independently indexable; (b) crawlability of the section graph is restored by the hand-written `sitemap.xml` (below), which lists every URL explicitly; and (c) the inline pre-paint theme snippet stays inline (never deferred) so dark mode never flashes.
- **Option B — build-time injection (your `node` is available, so this is real).** A tiny zero-dependency `tools/build_site.js` (modeled on `enso/build_calendar.js`) injects the shared head/header/footer between marker comments and commits baked-in static HTML, making the nav natively crawlable. The honest caveat: this mutates ~17 living hand-authored source files in place — riskier text-surgery than `build_calendar.js` (which extracts from one file and writes one generated file), and exactly the multi-file mutation that CLAUDE.md gotcha #1 warns about. So it ships with a loud "generated — do not edit between markers" banner, a control-count assertion, and a git-diff review gate.

Both are viable on your stack. The choice is SEO-crawlability-of-nav (Option B) vs. never-touch-node-for-a-text-edit (Option A); see §7.5. The sitemap makes the SEO gap small either way.

### (3) `partials/header.html` + `partials/footer.html` + the canonical `<head>` set

Single source of truth for nav, footer, the academic-icon row (as **valid** markup, fixing the bare-text-in-`<ul>` bug), the canonical copyright, the theme toggle, and **the HTML5 UP attribution credit line** (satisfying the CCA-3.0 license once the per-page Strata template comment is removed; `LICENSE.txt` stays at root untouched).

**The shared `<head>` partial is explicitly committed to carrying forward the complete existing head asset set — authored from `shop.html`'s head (the most complete in the repo), NOT the enso head (which has none of these).** Enumerated, the partial **must** include, verbatim and site-wide:

```
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/manifest.json">
<link rel="mask-icon" href="/safari-pinned-tab.svg" color="#5bbad5">
<meta name="theme-color" content="#ffffff">   <!-- light; paired dark via media -->
<meta name="google-site-verification" content="gBmU3RrJO0EJM2ZK92nWp1mKEWWL5MvmJLVxTDAgF-c">
```

Plus the root files these reference, all of which **stay in place and untouched**: `favicon.ico`, `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`, `mstile-150x150.png`, `safari-pinned-tab.svg`, `manifest.json`, and `browserconfig.xml`. **The Search Console verification stub `google690400622efc7ebc.html` at the repo root is preserved exactly** — it is what authorizes the new sitemap submission, so it cannot be touched, and the `google-site-verification` meta above is carried into the partial as belt-and-suspenders. **`manifest.json` is edited only to fix the `"Chris Gilbert"` name to current branding** — its presence and wiring are otherwise preserved so PWA install and the favicon set do not silently regress anywhere.

### (4) Legacy stack removal, page by page

Migrated pages drop jQuery + skel.js + poptrox + util.js + main.js + the IE8 conditional shims entirely — the toys prove none of it is needed. `sun.html` keeps its AWS-SDK S3 viewer (a real feature, re-skinned only). `shop.html` keeps its store-redirect behavior but sheds the AWS-SDK chrome it no longer needs. Nothing is `git rm`'d. **Right-sizing the effort:** the lowest-value pages (`skitPage.html`, and the rebuilt `shop.html` landing) need only a minimal head-partial + nav graft, not a full bespoke reskin — full migration energy goes to the homepage, the science core, and the toy hub.

### (5) Analytics

Remove the dead `UA-82880034-1` tag site-wide. If Gilly wants tracking, **Cloudflare Web Analytics** (privacy-friendly, cookieless, no consent banner, already in his ecosystem) over GA4 — a taste call, see §7.

### (6) SEO / social / health

The head partial adds per-page `<title>`, `meta description`, `og:title/type/url/description`, an **absolute** `og:image`, `twitter:card=summary_large_image`, and a `<link rel="canonical">` to the single chosen host — resolving the four-hostname duplicate-content problem. Hand-write `sitemap.xml` + `robots.txt` (static files, no build) — the sitemap doubles as the crawlability backstop for the JS-injected nav — and submit via the already-verified Search Console property. Add `loading="lazy"` to the YouTube iframes and the big Kelvin GIFs. **Ship a `404.html`** — GitHub Pages serves it automatically — carrying the shared nav so old or typo'd URLs land somewhere navigable instead of GitHub's bare default.

### (7) Optional live Publications (within the one-Worker budget)

If Gilly wants publications genuinely live, *extend the existing `enso-impressions` Worker* with a `GET /publications` route that queries NASA ADS by ORCID (`0000-0003-0021-9056`), normalizes to JSON, and caches it. Three caveats made explicit so it isn't hand-waved: (a) the cache key must be **namespaced away from the `impression:YYYY-MM-DD` keys** (e.g. `pub:ads-orcid`) so it never trips the worker's date-regex cache-key validation; (b) the **ADS token expires and must be rotated** — stored as a Worker secret, with a note in CLAUDE.md on where to refresh it; (c) the route needs its own daily-TTL handling. `publications.html` ships a hand-authored static list as the guaranteed fallback and enriches on load. **This is optional and de-emphasized — a hand-maintained static list is the recommended default and adds zero infrastructure.**

### (8) Phase 0 cruft + correctness fixes (no deletions, no history rewrite)

The verified contradictions from §2 become concrete fixes, not future options:

- **Make `.gitignore` real.** Replace it with rules that match the actual junk (`.vs/`, `.idea/`, `.vscode/`, `*.sln`, `*.code-workspace`, `*.zip`, `.DS_Store`) **and `git rm --cached`** the already-tracked files those rules name, so the rules finally take effect. The bytes are *moved* into `archive/_repo-cruft/` (the three zips incl. `bkk/academicons-1.8.6.zip` and `favicons.zip`, the `.idea/`+`.vs/`+`.vscode/` folders, the two Dropbox "conflicted copy" files, `websiteSolution.sln`, `Website.code-workspace`) rather than purged from history.
- **Reconcile the LFS lie.** `.gitattributes` routes `*.mp4`/`*.mov` through LFS but LFS is inactive and the same files are also `*.mp4`-gitignored — a triple contradiction. Resolve it now: since the user has no npm and likely no `git-lfs`, **remove the inert `filter=lfs` attributes** and the blanket `*.mp4` gitignore line, then decide the two real MP4s' fate explicitly in §3 (embed on a science page, or re-home to Archive).
- **`bkk/` is content-vs-cruft, fully accounted for.** It holds both a zip *and* a full extracted second academicons font tree (`bkk/academicons-1.8.6/`) plus a near-twin `bkk/main.css`. The zip moves to `archive/_repo-cruft/`; the extracted font tree and `bkk/main.css` are kept on disk under no-delete but are *not linked by any migrated page* (the live site uses the canonical `assets/css/academicons.min.css`), with a one-line note in the Archive provenance so a future reader knows it's a superseded duplicate, not an active dependency.
- **Drift fixes.** Worker health-string and CLAUDE.md reconciled to the live model; `manifest.json` name corrected; footer email (`→ NWRA`) and copyright normalized across pages.

The 79 MB thesis stays reachable (now *linked*, finally); Git-LFS-or-external-hosting for the heavy binaries is flagged as a *future* lever, distinct from the present-tense LFS-attribute fix above.

---

## 6. Phased roadmap

Each phase leaves the site strictly better, so Gilly can stop after any one.

**Phase 0 — Foundations, plumbing truth, & quick wins (one sitting, near-zero visual change, near-zero risk).**
Author `assets/site.css` (enso light+dark tokens, type scale, grid/card/nav/footer/embed components). Write `partials/header.html` + `partials/footer.html` + the enumerated canonical `<head>` set (favicons/manifest/mask-icon/theme-color/verification all carried forward) + the HTML5 UP attribution line. Write `assets/site.js` (the zero-build fetch injector). **Fix the verified repo contradictions:** make `.gitignore` real and `git rm --cached` the tracked junk into `archive/_repo-cruft/`; remove the inert LFS attributes and the contradictory `*.mp4` gitignore; account for `bkk/`. Fix the cheap correctness wins: **uncomment the GHOSTS link** (`Research.html:60`), **link the local thesis PDF**, add a `<title>` to `shineVideo.html`, fix `sun.html`'s LASP→NWRA affiliation and the "2024, in prep" citation, normalize footer email/copyright, fix the `manifest.json` name, reconcile the worker/CLAUDE.md drift, fill in `README.md`. Nothing user-facing is restyled yet — pure groundwork plus high-value fixes that ship value before any redesign.

**Phase 1 — Ship the shell + the first real nav (highest leverage).**
Wire `assets/site.js` + the partials into every page (placeholders + the inline pre-paint theme snippet + `<noscript>` home link). Re-skin **`index.html`** as the portfolio home (identity + credential row + selected-highlights cards incl. the store + quiet section links), drop jQuery/skel/poptrox from it, add real `alt` text. Add `sitemap.xml`, `robots.txt`, and **`404.html`**; submit the sitemap via the verified Search Console property. After this phase the site has navigation, a shared theme, fixed social cards, a featured store link, graceful 404s, no dead analytics, and no duplicate-content ambiguity — the two biggest structural failures are gone.

**Phase 2 — Migrate the academic core, the store, + surface the toys.**
Re-skin `Research.html`, `PastResearch.html`, `Kelvin.html` (confirmed single-sourced as canonical before its clone is archived), `resources.html`, `sun.html` onto `site.css` + the partials; build the **Research** and **The Sun** hub landings; ship **`publications.html`** (static list linking local PDFs + ADS/arXiv); **rebuild `shop.html`** as the clean re-skinned store landing and wire its nav slot. Build the **`play/index.html`** hub and add a quiet "← gilly.space" back-link into each of the three toys. Resolve CV sprawl by labeling on About/CV. Clean `resources.html` markup; add responsive embeds + `loading="lazy"`; resolve the two orphaned MP4s (embed-or-archive).

**Phase 3 — Outreach, creative, archive, polish.**
Re-skin `RecordedPublicTalks.html`, `Space-Is-Full.html` (move source-URLs out of `alt` into real `<figcaption>` credits, elevate into Outreach), `Music-and-Theater.html`, `skitPage.html` (minimal). Stand up `archive/index.html` linking `index_withvideo.html`, `shineVideo.html`, `evan/` (with the third-party-data decision surfaced to Gilly), the SSI/README provenance, and any unembeddable MP4 — linked from both the footer and the About/CV body. Write the **Colophon** (no-npm story, CCA-3.0 attribution, the haiku prompt, the determinism contract). Final accessibility pass (skip-links, iframe titles, focus rings, alt sweep), mixed-content `http→https` fixes, and a Lighthouse/contrast check against the sudoku-grade bar. *Optional add-ons:* the live-Publications Worker route and a self-hosted display serif.

---

## 7. Open choices for Gilly

These are the genuine taste decisions where your input should come before building.

1. **Canonical hostname.** Four domains, one canonical needed. `gilly.space` is the brand and the pun; `chrisgilbert.space` is the professional-name fallback. Recommended: **`https://gilly.space`** canonical with the others as aliases — flip it if you'd rather lead with your legal name for grant/hiring discoverability. Baked into every `<link rel="canonical">`, so decide once.

2. **Analytics: Cloudflare Web Analytics, GA4, or none.** The dead UA tag goes regardless. Lean **Cloudflare Web Analytics** (cookieless, no consent banner, already your ecosystem); GA4 or nothing are both fine.

3. **How "live" Publications should be.** Hand-maintained static list (recommended, zero-infra) vs. the cached ADS proxy on the existing Worker (auto-updating from your ORCID, at the cost of one route + a rotating ADS token). Ship static and treat live as a later add-on — confirm if you want otherwise.

4. **One display serif, or system-only.** A self-hosted serif (Fraunces/Newsreader, woff2, no CDN) gives headings literary gravitas at the cost of one small binary asset; system-only ships zero new assets and is faster. Minor, but it sets every heading's personality — worth a glance at one mock first.

5. **Build mechanism: zero-build JS nav, or `node` build-time injection.** Your `CLAUDE.md` confirms `node` is on your Mac, so both are real. **Option A (zero-build):** never touch node for a text edit; nav is JS-rendered (sitemap carries crawlability). **Option B (`node` build):** nav baked into static HTML, natively crawlable, at the cost of running a build script and guarding multi-file mutation. Pick the value you weigh higher: zero-ceremony edits vs. maximal SEO crawlability of the nav graph.

6. **Store placement: sixth nav slot, or nested in "The Sun."** The live Solar Archive store is featured either way. A dedicated **Store** nav item maximizes prominence (good for a revenue/print outlet); nesting it as a "Prints" card inside The Sun keeps the nav to five items and ties it visually to the RHE imagery it sells. Leaning toward the dedicated slot given it's your only commercial outlet and was just updated — your call.

7. **`evan/index.html`: keep hosting, or retire to a stub.** No-delete means we preserve it by default in the Archive, but it's someone else's stale page with their contact info under your domain. Keep it as-is, or replace with a one-line "page retired" stub that still satisfies preservation? Your call — flagged, not decided for you.

8. **The homepage hero — restrained, or a touch of drama.** The portfolio default is a calm, instant-loading hero (avatar + identity + credential row + a small live Sun/enso thumbnail). A homepage-*only* full-bleed RHE Sun with a short scroll-reveal of the "Space Is Full" opening is available as a flourish, but leaning **against** it for now — the primary front-door use case is a program officer scanning for your CV, and it's bespoke code to own. Easy to add later if you want it.
