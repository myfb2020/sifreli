"""🧊 3B görünüm (2026-11-27): halının yüzey resmi + kabartma haritası (tarayıcıda Three.js ile kalın halı).

Yüzey resmi önizlemeyle aynı çizimden (fotoğraf esaslı ya da parça parça çizim) gelir, yalnız halının kendisi kırpılır
(arka zemin ve gölge yok). Kabartma haritası gri resimdir (128 = düz): biye yuvarlak ve kabarık, parça birleşimleri
(zig-zag dikişi) hafif çukur, lazer delikleri ve doku ayrıntısı resmin kendi ışığından (yüksek frekans) gelir; böylece
fotoğraf esaslı resimde de delikler tam yerinde çukur görünür.
"""

import io
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import parcali as pc
from . import parcali_gorsel as pg

UZUN_KENAR = 1100  # telefonda yeterince keskin, sunucuda ~1 sn
KALINLIK_CM = 1.4  # suni deri halı (lamine + taban) yaklaşık kalınlığı
KOSE_CM = 3


def _resim(v, uzun_kenar):
    from . import foto_temel
    return foto_temel.bilesik(v, uzun_kenar) or pg.ciz(v, uzun_kenar)


def _olcek(v, uzun_kenar):
    px = uzun_kenar / max(v["en"], v["boy"])
    return px, int(round(v["en"] * px)), int(round(v["boy"] * px))


def sekil(v):
    return "oval" if v.get("duzen") == "yuvarlak" or v.get("sekil") == "oval" else "dikdortgen"


def _dis(v, px, W, H):
    if sekil(v) == "oval":
        return pg._poli_maske((W, H), [(x * px, y * px) for x, y in pc.dis_hat(v)])
    dis = Image.new("L", (W, H), 0)
    ImageDraw.Draw(dis).rounded_rectangle((0, 0, W - 1, H - 1), radius=max(3, int(px * KOSE_CM)), fill=255)
    return dis


def yuzey(v, uzun_kenar=UZUN_KENAR):
    """Halının yalnız kendisi (RGB, en × boy oranında); kenar dışı (oval / yuvarlak köşe) komşu renkle doldurulur."""
    px, W, H = _olcek(v, uzun_kenar)
    tuval = _resim(v, uzun_kenar)
    pay = (tuval.width - W) // 2
    resim = tuval.crop((pay, pay, pay + W, pay + H)).convert("RGB")
    # kenar dışındaki açık arka zemin dokuya karışmasın (mip-map / süzme kenarda beyaz çizgi yapıyordu)
    dis = _dis(v, px, W, H)
    dolgu = resim.filter(ImageFilter.BoxBlur(max(2, int(px * 1.5))))
    return Image.composite(resim, dolgu, pg.genislet(dis, 3) if dis.getbbox() else dis)


def kabartma(v, resim, uzun_kenar=UZUN_KENAR):
    """Gri kabartma haritası (128 düz, açık = kabarık)."""
    px, W, H = _olcek(v, uzun_kenar)
    L = resim.convert("L")
    # 1) doku + lazer delikleri: resmin yerel ışık farkı (delikteki koyu alt zemin çukur, peluş tüyü pürüz)
    yerel = L.filter(ImageFilter.GaussianBlur(max(2, px * 0.9)))
    fark = ImageChops.subtract(L, yerel, scale=1, offset=128)  # 128 ± ayrıntı
    harita = fark.point(lambda q: max(0, min(255, int(128 + (q - 128) * 0.55))))
    # 2) parça birleşimleri (zig-zag dikişi): ince çukur
    dikis = Image.new("L", (W, H), 0)
    cizgi = ImageDraw.Draw(dikis)
    kalin = max(1, int(px * 0.35))
    for p in pc.parcalar(v):
        poli = [(x * px, y * px) for x, y in p["poli"]]
        if len(poli) > 2:
            cizgi.line(poli + [poli[0]], fill=255, width=kalin)
    dikis = dikis.filter(ImageFilter.GaussianBlur(max(1, px * 0.3)))
    harita = ImageChops.subtract(harita, dikis.point(lambda q: int(q * 0.22)))
    # 3) biye: dış kenarı saran yuvarlak boru (dıştan içe yükselir, sırtı kabarık, içe doğru iner)
    dis = _dis(v, px, W, H)
    if v.get("kenar") in ("biye", "lanfel"):
        b = max(3, int(px * (2.2 if v.get("kenar") == "biye" else 1.0)))
        yukseklik = 70 if v.get("kenar") == "biye" else 28
        profil = Image.new("L", (W, H), 0)
        onceki = ImageOps.expand(dis, 2, 0)
        for k in range(b):
            sonraki = pg.asindir(onceki, 3)
            halka = ImageChops.subtract(onceki, sonraki).crop((2, 2, 2 + W, 2 + H))
            t = (k + 0.5) / b
            profil.paste(int(yukseklik * math.sin(math.pi * min(1.0, t)) ** 0.7), (0, 0), halka)
            onceki = sonraki
        profil = profil.filter(ImageFilter.GaussianBlur(max(0.8, px * 0.25)))
        harita = ImageChops.add(harita, profil)
    harita = harita.filter(ImageFilter.GaussianBlur(0.6))
    return Image.composite(harita, Image.new("L", (W, H), 96), dis)  # kenar dışı (görünmez) biraz alçak


def dosyalar(v, uzun_kenar=UZUN_KENAR):
    """(yüzey JPEG, kabartma PNG) baytları."""
    resim = yuzey(v, uzun_kenar)
    t1, t2 = io.BytesIO(), io.BytesIO()
    resim.save(t1, "JPEG", quality=86)
    kabartma(v, resim, uzun_kenar).save(t2, "PNG", optimize=True)
    return t1.getvalue(), t2.getvalue()


def bilgi(v):
    """Tarayıcıdaki 3B sahne için ölçü + şekil (cm)."""
    return {"en": v["en"], "boy": v["boy"], "sekil": sekil(v), "kose": KOSE_CM, "kalinlik": KALINLIK_CM,
            "kenar": v.get("kenar") or ""}


def onbellekli(v, tur, uzun_kenar=UZUN_KENAR):
    """'yuzey' (JPEG) ya da 'kabartma' (PNG) baytları; ikisi birlikte üretilir ve medya/onizleme/3b'de saklanır."""
    import hashlib
    import json
    from pathlib import Path

    from django.conf import settings

    from .tasarim_views import ONIZLEME_SURUM

    anahtar = hashlib.sha1(json.dumps([ONIZLEME_SURUM, "3b", uzun_kenar, v], sort_keys=True, default=str).encode()).hexdigest()
    klasor = Path(settings.MEDIA_ROOT) / "onizleme" / "3b"
    yollar = {"yuzey": klasor / f"{anahtar}.jpg", "kabartma": klasor / f"{anahtar}.png"}
    try:
        if yollar[tur].exists():
            return yollar[tur].read_bytes()
    except OSError:
        pass
    yuzey_b, kabartma_b = dosyalar(v, uzun_kenar)
    try:
        klasor.mkdir(parents=True, exist_ok=True)
        yollar["yuzey"].write_bytes(yuzey_b)
        yollar["kabartma"].write_bytes(kabartma_b)
        eskiler = sorted(klasor.glob("*.jpg"), key=lambda d: d.stat().st_mtime)[:-300]
        for eski in eskiler:
            eski.unlink(missing_ok=True)
            eski.with_suffix(".png").unlink(missing_ok=True)
    except OSError:
        pass
    return yuzey_b if tur == "yuzey" else kabartma_b


def yanit(v, tur):
    import json

    from django.http import Http404, HttpResponse

    if tur not in ("yuzey", "kabartma") or v.get("duzen") != "halkali":
        raise Http404
    r = HttpResponse(onbellekli(v, tur), content_type="image/jpeg" if tur == "yuzey" else "image/png")
    r["X-Bilgi"] = json.dumps(bilgi(v))
    r["Cache-Control"] = "private, max-age=86400"
    return r
