/* ============================================================================
   gilly.space service worker — offline-resilient, instant repeat visits.
   ----------------------------------------------------------------------------
   Strategy:
     • Precache the shared shell (CSS, JS, partials, icon fonts, favicons).
     • HTML  → network-first (fresh content), falling back to cache then /404.html.
     • Other same-origin GETs → stale-while-revalidate (fast, self-healing).
     • Cross-origin (S3 sun images, the worker, fonts CDN) → left to the network.
   Bump CACHE_VERSION to invalidate. Registered from assets/site.js behind a
   feature check, so no-JS / unsupported browsers are unaffected.
   ========================================================================== */
const CACHE_VERSION = 'gilly-v1';
const PRECACHE = [
  '/', '/assets/site.css', '/assets/site.js',
  '/partials/header.html', '/partials/footer.html',
  '/assets/css/academicons.min.css', '/assets/css/font-awesome.min.css',
  '/favicon-32x32.png', '/apple-touch-icon.png', '/manifest.json', '/404.html'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_VERSION)
      .then((c) => Promise.allSettled(PRECACHE.map((u) => c.add(u))))   // never fail install on one missing asset
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                 // don't touch cross-origin (S3, worker, fonts)

  const isHTML = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');

  if (isHTML) {
    // network-first so content stays fresh; fall back to cache, then offline 404
    e.respondWith(
      fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(CACHE_VERSION).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req).then((m) => m || caches.match('/404.html')))
    );
    return;
  }

  // static assets: stale-while-revalidate
  e.respondWith(
    caches.match(req).then((cached) => {
      const net = fetch(req).then((res) => {
        if (res && res.status === 200) { const copy = res.clone(); caches.open(CACHE_VERSION).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => cached);
      return cached || net;
    })
  );
});
