/* ============================================================================
   gilly.space — analytics.js  (single source of truth for site analytics)
   ----------------------------------------------------------------------------
   Loaded on EVERY page: the shell pages pull it in via assets/site.js; the
   standalone toys (enso/, sudoku/) reference it directly in their <head>.

   Fill in the two IDs below to switch tracking on. Leave a value '' to disable
   that provider. No-op until at least one is set — safe to ship empty.
     • CF_BEACON_TOKEN — Cloudflare Web Analytics (cookieless, no consent banner)
     • GA4_ID          — Google Analytics 4 Measurement ID (looks like G-XXXXXXX)
   Running both in parallel is intentional (compare, drop the weaker later).
   ============================================================================ */
(function () {
  var CF_BEACON_TOKEN = '684268c9d5304fca8d70c30737ed2be7';   // Cloudflare Web Analytics (gilly.space)
  var GA4_ID          = 'G-QV87BEFHZ6';   // Google Analytics 4 (gilly.space)

  try {
    if (CF_BEACON_TOKEN) {
      var c = document.createElement('script');
      c.defer = true;
      c.src = 'https://static.cloudflareinsights.com/beacon.min.js';
      c.setAttribute('data-cf-beacon', JSON.stringify({ token: CF_BEACON_TOKEN }));
      document.head.appendChild(c);
    }
    if (GA4_ID) {
      var g = document.createElement('script');
      g.async = true;
      g.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA4_ID;
      document.head.appendChild(g);
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { dataLayer.push(arguments); };
      window.gtag('js', new Date());
      window.gtag('config', GA4_ID);
    }
  } catch (e) { /* analytics must never break the page */ }
})();
