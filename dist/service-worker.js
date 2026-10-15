const CACHE_NAME = 'nada-ai-shell-v3';
const SHELL = [
  '/',
  '/index.html',
  '/styles.css',
  '/frontend/app.js',
  '/frontend/api.js',
  '/frontend/status.js',
  '/frontend/voice-engine.js',
  '/frontend/account-browser.js',
  '/frontend/company-builder.js',
  '/brand-mark.svg',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/oauth/') || url.pathname === '/mcp') return;
  event.respondWith(fetch(event.request).then((response) => {
    if (event.request.method === 'GET' && response.ok) {
      const copy = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
    }
    return response;
  }).catch(() => caches.match(event.request).then((cached) => cached || caches.match('/index.html'))));
});
