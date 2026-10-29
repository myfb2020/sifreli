"""Parçalı (lego) suni deri halı: halı lazerle kesilen parçalardan oluşur, zig-zag ile birleştirilir.

Bir tasarım (`v`) bir düzen ve ölçülerden oluşur; `parcalar(v)` her parçanın şeklini (cm), malzemesini,
desenini ve istasyonunu verir. Atölye sınırları: rulo eni 140 cm, lazer tablası 140×300 cm, nakış alanı
40×60 cm (7 kafa aynı anda işler). Bu sınırları aşan parçalar program tarafından bölünür.
"""

import math
import re

RULO_ENI = 140  # cm
TABLA_BOYU = 300  # cm (lazer tablası 140×300)
NAKIS_EN, NAKIS_BOY = 40, 60  # cm, nakış makinesinin en büyük alanı
NAKIS_KAFA = 7  # aynı motif aynı anda kaç kez işlenir

DUZENLER = [
    ("cerceve", "Dikdörtgen çerçeve", "Zemin + desenli bantlar; bantlar uç uca birleşir"),
    ("oval_serit", "Oval + nakış şeridi", "Oval zemin, ortadan geçen nakışlı şerit"),
    ("yuvarlak", "Yuvarlak halka", "Orta disk + parçalı desenli halka + dış halka"),
]

# Suni deri malzemeler: doku = fotoğraf dokusu (tasarim_varlik/doku), yoksa renk.
MALZEMELER = [
    ("beyaz_keten", "Beyaz keten görünümlü", "#ece7dd"),
    ("bej_keten", "Bej keten görünümlü", "#cdbd9f"),
    ("gri_keten", "Gri keten görünümlü", "#9a9894"),
    ("antrasit_keten", "Antrasit keten görünümlü", "#55524e"),
    ("siyah_kadife", "Siyah kadife", "#151417"),
    ("gri_kadife", "Gri kadife", "#a7a6a3"),
    ("dalgali_pelus", "Dalgalı peluş", "#d9d3c8"),
    ("varak_altin", "Altın varaklı", "#e9dcbc"),
    ("varak_gumus", "Gümüş varaklı", "#cfd0d1"),
    ("varak_sampanya", "Şampanya varaklı", "#ddd0b8"),
    ("krem_deri", "Krem deri", "#e4d6b8"),
    ("siyah_deri", "Siyah deri", "#1f1d1c"),
    ("altin", "Altın (metalik)", "#d6b26a"),
    ("gumus", "Gümüş (metalik)", "#c2c5c9"),
]
MALZEME_AD = {k: a for k, a, _ in MALZEMELER}
MALZEME_HEX = {k: h for k, _, h in MALZEMELER}
ALTLAR = [("siyah", "Siyah"), ("kahve", "Kahve"), ("krem", "Krem"), ("altin_sim", "Altın sim"),
          ("gumus_sim", "Gümüş sim"), ("siyah_rugan", "Siyah rugan")]
NAKISLAR = [("yok", "Nakış yok"), ("grek_kare", "Grek kare (altın iplik)"), ("grek_kare_gumus", "Grek kare (gümüş iplik)")]
KENARLAR = [("biye", "Biye"), ("lanfel", "Lanfel")]
KENAR_RENKLERI = [("altin", "Altın"), ("gumus", "Gümüş"), ("siyah", "Siyah"), ("beyaz", "Beyaz"), ("bej", "Bej")]

VARSAYILAN = {
    "duzen": "cerceve", "en": 120, "boy": 180, "pay": 1,
    # çerçeve
    "dis_bant": 8, "dis_malzeme": "antrasit_keten", "dis_desen": "",
    "ara": 14, "ara_malzeme": "beyaz_keten",
    "ic_bant": 12, "ic_malzeme": "antrasit_keten", "ic_desen": "DB003",
    "zemin": "beyaz_keten", "desen_alti": "kahve",
    # oval + şerit
    "serit": 26, "serit_malzeme": "beyaz_keten", "nakis": "grek_kare", "motif": 22, "aralik": 4,
    # yuvarlak
    "cap": 200, "dis_halka": 26, "desen_halka": 24, "halka_malzeme": "siyah_kadife",
    "desen_malzeme": "varak_gumus", "desen": "DB003",
    "kenar": "biye", "kenar_renk": "altin",
}

# Fotoğraflardaki atölye halıları (başlangıç noktası)
HAZIRLAR = [
    ("P-1", "Gri bant, beyaz zemin, lazer çerçeve", {
        "duzen": "cerceve", "en": 90, "boy": 160, "dis_bant": 6, "dis_malzeme": "antrasit_keten", "dis_desen": "",
        "ara": 12, "ara_malzeme": "beyaz_keten", "ic_bant": 11, "ic_malzeme": "antrasit_keten", "ic_desen": "DB003",
        "zemin": "beyaz_keten", "desen_alti": "krem", "kenar": "biye", "kenar_renk": "siyah"}),
    ("P-2", "Gümüş varak, lazer bant, altın biye", {
        "duzen": "cerceve", "en": 100, "boy": 150, "dis_bant": 0, "ara": 0, "ic_bant": 13,
        "ic_malzeme": "varak_gumus", "ic_desen": "DB001", "zemin": "varak_gumus", "desen_alti": "altin_sim",
        "kenar": "biye", "kenar_renk": "altin"}),
    ("P-3", "Bej oval, beyaz şerit, Grek nakış", {
        "duzen": "oval_serit", "en": 130, "boy": 190, "zemin": "bej_keten", "serit": 26, "serit_malzeme": "beyaz_keten",
        "nakis": "grek_kare", "motif": 22, "aralik": 4, "kenar": "biye", "kenar_renk": "bej"}),
    ("P-4", "Yuvarlak: siyah kadife, gümüş desenli halka", {
        "duzen": "yuvarlak", "cap": 200, "dis_halka": 26, "halka_malzeme": "siyah_kadife", "desen_halka": 24,
        "desen_malzeme": "varak_gumus", "desen": "DB003", "zemin": "siyah_kadife", "desen_alti": "krem",
        "kenar": "biye", "kenar_renk": "siyah"}),
]
HAZIR = {k: d for k, _, d in HAZIRLAR}


# --- Değerleri temizleme --------------------------------------------------------


def _sayi(deger, varsayilan, alt, ust):
    try:
        s = float(str(deger).replace(",", "."))
    except (TypeError, ValueError):
        s = varsayilan
    if math.isnan(s):
        s = varsayilan
    return round(min(max(s, alt), ust), 1)


def _sec(deger, secenekler, varsayilan):
    anahtarlar = [s[0] for s in secenekler]
    return deger if deger in anahtarlar else varsayilan


def hazir_degerler(kod):
    return {**VARSAYILAN, **HAZIR.get(kod, {}), "hazir": kod if kod in HAZIR else ""}


def temizle(veri, desen_kodlari=()):
    veri = veri or {}
    g = lambda a: veri.get(a, VARSAYILAN[a])  # noqa: E731
    desen = lambda a: (str(g(a) or "").upper() if str(g(a) or "").upper() in desen_kodlari  # noqa: E731
                       and re.fullmatch(r"[A-Z0-9-]{1,20}", str(g(a) or "").upper()) else "")
    v = {"tip": "parcali", "duzen": _sec(g("duzen"), DUZENLER, "cerceve")}
    v["pay"] = _sayi(g("pay"), 1, 0, 2)
    v["zemin"] = _sec(g("zemin"), MALZEMELER, "beyaz_keten")
    v["desen_alti"] = _sec(g("desen_alti"), ALTLAR, "siyah")
    v["kenar"] = _sec(g("kenar"), KENARLAR, "biye")
    v["kenar_renk"] = _sec(g("kenar_renk"), KENAR_RENKLERI, "altin")
    v["hazir"] = veri.get("hazir") if veri.get("hazir") in HAZIR else ""
    if v["duzen"] == "yuvarlak":
        v["cap"] = _sayi(g("cap"), 200, 60, 400)
        v["en"] = v["boy"] = v["cap"]
        kalan = v["cap"] / 2 - 15
        v["dis_halka"] = _sayi(g("dis_halka"), 0, 0, max(0, min(50, kalan)))
        v["desen_halka"] = _sayi(g("desen_halka"), 0, 0, max(0, min(40, kalan - v["dis_halka"])))
        v["halka_malzeme"] = _sec(g("halka_malzeme"), MALZEMELER, "siyah_kadife")
        v["desen_malzeme"] = _sec(g("desen_malzeme"), MALZEMELER, "varak_gumus")
        v["desen"] = desen("desen")
        return v
    v["en"] = _sayi(g("en"), 120, 60, 400)
    v["boy"] = _sayi(g("boy"), 180, 60, 600)
    kisa = min(v["en"], v["boy"])
    if v["duzen"] == "oval_serit":
        v["serit"] = _sayi(g("serit"), 26, 10, max(10, min(60, kisa / 2)))
        v["serit_malzeme"] = _sec(g("serit_malzeme"), MALZEMELER, "beyaz_keten")
        v["nakis"] = _sec(g("nakis"), NAKISLAR, "grek_kare")
        v["motif"] = _sayi(g("motif"), 22, 8, min(NAKIS_EN, v["serit"] - 2))
        v["aralik"] = _sayi(g("aralik"), 4, 1, 30)
        return v
    kalan = kisa / 2 - 10
    for alan, mal in (("dis_bant", "dis_malzeme"), ("ara", "ara_malzeme"), ("ic_bant", "ic_malzeme")):
        v[alan] = _sayi(g(alan), 0, 0, max(0, min(40, kalan)))
        kalan -= v[alan]
        v[mal] = _sec(g(mal), MALZEMELER, "beyaz_keten")
    v["dis_desen"] = desen("dis_desen")
    v["ic_desen"] = desen("ic_desen")
    return v


# --- Geometri (cm, y aşağı) --------------------------------------------------------


def dikd(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def daire(cx, cy, r, n=120):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def yay(cx, cy, r1, r2, a0, a1, n=24):
    dis = [(cx + r2 * math.cos(a0 + (a1 - a0) * i / n), cy + r2 * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    ic = [(cx + r1 * math.cos(a1 - (a1 - a0) * i / n), cy + r1 * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
    return dis + ic


def stadyum(en, boy, n=40):
    """Uçları yarım daire oval (atölyedeki oval halılar böyle)."""
    if boy >= en:
        r = en / 2
        ust = [(r + r * math.cos(math.pi + math.pi * i / n), r + r * math.sin(math.pi + math.pi * i / n)) for i in range(n + 1)]
        alt = [(r + r * math.cos(math.pi * i / n), boy - r + r * math.sin(math.pi * i / n)) for i in range(n + 1)]
        return ust + alt
    r = boy / 2
    sag = [(en - r + r * math.cos(-math.pi / 2 + math.pi * i / n), r + r * math.sin(-math.pi / 2 + math.pi * i / n))
           for i in range(n + 1)]
    sol = [(r + r * math.cos(math.pi / 2 + math.pi * i / n), r + r * math.sin(math.pi / 2 + math.pi * i / n))
           for i in range(n + 1)]
    return sag + sol


def kirp(poli, eksen, deger, buyuk):
    """Sutherland–Hodgman: poligonu eksen (0=x, 1=y) için deger'in büyük/küçük tarafında bırakır."""
    if not poli:
        return []
    icinde = (lambda p: p[eksen] >= deger - 1e-9) if buyuk else (lambda p: p[eksen] <= deger + 1e-9)
    sonuc = []
    for i, cur in enumerate(poli):
        prev = poli[i - 1]
        if icinde(cur):
            if not icinde(prev):
                sonuc.append(_kesisim(prev, cur, eksen, deger))
            sonuc.append(cur)
        elif icinde(prev):
            sonuc.append(_kesisim(prev, cur, eksen, deger))
    return sonuc


def _kesisim(a, b, eksen, deger):
    t = (deger - a[eksen]) / ((b[eksen] - a[eksen]) or 1e-12)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def kutu(poli):
    xs, ys = [p[0] for p in poli], [p[1] for p in poli]
    return min(xs), min(ys), max(xs), max(ys)


def alan(poli):
    return abs(sum(poli[i][0] * poli[i - 1][1] - poli[i - 1][0] * poli[i][1] for i in range(len(poli)))) / 2


def sigar(w, h, pay=0):
    a, b = sorted((w + 2 * pay, h + 2 * pay))
    return a <= RULO_ENI and b <= TABLA_BOYU


def bol(poli, pay):
    """Lazer tablasına (140×300) sığmayan parçayı ızgarayla en az parçaya böler."""
    x0, y0, x1, y1 = kutu(poli)
    w, h = x1 - x0, y1 - y0
    en_iyi = None
    for nx in range(1, 12):
        for ny in range(1, 12):
            if sigar(w / nx, h / ny, pay) and (en_iyi is None or nx * ny < en_iyi[0] * en_iyi[1]):
                en_iyi = (nx, ny)
    nx, ny = en_iyi or (1, 1)
    parcalar = []
    for i in range(nx):
        for j in range(ny):
            p = poli
            if nx > 1:
                p = kirp(kirp(p, 0, x0 + w * i / nx, True), 0, x0 + w * (i + 1) / nx, False)
            if ny > 1:
                p = kirp(kirp(p, 1, y0 + h * j / ny, True), 1, y0 + h * (j + 1) / ny, False)
            if len(p) >= 3 and alan(p) > 1:
                parcalar.append(p)
    return parcalar


def _disa_kaydir(poli, d):
    """Dikiş payı: poligonu d cm dışa büyütür (kenarlar paralel kaydırılıp kesiştirilir)."""
    if d <= 0:
        return list(poli)
    isaret = 1 if sum(poli[i][0] * poli[i - 1][1] - poli[i - 1][0] * poli[i][1] for i in range(len(poli))) > 0 else -1
    cizgiler = []
    for i in range(len(poli)):
        (x1, y1), (x2, y2) = poli[i], poli[(i + 1) % len(poli)]
        dx, dy = x2 - x1, y2 - y1
        u = math.hypot(dx, dy) or 1
        nx, ny = -dy / u * isaret, dx / u * isaret
        cizgiler.append(((x1 - nx * d, y1 - ny * d), (dx, dy)))
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


# --- Parçalar --------------------------------------------------------------------


def _parca(ad, tur, poli, malzeme, desen="", **ek):
    return {"ad": ad, "tur": tur, "poli": poli, "malzeme": malzeme, "desen": desen, **ek}


def _cerceve(v):
    en, boy = v["en"], v["boy"]
    sonuc, d = [], 0.0
    for gen, mal, desen, ad in ((v["dis_bant"], v["dis_malzeme"], v["dis_desen"], "Dış bant"),
                                (v["ara"], v["ara_malzeme"], "", "Ara şerit"),
                                (v["ic_bant"], v["ic_malzeme"], v["ic_desen"], "İç bant")):
        if gen <= 0:
            continue
        w, h = en - 2 * d, boy - 2 * d
        tur = "bant" if desen else "serit"
        # yan bantlar boydan boya, üst/alt bantlar aralarına uç uca
        for yon, poli in (("sol", dikd(d, d, gen, h)), ("sağ", dikd(en - d - gen, d, gen, h)),
                          ("üst", dikd(d + gen, d, w - 2 * gen, gen)), ("alt", dikd(d + gen, boy - d - gen, w - 2 * gen, gen))):
            sonuc.append(_parca(f"{ad} ({yon})", tur, poli, mal, desen, yon="dikey" if yon in ("sol", "sağ") else "yatay"))
        d += gen
    sonuc.append(_parca("Orta zemin", "zemin", dikd(d, d, en - 2 * d, boy - 2 * d), v["zemin"]))
    return sonuc


def nakis_konumlari(v):
    """Oval şeritteki motiflerin merkezleri (cm)."""
    en, boy, s, m, a = v["en"], v["boy"], v["serit"], v["motif"], v["aralik"]
    dikey = boy >= en
    uzun, kisa = (boy, en) if dikey else (en, boy)
    # şeridin oval içinde kalan boyu (uçlar yarım daire): kenardan güvenli pay
    r = kisa / 2
    kenar_pay = r - math.sqrt(max(0, r * r - (s / 2) ** 2)) + 4
    kullanilir = uzun - 2 * kenar_pay
    n = max(0, int((kullanilir + a) // (m + a)))
    toplam = n * m + (n - 1) * a if n else 0
    bas = (uzun - toplam) / 2 + m / 2
    merkezler = [bas + i * (m + a) for i in range(n)]
    return [(kisa / 2, c) if dikey else (c, kisa / 2) for c in merkezler]


def _oval_serit(v):
    en, boy, s = v["en"], v["boy"], v["serit"]
    oval = stadyum(en, boy)
    dikey = boy >= en
    eksen, orta = (0, en / 2) if dikey else (1, boy / 2)
    taraf = ("sol", "sağ") if dikey else ("üst", "alt")
    return [
        _parca(f"Zemin ({taraf[0]})", "zemin", kirp(oval, eksen, orta - s / 2, False), v["zemin"]),
        _parca(f"Zemin ({taraf[1]})", "zemin", kirp(oval, eksen, orta + s / 2, True), v["zemin"]),
        _parca("Nakış şeridi", "nakis" if v["nakis"] != "yok" else "serit",
               kirp(kirp(oval, eksen, orta - s / 2, True), eksen, orta + s / 2, False), v["serit_malzeme"],
               nakis=v["nakis"], yon="dikey" if dikey else "yatay"),
    ]


def _halka_parcalari(ad, tur, cx, r1, r2, malzeme, desen, pay):
    """Halkayı lazer tablasına sığan en az (en az 4) yay parçasına böler."""
    for n in range(4, 40):
        aci = 2 * math.pi / n
        a0 = -math.pi / 2
        x0, y0, x1, y1 = kutu(yay(cx, cx, r1, r2, a0, a0 + aci))
        if sigar(x1 - x0, y1 - y0, pay):
            break
    return [_parca(f"{ad} {i + 1}/{n}", tur, yay(cx, cx, r1, r2, -math.pi / 2 + i * aci, -math.pi / 2 + (i + 1) * aci),
                   malzeme, desen, halka=(r1, r2)) for i in range(n)]


def _yuvarlak(v):
    R = v["cap"] / 2
    sonuc, r = [], R
    if v["dis_halka"] > 0:
        sonuc += _halka_parcalari("Dış halka", "yay", R, r - v["dis_halka"], r, v["halka_malzeme"], "", v["pay"])
        r -= v["dis_halka"]
    if v["desen_halka"] > 0:
        sonuc += _halka_parcalari("Desenli halka", "yay", R, r - v["desen_halka"], r, v["desen_malzeme"], v["desen"], v["pay"])
        r -= v["desen_halka"]
    sonuc.append(_parca("Orta disk", "zemin", daire(R, R, r), v["zemin"]))
    return sonuc


def parcalar(v):
    """Tasarımın tüm parçaları; tablaya sığmayanlar bölünmüş, numaralı, kesim ölçüleriyle."""
    ham = {"cerceve": _cerceve, "oval_serit": _oval_serit, "yuvarlak": _yuvarlak}[v["duzen"]](v)
    sonuc = []
    for p in ham:
        if p["tur"] == "yay":
            bolunmus = [p["poli"]]
        else:
            bolunmus = bol(p["poli"], v["pay"])
        for i, poli in enumerate(bolunmus):
            q = dict(p, poli=poli)
            if len(bolunmus) > 1:
                q["ad"] = f"{p['ad']} {i + 1}/{len(bolunmus)}"
            x0, y0, x1, y1 = kutu(poli)
            q["en"], q["boy"] = round(x1 - x0, 1), round(y1 - y0, 1)
            q["kesim_en"], q["kesim_boy"] = round(x1 - x0 + 2 * v["pay"], 1), round(y1 - y0 + 2 * v["pay"], 1)
            q["m2"] = round(alan(poli) / 10000, 3)
            q["istasyon"] = "Lazer kesim" + (" + Nakış" if q["tur"] == "nakis" else "")
            sonuc.append(q)
    for i, q in enumerate(sonuc, 1):
        q["no"] = f"P{i}"
    return sonuc


def dis_hat(v):
    if v["duzen"] == "yuvarlak":
        return daire(v["cap"] / 2, v["cap"] / 2, v["cap"] / 2)
    if v["duzen"] == "oval_serit":
        return stadyum(v["en"], v["boy"])
    return dikd(0, 0, v["en"], v["boy"])


def cevre(poli):
    return sum(math.dist(poli[i - 1], poli[i]) for i in range(len(poli)))


def alan_m2(v):
    return round(alan(dis_hat(v)) / 10000, 2)


# --- Üretim çıktıları --------------------------------------------------------------


def rulo_yerlesimi(parcalar_, pay):
    """Raf yöntemi: her malzeme için parçaları 140 cm ene dizer. {malzeme: {"metre", "yerler": [(parça, x, y, döndü)]}}."""
    gruplar = {}
    for p in parcalar_:
        gruplar.setdefault(p["malzeme"], []).append(p)
    sonuc = {}
    for malzeme, liste in gruplar.items():
        kutular = []
        for p in liste:
            w, h = p["kesim_en"], p["kesim_boy"]
            dondu = w > RULO_ENI or (h <= RULO_ENI and h > w)  # uzun kenar rulo boyunca
            if dondu:
                w, h = h, w
            kutular.append((p, w, h, dondu))
        kutular.sort(key=lambda k: -k[2])
        yerler, x, y, raf_h = [], 0.0, 0.0, 0.0
        for p, w, h, dondu in kutular:
            if x + w > RULO_ENI + 1e-6:
                x, y, raf_h = 0.0, y + raf_h + 1, 0.0
            yerler.append((p, x, y, dondu))
            x += w + 1
            raf_h = max(raf_h, h)
        sonuc[malzeme] = {"metre": round((y + raf_h) / 100, 2), "yerler": yerler,
                          "m2": round(sum(p["m2"] for p in liste), 2), "adet": len(liste)}
    return sonuc


def nakis_bilgisi(v):
    if v["duzen"] != "oval_serit" or v["nakis"] == "yok":
        return None
    n = len(nakis_konumlari(v))
    return {"motif": dict(NAKISLAR)[v["nakis"]], "olcu": v["motif"], "adet": n,
            "tur": math.ceil(n / NAKIS_KAFA) if n else 0,
            "oneri": None if n % NAKIS_KAFA == 0 or n < NAKIS_KAFA else
            f"{n} motif {NAKIS_KAFA} kafaya tam bölünmüyor; {n - n % NAKIS_KAFA} ya da {n - n % NAKIS_KAFA + NAKIS_KAFA} motif makineyi boş çalıştırmaz."}


def uyarilar(v):
    u = []
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok" and v["motif"] > NAKIS_EN:
        u.append(f"Nakış motifi {NAKIS_EN}×{NAKIS_BOY} cm alanı aşıyor.")
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok" and not nakis_konumlari(v):
        u.append("Şerit nakış motifi için çok kısa.")
    return u


def montaj_sirasi(v):
    kenar = dict(KENARLAR)[v["kenar"]]
    if v["duzen"] == "cerceve":
        adimlar = ["Lazer: tüm parçaları malzemelerine göre kes (desenli bantların delikleri dahil).",
                   "Desenli bantların altına desen altı malzemesini yerleştir.",
                   "İçten dışa: orta zemine üst/alt bantları, sonra yan bantları zig-zag ile ekle; her halka için tekrarla."]
    elif v["duzen"] == "oval_serit":
        adimlar = ["Lazer: zemin yarımlarını ve şeridi kes.",
                   "Nakış: şeride motifleri işle (7 kafa aynı anda)." if v["nakis"] != "yok" else "Şeridi hazırla.",
                   "Şeridi iki zemin yarımı arasına zig-zag ile dik."]
    else:
        adimlar = ["Lazer: orta diski ve halka yay parçalarını kes.",
                   "Desenli halka parçalarının altına desen altı malzemesini yerleştir.",
                   "Yay parçalarını kendi aralarında zig-zag ile birleştir, sonra diske ve dış halkaya dik."]
    adimlar.append(f"Kenar: {kenar} ({dict(KENAR_RENKLERI)[v['kenar_renk']].lower()}) ile çevir.")
    return adimlar


def ozet(v):
    d = dict((k, a) for k, a, _ in DUZENLER)[v["duzen"]]
    if v["duzen"] == "yuvarlak":
        olcu = f"Ø{v['cap']:g} cm"
    else:
        olcu = f"{v['en']:g}×{v['boy']:g} cm"
    p = [f"Suni deri parçalı halı – {d.lower()} {olcu}", f"zemin {MALZEME_AD[v['zemin']].lower()}"]
    if v["duzen"] == "cerceve":
        for gen, mal, desen, ad in ((v["dis_bant"], v["dis_malzeme"], v["dis_desen"], "dış bant"),
                                    (v["ara"], v["ara_malzeme"], "", "ara şerit"),
                                    (v["ic_bant"], v["ic_malzeme"], v["ic_desen"], "iç bant")):
            if gen:
                p.append(f"{ad} {gen:g} cm {MALZEME_AD[mal].lower()}" + (f" {desen}" if desen else ""))
    elif v["duzen"] == "oval_serit":
        p.append(f"şerit {v['serit']:g} cm {MALZEME_AD[v['serit_malzeme']].lower()}")
        if v["nakis"] != "yok":
            p.append(f"{len(nakis_konumlari(v))} × {dict(NAKISLAR)[v['nakis']].lower()} {v['motif']:g} cm")
    else:
        if v["dis_halka"]:
            p.append(f"dış halka {v['dis_halka']:g} cm {MALZEME_AD[v['halka_malzeme']].lower()}")
        if v["desen_halka"]:
            p.append(f"desenli halka {v['desen_halka']:g} cm {MALZEME_AD[v['desen_malzeme']].lower()}"
                     + (f" {v['desen']}" if v["desen"] else ""))
    p.append(f"{dict(KENARLAR)[v['kenar']].lower()} {dict(KENAR_RENKLERI)[v['kenar_renk']].lower()}")
    if v.get("hazir"):
        p.append(f"({v['hazir']} esinli)")
    return " · ".join(p)


def dxf(v, malzeme=None, baslik=""):
    """Malzeme bazlı lazer dosyası (mm): parçalar rulo yerleşimindeki yerlerinde, dikiş payı eklenmiş hâlde.

    Katmanlar: KESIM (dış hat), DIKIS (net hat, işaret), NOT (parça no). Desen delikleri DXF desen dosyası
    gelince eklenecek; şimdilik parça üzerine desen kodu yazılır.
    """
    mm = 10
    yer = rulo_yerlesimi(parcalar(v), v["pay"])
    s = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$MEASUREMENT", "70", "1",
         "0", "ENDSEC", "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "3"]
    for ad, renk in (("KESIM", 7), ("DIKIS", 3), ("NOT", 8)):
        s += ["0", "LAYER", "2", ad, "70", "0", "62", str(renk), "6", "CONTINUOUS"]
    s += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]

    def cokgen(noktalar, katman):
        s.extend(["0", "POLYLINE", "8", katman, "66", "1", "70", "1"])
        for x, y in noktalar:
            s.extend(["0", "VERTEX", "8", katman, "10", f"{x * mm:.3f}", "20", f"{-y * mm:.3f}"])
        s.extend(["0", "SEQEND", "8", katman])

    def yazi(x, y, metin, boy=25):
        guvenli = re.sub(r"[^\w .×·/()-]", "", metin)[:120]
        s.extend(["0", "TEXT", "8", "NOT", "10", f"{x * mm:.1f}", "20", f"{-y * mm:.1f}", "40", str(boy), "1", guvenli])

    ofset = 0.0
    for mal, bilgi in yer.items():
        if malzeme and mal != malzeme:
            continue
        yazi(ofset, -8, f"{MALZEME_AD[mal]} - rulo {RULO_ENI} cm - {bilgi['metre']} m", 40)
        for p, x, y, dondu in bilgi["yerler"]:
            poli = [(b, a) for a, b in p["poli"]] if dondu else p["poli"]
            x0, y0, _, _ = kutu(poli)
            kaydir = lambda q: [(a - x0 + x + v["pay"] + ofset, b - y0 + y + v["pay"]) for a, b in q]  # noqa: E731
            cokgen(kaydir(_disa_kaydir(poli, v["pay"])), "KESIM")
            if v["pay"]:
                cokgen(kaydir(poli), "DIKIS")
            cx, cy = kutu(kaydir(poli))[:2]
            yazi(cx + 2, cy + 6, f"{p['no']} {p['ad']}" + (f" {p['desen']}" if p["desen"] else ""))
        ofset += RULO_ENI + 40
    if baslik:
        yazi(0, -20, baslik, 40)
    s += ["0", "ENDSEC", "0", "EOF"]
    return "\r\n".join(s) + "\r\n"
