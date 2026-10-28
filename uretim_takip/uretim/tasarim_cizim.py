"""Tasarım stüdyosu: tasarım değerleri, özet, alan ve lazer çıktısı (DXF / SVG, mm).

Halı katalogdaki Toskana yapısındadır (dıştan içe):
dış bant (desenli metal / deri) → kürk halka → iç bant (desenli) → kürk zemin → orta madalyon.
Bayiden gelen değerler `temizle` ile sınırlanır; görsel (`hali_gorsel`) ve lazer dosyası hep bu değerlerden üretilir.
"""

import math
import re

SEKILLER = [("dikdortgen", "Dikdörtgen"), ("oval", "Oval")]
# Bantlar: lazerle kesilen metalik / düz deri
BANTLAR = [
    ("altin", "Altın", "#d6b26a"), ("gumus", "Gümüş", "#c2c5c9"), ("bronz", "Bronz", "#a57846"),
    ("beyaz_deri", "Beyaz deri", "#f1ede4"), ("krem_deri", "Krem deri", "#e4d6b8"), ("siyah_deri", "Siyah deri", "#1f1d1c"),
]
# Zeminler: katalog fotoğraflarından alınan kürk / patchwork dokuları
ZEMINLER = [
    ("siyah_kurk", "Siyah kürk"), ("antrasit_kurk", "Antrasit kürk"), ("gri_kurk", "Gri kürk"),
    ("kahve_kurk", "Kahve kürk"), ("vizon_kurk", "Vizon kürk"), ("tilki_kurk", "Tilki (benekli)"),
    ("lacivert_kurk", "Lacivert kürk"), ("beyaz_kurk", "Beyaz kürk"), ("krem_patchwork", "Krem patchwork"),
    ("lacivert_patchwork", "Lacivert patchwork"),
]
# Desen kesiklerinin içinden görünen alt deri
ALTLAR = [
    ("siyah", "Siyah", "#1b1918"), ("beyaz", "Beyaz", "#f4f1ea"), ("krem", "Krem", "#e8dcc2"),
    ("altin", "Altın", "#c9a24a"), ("gri", "Gri", "#77797c"), ("kahve", "Kahve", "#4a3020"),
]
BANT_HEX = {k: h for k, _, h in BANTLAR}
ALT_HEX = {k: h for k, _, h in ALTLAR}
AD = {k: a for k, a, *_ in BANTLAR + ALTLAR}
ZEMIN_AD = dict(ZEMINLER)

VARSAYILAN = {
    "sekil": "dikdortgen", "en": 160, "boy": 230,
    "dis_bant": 16, "dis_malzeme": "altin", "dis_desen": "DB007",
    "halka": 20, "halka_zemin": "siyah_kurk",
    "ic_bant": 7, "ic_malzeme": "altin", "ic_desen": "DB007",
    "zemin": "siyah_kurk", "desen_alti": "siyah",
    "madalyon": 32, "madalyon_malzeme": "beyaz_deri",
    "katalog": "",
}

# Katalogdaki halılardan başlangıç kombinasyonları (bayi buradan başlayıp değiştirir).
HAZIRLAR = [
    ("TOS-034", "Siyah kürk, altın bantlar", {"dis_malzeme": "altin", "dis_desen": "DB007", "halka_zemin": "siyah_kurk",
                                              "ic_malzeme": "altin", "ic_desen": "DB007", "zemin": "siyah_kurk",
                                              "desen_alti": "siyah", "madalyon": 32, "madalyon_malzeme": "beyaz_deri"}),
    ("TOS-035", "Kahve halka, beyaz zemin", {"dis_bant": 0, "halka": 24, "halka_zemin": "kahve_kurk", "ic_bant": 12,
                                             "ic_malzeme": "altin", "ic_desen": "DB007", "zemin": "beyaz_kurk",
                                             "desen_alti": "kahve", "madalyon": 0}),
    ("TOS-036", "Antrasit kürk, gümüş", {"dis_malzeme": "gumus", "dis_desen": "DB007", "halka_zemin": "antrasit_kurk",
                                         "ic_malzeme": "gumus", "ic_desen": "DB007", "zemin": "antrasit_kurk",
                                         "desen_alti": "siyah", "madalyon": 30, "madalyon_malzeme": "beyaz_deri"}),
    ("TOS-037", "Kahve kürk, altın", {"dis_bant": 10, "dis_malzeme": "altin", "dis_desen": "DB007", "halka": 14,
                                      "halka_zemin": "kahve_kurk", "ic_bant": 6, "ic_malzeme": "altin", "ic_desen": "DB007",
                                      "zemin": "kahve_kurk", "desen_alti": "kahve", "madalyon": 30,
                                      "madalyon_malzeme": "krem_deri"}),
    ("TOS-038", "Siyah kürk, tek altın bant", {"dis_bant": 12, "dis_malzeme": "altin", "dis_desen": "DB010",
                                               "halka": 0, "ic_bant": 0, "zemin": "siyah_kurk", "desen_alti": "siyah",
                                               "madalyon": 0}),
    ("TOS-044", "Lacivert kürk, gümüş", {"dis_bant": 10, "dis_malzeme": "gumus", "dis_desen": "DB007", "halka": 16,
                                         "halka_zemin": "lacivert_kurk", "ic_bant": 6, "ic_malzeme": "gumus",
                                         "ic_desen": "DB007", "zemin": "lacivert_kurk", "desen_alti": "siyah",
                                         "madalyon": 30, "madalyon_malzeme": "beyaz_deri"}),
    ("TOS-050", "Tilki kürk, altın", {"dis_bant": 12, "dis_malzeme": "altin", "dis_desen": "", "halka": 14,
                                      "halka_zemin": "tilki_kurk", "ic_bant": 5, "ic_malzeme": "altin", "ic_desen": "",
                                      "zemin": "tilki_kurk", "madalyon": 0}),
    ("TOS-055", "Gri kürk, krem motifli bant", {"dis_bant": 18, "dis_malzeme": "krem_deri", "dis_desen": "DB011",
                                                "halka": 0, "ic_bant": 0, "zemin": "gri_kurk", "desen_alti": "kahve",
                                                "madalyon": 34, "madalyon_malzeme": "krem_deri"}),
    ("LTS-003", "Vizon kürk, beyaz lazer bant", {"dis_bant": 0, "halka": 16, "halka_zemin": "vizon_kurk",
                                                 "ic_bant": 16, "ic_malzeme": "beyaz_deri", "ic_desen": "DB004",
                                                 "zemin": "vizon_kurk", "desen_alti": "siyah", "madalyon": 30,
                                                 "madalyon_malzeme": "gumus"}),
    ("LTS-005", "Krem patchwork, krem lazer bant", {"dis_bant": 18, "dis_malzeme": "krem_deri", "dis_desen": "DB001",
                                                    "halka": 0, "ic_bant": 0, "zemin": "krem_patchwork",
                                                    "desen_alti": "krem", "madalyon": 0}),
    ("LTS-006", "Lacivert patchwork, altın lazer", {"dis_bant": 20, "dis_malzeme": "altin", "dis_desen": "DB002",
                                                    "halka": 0, "ic_bant": 0, "zemin": "lacivert_patchwork",
                                                    "desen_alti": "siyah", "madalyon": 0}),
]
HAZIR = {kod: deger for kod, _, deger in HAZIRLAR}


def _sayi(deger, varsayilan, alt, ust):
    try:
        sayi = float(str(deger).replace(",", "."))
    except (TypeError, ValueError):
        sayi = varsayilan
    if math.isnan(sayi):
        sayi = varsayilan
    return round(min(max(sayi, alt), ust), 1)


def _secim(deger, anahtarlar, varsayilan):
    return deger if deger in anahtarlar else varsayilan


def hazir_degerler(kod):
    """Katalog kombinasyonu: varsayılanların üzerine o modelin ayarları."""
    return {**VARSAYILAN, **HAZIR.get(kod, {}), "katalog": kod if kod in HAZIR else ""}


def temizle(veri, desen_kodlari=()):
    """Bayiden gelen değerleri üretilebilir sınırlara çeker. desen_kodlari: kullanılabilir lazer desenleri."""
    veri = veri or {}
    g = lambda alan: veri.get(alan, VARSAYILAN[alan])  # noqa: E731
    bantlar, zeminler, altlar = [k for k, *_ in BANTLAR], [k for k, _ in ZEMINLER], [k for k, *_ in ALTLAR]
    v = {"sekil": _secim(g("sekil"), [k for k, _ in SEKILLER], "dikdortgen")}
    v["en"] = _sayi(g("en"), VARSAYILAN["en"], 60, 600)
    v["boy"] = _sayi(g("boy"), VARSAYILAN["boy"], 60, 800)
    kisa = min(v["en"], v["boy"])
    kalan = kisa / 2 - 10  # ortada en az 20 cm zemin kalsın
    v["dis_bant"] = _sayi(g("dis_bant"), 0, 0, min(40, kalan))
    kalan -= v["dis_bant"]
    v["halka"] = _sayi(g("halka"), 0, 0, max(0, min(60, kalan)))
    kalan -= v["halka"]
    v["ic_bant"] = _sayi(g("ic_bant"), 0, 0, max(0, min(30, kalan)))
    for alan in ("dis", "ic"):
        v[f"{alan}_malzeme"] = _secim(g(f"{alan}_malzeme"), bantlar, "altin")
        kod = str(g(f"{alan}_desen") or "").strip().upper()
        v[f"{alan}_desen"] = kod if kod in desen_kodlari and v["sekil"] == "dikdortgen" else ""
    v["halka_zemin"] = _secim(g("halka_zemin"), zeminler, "siyah_kurk")
    v["zemin"] = _secim(g("zemin"), zeminler, "siyah_kurk")
    v["desen_alti"] = _secim(g("desen_alti"), altlar, "siyah")
    ic_kisa = kisa - 2 * (v["dis_bant"] + v["halka"] + v["ic_bant"])
    v["madalyon"] = _sayi(g("madalyon"), 0, 0, max(0, round(ic_kisa * 0.6)))
    if 0 < v["madalyon"] < 10:
        v["madalyon"] = 10
    v["madalyon_malzeme"] = _secim(g("madalyon_malzeme"), bantlar, "beyaz_deri")
    v["katalog"] = g("katalog") if g("katalog") in HAZIR else ""
    if v["halka"] == 0:
        v["halka_zemin"] = v["zemin"]
    return v


def alan_m2(v):
    w, h = v["en"], v["boy"]
    alan = math.pi * w * h / 4 if v["sekil"] == "oval" else w * h
    return round(alan / 10000, 2)


def ozet(v):
    p = [f"{dict(SEKILLER)[v['sekil']]} {v['en']:g}×{v['boy']:g} cm"]
    if v["dis_bant"]:
        p.append(f"dış bant {v['dis_bant']:g} cm {AD[v['dis_malzeme']]}" + (f" {v['dis_desen']}" if v["dis_desen"] else ""))
    if v["halka"]:
        p.append(f"{ZEMIN_AD[v['halka_zemin']].lower()} halka {v['halka']:g} cm")
    if v["ic_bant"]:
        p.append(f"iç bant {v['ic_bant']:g} cm {AD[v['ic_malzeme']]}" + (f" {v['ic_desen']}" if v["ic_desen"] else ""))
    p.append(f"zemin {ZEMIN_AD[v['zemin']].lower()}")
    if v["dis_desen"] or v["ic_desen"]:
        p.append(f"desen altı {AD[v['desen_alti']].lower()}")
    if v["madalyon"]:
        p.append(f"madalyon Ø{v['madalyon']:g} cm {AD[v['madalyon_malzeme']]}")
    if v["katalog"]:
        p.append(f"({v['katalog']} esinli)")
    return " · ".join(p)


# --- Lazer çıktısı (mm) --------------------------------------------------------

KOSE_CM = 3  # katalogdaki halıların köşe yuvarlaklığı


def _yuvarlak_dikdortgen(x, y, w, h, r, n=8):
    r = max(0.0, min(r, w / 2, h / 2))
    noktalar = []
    for cx, cy, bas in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for i in range(n + 1):
            a = math.radians(bas + 90 * i / n)
            noktalar.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return noktalar


def _elips(cx, cy, rx, ry, n=96):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def hatlar(v):
    """Kesim hatları (cm): [(katman, noktalar)]. Dış hat, bant kenarları ve madalyon."""
    w, h = v["en"], v["boy"]
    sonuc = []
    icerlek = [("KESIM", 0)]
    d = v["dis_bant"]
    if d:
        icerlek.append(("DIS_BANT", d))
    d += v["halka"]
    if v["ic_bant"]:
        icerlek += [("IC_BANT", d), ("IC_BANT", d + v["ic_bant"])]
    for katman, d in icerlek:
        if v["sekil"] == "oval":
            sonuc.append((katman, _elips(w / 2, h / 2, w / 2 - d, h / 2 - d)))
        else:
            sonuc.append((katman, _yuvarlak_dikdortgen(d, d, w - 2 * d, h - 2 * d, max(KOSE_CM - d, 0.5))))
    if v["madalyon"]:
        sonuc.append(("MADALYON", _elips(w / 2, h / 2, v["madalyon"] / 2, v["madalyon"] / 2)))
    return sonuc


def svg_lazer(v):
    mm = 10
    w, h = v["en"] * mm, v["boy"] * mm
    renk = {"KESIM": "#000", "DIS_BANT": "#00f", "IC_BANT": "#f00", "MADALYON": "#0a0"}
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}mm" height="{h:.0f}mm" viewBox="0 0 {w:.0f} {h:.0f}">',
         '<g fill="none" stroke-width="0.3">']
    for katman, noktalar in hatlar(v):
        nokta = " ".join(f"{x * mm:.2f},{y * mm:.2f}" for x, y in noktalar)
        p.append(f'<polygon class="{katman}" stroke="{renk[katman]}" points="{nokta}"/>')
    p.append("</g></svg>")
    return "".join(p)


def dxf(v, baslik=""):
    """AutoCAD R12 ASCII DXF, mm. Katmanlar: KESIM, DIS_BANT, IC_BANT, MADALYON (+ NOT)."""
    mm, yuk = 10, v["boy"]
    s = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$MEASUREMENT", "70", "1",
         "0", "ENDSEC", "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "5"]
    for ad, renk in (("KESIM", 7), ("DIS_BANT", 5), ("IC_BANT", 1), ("MADALYON", 3), ("NOT", 8)):
        s += ["0", "LAYER", "2", ad, "70", "0", "62", str(renk), "6", "CONTINUOUS"]
    s += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for katman, noktalar in hatlar(v):
        s += ["0", "POLYLINE", "8", katman, "66", "1", "70", "1"]
        for x, y in noktalar:  # DXF'te y yukarı doğru
            s += ["0", "VERTEX", "8", katman, "10", f"{x * mm:.3f}", "20", f"{(yuk - y) * mm:.3f}"]
        s += ["0", "SEQEND", "8", katman]
    notlar = [baslik] if baslik else []
    if v["dis_desen"]:
        notlar.append(f"Dis bant deseni {v['dis_desen']}")
    if v["ic_desen"]:
        notlar.append(f"Ic bant deseni {v['ic_desen']}")
    for i, metin in enumerate(notlar):
        guvenli = re.sub(r"[^\w .×·-]", "", metin)[:120]
        s += ["0", "TEXT", "8", "NOT", "10", "0", "20", f"{-40 - i * 35:.1f}", "40", "25", "1", guvenli]
    s += ["0", "ENDSEC", "0", "EOF"]
    return "\r\n".join(s) + "\r\n"
