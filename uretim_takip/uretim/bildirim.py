"""Telefona anlık bildirim (Web Push, RFC 8291 + VAPID RFC 8292).

Ek kütüphane olarak yalnız `cryptography` kullanılır; gönderim urllib ile yapılır (PythonAnywhere'de vekil sunucu
ortam değişkeninden kendiliğinden kullanılır). Kütüphane kurulu değilse bildirim sessizce atlanır, program çalışır.
"""

import base64
import json
import logging
import os
import struct
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

log = logging.getLogger(__name__)
KAYIT_UZUNLUGU = 4096


def _b64(veri):
    return base64.urlsafe_b64encode(veri).rstrip(b"=").decode()


def _b64_coz(metin):
    metin = metin.strip()
    return base64.urlsafe_b64decode(metin + "=" * (-len(metin) % 4))


def kullanilabilir():
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return True


def vapid_anahtarlari():
    """(özel anahtar nesnesi, açık anahtar base64url). İlk istekte üretilip sistem ayarına yazılır."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from .models import SistemAyari

    ayar = SistemAyari.yukle()
    if not ayar.vapid_ozel:
        ozel = ec.generate_private_key(ec.SECP256R1())
        ayar.vapid_ozel = ozel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()).decode()
        ayar.vapid_acik = _b64(ozel.public_key().public_bytes(serialization.Encoding.X962,
                                                              serialization.PublicFormat.UncompressedPoint))
        SistemAyari.objects.filter(pk=ayar.pk).update(vapid_ozel=ayar.vapid_ozel, vapid_acik=ayar.vapid_acik)
    ozel = serialization.load_pem_private_key(ayar.vapid_ozel.encode(), password=None)
    return ozel, ayar.vapid_acik


def acik_anahtar():
    if not kullanilabilir():
        return ""
    return vapid_anahtarlari()[1]


def sifrele(icerik, p256dh, auth, tuz=None, sunucu_ozel=None):
    """İçeriği aboneliğin anahtarlarıyla aes128gcm biçiminde şifreler (RFC 8291). Gövdeyi döndürür."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    ua_acik_bayt = _b64_coz(p256dh)
    ua_acik = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_acik_bayt)
    sunucu_ozel = sunucu_ozel or ec.generate_private_key(ec.SECP256R1())
    sunucu_acik_bayt = sunucu_ozel.public_key().public_bytes(serialization.Encoding.X962,
                                                             serialization.PublicFormat.UncompressedPoint)
    ortak = sunucu_ozel.exchange(ec.ECDH(), ua_acik)
    tuz = tuz or os.urandom(16)

    def hkdf(tuz_, girdi, bilgi, uzunluk):
        return HKDF(algorithm=hashes.SHA256(), length=uzunluk, salt=tuz_, info=bilgi).derive(girdi)

    ikm = hkdf(_b64_coz(auth), ortak, b"WebPush: info\x00" + ua_acik_bayt + sunucu_acik_bayt, 32)
    cek = hkdf(tuz, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(tuz, ikm, b"Content-Encoding: nonce\x00", 12)
    sifreli = AESGCM(cek).encrypt(nonce, icerik + b"\x02", None)
    return tuz + struct.pack("!IB", KAYIT_UZUNLUGU, len(sunucu_acik_bayt)) + sunucu_acik_bayt + sifreli


def _vapid_basligi(endpoint, iletisim):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    ozel, acik = vapid_anahtarlari()
    parca = urlsplit(endpoint)
    baslik = _b64(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    govde = _b64(json.dumps({"aud": f"{parca.scheme}://{parca.netloc}", "exp": int(time.time()) + 12 * 3600,
                             "sub": iletisim}).encode())
    imzali = f"{baslik}.{govde}".encode()
    r, s = decode_dss_signature(ozel.sign(imzali, ec.ECDSA(hashes.SHA256())))
    imza = _b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={baslik}.{govde}.{imza}, k={acik}"


def gonder(abonelik, baslik, metin, adres="/", iletisim="https://uretim.pythonanywhere.com"):
    """Tek aboneliğe bildirim gönderir. True: gitti; False: abonelik geçersiz (silinmeli); None: geçici hata."""
    icerik = json.dumps({"baslik": baslik, "metin": metin, "adres": adres}, ensure_ascii=False).encode()
    govde = sifrele(icerik, abonelik.p256dh, abonelik.auth)
    istek = urllib.request.Request(abonelik.endpoint, data=govde, method="POST", headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": "86400",
        "Urgency": "high", "Authorization": _vapid_basligi(abonelik.endpoint, iletisim)})
    try:
        with urllib.request.urlopen(istek, timeout=10):
            return True
    except urllib.error.HTTPError as hata:
        if hata.code in (404, 410):
            return False
        log.warning("Bildirim gönderilemedi (%s): %s", hata.code, abonelik.endpoint[:60])
    except OSError as hata:
        log.warning("Bildirim gönderilemedi: %s", hata)
    return None


def ofise_bildir(baslik, metin, adres="/"):
    """Ofis ve yönetici hesaplarının bütün telefonlarına bildirim. Gönderilen sayısını döndürür."""
    if not kullanilabilir():
        return 0
    from .models import BildirimAboneligi

    gonderilen = 0
    for abonelik in BildirimAboneligi.objects.filter(kullanici__is_staff=True, kullanici__is_active=True):
        try:
            sonuc = gonder(abonelik, baslik, metin, adres)
        except Exception:  # bildirim hiçbir zaman siparişi bozmasın
            log.exception("Bildirim hatası")
            continue
        if sonuc is False:
            abonelik.delete()
        elif sonuc:
            gonderilen += 1
    return gonderilen


def yeni_bayi_siparisi(siparis):
    from django.urls import reverse

    return ofise_bildir("🆕 Yeni bayi siparişi", f"{siparis.musteri} – {siparis.urun}",
                        reverse("siparis_detay", args=[siparis.pk]))
