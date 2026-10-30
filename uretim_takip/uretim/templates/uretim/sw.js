{% autoescape off %}// Üretim Takip service worker – {{ surum }}
// Sayfalar her zaman sunucudan gelir (veriler güncel kalsın diye).
// Sunucuya ulaşılamazsa "bağlantı yok" sayfası gösterilir.
const ONBELLEK = "uretim-{{ surum }}";
const DOSYALAR = {{ onbellek }};
const CEVRIMDISI = DOSYALAR[0];
const PAYLASILAN = "paylasilan";  // WhatsApp vb.'den "Paylaş" ile gelen fotoğraflar (paylaş sayfası okur)
const PAYLAS_ADRESI = "{{ paylas }}";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(ONBELLEK).then((c) => c.addAll(DOSYALAR)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((anahtarlar) => Promise.all(anahtarlar.filter((a) => a !== ONBELLEK && a !== PAYLASILAN).map((a) => caches.delete(a))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const istek = e.request;
  if (istek.method === "POST" && new URL(istek.url).pathname === PAYLAS_ADRESI) {
    // Android "Paylaş → Üretim Takip": fotoğrafları sakla, paylaş sayfasına geç (sipariş seçilince yüklenir)
    e.respondWith((async () => {
      const veri = await istek.formData();
      const dosyalar = veri.getAll("fotograflar").filter((d) => d && d.size);
      await caches.delete(PAYLASILAN);
      const kap = await caches.open(PAYLASILAN);
      await Promise.all(dosyalar.slice(0, 3).map((d, i) => kap.put(`/paylasilan/${i}`,
        new Response(d, { headers: { "Content-Type": d.type || "image/jpeg", "X-Ad": encodeURIComponent(d.name || `foto${i}.jpg`) } }))));
      return Response.redirect(`${PAYLAS_ADRESI}?adet=${dosyalar.length}`, 303);
    })());
    return;
  }
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
