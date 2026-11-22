// Offline cache for the field page: installed once at base, works with no network after.
// Pages and code: network first (fresh when online), cache when offline.
// The model, libraries and landmark cues: cache first (big, rarely change).
const CACHE = "near-field-v3";
const CORE = ["/field", "/static/common.css", "/static/field.js", "/static/modem.js", "/static/packet.js",
  "/static/phone.js", "/static/manifest.json", "/static/vendor/ort/ort.min.js",
  "/static/vendor/ort/ort-wasm-simd-threaded.wasm", "/static/vendor/ort/ort-wasm-simd-threaded.mjs",
  "/static/vendor/qr/qrcode.js", "/models/near-small/near_small.onnx", "/models/near-small/labels.json",
  "/api/cues", "/api/probe", "/api/config"];
const BIG = ["/models/", "/static/vendor/", "/api/cues"];

self.addEventListener("install", (e) => e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  if (BIG.some((p) => u.pathname.startsWith(p))) {
    e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
      const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return r; })));
    return;
  }
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
    return r;
  }).catch(() => caches.match(e.request)));
});
