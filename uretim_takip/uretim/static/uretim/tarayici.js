// Kamerayla QR okuma. Varsa tarayıcının yerleşik BarcodeDetector'ı, yoksa jsQR kullanılır.
// Kullanım: const t = QrTarayici.baslat({video, durum, kap, onKod}); ... t.durdur();
(function () {
  // Etiketteki QR, ".../q/<NO>/" adresini taşır. Düz metin okutulursa olduğu gibi kullanılır.
  function kodCoz(metin) {
    metin = (metin || "").trim();
    const eslesme = metin.match(/\/q\/([^/?#]+)/);
    const kod = eslesme ? decodeURIComponent(eslesme[1]) : metin;
    return /^[A-Za-z0-9._-]{2,20}$/.test(kod) ? kod.toUpperCase() : null;
  }

  function baslat({ video, durum, kap, onKod }) {
    let akis = null;
    let bitti = false;

    function bildir(metin, hata) {
      if (!durum) return;
      durum.textContent = metin;
      durum.className = hata ? "mesaj error" : "mesaj info";
    }

    function durdur() {
      bitti = true;
      if (akis) akis.getTracks().forEach((t) => t.stop());
      akis = null;
    }

    function okundu(metin) {
      const kod = kodCoz(metin);
      if (!kod) {
        bildir("Bu QR kod sistemin etiketi değil: " + metin, true);
        return false;
      }
      if (navigator.vibrate) navigator.vibrate(120);
      durdur();
      onKod(kod);
      return true;
    }

    function dongu(algila) {
      let sonHata = 0;
      async function kare() {
        if (bitti) return;
        if (video.readyState >= 2) {
          try {
            const metin = await algila();
            if (metin && !okundu(metin)) sonHata = Date.now();
          } catch (e) { /* bir sonraki karede tekrar dene */ }
        }
        setTimeout(() => requestAnimationFrame(kare), Date.now() - sonHata < 1500 ? 800 : 150);
      }
      kare();
    }

    (async function () {
      if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (kap) kap.hidden = true;
        bildir("Bu bağlantıda kamera açılamıyor (HTTPS gerekir). Numarayı elle yazın.", true);
        return;
      }
      try {
        akis = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      } catch (e) {
        if (kap) kap.hidden = true;
        bildir("Kameraya izin verilmedi. Numarayı elle yazabilirsiniz.", true);
        return;
      }
      if (bitti) { durdur(); return; }
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
    })();

    window.addEventListener("pagehide", durdur, { once: true });
    return { durdur };
  }

  window.QrTarayici = { baslat, kodCoz };
})();
