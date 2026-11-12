"""Parçalı suni deri halının görseli: her parça kendi malzemesiyle, desen delikleri, nakış ve dikiş izleriyle."""

import io
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import hali_gorsel as hg
from . import parcali as pc
from . import tasarim_cizim as cizim

NAKIS_KLASORU = Path(__file__).resolve().parent / "tasarim_varlik" / "nakis"
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


def ImageStat_ort(resim):
    return resim.resize((1, 1), Image.BOX).getpixel((0, 0))


@lru_cache(maxsize=24)
def _kartela_dokusu(ad, boyut, px):
    """Rono / Bienca: atölye numune fotoğrafı (ışığı düzeltilmiş) gerçek ölçüsünde, ayna döşeme yerine
    büyük yumuşak geçişli yamalarla. Bienca baskısı büyük ve tekrarsızdır: bütün halıyı tek parça kaplar."""
    import random
    kaynak = hg._doku(ad)
    if ad.startswith("bienca"):
        k = max(boyut[0] / kaynak.width, boyut[1] / kaynak.height)
        b = kaynak.resize((max(1, round(kaynak.width * k)), max(1, round(kaynak.height * k))), Image.LANCZOS)
        # numune fotoğrafındaki ışık-gölge (kıvrım, pencere ışığı) halıda gölge gibi görünür: geniş ölçekli
        # parlaklık farkı silinir, desenin kendi açık-koyu tonu kalır
        gri = b.convert("L")
        ort = max(1, gri.resize((1, 1), Image.BOX).getpixel((0, 0)))
        genis = gri.filter(ImageFilter.GaussianBlur(max(4, b.width / 8)))
        duz = genis.point(lambda q: max(0, min(255, round(128 * ort / max(q, 1)))))
        b = ImageChops.multiply(b, Image.merge("RGB", (duz,) * 3)).point(lambda q: min(255, q * 2))
        return b.crop(((b.width - boyut[0]) // 2, (b.height - boyut[1]) // 2,
                       (b.width - boyut[0]) // 2 + boyut[0], (b.height - boyut[1]) // 2 + boyut[1]))
    # Rono: numunenin genel rengi ve hafif eskitme tonları bütün parçayı tek kaplar (kare kare tekrar görünmez);
    # ince dokuma gerçek ölçüsünde üstüne işlenir
    gri = kaynak.convert("L")
    bulanik = kaynak.filter(ImageFilter.GaussianBlur(max(2, kaynak.width / 40)))
    k = max(boyut[0] / kaynak.width, boyut[1] / kaynak.height)
    taban = bulanik.resize((max(1, round(kaynak.width * k)), max(1, round(kaynak.height * k))), Image.LANCZOS)
    taban = taban.crop(((taban.width - boyut[0]) // 2, (taban.height - boyut[1]) // 2,
                        (taban.width - boyut[0]) // 2 + boyut[0], (taban.height - boyut[1]) // 2 + boyut[1]))
    ort = ImageStat_ort(taban)
    taban = Image.blend(taban, Image.new("RGB", boyut, ort), 0.55)  # eskitme lekeleri yumuşak kalsın
    cm = hg.DOKU_CM_OZEL.get(ad, 15)
    w = max(12, round(cm * px))
    ince = kaynak.resize((w, max(12, round(kaynak.height * w / kaynak.width))), Image.LANCZOS).convert("L")
    ince = ImageChops.subtract(ince, ince.filter(ImageFilter.GaussianBlur(3)), 1, 128)  # yalnız dokuma ayrıntısı
    kes = min(8, ince.width // 4, ince.height // 4)  # bulanıklaştırmanın kenarda bıraktığı parlak şerit kesilir
    ince = ince.crop((kes, kes, ince.width - kes, ince.height - kes)).point(lambda q: round(128 + (q - 128) * 0.7))
    doku = Image.new("L", boyut, 128)
    for sira, y in enumerate(range(0, boyut[1], ince.height)):
        kay = (sira * ince.width // 3) % ince.width  # tuğla gibi kaydırılır: tekrar sırası görünmesin
        for x in range(-kay, boyut[0], ince.width):
            doku.paste(ince, (x, y))
    return ImageChops.multiply(taban, Image.merge("RGB", (doku,) * 3)).point(lambda q: min(255, q * 2))


@lru_cache(maxsize=12)
def _bienca_ince(ad, boyut, px, bolum=3):
    """Dar bant için Bienca: baskı 1/3 ölçekte, aynalı döşenir → büyük lekeler yerine ince eskitme."""
    from PIL import ImageOps
    kucuk = _kartela_dokusu(ad, (max(8, boyut[0] // bolum), max(8, boyut[1] // bolum)), px)
    ikili = Image.new("RGB", (kucuk.width * 2, kucuk.height * 2))
    ikili.paste(kucuk, (0, 0)); ikili.paste(ImageOps.mirror(kucuk), (kucuk.width, 0))
    ikili.paste(ImageOps.flip(kucuk), (0, kucuk.height))
    ikili.paste(ImageOps.flip(ImageOps.mirror(kucuk)), (kucuk.width, kucuk.height))
    tuval = Image.new("RGB", boyut)
    for y in range(0, boyut[1], ikili.height):
        for x in range(0, boyut[0], ikili.width):
            tuval.paste(ikili, (x, y))
    return tuval


def _metal_parilti(boyut, guc=0.45):
    """Altın / gümüş biye: çapraz yumuşak ışık bantları (fotoğraftaki metal parıltısı), 128 = değişmez."""
    W, H = boyut
    kucuk = Image.new("L", (64, 64))
    import math
    kucuk.putdata([round(128 + 127 * guc * math.sin((x + y) / 64 * math.pi * 3) ** 3)
                   for y in range(64) for x in range(64)])
    return kucuk.resize(boyut, Image.BICUBIC)


def _parlaklik(resim, maske):
    from PIL import ImageStat
    return ImageStat.Stat(resim.convert("L"), maske).mean[0] if maske.getbbox() else 128


@lru_cache(maxsize=24)
def _pelus(ad, boyut, px):
    """Peluş: tüy görünümü. Büyük yumuşak ton dalgaları (elle taranmış tüy), tüy yönünde ince çizgiler ve ince
    gren; fotoğraf karosu gibi tekrar etmez. 128 tabanlı katmanlar renge çarpılır."""
    w, h = boyut
    renk = _hex(pc.MALZEME_HEX[ad])
    koyu = sum(renk) / 3 < 70

    def gurultu(bw, bh, sigma, bulanik):
        g = Image.effect_noise((max(4, bw), max(4, bh)), sigma).filter(ImageFilter.GaussianBlur(bulanik))
        return g.resize(boyut, Image.BICUBIC)

    dalga = gurultu(w // max(8, int(px * 9)), h // max(8, int(px * 9)), 60, 1.2)       # ~9 cm'lik ton dalgaları
    tarak = gurultu(w // max(3, int(px * 1.2)), h // max(10, int(px * 7)), 45, 0.8)     # tüy yönünde çizgiler
    gren = Image.effect_noise(boyut, 26).filter(ImageFilter.GaussianBlur(0.5))
    guc = (0.34, 0.22, 0.30) if koyu else (0.16, 0.10, 0.14)
    ton = Image.new("L", boyut, 128)
    for katman, g in zip((dalga, tarak, gren), guc):
        ton = ImageChops.add(ton, katman.point(lambda q, g=g: int((q - 128) * g) + 128), 1, -128)
    taban = Image.new("RGB", boyut, tuple(min(255, c + (5 if koyu else 0)) for c in renk))
    return ImageChops.multiply(taban, Image.merge("RGB", (ton,) * 3)).point(lambda q: min(255, q * 2))


def malzeme_dokusu(ad, boyut, px):
    if ad.startswith("pelus_"):
        return _pelus(ad, boyut, round(px, 3))
    if (ad.startswith("bienca_bn") or ad.endswith("_keten")) and hg._var_mi(ad):
        return _kartela_dokusu(ad, boyut, round(px, 3))
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
    if hg.desen_bilgisi().get(kod, {}).get("tur") == "lz":
        return hg._lz_serit(kod, uzunluk, bant)
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


def _yol_deseni(kod, boyut, yol, bant):
    """Kapalı bir yol (px) boyunca desen: düz bant deseni küçük dilimler hâlinde yolun yönüne çevrilip dizilir."""
    b = max(6, int(bant))
    uzunluklar = [math.dist(yol[i - 1], yol[i]) for i in range(len(yol))]
    cevre = int(sum(uzunluklar))
    serit = _desen_serit(kod, cevre, b)
    maske = Image.new("L", boyut, 0)
    dilim = max(4, b // 3)
    i, gecilen = 0, 0.0
    for x in range(0, cevre, dilim):
        t = x + dilim / 2
        while i < len(yol) - 1 and gecilen + uzunluklar[(i + 1) % len(yol)] < t:
            gecilen += uzunluklar[(i + 1) % len(yol)]
            i += 1
        (x1, y1), (x2, y2) = yol[i], yol[(i + 1) % len(yol)]
        oran = (t - gecilen) / (uzunluklar[(i + 1) % len(yol)] or 1)
        cx, cy = x1 + (x2 - x1) * oran, y1 + (y2 - y1) * oran
        aci = math.degrees(math.atan2(y2 - y1, x2 - x1))
        parca = serit.crop((x, 0, x + dilim + 1, b))
        dondu = parca.rotate(-aci, expand=True, resample=Image.BICUBIC)
        maske.paste(dondu, (int(cx - dondu.width / 2), int(cy - dondu.height / 2)), dondu)
    return maske


def _halkali_desen(v, anahtar, boyut, px):
    """Halkalı tasarımda bir halkanın (ya da orta şeridin) desen delikleri."""
    W, H = boyut
    tur, no = anahtar
    if tur == "h":
        h = next(h for h in pc.halkalar(v) if h["no"] == no)
        if v["sekil"] == "oval":
            orta = h["d"] + h["gen"] / 2
            yol = [(x * px, y * px) for x, y in pc.stadyum_ofset(v["en"], v["boy"], orta)]
            return _yol_deseni(h["desen"], boyut, yol, h["gen"] * px)
        x0 = int(round(h["d"] * px))
        m = Image.new("L", boyut, 0)
        m.paste(hg._kenar_desen_maskesi(h["desen"], (W - 2 * x0, H - 2 * x0), h["gen"] * px), (x0, x0))
        return m
    p = next(p for p in pc.parcalar(v) if p.get("desen_anahtar") == anahtar)
    x0, y0, x1, y1 = pc.kutu(p["poli"])
    m = Image.new("L", boyut, 0)
    if p["yon"] == "dikey":
        serit = _desen_serit(p["desen"], int((y1 - y0) * px), int((x1 - x0) * px)).rotate(90, expand=True)
    else:
        serit = _desen_serit(p["desen"], int((x1 - x0) * px), int((y1 - y0) * px))
    m.paste(serit, (int(x0 * px), int(y0 * px)))
    return m


def _poli_maske(boyut, poli):
    m = Image.new("L", boyut, 0)
    ImageDraw.Draw(m).polygon(poli, fill=255)
    return m


def ciz(v, uzun_kenar=900, arka=(252, 251, 249)):
    px = uzun_kenar / max(v["en"], v["boy"])
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    boyut = (W, H)
    olc = lambda poli: [(x * px, y * px) for x, y in poli]  # noqa: E731
    parcalar = pc.parcalar(v)
    resim = Image.new("RGB", boyut, (0, 0, 0))
    dokular = {}
    bos_alt = v["desen_alti"] == "yok"  # delikler boş: altından halının altı (zemin) görünür
    alt = None if bos_alt else hg.alt_katman(v["desen_alti"], boyut, px)
    delikler = Image.new("L", boyut, 0)

    # desen maskeleri (tüm halka/çerçeve için bir kez)
    desen_maskeleri = {}
    if v["duzen"] == "cerceve" or v["duzen"] in pc.IZGARALI:
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

    if v["duzen"] == "halkali":
        for p in parcalar:
            if p.get("desen_anahtar") and p["desen_anahtar"] not in desen_maskeleri:
                desen_maskeleri[p["desen_anahtar"]] = _halkali_desen(v, p["desen_anahtar"], boyut, px)

    golge_kaynak = Image.new("L", boyut, 0)
    ton = Image.new("L", boyut, 128)  # parçaların tüy / dokuma yönü: yatay ve dikey parça ışığı farklı yansıtır
    for sira, p in enumerate(parcalar):
        poli = olc(p["poli"])
        maske = _poli_maske(boyut, poli)
        if p.get("tur") != "zemin":
            ton.paste(134 if p.get("yon") == "yatay" else 122 if p.get("yon") == "dikey" else 128 + (sira % 3 - 1) * 4,
                      (0, 0), maske)
        ince = p["malzeme"].startswith("bienca") and p.get("tur") != "zemin"
        if (p["malzeme"], ince) not in dokular:
            dokular[p["malzeme"], ince] = (_bienca_ince(p["malzeme"], boyut, round(px, 3)) if ince
                                           else malzeme_dokusu(p["malzeme"], boyut, px))
        katman = dokular[p["malzeme"], ince]
        if p["desen"]:
            if v["duzen"] == "halkali":
                delik = desen_maskeleri.get(p.get("desen_anahtar"))
            elif v["duzen"] == "yuvarlak":
                delik = desen_maskeleri.get("halka")
            else:
                delik = next((m for (kod, gen, d), m in desen_maskeleri.items() if kod == p["desen"]
                              and abs(min(p["en"], p["boy"]) - gen) < 0.6), None)
            if delik is not None:
                delik = ImageChops.multiply(delik, maske)
                kenar = ImageChops.subtract(delik.filter(ImageFilter.MaxFilter(3)), delik)
                if bos_alt:
                    delikler = ImageChops.lighter(delikler, delik)
                else:
                    katman = Image.composite(alt, katman, delik)
                # desen kenarı: açık bantta koyu çizgi, koyu bantta açık çizgi (delik koyu zeminde de okunsun)
                koyu = _parlaklik(katman, maske) < 95
                cizgi_renk = (175, 165, 150) if koyu else (25, 20, 15)
                katman = Image.composite(Image.new("RGB", boyut, cizgi_renk), katman,
                                         kenar.point(lambda q: int(q * 0.8) if koyu else q // 2))
            golge_kaynak = ImageChops.lighter(golge_kaynak, maske)
        resim.paste(katman, (0, 0), maske)

    resim = ImageChops.multiply(resim, Image.merge("RGB", (ton,) * 3)).point(lambda q: min(255, q * 2))

    # nakış motifleri
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok":
        _motifler(resim, "61.01", "gumus" if v["nakis"] == "grek_kare_gumus" else "altin",
                  [(x, y, v["motif"], v["motif"], 0) for x, y in pc.nakis_konumlari(v)], px)
    for p in parcalar:
        if p.get("motifler"):
            _motifler(resim, p["nakis"], v.get("iplik", "altin"), p["motifler"], px)

    # bantların gölgesi ve dikiş (zig-zag) izleri
    if golge_kaynak.getbbox():
        golge = golge_kaynak.filter(ImageFilter.GaussianBlur(max(2, px * 0.8)))
        golge = ImageChops.subtract(golge, golge_kaynak).point(lambda q: int(q * 0.2))
        resim = Image.composite(Image.new("RGB", boyut, (0, 0, 0)), resim, golge)
    # kabartma: her parça dikiş yerinde hafifçe içe çöker (gölge), ortası ışık alır
    dikis = Image.new("L", boyut, 0)
    cizgi = ImageDraw.Draw(dikis)
    kalin = max(1, int(px * 0.3))
    for p in parcalar:
        if p.get("tur") == "zemin":  # zemin parçaları arası ek yeri (rulo, madalyon için sol/sağ) görüntüde gösterilmez
            continue  # 140 cm'lik rulo ek yeri: üretim bilgisi, görüntüde gösterilmez
        poli = olc(p["poli"])
        cizgi.line(poli + [poli[0]], fill=255, width=kalin)
    yumusak = dikis.filter(ImageFilter.GaussianBlur(max(1.5, px * 1.2)))
    resim = Image.composite(Image.new("RGB", boyut, (20, 16, 12)), resim, yumusak.point(lambda q: int(q * 0.55)))
    isik_kenar = ImageChops.offset(yumusak, -max(1, int(px * 0.6)), -max(1, int(px * 0.6)))
    isik_kenar = ImageChops.subtract(isik_kenar, yumusak).point(lambda q: int(q * 0.35))
    resim = Image.composite(Image.new("RGB", boyut, (255, 250, 240)), resim, isik_kenar)
    resim = Image.composite(Image.new("RGB", boyut, (48, 42, 36)), resim, dikis.point(lambda q: int(q * 0.7)))

    # kenar (biye / lanfel); dikdörtgen halının köşeleri katalogdaki gibi hafif yuvarlak
    if v.get("duzen") == "yuvarlak" or (v.get("sekil") == "oval"):
        dis = _poli_maske(boyut, olc(pc.dis_hat(v)))
    else:
        dis = Image.new("L", boyut, 0)
        ImageDraw.Draw(dis).rounded_rectangle((0, 0, W - 1, H - 1), radius=max(3, int(px * 3)), fill=255)
    b = max(3, int(px * 2.2))
    # resim kenarına dayanan hat süzgeçte aşınmaz (kenar piksel uzatılır): önce siyah pay eklenir
    genis = ImageOps.expand(dis, b + 2, 0).filter(ImageFilter.MinFilter(b * 2 + 1))
    serit = ImageChops.subtract(dis, genis.crop((b + 2, b + 2, b + 2 + W, b + 2 + H)))
    kenar_renk = KENAR_HEX.get(v["kenar_renk"]) or pc.MALZEME_HEX.get(v["kenar_renk"], "#888888")
    kenar = (hg.malzeme(v["kenar_renk"], boyut, px) if v["kenar_renk"] in ("altin", "gumus")
             else malzeme_dokusu(v["kenar_renk"], boyut, px) if v["kenar_renk"] in pc.MALZEME_HEX
             else Image.new("RGB", boyut, _hex(kenar_renk)))
    metal = v["kenar_renk"] in ("altin", "gumus")
    if metal:
        parilti = _metal_parilti(boyut)
        if v["kenar_renk"] == "altin":  # fotoğraf dokusu soluk: katalogdaki altın biye daha doygun sarı
            from PIL import ImageEnhance
            kenar = ImageEnhance.Color(kenar).enhance(1.7)
        kenar = ImageChops.multiply(kenar, Image.merge("RGB", (parilti,) * 3)).point(lambda q: min(255, q * 2))
    if v["kenar"] == "biye":
        # biye halının kenarını saran yuvarlak boru: dış ve iç kenarı gölgede, üçte birinde parlak sırt
        profil = _biye_profili(dis, b, W, H, metal)
        kenar = ImageChops.multiply(kenar, Image.merge("RGB", (profil,) * 3)).point(lambda q: min(255, q * 2))
    resim.paste(kenar, (0, 0), serit)
    # biyenin içteki halıya düşen ince gölgesi (biye kabarık durur)
    ic = genis.crop((b + 2, b + 2, b + 2 + W, b + 2 + H))
    biye_golge = ImageChops.subtract(ic, ic.filter(ImageFilter.MinFilter(max(3, int(px * 0.8)) | 1)))
    biye_golge = biye_golge.filter(ImageFilter.GaussianBlur(max(1, px * 0.4))).point(lambda q: int(q * 0.45))
    resim = Image.composite(Image.new("RGB", boyut, (15, 12, 10)), resim, biye_golge)
    if v["kenar"] == "lanfel":
        # Lanfel (overlok): kenar şeridinin iç sınırında kesik kesik iplik izi.
        dikis = ImageChops.subtract(ic, ic.filter(ImageFilter.MinFilter(3)))
        kesik = Image.effect_noise(boyut, 120).point(lambda q: 255 if q > 128 else 0)
        noktalar = ImageChops.multiply(dikis, kesik)
        resim = Image.composite(Image.new("RGB", boyut, (70, 60, 45)), resim, noktalar)

    isik = Image.radial_gradient("L").resize(boyut).point(lambda q: 255 - q // 7)
    resim = ImageChops.multiply(resim, Image.merge("RGB", (isik, isik, isik)))
    # sol üstten yumuşak pencere ışığı (fotoğraftaki gibi): parlak alan biraz açılır
    egim = Image.new("L", (2, 2)); egim.putdata([34, 12, 12, 0])  # sol üst en açık, sağ alt hiç
    egim = egim.resize((4, 4), Image.NEAREST).resize(boyut, Image.BICUBIC).filter(ImageFilter.GaussianBlur(boyut[0] / 6))
    resim = Image.composite(Image.new("RGB", boyut, (255, 252, 244)), resim, egim)
    # metal / varak parıltısı: ışığın vurduğu çapraz bantta parlak yerler (varak, metal) biraz daha parlar
    resim = _varak_parlat(resim, boyut)

    pay = int(uzun_kenar * 0.05)
    acik = sum(arka) / 3 > 128
    tuval = Image.new("RGB", (W + 2 * pay, H + 2 * pay), arka) if acik else _deri_zemin((W + 2 * pay, H + 2 * pay), arka)
    golge = Image.new("L", tuval.size, 0)
    golge.paste(dis, (pay + int(px * 1.2), pay + int(px * 2.2)))
    golge = golge.filter(ImageFilter.GaussianBlur(pay / 2.5)).point(lambda q: int(q * (0.42 if acik else 0.7)))
    tuval = Image.composite(Image.new("RGB", tuval.size, (40, 34, 28) if acik else (0, 0, 0)), tuval, golge)
    gorunur = ImageChops.subtract(dis, delikler)
    # lazer deliklerinden halının altı (koyu zemin) görünür; halının kalınlığı deliğin içine (sağ alta) gölge düşürür
    if delikler.getbbox():
        if acik:
            tuval.paste((58, 52, 47), (pay, pay), dis)
        d = max(2, int(px * 0.5))
        derin = Image.new("L", tuval.size, 0)
        derin.paste(gorunur, (pay + d, pay + d))
        derin = derin.filter(ImageFilter.GaussianBlur(max(1, px * 0.35))).point(lambda q: int(q * 0.75))
        tuval = Image.composite(Image.new("RGB", tuval.size, (0, 0, 0)), tuval, derin)
    tuval.paste(resim, (pay, pay), gorunur)
    return tuval


def _biye_profili(dis, b, W, H, metal):
    """Biye şeridinde dıştan içe ışık profili (128 = değişmez): kenarlar koyu, dıştan üçte birde parlak sırt."""
    profil = Image.new("L", (W, H), 128)
    onceki = ImageOps.expand(dis, 2, 0)
    for k in range(b):
        sonraki = onceki.filter(ImageFilter.MinFilter(3))
        halka = ImageChops.subtract(onceki, sonraki).crop((2, 2, 2 + W, 2 + H))
        t = (k + 0.5) / b
        deger = 0.62 + 0.55 * math.sin(math.pi * min(1, t * 1.25)) ** 1.5 + (0.18 if metal and 0.25 < t < 0.45 else 0)
        profil.paste(max(0, min(255, round(128 * deger))), (0, 0), halka)
        onceki = sonraki
    return profil.filter(ImageFilter.GaussianBlur(0.8))


@lru_cache(maxsize=4)
def _deri_zemin(boyut, arka):
    """Katalog fotoğraflarındaki gibi halının altında koyu, kabarcıklı deri zemin."""
    w, h = boyut
    k = Image.effect_noise((max(8, w // 4), max(8, h // 4)), 90).filter(ImageFilter.GaussianBlur(1.0))
    k = ImageOps.autocontrast(k).resize(boyut, Image.BICUBIC)
    kabarik = k.point(lambda q: 255 if q > 150 else int(q * 0.5)).filter(ImageFilter.GaussianBlur(1.5))
    isik = ImageChops.subtract(kabarik, ImageChops.offset(kabarik, 2, 2))
    zemin = Image.new("RGB", boyut, arka)
    zemin = Image.composite(Image.new("RGB", boyut, tuple(min(255, c + 26) for c in arka)), zemin,
                            isik.point(lambda q: min(255, q * 2)))
    golge = ImageChops.subtract(ImageChops.offset(kabarik, 2, 2), kabarik)
    return Image.composite(Image.new("RGB", boyut, (8, 7, 6)), zemin, golge.point(lambda q: min(255, q * 2)))


def _varak_parlat(resim, boyut):
    """Parlak (varak / metal) noktalar çapraz ışık bandında açılır; mat malzemelere neredeyse dokunmaz."""
    gri = resim.convert("L")
    parlak = gri.point(lambda q: max(0, q - 170) * 3)  # yalnız zaten parlak yerler
    bant = Image.new("L", (64, 64))
    bant.putdata([round(255 * max(0, math.cos((x + y - 52) / 64 * math.pi * 1.6)) ** 4) for y in range(64) for x in range(64)])
    bant = bant.resize(boyut, Image.BICUBIC)
    maske = ImageChops.multiply(parlak, bant).point(lambda q: int(q * 0.45))
    return Image.composite(Image.new("RGB", boyut, (255, 252, 240)), resim, maske)


@lru_cache(maxsize=64)
def nakis_maskesi(kod):
    """Atölyenin nakış kataloğundaki motifin şekli (L, 255 = iplik)."""
    yol = NAKIS_KLASORU / f"{kod.replace('.', '_')}.png"
    if not yol.exists():
        return motif_maskesi(200)
    return Image.open(yol).convert("L")


def _iplik_dokusu(iplik, boyut, px):
    renk = _hex(pc.IPLIK_HEX[iplik])
    if iplik in ("altin", "gumus"):
        return Image.blend(Image.new("RGB", boyut, renk), hg.malzeme(iplik, boyut, px), 0.5)
    taban = Image.new("RGB", boyut, renk)
    isik = Image.new("RGB", boyut, tuple(min(255, c + 35) for c in renk))
    return Image.composite(isik, taban, Image.effect_noise(boyut, 60).point(lambda q: max(0, q - 150)))


def _motifler(resim, kod, iplik, konumlar, px):
    """Nakış motiflerini (cx, cy, w, h, açı) yerlerine işler; motifin uzun kenarı w/h'nin uzun olanına gelir."""
    kaynak = nakis_maskesi(kod)
    for cx, cy, w, h, aci in konumlar:
        W, H = max(4, int(w * px)), max(4, int(h * px))
        m = kaynak
        if (m.width > m.height) != (W > H) and abs(W - H) > 2:
            m = m.rotate(90, expand=True)
        m = m.resize((W, H), Image.LANCZOS)
        if aci:
            m = m.rotate(-aci, expand=True, resample=Image.BICUBIC)
        doku = _iplik_dokusu(iplik, m.size, px)
        golge = m.filter(ImageFilter.GaussianBlur(max(1, px * 0.3))).point(lambda q: q // 3)
        x, y = int(cx * px - m.width / 2), int(cy * px - m.height / 2)
        resim.paste((40, 32, 20), (x + 1, y + 2), golge)
        resim.paste(doku, (x, y), m)


def nakis_ornegi(kod, iplik="altin", boy=160):
    """Motif seçim düğmesi için: açık zemin üstünde motif."""
    en, yuk = pc.MOTIF[kod]["en"], pc.MOTIF[kod]["boy"]
    olcek = (boy - 16) / max(en, yuk)
    im = Image.new("RGB", (boy, boy), (236, 231, 222))
    _motifler(im, kod, iplik, [(boy / 2 / olcek, boy / 2 / olcek, en, yuk, 0)], olcek)
    t = io.BytesIO()
    im.save(t, "PNG")
    return t.getvalue()


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
