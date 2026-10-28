"""Tasarımın gerçekçi görseli (PNG): katalog kürk dokuları, metal / deri bantlar ve lazer desen kesikleri.

Desenler (DB001…) halının sağ üst köşesini gösterir: üst bant + sağ bant. Desen bant genişliğine ölçeklenir,
kenar boyunca tekrar ettirilir (periyodik desen) ya da aynalanarak uzatılır; dört köşeye aynalanınca tüm kenar çıkar.
"""

import io
import json
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import tasarim_cizim as cizim

VARLIK = Path(__file__).resolve().parent / "tasarim_varlik"
DOKU_CM = 55  # bir doku parçasının halıda kapladığı genişlik (katalog fotoğraflarından ≈ 3 px/cm)


@lru_cache(maxsize=1)
def desen_bilgisi():
    return json.loads((VARLIK / "desen" / "desenler.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def _maske(kod):
    return Image.open(VARLIK / "desen" / f"{kod}.png").convert("L")


@lru_cache(maxsize=16)
def _doku(ad):
    return Image.open(VARLIK / "doku" / f"{ad}.jpg").convert("RGB")


@lru_cache(maxsize=64)
def _yumusak_maske(w, h, pay):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rectangle((pay, pay, w - 1 - pay, h - 1 - pay), fill=255)
    return m.filter(ImageFilter.GaussianBlur(max(1, pay / 2)))


def _hex(renk):
    renk = renk.lstrip("#")
    return tuple(int(renk[i:i + 2], 16) for i in (0, 2, 4))


def doku_doldur(ad, boyut, px_cm):
    """Kürk parçalarını rastgele yer ve yönlerle, kenarları yumuşatarak döşer (tekrar ve ayna izi kalmaz)."""
    kaynak = _doku(ad)
    oran = DOKU_CM * px_cm / kaynak.width
    kaynak = kaynak.resize((max(8, int(kaynak.width * oran)), max(8, int(kaynak.height * oran))), Image.LANCZOS)
    kw, kh = kaynak.size
    pw, ph = max(8, int(kw * 0.6)), max(8, int(kh * 0.6))  # bir yama
    adim_x, adim_y = max(4, int(pw * 0.75)), max(4, int(ph * 0.75))
    rast = random.Random(ad)  # aynı doku her çizimde aynı görünür
    tuval = Image.new("RGB", boyut, kaynak.resize((1, 1)).getpixel((0, 0)))
    maske = _yumusak_maske(pw, ph, max(2, min(pw, ph) // 8))
    for y in range(-ph // 4, boyut[1], adim_y):
        for x in range(-pw // 4, boyut[0], adim_x):
            sx, sy = rast.randint(0, kw - pw), rast.randint(0, kh - ph)
            yama = kaynak.crop((sx, sy, sx + pw, sy + ph))
            if rast.random() < 0.5:
                yama = ImageOps.mirror(yama)
            tuval.paste(yama, (x + rast.randint(-adim_x // 6, adim_x // 6), y), maske)
    return tuval


def malzeme(ad, boyut):
    """Metalik varak ya da düz deri: renk + ışık geçişi + ince doku."""
    w, h = boyut
    taban = Image.new("RGB", boyut, _hex(cizim.BANT_HEX[ad]))
    metal = ad in ("altin", "gumus", "bronz")
    # sol üstten sağ alta çapraz ışık geçişi
    gecis = Image.blend(Image.linear_gradient("L"), Image.linear_gradient("L").transpose(Image.ROTATE_90), 0.5)
    gecis = ImageOps.autocontrast(gecis).resize(boyut)
    if metal:
        parlak = Image.new("RGB", boyut, (255, 249, 232))
        koyu = Image.new("RGB", boyut, (110, 85, 45) if ad != "gumus" else (110, 112, 116))
        taban = Image.composite(Image.blend(taban, parlak, 0.45), Image.blend(taban, koyu, 0.2), gecis)
    gurultu = Image.effect_noise(boyut, 18 if metal else 10).convert("RGB")
    return Image.blend(taban, ImageChops.overlay(taban, gurultu), 0.25 if metal else 0.18)


def _kenar_desen_maskesi(kod, boyut, bant_px):
    """Verilen dikdörtgen (bant dış kenarı) için tüm kenar boyunca desen kesikleri (L, 255 = delik)."""
    bilgi = desen_bilgisi().get(kod)
    if not bilgi or bant_px < 6:
        return Image.new("L", boyut, 0)
    W, H = boyut
    qw, qh = (W + 1) // 2, (H + 1) // 2
    k = bant_px / bilgi["bant"]
    kaynak = _maske(kod)
    ts = kaynak.resize((max(1, int(kaynak.width * k)), max(1, int(kaynak.height * k))), Image.LANCZOS)
    ws, hs = ts.size
    b = int(round(bant_px))
    ceyrek = Image.new("L", (qw, qh), 0)
    X = qw - ws  # karonun sol kenarı
    ceyrek.paste(ts, (X, 0))
    if bilgi["tur"] != "kose":
        ust = ts.crop((0, 0, max(1, ws - b), b))
        sag = ts.crop((ws - b, b, ws, max(b + 1, hs)))
        if bilgi["tur"] == "periyodik" and bilgi["periyot"]:
            p = max(4, int(round(bilgi["periyot"] * k)))
            x0 = min(p, max(0, ust.width - p))
            parca = ust.crop((x0, 0, x0 + p, b))
            x = X + x0 - p
            while x > -p:
                ceyrek.paste(parca, (x, 0))
                x -= p
            y0 = min(p, max(0, sag.height - p))
            dparca = sag.crop((0, y0, b, y0 + p))
            y = b + y0
            while y < qh:
                ceyrek.paste(dparca, (qw - b, y))
                y += p
        else:  # aynalayarak uzat
            x, ters = X, True
            while x > 0:
                parca = ImageOps.mirror(ust) if ters else ust
                x -= parca.width
                ceyrek.paste(parca, (x, 0))
                ters = not ters
            y, ters = hs, True
            while y < qh:
                parca = ImageOps.flip(sag) if ters else sag
                ceyrek.paste(parca, (qw - b, y))
                y += parca.height
                ters = not ters
    tam = Image.new("L", (qw * 2, qh * 2), 0)
    tam.paste(ceyrek, (qw, 0))
    tam.paste(ImageOps.mirror(ceyrek), (0, 0))
    ust_yari = tam.crop((0, 0, qw * 2, qh))
    tam.paste(ImageOps.flip(ust_yari), (0, qh))
    tam = tam.crop((0, 0, W, H))
    # yalnızca bant şeridinde kalsın
    serit = Image.new("L", boyut, 255)
    ImageDraw.Draw(serit).rectangle((b, b, W - 1 - b, H - 1 - b), fill=0)
    return ImageChops.multiply(tam, serit)


def _sekil(boyut, kutu, oval, r):
    m = Image.new("L", boyut, 0)
    d = ImageDraw.Draw(m)
    if kutu[2] <= kutu[0] or kutu[3] <= kutu[1]:
        return m
    if oval:
        d.ellipse(kutu, fill=255)
    else:
        d.rounded_rectangle(kutu, radius=max(0, int(r)), fill=255)
    return m


def ciz(veri, uzun_kenar=900, arka=(38, 35, 33)):
    """Tasarımın görseli (PIL Image)."""
    v = veri
    px = uzun_kenar / max(v["en"], v["boy"])
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    pay = int(uzun_kenar * 0.05)
    oval = v["sekil"] == "oval"
    boyut = (W, H)
    r_kose = cizim.KOSE_CM * px

    def kutu(cm):
        d = cm * px
        return (d, d, W - 1 - d, H - 1 - d)

    d1 = v["dis_bant"]
    d2 = d1 + v["halka"]
    d3 = d2 + v["ic_bant"]
    dis = _sekil(boyut, kutu(0), oval, r_kose)
    m1, m2, m3 = (_sekil(boyut, kutu(d), oval, max(r_kose - d * px, 2)) for d in (d1, d2, d3))

    resim = doku_doldur(v["halka_zemin"], boyut, px)
    resim.paste(doku_doldur(v["zemin"], boyut, px), (0, 0), m3 if d3 else dis)
    alt = Image.new("RGB", boyut, _hex(cizim.ALT_HEX[v["desen_alti"]]))
    golge_kaynak = Image.new("L", boyut, 0)

    def bant_koy(dis_m, ic_m, malzeme_ad, desen, dis_cm, bant_cm):
        nonlocal resim, golge_kaynak
        bolge = ImageChops.subtract(dis_m, ic_m)
        katman = malzeme(malzeme_ad, boyut)
        if desen:
            x0 = int(round(dis_cm * px))
            alan = (W - 2 * x0, H - 2 * x0)
            delik = Image.new("L", boyut, 0)
            delik.paste(_kenar_desen_maskesi(desen, alan, bant_cm * px), (x0, x0))
            delik = ImageChops.multiply(delik, bolge)
            # kesik kenarlarında ince gölge: derinlik hissi
            kenar = ImageChops.subtract(delik.filter(ImageFilter.MaxFilter(3)), delik)
            katman = Image.composite(alt, katman, delik)
            katman = Image.composite(Image.new("RGB", boyut, (25, 20, 15)), katman, kenar.point(lambda p: p // 2))
        resim.paste(katman, (0, 0), bolge)
        golge_kaynak = ImageChops.lighter(golge_kaynak, bolge)

    if v["dis_bant"]:
        bant_koy(dis, m1, v["dis_malzeme"], v["dis_desen"], 0, v["dis_bant"])
    if v["ic_bant"]:
        bant_koy(m2, m3, v["ic_malzeme"], v["ic_desen"], d2, v["ic_bant"])

    # bantların kürk üzerine düşen yumuşak gölgesi
    if v["dis_bant"] or v["ic_bant"]:
        golge = golge_kaynak.filter(ImageFilter.GaussianBlur(max(2, px * 1.2)))
        golge = ImageChops.subtract(golge, golge_kaynak).point(lambda p: int(p * 0.55))
        resim = Image.composite(Image.new("RGB", boyut, (0, 0, 0)), resim, golge)

    if v["madalyon"]:
        r = v["madalyon"] * px / 2
        cx, cy = W / 2, H / 2
        mad = _sekil(boyut, (cx - r, cy - r, cx + r, cy + r), True, 0)
        resim.paste(malzeme(v["madalyon_malzeme"], boyut), (0, 0), mad)
        cizgi = ImageDraw.Draw(resim)
        for oran, renk in ((0.84, (120, 95, 50)), (0.8, (250, 245, 230))):
            cizgi.ellipse((cx - r * oran, cy - r * oran, cx + r * oran, cy + r * oran), outline=renk, width=max(1, int(px * 0.4)))
        golge = mad.filter(ImageFilter.GaussianBlur(max(2, px)))
        golge = ImageChops.subtract(golge, mad).point(lambda p: int(p * 0.5))
        resim = Image.composite(Image.new("RGB", boyut, (0, 0, 0)), resim, golge)

    # zemin üstünde hafif ışık (katalog fotoğrafları gibi)
    isik = Image.radial_gradient("L").resize(boyut).point(lambda p: 255 - p // 3)
    resim = ImageChops.multiply(resim, Image.merge("RGB", (isik, isik, isik)))

    tuval = Image.new("RGB", (W + 2 * pay, H + 2 * pay), arka)
    golge = Image.new("L", tuval.size, 0)
    golge.paste(dis, (pay + int(px * 1.5), pay + int(px * 2.5)))
    golge = golge.filter(ImageFilter.GaussianBlur(pay / 3)).point(lambda p: int(p * 0.7))
    tuval = Image.composite(Image.new("RGB", tuval.size, (0, 0, 0)), tuval, golge)
    tuval.paste(resim, (pay, pay), dis)
    return tuval


def png(veri, uzun_kenar=900):
    tampon = io.BytesIO()
    ciz(veri, uzun_kenar).save(tampon, "PNG", optimize=False)
    return tampon.getvalue()


def jpeg(veri, uzun_kenar=900):
    tampon = io.BytesIO()
    ciz(veri, uzun_kenar).save(tampon, "JPEG", quality=85)
    return tampon.getvalue()
