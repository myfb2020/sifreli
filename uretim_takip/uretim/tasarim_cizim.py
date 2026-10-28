"""Tasarım stüdyosu çizimi: tek geometriden hem ekran önizlemesi (SVG) hem lazer dosyası (DXF / SVG, mm).

Ölçüler cm olarak tutulur; lazer çıktısı mm'dir. Bayiden gelen değerler `temizle` ile sınırlanır,
çizim her zaman sunucuda bu değerlerden üretilir (tarayıcıdan gelen çizim kullanılmaz).
"""

import math
import re

SEKILLER = [("dikdortgen", "Dikdörtgen"), ("kesik", "Köşesi kesik"), ("oval", "Oval"), ("yuvarlak", "Yuvarlak")]
MOTIFLER = [("yok", "Motif yok"), ("daire", "Daire"), ("baklava", "Baklava"), ("yildiz", "Yıldız"),
            ("altigen", "Altıgen")]
MADALYONLAR = [("yok", "Madalyon yok"), ("daire", "Daire"), ("oval", "Oval")]
RENKLER = [
    ("siyah", "Siyah", "#1d1b1a"), ("antrasit", "Antrasit", "#3b3d40"), ("gri", "Gri", "#8d8f92"),
    ("beyaz", "Beyaz", "#f7f5f0"), ("krem", "Krem", "#ece2cc"), ("bej", "Bej", "#d6c2a0"),
    ("taba", "Taba", "#a8693a"), ("kahve", "Kahve", "#5b3a26"), ("altin", "Altın", "#c9a24a"),
    ("gumus", "Gümüş", "#b9bcc0"), ("bordo", "Bordo", "#6e1f2b"), ("lacivert", "Lacivert", "#1f2c4c"),
    ("yesil", "Yeşil", "#3f5a3c"),
]
RENK_HEX = {k: h for k, _, h in RENKLER}
RENK_AD = {k: a for k, a, _ in RENKLER}

VARSAYILAN = {
    "sekil": "dikdortgen", "en": 160, "boy": 230, "zemin_renk": "krem", "bant": 15, "bant_renk": "altin",
    "motif": "baklava", "motif_renk": "siyah", "madalyon": "daire", "madalyon_cap": 50, "madalyon_renk": "altin",
    "desen_kodu": "",
}


def _sayi(deger, varsayilan, alt, ust):
    try:
        sayi = float(str(deger).replace(",", "."))
    except (TypeError, ValueError):
        sayi = varsayilan
    if math.isnan(sayi):
        sayi = varsayilan
    return round(min(max(sayi, alt), ust), 1)


def _secim(deger, secenekler, varsayilan):
    anahtarlar = [s[0] for s in secenekler]
    return deger if deger in anahtarlar else varsayilan


def temizle(veri, desen_kodlari=()):
    """Bayiden gelen tasarım değerlerini güvenli ve üretilebilir sınırlara çeker."""
    veri = veri or {}
    v = {}
    v["sekil"] = _secim(veri.get("sekil"), SEKILLER, VARSAYILAN["sekil"])
    v["en"] = _sayi(veri.get("en"), VARSAYILAN["en"], 40, 1000)
    v["boy"] = v["en"] if v["sekil"] == "yuvarlak" else _sayi(veri.get("boy"), VARSAYILAN["boy"], 40, 1500)
    kisa = min(v["en"], v["boy"])
    for alan in ("zemin_renk", "bant_renk", "motif_renk", "madalyon_renk"):
        v[alan] = veri.get(alan) if veri.get(alan) in RENK_HEX else VARSAYILAN[alan]
    v["bant"] = _sayi(veri.get("bant"), VARSAYILAN["bant"], 0, kisa / 4)
    v["motif"] = _secim(veri.get("motif"), MOTIFLER, VARSAYILAN["motif"]) if v["bant"] >= 4 else "yok"
    v["madalyon"] = _secim(veri.get("madalyon"), MADALYONLAR, VARSAYILAN["madalyon"])
    ic_kisa = kisa - 2 * v["bant"]
    v["madalyon_cap"] = _sayi(veri.get("madalyon_cap"), VARSAYILAN["madalyon_cap"], 10, max(10, ic_kisa * 0.7))
    kod = str(veri.get("desen_kodu") or "").strip().upper()
    v["desen_kodu"] = kod if kod in desen_kodlari and re.fullmatch(r"[A-Z0-9-]{1,20}", kod) else ""
    return v


# --- Geometri (cm, y aşağı doğru) ---------------------------------------------


def _elips(cx, cy, rx, ry, n=96):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def dis_sekil(v):
    w, h = v["en"], v["boy"]
    if v["sekil"] in ("oval", "yuvarlak"):
        return _elips(w / 2, h / 2, w / 2, h / 2)
    if v["sekil"] == "kesik":
        c = min(w, h) * 0.15
        return [(c, 0), (w - c, 0), (w, c), (w, h - c), (w - c, h), (c, h), (0, h - c), (0, c)]
    return [(0, 0), (w, 0), (w, h), (0, h)]


def _alan_isareti(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def iceri_kaydir(p, d):
    """Dışbükey çokgeni d kadar içeri kaydırır (kenarlar paralel taşınıp kesiştirilir)."""
    if d <= 0:
        return list(p)
    yon = 1 if _alan_isareti(p) > 0 else -1
    cizgiler = []
    for i in range(len(p)):
        (x1, y1), (x2, y2) = p[i], p[(i + 1) % len(p)]
        dx, dy = x2 - x1, y2 - y1
        boy = math.hypot(dx, dy) or 1
        nx, ny = -dy / boy * yon, dx / boy * yon  # içe bakan normal
        cizgiler.append(((x1 + nx * d, y1 + ny * d), (dx, dy)))
    sonuc = []
    for i in range(len(cizgiler)):
        (a, da), (b, db) = cizgiler[i - 1], cizgiler[i]
        bolen = da[0] * db[1] - da[1] * db[0]
        if abs(bolen) < 1e-9:
            sonuc.append(b)
            continue
        t = ((b[0] - a[0]) * db[1] - (b[1] - a[1]) * db[0]) / bolen
        sonuc.append((a[0] + da[0] * t, a[1] + da[1] * t))
    return sonuc


def _motif(tur, x, y, r, aci):
    if tur == "daire":
        return {"tur": "daire", "x": x, "y": y, "r": r * 0.8}
    if tur == "baklava":
        yerel = [(r, 0), (0, r * 0.6), (-r, 0), (0, -r * 0.6)]
    elif tur == "yildiz":
        yerel = [((r if i % 2 == 0 else r * 0.45) * math.cos(math.pi * i / 8),
                  (r if i % 2 == 0 else r * 0.45) * math.sin(math.pi * i / 8)) for i in range(16)]
    else:  # altıgen
        yerel = [(r * 0.85 * math.cos(math.pi * i / 3), r * 0.85 * math.sin(math.pi * i / 3)) for i in range(6)]
    c, s = math.cos(aci), math.sin(aci)
    return {"tur": "poligon", "noktalar": [(x + px * c - py * s, y + px * s + py * c) for px, py in yerel]}


def motifler(v, orta_cizgi):
    """Kenar bandının orta çizgisi boyunca eşit aralıklı motifler. Köşeli şekillerde köşelere de motif gelir."""
    if v["motif"] == "yok":
        return []
    r = v["bant"] * 0.32
    aralik = r * 3.2
    sonuc = []
    koseli = len(orta_cizgi) <= 8
    for i in range(len(orta_cizgi)):
        (x1, y1), (x2, y2) = orta_cizgi[i], orta_cizgi[(i + 1) % len(orta_cizgi)]
        aci = math.atan2(y2 - y1, x2 - x1)
        if koseli:
            sonuc.append(_motif(v["motif"], x1, y1, r, aci))
            kenar = math.hypot(x2 - x1, y2 - y1)
            k = max(0, round(kenar / aralik) - 1)
            for j in range(1, k + 1):
                t = j / (k + 1)
                sonuc.append(_motif(v["motif"], x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, aci))
    if not koseli:  # eğri: çevre boyunca yay uzunluğuna göre
        kenarlar = [math.hypot(orta_cizgi[(i + 1) % len(orta_cizgi)][0] - orta_cizgi[i][0],
                               orta_cizgi[(i + 1) % len(orta_cizgi)][1] - orta_cizgi[i][1])
                    for i in range(len(orta_cizgi))]
        cevre = sum(kenarlar)
        adet = max(3, int(cevre / aralik))
        hedefler = [cevre * j / adet for j in range(adet)]
        yol, i = 0.0, 0
        for hedef in hedefler:
            while i < len(kenarlar) - 1 and yol + kenarlar[i] < hedef:
                yol += kenarlar[i]
                i += 1
            (x1, y1), (x2, y2) = orta_cizgi[i], orta_cizgi[(i + 1) % len(orta_cizgi)]
            t = (hedef - yol) / (kenarlar[i] or 1)
            sonuc.append(_motif(v["motif"], x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, math.atan2(y2 - y1, x2 - x1)))
    return sonuc


def madalyon(v):
    if v["madalyon"] == "yok":
        return None
    w, h, r = v["en"], v["boy"], v["madalyon_cap"] / 2
    if v["madalyon"] == "daire":
        return _elips(w / 2, h / 2, r, r)
    uzun_dikey = h >= w
    return _elips(w / 2, h / 2, r if uzun_dikey else r * 1.4, r * 1.4 if uzun_dikey else r)


def cizim(v):
    """Tüm parçalar: {'dis', 'ic', 'motifler', 'madalyon'} (cm)."""
    dis = dis_sekil(v)
    ic = iceri_kaydir(dis, v["bant"]) if v["bant"] > 0 else None
    orta = iceri_kaydir(dis, v["bant"] / 2) if v["bant"] > 0 else None
    return {"dis": dis, "ic": ic, "motifler": motifler(v, orta) if orta else [], "madalyon": madalyon(v)}


def alan_m2(v):
    w, h = v["en"], v["boy"]
    if v["sekil"] in ("oval", "yuvarlak"):
        alan = math.pi * w * h / 4
    elif v["sekil"] == "kesik":
        c = min(w, h) * 0.15
        alan = w * h - 2 * c * c
    else:
        alan = w * h
    return round(alan / 10000, 2)


def ozet(v):
    parcalar = [f"{dict(SEKILLER)[v['sekil']]} {v['en']:g}×{v['boy']:g} cm", f"zemin {RENK_AD[v['zemin_renk']]}"]
    if v["bant"]:
        bant = f"{v['bant']:g} cm {RENK_AD[v['bant_renk']]} kenar"
        if v["motif"] != "yok":
            bant += f", {dict(MOTIFLER)[v['motif']].lower()} motif ({RENK_AD[v['motif_renk']]} görünür)"
        parcalar.append(bant)
    if v["madalyon"] != "yok":
        parcalar.append(f"{dict(MADALYONLAR)[v['madalyon']].lower()} madalyon {v['madalyon_cap']:g} cm "
                        f"{RENK_AD[v['madalyon_renk']]}")
    if v["desen_kodu"]:
        parcalar.append(f"lazer deseni {v['desen_kodu']}")
    return " · ".join(parcalar)


# --- Çıktılar -----------------------------------------------------------------


def _nokta_metni(noktalar, olcek=1.0):
    return " ".join(f"{x * olcek:.2f},{y * olcek:.2f}" for x, y in noktalar)


def svg_onizleme(v):
    """Renkli önizleme (ekran ve istasyon için)."""
    c = cizim(v)
    pay = max(v["en"], v["boy"]) * 0.04
    w, h = v["en"] + 2 * pay, v["boy"] + 2 * pay + pay * 2.5
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pay:.1f} {-pay:.1f} {w:.1f} {h:.1f}" '
         f'role="img" aria-label="Halı tasarımı">']
    kalem = max(v["en"], v["boy"]) / 400
    dis_renk = RENK_HEX[v["bant_renk"]] if c["ic"] else RENK_HEX[v["zemin_renk"]]
    p.append(f'<polygon points="{_nokta_metni(c["dis"])}" fill="{dis_renk}" stroke="#333" stroke-width="{kalem:.2f}"/>')
    if c["ic"]:
        p.append(f'<polygon points="{_nokta_metni(c["ic"])}" fill="{RENK_HEX[v["zemin_renk"]]}" stroke="#333" '
                 f'stroke-width="{kalem:.2f}"/>')
    motif_renk = RENK_HEX[v["motif_renk"]]
    for m in c["motifler"]:
        if m["tur"] == "daire":
            p.append(f'<circle cx="{m["x"]:.2f}" cy="{m["y"]:.2f}" r="{m["r"]:.2f}" fill="{motif_renk}"/>')
        else:
            p.append(f'<polygon points="{_nokta_metni(m["noktalar"])}" fill="{motif_renk}"/>')
    if c["madalyon"]:
        p.append(f'<polygon points="{_nokta_metni(c["madalyon"])}" fill="{RENK_HEX[v["madalyon_renk"]]}" '
                 f'stroke="#333" stroke-width="{kalem:.2f}"/>')
    yazi = f"{v['en']:g} × {v['boy']:g} cm" + (f" · {v['desen_kodu']}" if v["desen_kodu"] else "")
    p.append(f'<text x="{v["en"] / 2:.1f}" y="{v["boy"] + pay * 2.2:.1f}" text-anchor="middle" '
             f'font-family="sans-serif" font-size="{pay * 1.4:.1f}" fill="#555">{yazi}</text>')
    p.append("</svg>")
    return "".join(p)


def svg_lazer(v):
    """Lazer için yalnızca kesim çizgileri, gerçek ölçüde (mm)."""
    c = cizim(v)
    mm = 10
    w, h = v["en"] * mm, v["boy"] * mm
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}mm" height="{h:.0f}mm" viewBox="0 0 {w:.0f} {h:.0f}">',
         '<g fill="none" stroke-width="0.3">']
    p.append(f'<polygon id="KESIM" stroke="#000" points="{_nokta_metni(c["dis"], mm)}"/>')
    if c["ic"]:
        p.append(f'<polygon id="BANT" stroke="#00f" points="{_nokta_metni(c["ic"], mm)}"/>')
    for m in c["motifler"]:
        if m["tur"] == "daire":
            p.append(f'<circle stroke="#f00" cx="{m["x"] * mm:.2f}" cy="{m["y"] * mm:.2f}" r="{m["r"] * mm:.2f}"/>')
        else:
            p.append(f'<polygon stroke="#f00" points="{_nokta_metni(m["noktalar"], mm)}"/>')
    if c["madalyon"]:
        p.append(f'<polygon id="MADALYON" stroke="#0a0" points="{_nokta_metni(c["madalyon"], mm)}"/>')
    p.append("</g></svg>")
    return "".join(p)


def dxf(v, baslik=""):
    """AutoCAD R12 ASCII DXF, mm. Katmanlar: KESIM (dış hat), BANT, DESEN (motifler), MADALYON."""
    c = cizim(v)
    mm, yuk = 10, v["boy"]
    satirlar = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$MEASUREMENT", "70", "1",
                "0", "ENDSEC", "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "4"]
    for ad, renk in (("KESIM", 7), ("BANT", 5), ("DESEN", 1), ("MADALYON", 3)):
        satirlar += ["0", "LAYER", "2", ad, "70", "0", "62", str(renk), "6", "CONTINUOUS"]
    satirlar += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def cokgen(noktalar, katman):
        satirlar.extend(["0", "POLYLINE", "8", katman, "66", "1", "70", "1"])
        for x, y in noktalar:  # DXF'te y yukarı doğru
            satirlar.extend(["0", "VERTEX", "8", katman, "10", f"{x * mm:.3f}", "20", f"{(yuk - y) * mm:.3f}"])
        satirlar.extend(["0", "SEQEND", "8", katman])

    cokgen(c["dis"], "KESIM")
    if c["ic"]:
        cokgen(c["ic"], "BANT")
    for m in c["motifler"]:
        if m["tur"] == "daire":
            satirlar += ["0", "CIRCLE", "8", "DESEN", "10", f"{m['x'] * mm:.3f}", "20", f"{(yuk - m['y']) * mm:.3f}",
                         "40", f"{m['r'] * mm:.3f}"]
        else:
            cokgen(m["noktalar"], "DESEN")
    if c["madalyon"]:
        cokgen(c["madalyon"], "MADALYON")
    if baslik:
        guvenli = re.sub(r"[^\w .×·-]", "", baslik)[:120]
        satirlar += ["0", "TEXT", "8", "NOT", "10", "0", "20", f"{-40:.1f}", "40", "25", "1", guvenli]
    satirlar += ["0", "ENDSEC", "0", "EOF"]
    return "\r\n".join(satirlar) + "\r\n"
