{% autoescape off %}// Üretim Takip service worker – {{ surum }}
// Sayfalar her zaman sunucudan gelir (veriler güncel kalsın diye).
// Sunucuya ulaşılamazsa "bağlantı yok" sayfası gösterilir.
const ONBELLEK = "uretim-{{ surum }}";
const DOSYALAR = {{ onbellek }};
const CEVRIMDISI = DOSYALAR[0];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(ONBELLEK).then((c) => c.addAll(DOSYALAR)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((anahtarlar) => Promise.all(anahtarlar.filter((a) => a !== ONBELLEK).map((a) => caches.delete(a))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const istek = e.request;
  if (istek.method !== "GET") return;

  if (istek.mode === "navigate") {
    e.respondWith(fetch(istek).catch(() => caches.match(CEVRIMDISI)));
    return;
  }
  const url = new URL(istek.url);
  if (url.origin === location.origin && url.pathname.startsWith("/static/")) {
    e.respondWith(caches.match(istek).then((kayitli) => kayitli || fetch(istek)));
  }
});
{% endautoescape %}
