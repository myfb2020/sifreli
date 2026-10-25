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
      // Önce arka kamerayı yüksek çözünürlükte iste; olmazsa herhangi bir kamerayı dene (dizüstü vb.).
      const istekler = [
        { video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
        { video: true, audio: false },
      ];
      let sonHata = null;
      for (const istek of istekler) {
        try { akis = await navigator.mediaDevices.getUserMedia(istek); break; } catch (e) { sonHata = e; }
      }
      if (!akis) {
        if (kap) kap.hidden = true;
        const ad = sonHata && sonHata.name;
        bildir(ad === "NotAllowedError" || ad === "SecurityError"
          ? "Kameraya izin verilmedi. Adres çubuğundaki kilit simgesinden kamera iznini açın ya da numarayı elle yazın."
          : ad === "NotFoundError" || ad === "OverconstrainedError"
            ? "Bu cihazda kamera bulunamadı. Numarayı elle yazın."
            : ad === "NotReadableError"
              ? "Kamera başka bir uygulama tarafından kullanılıyor. O uygulamayı kapatıp tekrar deneyin."
              : "Kamera açılamadı. Numarayı elle yazabilirsiniz.", true);
        return;
      }
      if (bitti) { durdur(); return; }
      video.setAttribute("playsinline", "");
      video.muted = true;
      video.srcObject = akis;
      try { await video.play(); } catch (e) { /* bazı tarayıcılar otomatik oynatmayı geciktirir */ }
      bildir("Etiketteki QR kodu çerçevenin içine tutun.");

      // Yerleşik dedektör bazı cihazlarda var görünür ama QR bulamaz; bu yüzden her karede
      // önce onu, sonuç yoksa jsQR'ı dener.
      let dedektor = null;
      if ("BarcodeDetector" in window) {
        try {
          const turler = BarcodeDetector.getSupportedFormats ? await BarcodeDetector.getSupportedFormats() : ["qr_code"];
          if (turler.includes("qr_code")) dedektor = new BarcodeDetector({ formats: ["qr_code"] });
        } catch (e) { dedektor = null; }
      }
      const tuval = document.createElement("canvas");
      const ctx = tuval.getContext("2d", { willReadFrequently: true });
      function jsqrIleOku() {
        const g = video.videoWidth, y = video.videoHeight;
        if (!g || !y || !window.jsQR) return null;
        const oran = Math.min(1, 800 / Math.max(g, y));
        tuval.width = Math.round(g * oran);
        tuval.height = Math.round(y * oran);
        ctx.drawImage(video, 0, 0, tuval.width, tuval.height);
        const veri = ctx.getImageData(0, 0, tuval.width, tuval.height);
        const kod = window.jsQR(veri.data, veri.width, veri.height, { inversionAttempts: "attemptBoth" });
        return kod ? kod.data : null;
      }
      dongu(async () => {
        if (dedektor) {
          try {
            const sonuc = await dedektor.detect(video);
            if (sonuc.length) return sonuc[0].rawValue;
          } catch (e) { dedektor = null; }
        }
        return jsqrIleOku();
      });
    })();

    window.addEventListener("pagehide", durdur, { once: true });
    return { durdur };
  }

  window.QrTarayici = { baslat, kodCoz };
})();
