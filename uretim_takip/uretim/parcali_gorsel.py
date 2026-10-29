"""Parçalı suni deri halının görseli: her parça kendi malzemesiyle, desen delikleri, nakış ve dikiş izleriyle."""

import io
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import hali_gorsel as hg
from . import parcali as pc
from . import tasarim_cizim as cizim

KENAR_HEX = {"altin": "#d6b26a", "gumus": "#c2c5c9", "siyah": "#1c1b1a", "beyaz": "#f1ede4", "bej": "#cdbd9f"}


def _hex(h):
    return hg._hex(h)


def _keten(boyut, renk, seed):
    """Keten görünümlü suni deri: renk + ince çapraz dokuma + yumuşak lekeler."""
    w, h = boyut
    taban = Image.new("RGB", boyut, _hex(renk))
    yatay = Image.effect_noise((max(1, w // 6), h), 40).resize(boyut)
    dikey = Image.effect_noise((w, max(1, h // 6)), 40).resize(boyut)
    dokuma = ImageChops.add(yatay, dikey, scale=2)
    leke = Image.effect_noise((max(2, w // 40), max(2, h // 40)), 60).resize(boyut, Image.BICUBIC)
    acik = Image.new("RGB", boyut, tuple(min(255, c + 22) for c in _hex(renk)))
    koyu = Image.new("RGB", boyut, tuple(max(0, c - 22) for c in _hex(renk)))
    taban = Image.composite(acik, taban, leke.point(lambda p: max(0, p - 140)))
    return Image.composite(koyu, taban, dokuma.point(lambda p: max(0, 150 - p) // 2))


def _kadife(boyut, renk):
    taban = Image.new("RGB", boyut, _hex(renk))
    parlak = Image.new("RGB", boyut, tuple(min(255, c + 45) for c in _hex(renk)))
    w, h = boyut
    leke = Image.effect_noise((max(2, w // 25), max(2, h // 25)), 70).resize(boyut, Image.BICUBIC)
    return Image.composite(parlak, taban, leke.point(lambda p: max(0, p - 150)))


def malzeme_dokusu(ad, boyut, px):
    if hg._var_mi(ad):
        return hg.doku_doldur(ad, boyut, px)
    if ad in cizim.BANT_HEX:
        return hg.malzeme(ad, boyut, px)
    if ad.endswith("_kadife"):
        return _kadife(boyut, pc.MALZEME_HEX[ad])
    return _keten(boyut, pc.MALZEME_HEX[ad], ad)


@lru_cache(maxsize=8)
def motif_maskesi(boy):
    """Grek kare nakış motifi (atölyedeki nakış şeridindeki gibi): dört çeyrek, köşe parantezi + iç spiral."""
    n = max(8, boy)
    m = Image.new("L", (n * 4, n * 4), 0)
    d = ImageDraw.Draw(m)
    s = n * 4
    k = max(2, int(s * 0.055))

    def cizgi(pts):
        d.line([(x * s, y * s) for x, y in pts], fill=255, width=k, joint="curve")

    for fx in (False, True):
        for fy in (False, True):
            t = lambda pts: [((1 - x) if fx else x, (1 - y) if fy else y) for x, y in pts]  # noqa: E731
            cizgi(t([(0.46, 0.06), (0.06, 0.06), (0.06, 0.46)]))
            cizgi(t([(0.42, 0.2), (0.2, 0.2), (0.2, 0.42), (0.34, 0.42), (0.34, 0.31)]))
    return m.resize((boy, boy), Image.LANCZOS)


def _desen_serit(kod, uzunluk, bant):
    """Düz bir bant boyunca desen delikleri (yatay)."""
    if not kod or bant < 6:
        return Image.new("L", (max(1, uzunluk), max(1, bant)), 0)
    tam = hg._kenar_desen_maskesi(kod, (uzunluk + 4 * bant, 6 * bant), bant)
    return tam.crop((2 * bant, 0, 2 * bant + uzunluk, bant))


def _halka_deseni(kod, boyut, merkez, r1, r2):
    """Halka boyunca desen: düz bant deseni küçük dilimler hâlinde çevrilerek halkaya dizilir."""
    b = max(6, int(r2 - r1))
    rm = (r1 + r2) / 2
    cevre = int(2 * math.pi * rm)
    serit = _desen_serit(kod, cevre, b)
    maske = Image.new("L", boyut, 0)
    dilim = max(4, b // 3)
    for x in range(0, cevre, dilim):
        parca = serit.crop((x, 0, x + dilim + 1, b))
        aci = x / rm + dilim / (2 * rm)
        dondu = parca.rotate(-math.degrees(aci) - 90, expand=True, resample=Image.BICUBIC)
        cx = merkez[0] + rm * math.cos(aci)
        cy = merkez[1] + rm * math.sin(aci)
        kat = Image.new("L", boyut, 0)
        kat.paste(dondu, (int(cx - dondu.width / 2), int(cy - dondu.height / 2)))
        maske = ImageChops.lighter(maske, kat)
    return maske


def _poli_maske(boyut, poli):
    m = Image.new("L", boyut, 0)
    ImageDraw.Draw(m).polygon(poli, fill=255)
    return m


def ciz(v, uzun_kenar=900, arka=(38, 35, 33)):
    px = uzun_kenar / max(v["en"], v["boy"])
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    boyut = (W, H)
    olc = lambda poli: [(x * px, y * px) for x, y in poli]  # noqa: E731
    parcalar = pc.parcalar(v)
    resim = Image.new("RGB", boyut, (0, 0, 0))
    dokular = {}
    alt = hg.alt_katman(v["desen_alti"], boyut, px)

    # desen maskeleri (tüm halka/çerçeve için bir kez)
    desen_maskeleri = {}
    if v["duzen"] == "cerceve":
        d = 0.0
        for gen, desen in ((v["dis_bant"], v["dis_desen"]), (v["ara"], ""), (v["ic_bant"], v["ic_desen"])):
            if gen and desen:
                x0 = int(round(d * px))
                m = Image.new("L", boyut, 0)
                m.paste(hg._kenar_desen_maskesi(desen, (W - 2 * x0, H - 2 * x0), gen * px), (x0, x0))
                desen_maskeleri[desen, gen, d] = m
            d += gen
    elif v["duzen"] == "yuvarlak" and v["desen"] and v["desen_halka"]:
        r2 = (v["cap"] / 2 - v["dis_halka"]) * px
        desen_maskeleri["halka"] = _halka_deseni(v["desen"], boyut, (W / 2, H / 2), r2 - v["desen_halka"] * px, r2)

    golge_kaynak = Image.new("L", boyut, 0)
    for p in parcalar:
        poli = olc(p["poli"])
        maske = _poli_maske(boyut, poli)
        if p["malzeme"] not in dokular:
            dokular[p["malzeme"]] = malzeme_dokusu(p["malzeme"], boyut, px)
        katman = dokular[p["malzeme"]]
        if p["desen"]:
            if v["duzen"] == "yuvarlak":
                delik = desen_maskeleri.get("halka")
            else:
                delik = next((m for (kod, gen, d), m in desen_maskeleri.items() if kod == p["desen"]
                              and abs(min(p["en"], p["boy"]) - gen) < 0.6), None)
            if delik is not None:
                delik = ImageChops.multiply(delik, maske)
                kenar = ImageChops.subtract(delik.filter(ImageFilter.MaxFilter(3)), delik)
                katman = Image.composite(alt, katman, delik)
                katman = Image.composite(Image.new("RGB", boyut, (25, 20, 15)), katman, kenar.point(lambda q: q // 2))
            golge_kaynak = ImageChops.lighter(golge_kaynak, maske)
        resim.paste(katman, (0, 0), maske)

    # nakış motifleri
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok":
        boy = max(8, int(v["motif"] * px))
        mm = motif_maskesi(boy)
        renk = (214, 186, 120) if v["nakis"] == "grek_kare" else (200, 202, 206)
        iplik = hg.malzeme("altin" if v["nakis"] == "grek_kare" else "gumus", (boy, boy), px)
        iplik = Image.blend(Image.new("RGB", (boy, boy), renk), iplik, 0.5)
        golge = mm.filter(ImageFilter.GaussianBlur(max(1, boy / 60)))
        for cx, cy in pc.nakis_konumlari(v):
            x, y = int(cx * px - boy / 2), int(cy * px - boy / 2)
            resim.paste((40, 32, 20), (x + 1, y + 2), golge.point(lambda q: q // 3))
            resim.paste(iplik, (x, y), mm)

    # bantların gölgesi ve dikiş (zig-zag) izleri
    if golge_kaynak.getbbox():
        golge = golge_kaynak.filter(ImageFilter.GaussianBlur(max(2, px * 0.8)))
        golge = ImageChops.subtract(golge, golge_kaynak).point(lambda q: int(q * 0.45))
        resim = Image.composite(Image.new("RGB", boyut, (0, 0, 0)), resim, golge)
    cizgi = ImageDraw.Draw(resim)
    kalin = max(1, int(px * 0.25))
    for p in parcalar:
        poli = olc(p["poli"])
        cizgi.line(poli + [poli[0]], fill=(60, 55, 50), width=kalin)

    # kenar (biye / lanfel)
    dis = _poli_maske(boyut, olc(pc.dis_hat(v)))
    b = max(2, int(px * 1.6))
    serit = ImageChops.subtract(dis, dis.filter(ImageFilter.MinFilter(b * 2 + 1)))
    kenar_renk = KENAR_HEX[v["kenar_renk"]]
    kenar = (hg.malzeme(v["kenar_renk"], boyut, px) if v["kenar_renk"] in ("altin", "gumus")
             else Image.new("RGB", boyut, _hex(kenar_renk)))
    resim.paste(kenar, (0, 0), serit)
    if v["kenar"] == "lanfel":
        # Lanfel (overlok): kenar şeridinin iç sınırında kesik kesik iplik izi.
        ic = dis.filter(ImageFilter.MinFilter(b | 1))  # süzgeç boyu tek sayı olmalı
        dikis = ImageChops.subtract(ic, ic.filter(ImageFilter.MinFilter(3)))
        kesik = Image.effect_noise(boyut, 120).point(lambda q: 255 if q > 128 else 0)
        noktalar = ImageChops.multiply(dikis, kesik)
        resim = Image.composite(Image.new("RGB", boyut, (70, 60, 45)), resim, noktalar)

    isik = Image.radial_gradient("L").resize(boyut).point(lambda q: 255 - q // 4)
    resim = ImageChops.multiply(resim, Image.merge("RGB", (isik, isik, isik)))

    pay = int(uzun_kenar * 0.05)
    tuval = Image.new("RGB", (W + 2 * pay, H + 2 * pay), arka)
    golge = Image.new("L", tuval.size, 0)
    golge.paste(dis, (pay + int(px * 1.5), pay + int(px * 2.5)))
    golge = golge.filter(ImageFilter.GaussianBlur(pay / 3)).point(lambda q: int(q * 0.7))
    tuval = Image.composite(Image.new("RGB", tuval.size, (0, 0, 0)), tuval, golge)
    tuval.paste(resim, (pay, pay), dis)
    return tuval


def parca_plani(v, uzun_kenar=700):
    """Ofis/atölye için: parçaların numaralı planı (açık zemin, çizgiler, P1, P2…)."""
    px = uzun_kenar / max(v["en"], v["boy"])
    pay = 20
    W, H = int(v["en"] * px) + 2 * pay, int(v["boy"] * px) + 2 * pay
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    renkler = {}
    yazi = ImageFont.load_default(size=max(12, int(uzun_kenar / 40)))
    palet = [(236, 226, 206), (210, 222, 236), (226, 236, 212), (240, 214, 214), (226, 216, 240), (244, 236, 200)]
    for p in pc.parcalar(v):
        renk = renkler.setdefault(p["malzeme"], palet[len(renkler) % len(palet)])
        poli = [(x * px + pay, y * px + pay) for x, y in p["poli"]]
        d.polygon(poli, fill=renk, outline=(60, 55, 50))
        cx = sum(x for x, _ in poli) / len(poli)
        cy = sum(y for _, y in poli) / len(poli)
        d.text((cx, cy), p["no"], fill=(30, 30, 30), anchor="mm", font=yazi)
    return im


@lru_cache(maxsize=32)
def ornek(ad, boy=120):
    """Malzeme seçim düğmesi için küçük örnek."""
    t = io.BytesIO()
    malzeme_dokusu(ad, (boy, boy), 3).save(t, "JPEG", quality=85)
    return t.getvalue()


def jpeg(v, uzun_kenar=900):
    t = io.BytesIO()
    ciz(v, uzun_kenar).save(t, "JPEG", quality=85)
    return t.getvalue()


def plan_png(v, uzun_kenar=700):
    t = io.BytesIO()
    parca_plani(v, uzun_kenar).save(t, "PNG")
    return t.getvalue()
