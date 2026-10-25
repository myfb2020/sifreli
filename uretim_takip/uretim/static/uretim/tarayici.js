// Kamerayla lot QR kodu okuma. Varsa tarayıcının yerleşik BarcodeDetector'ı, yoksa jsQR kullanılır.
(function () {
  const video = document.getElementById("kamera");
  const durum = document.getElementById("tarama-durum");
  const kap = document.getElementById("kamera-kap");
  const LOT_DESENI = /UL-\d{4}-\d{4,}/i;
  let akis = null;
  let bitti = false;

  function bildir(metin, hata) {
    durum.textContent = metin;
    durum.className = hata ? "mesaj error" : "mesaj info";
  }

  function bulundu(metin) {
    const eslesme = (metin || "").match(LOT_DESENI);
    if (!eslesme) {
      bildir("Bu QR kod bir lot etiketi değil: " + metin, true);
      return false;
    }
    bitti = true;
    if (navigator.vibrate) navigator.vibrate(120);
    bildir(eslesme[0].toUpperCase() + " okundu, açılıyor…");
    if (akis) akis.getTracks().forEach((t) => t.stop());
    window.location.href = "/q/" + encodeURIComponent(eslesme[0].toUpperCase()) + "/";
    return true;
  }

  async function dongu(algila) {
    let sonHata = 0;
    async function kare() {
      if (bitti) return;
      if (video.readyState >= 2) {
        try {
          const metin = await algila();
          if (metin && !bulundu(metin)) {
            sonHata = Date.now();
          }
        } catch (e) { /* bir sonraki karede tekrar dene */ }
      }
      // Yanlış QR okunduysa uyarı görünsün diye biraz bekle.
      setTimeout(() => requestAnimationFrame(kare), Date.now() - sonHata < 1500 ? 800 : 150);
    }
    kare();
  }

  async function baslat() {
    if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      kap.hidden = true;
      bildir("Bu bağlantıda uygulama içinden kamera açılamıyor (HTTPS gerekir). " +
             "Telefonun kendi kamera uygulamasıyla etiketi okutun ya da lot numarasını aşağıya yazın.", true);
      return;
    }
    try {
      akis = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
    } catch (e) {
      kap.hidden = true;
      bildir("Kameraya izin verilmedi. Lot numarasını aşağıya yazabilirsiniz.", true);
      return;
    }
    video.srcObject = akis;
    await video.play();
    bildir("Etiketteki QR kodu çerçevenin içine tutun.");

    if ("BarcodeDetector" in window) {
      try {
        const dedektor = new BarcodeDetector({ formats: ["qr_code"] });
        dongu(async () => {
          const sonuc = await dedektor.detect(video);
          return sonuc.length ? sonuc[0].rawValue : null;
        });
        return;
      } catch (e) { /* jsQR'a geç */ }
    }
    const tuval = document.createElement("canvas");
    const ctx = tuval.getContext("2d", { willReadFrequently: true });
    dongu(async () => {
      const g = video.videoWidth, y = video.videoHeight;
      if (!g || !y) return null;
      const oran = Math.min(1, 640 / Math.max(g, y));
      tuval.width = Math.round(g * oran);
      tuval.height = Math.round(y * oran);
      ctx.drawImage(video, 0, 0, tuval.width, tuval.height);
      const veri = ctx.getImageData(0, 0, tuval.width, tuval.height);
      const kod = window.jsQR(veri.data, veri.width, veri.height, { inversionAttempts: "dontInvert" });
      return kod ? kod.data : null;
    });
  }

  window.addEventListener("pagehide", () => { if (akis) akis.getTracks().forEach((t) => t.stop()); });
  baslat();
})();
