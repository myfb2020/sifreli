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
    ("halkali", "Halkalı", "İç içe halkalar + orta; dikdörtgen ya da oval"),
    ("cerceve", "Dikdörtgen çerçeve", "Zemin + desenli bantlar; bantlar uç uca birleşir"),
    ("oval_serit", "Oval + nakış şeridi", "Oval zemin, ortadan geçen nakışlı şerit"),
    ("yuvarlak", "Yuvarlak halka", "Orta disk + parçalı desenli halka + dış halka"),
    ("seritler", "Şeritler", "Yan yana dikilmiş şeritler; eşit ya da serbest genişlikte"),
    ("izgara", "Kare ızgara", "Kare parçalar; dama, geçiş ya da karışık renk"),
    ("elmas", "Elmas (45°)", "Çapraz kare parçalar; merkezden kenara geçiş"),
    ("yarim", "İki parçalı", "Halı düz ya da çapraz iki bölgeye ayrılır"),
]
IZGARALI = ("seritler", "izgara", "elmas", "yarim")  # bu düzenlerde isteğe bağlı dış desenli bant da olur
# Atölyenin asıl yapısı "halkali": dış hat dikdörtgen ya da oval; dışarıdan içeriye en çok 4 halka, ortada büyük parça.
# Dikdörtgen halka 4 parça: uzun yanlar boydan boya, kısa üst/alt aralarına. Oval halka: düz yanlar + uç yayları.
# Diğer düzenler eski tasarımlar açılsın diye duruyor; bayi ekranında gösterilmez.
SEKILLER = [("dikdortgen", "Dikdörtgen"), ("oval", "Oval")]
HALKA_TURLERI = [("duz", "Düz"), ("desenli", "Lazer desenli"), ("nakisli", "Nakışlı")]
ORTA_TURLERI = [("duz", "Düz"), ("panel", "Nakış paneli"), ("serit", "Şerit")]
SERIT_TURLERI = [("desenli", "Lazer desenli"), ("nakisli", "Nakışlı")]
SERIT_YONLERI = [("boyuna", "Boyuna (uzunlamasına)"), ("enine", "Enine")]
EN_COK_HALKA = 4

# Renk aileleri: açıktan koyuya. Izgara / şerit / elmas parçaları bu sırayla boyanır.
AILELER = [
    ("krem_kahve", "Krem → kahve", ["beyaz_keten", "krem_keten", "bej_keten", "vizon_keten", "kahve_keten"]),
    ("gri_antrasit", "Beyaz → antrasit", ["beyaz_keten", "acik_gri_keten", "gri_keten", "antrasit_keten", "siyah_keten"]),
    ("siyah_altin", "Siyah – altın", ["siyah_keten", "varak_altin", "siyah_simli", "altin_ayna"]),
    ("gri_gumus", "Gri – gümüş", ["acik_gri_keten", "varak_gumus", "gri_keten", "gumus_sim"]),
    ("toprak_bakir", "Toprak – bakır", ["krem_keten", "bakir_varak", "vizon_keten", "kahve_keten"]),
    ("kontrast", "Siyah – beyaz", ["beyaz_keten", "siyah_keten"]),
]
AILE = {k: m for k, _, m in AILELER}
DIZILIMLER = [("gecis", "Merkezden kenara geçiş"), ("dama", "Dama (sırayla)"), ("karisik", "Karışık")]

# Suni deri malzemeler: doku = fotoğraf dokusu (tasarim_varlik/doku), yoksa renk.
MALZEMELER = [
    # keten görünümlü suni deriler (atölye fotoğrafları; adlar geçici)
    ("beyaz_keten", "Kırık beyaz keten", "#e6e2d8"),
    ("krem_keten", "Krem keten", "#d9d0bd"),
    ("bej_keten", "Kum beji keten", "#cdbd9f"),
    ("acik_gri_keten", "Açık gri keten", "#a9a7a2"),
    ("gri_keten", "Gri keten", "#8e8c88"),
    ("vizon_keten", "Vizon keten", "#8a8075"),
    ("kahve_keten", "Kahve keten", "#6b5d4c"),
    ("antrasit_keten", "Antrasit keten", "#55524e"),
    ("siyah_keten", "Siyah keten", "#2b2a29"),
    # varaklı / simli / metalik
    ("varak_altin", "Beyaz-altın varak", "#e9dcbc"),
    ("varak_gumus", "Beyaz-gümüş varak", "#cfd0d1"),
    ("bakir_varak", "Gri-bakır varak", "#b7a99a"),
    ("varak_sampanya", "Şampanya varak", "#ddd0b8"),
    ("gumus_sim", "Gümüş sim", "#b9bbbe"),
    ("siyah_simli", "Siyah simli", "#1a1a1c"),
    ("altin_ayna", "Ayna altın", "#c9a75e"),
    # diğer
    ("siyah_kadife", "Siyah kadife", "#151417"),
    ("gri_kadife", "Gri kadife", "#a7a6a3"),
    ("dalgali_pelus", "Dalgalı peluş", "#d9d3c8"),
    ("krem_deri", "Krem deri", "#e4d6b8"),
    ("siyah_deri", "Siyah deri", "#1f1d1c"),
    ("altin", "Altın (düz metalik)", "#d6b26a"),
    ("gumus", "Gümüş (düz metalik)", "#c2c5c9"),
]
MALZEME_AD = {k: a for k, a, _ in MALZEMELER}
MALZEME_HEX = {k: h for k, _, h in MALZEMELER}
ALTLAR = [("yok", "Boş (altı yok)"), ("siyah", "Siyah"), ("kahve", "Kahve"), ("krem", "Krem"), ("altin_sim", "Altın sim"),
          ("gumus_sim", "Gümüş sim"), ("siyah_rugan", "Siyah rugan")]
NAKISLAR = [("yok", "Nakış yok"), ("grek_kare", "Grek kare (altın iplik)"), ("grek_kare_gumus", "Grek kare (gümüş iplik)")]
MOTIFLER = NAKISLAR[1:]
KENARLAR = [("biye", "Biye"), ("lanfel", "Lanfel")]
KENAR_RENKLERI = [("altin", "Altın"), ("gumus", "Gümüş"), ("siyah", "Siyah"), ("beyaz", "Beyaz"), ("bej", "Bej")]

VARSAYILAN = {
    "duzen": "halkali", "en": 120, "boy": 180, "pay": 1,
    # halkalı
    "sekil": "dikdortgen", "halka_sayisi": 2,
    "h1_tur": "duz", "h1_gen": 12, "h1_malzeme": "beyaz_keten", "h1_desen": "", "h1_nakis": "grek_kare",
    "h2_tur": "desenli", "h2_gen": 14, "h2_malzeme": "antrasit_keten", "h2_desen": "DB003", "h2_nakis": "grek_kare",
    "h3_tur": "duz", "h3_gen": 8, "h3_malzeme": "antrasit_keten", "h3_desen": "", "h3_nakis": "grek_kare",
    "h4_tur": "duz", "h4_gen": 8, "h4_malzeme": "beyaz_keten", "h4_desen": "", "h4_nakis": "grek_kare",
    "orta": "duz", "panel_en": 40, "panel_boy": 60, "panel_malzeme": "beyaz_keten",
    "serit_tur": "desenli", "serit_yon": "boyuna", "serit_adet": 1, "serit_desen": "DB003",
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
    # şerit / ızgara / elmas / iki parçalı
    "aile": "krem_kahve", "dizilim": "gecis", "hucre": 40, "serit_sayisi": 7, "yon": "dikey", "serbest": "",
    "tohum": 1, "bolme": "capraz", "ikinci": "kahve_keten",
}

# Atölye halıları (başlangıç noktası); hepsi halkalı yapıda.
def _h(*halkalar):
    d = {"halka_sayisi": len(halkalar)}
    for i, (tur, gen, mal, ek) in enumerate(halkalar, 1):
        d.update({f"h{i}_tur": tur, f"h{i}_gen": gen, f"h{i}_malzeme": mal,
                  f"h{i}_desen": ek if tur == "desenli" else "", f"h{i}_nakis": ek if tur == "nakisli" else "grek_kare"})
    return d


HAZIRLAR = [
    ("P-1", "Krem düz halka, koyu lazer desenli halka", {
        "sekil": "dikdortgen", "en": 80, "boy": 150, **_h(("duz", 11, "beyaz_keten", ""), ("desenli", 12, "antrasit_keten", "DB003")),
        "zemin": "beyaz_keten", "orta": "duz", "kenar": "biye", "kenar_renk": "siyah"}),
    ("P-2", "Gümüş varak, lazer desenli halka, altın biye", {
        "sekil": "dikdortgen", "en": 100, "boy": 150, **_h(("desenli", 13, "varak_gumus", "DB001")),
        "zemin": "varak_gumus", "orta": "duz", "kenar": "biye", "kenar_renk": "altin"}),
    ("P-3", "Bej oval, boyuna nakışlı şerit", {
        "sekil": "oval", "en": 130, "boy": 190, "halka_sayisi": 0, "zemin": "bej_keten", "orta": "serit",
        "serit_tur": "nakisli", "serit_yon": "boyuna", "serit_adet": 1, "serit": 26, "serit_malzeme": "beyaz_keten",
        "nakis": "grek_kare", "aralik": 4, "kenar": "biye", "kenar_renk": "bej"}),
    ("P-4", "Yuvarlak: siyah kadife, gümüş desenli halka", {
        "sekil": "oval", "en": 200, "boy": 200, **_h(("duz", 24, "siyah_kadife", ""), ("desenli", 22, "varak_gumus", "DB003")),
        "zemin": "siyah_kadife", "orta": "duz", "kenar": "biye", "kenar_renk": "siyah"}),
    ("P-5", "Dört halka: siyah-altın", {
        "sekil": "dikdortgen", "en": 160, "boy": 230,
        **_h(("duz", 8, "siyah_keten", ""), ("desenli", 12, "varak_altin", "DB007"), ("duz", 10, "siyah_keten", ""),
             ("nakisli", 20, "beyaz_keten", "grek_kare")),
        "zemin": "siyah_keten", "orta": "duz", "kenar": "biye", "kenar_renk": "altin"}),
    ("P-6", "Oval: nakışlı halka, orta nakış paneli", {
        "sekil": "oval", "en": 150, "boy": 220, **_h(("duz", 12, "kahve_keten", ""), ("nakisli", 22, "krem_keten", "grek_kare")),
        "zemin": "bej_keten", "orta": "panel", "panel_en": 40, "panel_boy": 60, "panel_malzeme": "krem_keten",
        "nakis": "grek_kare", "motif": 30, "kenar": "lanfel", "kenar_renk": "bej"}),
    ("P-7", "Gri halka, ortada iki enine desenli şerit", {
        "sekil": "dikdortgen", "en": 160, "boy": 230, **_h(("duz", 14, "antrasit_keten", "")),
        "zemin": "acik_gri_keten", "orta": "serit", "serit_tur": "desenli", "serit_yon": "enine", "serit_adet": 2,
        "serit": 16, "serit_malzeme": "antrasit_keten", "serit_desen": "DB003", "kenar": "biye", "kenar_renk": "siyah"}),
    ("P-8", "Krem-kahve, orta nakış paneli", {
        "sekil": "dikdortgen", "en": 120, "boy": 180, **_h(("desenli", 12, "kahve_keten", "DB001"), ("duz", 10, "krem_keten", "")),
        "zemin": "krem_keten", "orta": "panel", "panel_en": 40, "panel_boy": 60, "panel_malzeme": "kahve_keten",
        "nakis": "grek_kare", "motif": 34, "kenar": "biye", "kenar_renk": "altin"}),
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
    if v["duzen"] == "halkali":
        return _halkali_temizle(v, g, desen)
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
    if v["duzen"] in IZGARALI:
        v["dis_bant"] = _sayi(g("dis_bant"), 0, 0, max(0, min(30, kisa / 2 - 20)))
        v["dis_malzeme"] = _sec(g("dis_malzeme"), MALZEMELER, "antrasit_keten")
        v["dis_desen"] = desen("dis_desen")
        v["ara"] = v["ic_bant"] = 0
        v["ara_malzeme"] = v["ic_malzeme"] = v["dis_malzeme"]
        v["ic_desen"] = ""
        v["aile"] = _sec(g("aile"), AILELER, "krem_kahve")
        v["dizilim"] = _sec(g("dizilim"), DIZILIMLER, "gecis")
        ic_kisa = kisa - 2 * v["dis_bant"]
        v["hucre"] = _sayi(g("hucre"), 40, 15, max(15, min(140, ic_kisa / 2)))
        v["serit_sayisi"] = int(_sayi(g("serit_sayisi"), 7, 2, 24))
        v["yon"] = g("yon") if g("yon") in ("dikey", "yatay") else "dikey"
        v["serbest"] = "on" if g("serbest") in ("on", True, "1", "true") else ""
        v["tohum"] = int(_sayi(g("tohum"), 1, 1, 9999))
        v["bolme"] = g("bolme") if g("bolme") in ("capraz", "duz") else "capraz"
        v["ikinci"] = _sec(g("ikinci"), MALZEMELER, "kahve_keten")
        return v
    kalan = kisa / 2 - 10
    for alan, mal in (("dis_bant", "dis_malzeme"), ("ara", "ara_malzeme"), ("ic_bant", "ic_malzeme")):
        v[alan] = _sayi(g(alan), 0, 0, max(0, min(40, kalan)))
        kalan -= v[alan]
        v[mal] = _sec(g(mal), MALZEMELER, "beyaz_keten")
    v["dis_desen"] = desen("dis_desen")
    v["ic_desen"] = desen("ic_desen")
    return v


def _halkali_temizle(v, g, desen):
    v["desen_alti"] = "yok"  # atölyede desenli parçanın altına bir şey konmaz; delikler boş
    v["sekil"] = _sec(g("sekil"), SEKILLER, "dikdortgen")
    v["en"] = _sayi(g("en"), 120, 60, 400)
    v["boy"] = _sayi(g("boy"), 180, 60, 600)
    kisa = min(v["en"], v["boy"])
    v["halka_sayisi"] = int(_sayi(g("halka_sayisi"), 2, 0, EN_COK_HALKA))
    kalan = kisa / 2 - 15  # ortada en az 30 cm kalsın
    for i in range(1, EN_COK_HALKA + 1):
        on = f"h{i}_"
        v[on + "tur"] = _sec(g(on + "tur"), HALKA_TURLERI, "duz")
        v[on + "malzeme"] = _sec(g(on + "malzeme"), MALZEMELER, "beyaz_keten")
        v[on + "desen"] = desen(on + "desen")
        v[on + "nakis"] = _sec(g(on + "nakis"), MOTIFLER, "grek_kare")
        alt = {"duz": 3, "desenli": 8, "nakisli": 12}[v[on + "tur"]]
        v[on + "gen"] = _sayi(g(on + "gen"), 10, 0, 50)
        if i <= v["halka_sayisi"]:
            v[on + "gen"] = min(v[on + "gen"], round(max(0, kalan), 1))
            if v[on + "gen"] < min(alt, kalan):
                v[on + "gen"] = round(max(0, min(alt, kalan)), 1)
            kalan -= v[on + "gen"]
    v["orta"] = _sec(g("orta"), ORTA_TURLERI, "duz")
    v["nakis"] = _sec(g("nakis"), MOTIFLER, "grek_kare")
    v["aralik"] = _sayi(g("aralik"), 4, 1, 30)
    v["panel_en"] = _sayi(g("panel_en"), 40, 20, 200)
    v["panel_boy"] = _sayi(g("panel_boy"), 60, 20, 300)
    v["panel_malzeme"] = _sec(g("panel_malzeme"), MALZEMELER, "beyaz_keten")
    v["motif"] = _sayi(g("motif"), 22, 8, NAKIS_EN)
    v["serit_tur"] = _sec(g("serit_tur"), SERIT_TURLERI, "desenli")
    v["serit_yon"] = _sec(g("serit_yon"), SERIT_YONLERI, "boyuna")
    v["serit_adet"] = int(_sayi(g("serit_adet"), 1, 1, 3))
    v["serit"] = _sayi(g("serit"), 20, 8 if v["serit_tur"] == "desenli" else 12, 60)
    v["serit_malzeme"] = _sec(g("serit_malzeme"), MALZEMELER, "beyaz_keten")
    v["serit_desen"] = desen("serit_desen")
    return v


def eskiden_cevir(v):
    """Eski düzenli bir tasarımı (çerçeve, oval şerit, yuvarlak) yeni halkalı yapıya çevirir; ızgara türleri P-1'den başlar."""
    if v.get("duzen") == "halkali":
        return v
    d = {k: v.get(k, VARSAYILAN[k]) for k in ("en", "boy", "pay", "zemin", "kenar", "kenar_renk")}
    d.update(duzen="halkali", orta="duz", sekil="dikdortgen")
    halka = []
    if v.get("duzen") == "cerceve":
        for gen, mal, desen in ((v.get("dis_bant"), v.get("dis_malzeme"), v.get("dis_desen")),
                                (v.get("ara"), v.get("ara_malzeme"), ""), (v.get("ic_bant"), v.get("ic_malzeme"), v.get("ic_desen"))):
            if gen:
                halka.append(("desenli" if desen else "duz", gen, mal, desen or ""))
    elif v.get("duzen") == "oval_serit":
        d.update(sekil="oval", orta="serit", serit_tur="nakisli" if v.get("nakis") != "yok" else "desenli",
                 serit_yon="boyuna", serit_adet=1, serit=v.get("serit"), serit_malzeme=v.get("serit_malzeme"),
                 nakis=v.get("nakis") if v.get("nakis") != "yok" else "grek_kare", aralik=v.get("aralik"))
    elif v.get("duzen") == "yuvarlak":
        d.update(sekil="oval", en=v.get("cap"), boy=v.get("cap"))
        if v.get("dis_halka"):
            halka.append(("duz", v["dis_halka"], v.get("halka_malzeme"), ""))
        if v.get("desen_halka"):
            halka.append(("desenli" if v.get("desen") else "duz", v["desen_halka"], v.get("desen_malzeme"), v.get("desen") or ""))
    else:
        return {**hazir_degerler("P-1"), "en": d["en"], "boy": d["boy"]}
    d["halka_sayisi"] = len(halka)
    for i, (tur, gen, mal, desen) in enumerate(halka, 1):
        d.update({f"h{i}_tur": tur, f"h{i}_gen": gen, f"h{i}_malzeme": mal, f"h{i}_desen": desen})
    return d


def halkalar(v):
    """Kullanılan halkalar, dışarıdan içeriye: [{"no", "tur", "gen", "malzeme", "desen", "nakis", "d"(dış kenara uzaklık)}]."""
    sonuc, d = [], 0.0
    for i in range(1, v["halka_sayisi"] + 1):
        on = f"h{i}_"
        if v[on + "gen"] <= 0:
            continue
        sonuc.append({"no": i, "tur": v[on + "tur"], "gen": v[on + "gen"], "malzeme": v[on + "malzeme"],
                      "desen": v[on + "desen"] if v[on + "tur"] == "desenli" else "",
                      "nakis": v[on + "nakis"] if v[on + "tur"] == "nakisli" else "", "d": d})
        d += v[on + "gen"]
    return sonuc


def halka_toplami(v):
    return sum(h["gen"] for h in halkalar(v))


def ana_desen(v):
    """Siparişe yazılacak lazer deseni: tasarımda geçen ilk desen."""
    if v.get("duzen") == "halkali":
        kodlar = [h["desen"] for h in halkalar(v) if h["desen"]]
        if v["orta"] == "serit" and v["serit_tur"] == "desenli" and v["serit_desen"]:
            kodlar.append(v["serit_desen"])
        return kodlar[0] if kodlar else ""
    return v.get("ic_desen") or v.get("dis_desen") or v.get("desen") or ""


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


def _dis_bant_ve_alan(v):
    """Izgaralı düzenlerde isteğe bağlı dış bant parçaları ve içte kalan alan (x, y, w, h)."""
    en, boy, b = v["en"], v["boy"], v["dis_bant"]
    sonuc = []
    if b > 0:
        tur = "bant" if v["dis_desen"] else "serit"
        for yon, poli in (("sol", dikd(0, 0, b, boy)), ("sağ", dikd(en - b, 0, b, boy)),
                          ("üst", dikd(b, 0, en - 2 * b, b)), ("alt", dikd(b, boy - b, en - 2 * b, b))):
            sonuc.append(_parca(f"Dış bant ({yon})", tur, poli, v["dis_malzeme"], v["dis_desen"]))
    return sonuc, (b, b, en - 2 * b, boy - 2 * b)


def _boya(v, i, j, ni, nj, rast):
    """Parçanın renk ailesindeki malzemesi: geçiş (merkezden uzaklık), dama ya da karışık."""
    renkler = AILE[v["aile"]]
    if v["dizilim"] == "dama":
        return renkler[(i + j) % len(renkler)]
    if v["dizilim"] == "karisik":
        return rast.choice(renkler)
    dx = abs((i + 0.5) / ni - 0.5) * 2 if ni else 0
    dy = abs((j + 0.5) / nj - 0.5) * 2 if nj else 0
    uzak = min(1.0, max(dx, dy))
    return renkler[min(len(renkler) - 1, int(uzak * len(renkler)))]


def _seritler(v):
    import random

    sonuc, (x, y, w, h) = _dis_bant_ve_alan(v)
    rast = random.Random(v["tohum"])
    n = v["serit_sayisi"]
    uzun = w if v["yon"] == "dikey" else h
    if v["serbest"]:
        agirlik = [rast.uniform(0.5, 1.6) for _ in range(n)]
    else:
        agirlik = [1] * n
    toplam = sum(agirlik)
    konum = 0.0
    for i, a in enumerate(agirlik):
        gen = uzun * a / toplam
        poli = dikd(x + konum, y, gen, h) if v["yon"] == "dikey" else dikd(x, y + konum, w, gen)
        sonuc.append(_parca(f"Şerit {i + 1}", "panel", poli, _boya(v, i, 0, n, 1, rast) if v["dizilim"] != "gecis"
                            else _boya(v, i, 0, n, 0, rast)))
        konum += gen
    return sonuc


def _izgara(v):
    import random

    sonuc, (x, y, w, h) = _dis_bant_ve_alan(v)
    rast = random.Random(v["tohum"])
    ni, nj = max(1, round(w / v["hucre"])), max(1, round(h / v["hucre"]))
    cw, ch = w / ni, h / nj
    for j in range(nj):
        for i in range(ni):
            sonuc.append(_parca(f"Kare {j + 1}-{i + 1}", "panel", dikd(x + i * cw, y + j * ch, cw, ch),
                                _boya(v, i, j, ni, nj, rast)))
    return sonuc


def _elmas(v):
    import random

    sonuc, (x, y, w, h) = _dis_bant_ve_alan(v)
    rast = random.Random(v["tohum"])
    d = v["hucre"] / math.sqrt(2)  # elmasın yarı köşegeni; kenar = hucre
    cx0, cy0 = x + w / 2, y + h / 2
    ki, kj = int(w / 2 / d) + 2, int(h / 2 / d) + 2
    for b in range(-kj, kj + 1):
        for a in range(-ki, ki + 1):
            if (a + b) % 2:
                continue
            cx, cy = cx0 + a * d, cy0 + b * d
            poli = [(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)]
            for eksen, deger, buyuk in ((0, x, True), (0, x + w, False), (1, y, True), (1, y + h, False)):
                poli = kirp(poli, eksen, deger, buyuk)
            if len(poli) < 3 or alan(poli) < 4:
                continue
            ui, uj = (a + ki) / (2 * ki), (b + kj) / (2 * kj)
            sonuc.append(_parca(f"Elmas {b + kj + 1}-{a + ki + 1}", "panel", poli,
                                _boya(v, int(ui * 20), int(uj * 20), 20, 20, rast) if v["dizilim"] == "gecis"
                                else _boya(v, (a + b) // 2 + ki, (b - a) // 2 + kj, 2 * ki, 2 * kj, rast)))
    return sonuc


def _yarim(v):
    sonuc, (x, y, w, h) = _dis_bant_ve_alan(v)
    alanp = dikd(x, y, w, h)
    if v["bolme"] == "duz":
        eksen, orta = (1, y + h / 2) if h >= w else (0, x + w / 2)
        a, b = kirp(alanp, eksen, orta, False), kirp(alanp, eksen, orta, True)
    else:  # sol üstten sağ alta çapraz: döndürülmüş eksende kırp
        def capraz(buyuk):
            sonuc_ = []
            pts = alanp
            for i, cur in enumerate(pts):
                prev = pts[i - 1]
                f = lambda p: (p[0] - x) / w - (p[1] - y) / h  # noqa: E731
                ic = (lambda p: f(p) >= 0) if buyuk else (lambda p: f(p) <= 0)
                if ic(cur):
                    if not ic(prev):
                        t = f(prev) / (f(prev) - f(cur))
                        sonuc_.append((prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t))
                    sonuc_.append(cur)
                elif ic(prev):
                    t = f(prev) / (f(prev) - f(cur))
                    sonuc_.append((prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t))
            return sonuc_
        a, b = capraz(True), capraz(False)
    sonuc.append(_parca("Bölge 1", "panel", a, v["zemin"]))
    sonuc.append(_parca("Bölge 2", "panel", b, v["ikinci"]))
    return sonuc


def stadyum_ofset(en, boy, d):
    """Ovalin d cm içeriden geçen eşi (merkezler aynı kalır)."""
    return [(x + d, y + d) for x, y in stadyum(en - 2 * d, boy - 2 * d)]


def icinde(poli, p):
    x, y = p
    ic = False
    for i in range(len(poli)):
        (x1, y1), (x2, y2) = poli[i - 1], poli[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-12):
            ic = not ic
    return ic


def _sira(bas, son, m, a):
    """bas–son arasına ortalanmış, m boyunda, a aralıklı motif merkezleri."""
    n = int((son - bas + a) // (m + a)) if son - bas >= m else 0
    ilk = (bas + son) / 2 - (n * m + (n - 1) * a) / 2 + m / 2
    return [ilk + i * (m + a) for i in range(n)]


def _kare_icinde(poli, cx, cy, m, pay=1.5):
    y = m / 2 + pay
    return all(icinde(poli, (cx + dx, cy + dy)) for dx in (-y, y) for dy in (-y, y))


def _motif_olcusu(gen):
    return max(8.0, min(float(NAKIS_EN), gen - 4))


def _halkali_yerel(v):
    """Parçalar yerel düzende: x kısa kenar (S), y uzun kenar (L). Yatay halıda sonra çevrilir."""
    S, L = sorted((v["en"], v["boy"]))
    oval = v["sekil"] == "oval"
    a = v["aralik"]
    sonuc = []
    for h in halkalar(v):
        d, g, no = h["d"], h["gen"], h["no"]
        tur = {"duz": "serit", "desenli": "bant", "nakisli": "nakis"}[h["tur"]]
        ad = f"{no}. halka"
        m = _motif_olcusu(g)
        if g < 12:  # motif sığmaz: nakışsız kalır, uyarı verilir
            tur = "serit" if tur == "nakis" else tur
        ek = {"halka": no, "desen_anahtar": ("h", no) if h["desen"] else None, "nakis": h["nakis"], "motif": m}
        if not oval:
            for yon, (x, y, w, hh) in (("sol", (d, d, g, L - 2 * d)), ("sağ", (S - d - g, d, g, L - 2 * d)),
                                        ("üst", (d + g, d, S - 2 * d - 2 * g, g)), ("alt", (d + g, L - d - g, S - 2 * d - 2 * g, g))):
                motifler = []
                if tur == "nakis":
                    if yon in ("sol", "sağ"):
                        motifler = [(x + w / 2, c) for c in _sira(y + 2, y + hh - 2, m, a)]
                    else:
                        motifler = [(c, y + hh / 2) for c in _sira(x + 2, x + w - 2, m, a)]
                sonuc.append(_parca(f"{ad} ({yon})", tur, dikd(x, y, w, hh), h["malzeme"], h["desen"],
                                    yon="dikey" if yon in ("sol", "sağ") else "yatay", motifler=motifler, **ek))
            continue
        r = S / 2
        r2, r1 = r - d, r - d - g
        rm = (r1 + r2) / 2
        duz = L - 2 * r
        if duz > 0.5:
            for yon, x in (("sol", d), ("sağ", S - d - g)):
                motifler = [(x + g / 2, c) for c in _sira(r, L - r, m, a)] if tur == "nakis" else []
                sonuc.append(_parca(f"{ad} ({yon})", tur, dikd(x, r, g, duz), h["malzeme"], h["desen"], yon="dikey",
                                    motifler=motifler, **ek))
        for uc, (cy, a0) in (("üst", (r, math.pi)), ("alt", (L - r, 0.0))):
            for k in range(2, 40):
                x0, y0, x1, y1 = kutu(yay(r, cy, r1, r2, a0, a0 + math.pi / k))
                if sigar(x1 - x0, y1 - y0, v["pay"]):
                    break
            for i in range(k):
                b0, b1 = a0 + math.pi * i / k, a0 + math.pi * (i + 1) / k
                motifler = []
                if tur == "nakis":
                    motifler = [(r + rm * math.cos(t / rm), cy + rm * math.sin(t / rm))
                                for t in _sira(b0 * rm + 1, b1 * rm - 1, m, a)]
                sonuc.append(_parca(f"{ad} ({uc} yay {i + 1}/{k})", tur, yay(r, cy, r1, r2, b0, b1), h["malzeme"],
                                    h["desen"], yay=True, motifler=motifler, **ek))
    D = halka_toplami(v)
    orta = stadyum_ofset(S, L, D) if oval else dikd(D, D, S - 2 * D, L - 2 * D)
    x0, y0, x1, y1 = kutu(orta)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    zemin = v["zemin"]
    if v["orta"] == "panel":
        pw = min(v["panel_en"], x1 - x0 - 16)
        ph = min(v["panel_boy"], y1 - y0 - 16)
        while oval and pw > 20 and not all(icinde(orta, (cx + sx * (pw / 2 + 8), cy + sy * (ph / 2 + 8)))
                                           for sx in (-1, 1) for sy in (-1, 1)):
            pw, ph = pw * 0.95, ph * 0.95
        px0, py0 = cx - pw / 2, cy - ph / 2
        m = min(v["motif"], _motif_olcusu(min(pw, ph)))
        motifler = [(mx, my) for my in _sira(py0 + 2, py0 + ph - 2, m, a) for mx in _sira(px0 + 2, px0 + pw - 2, m, a)]
        orta_sutun = kirp(kirp(orta, 0, px0, True), 0, px0 + pw, False)
        sonuc += [_parca("Zemin (sol)", "zemin", kirp(orta, 0, px0, False), zemin),
                  _parca("Zemin (sağ)", "zemin", kirp(orta, 0, px0 + pw, True), zemin),
                  _parca("Zemin (üst)", "zemin", kirp(orta_sutun, 1, py0, False), zemin),
                  _parca("Zemin (alt)", "zemin", kirp(orta_sutun, 1, py0 + ph, True), zemin),
                  _parca("Nakış paneli", "nakis", dikd(px0, py0, pw, ph), v["panel_malzeme"], nakis=v["nakis"],
                         motif=m, motifler=motifler)]
    elif v["orta"] == "serit":
        n = v["serit_adet"]
        eksen = 0 if v["serit_yon"] == "boyuna" else 1  # şeritlerin dizildiği eksen
        bas, son = (x0, x1) if eksen == 0 else (y0, y1)
        w = min(v["serit"], (son - bas) / (n + 1) * 0.8)
        merkezler = [bas + (son - bas) * (i + 1) / (n + 1) for i in range(n)]
        desenli = v["serit_tur"] == "desenli"
        m = _motif_olcusu(w)
        onceki = bas
        for i, c in enumerate(merkezler, 1):
            parca = kirp(kirp(orta, eksen, onceki, True), eksen, c - w / 2, False)
            sonuc.append(_parca(f"Zemin {i}", "zemin", parca, zemin))
            serit = kirp(kirp(orta, eksen, c - w / 2, True), eksen, c + w / 2, False)
            motifler = []
            if not desenli:
                ub, us = (y0, y1) if eksen == 0 else (x0, x1)
                for say in range(int((us - ub) // (m + a)), 0, -1):
                    adaylar = _sira((ub + us) / 2 - (say * (m + a) - a) / 2, (ub + us) / 2 + (say * (m + a) - a) / 2, m, a)
                    noktalar = [(c, t) if eksen == 0 else (t, c) for t in adaylar]
                    if all(_kare_icinde(orta, px_, py_, m) for px_, py_ in noktalar):
                        motifler = noktalar
                        break
            ad = f"{'Desenli' if desenli else 'Nakışlı'} şerit" + (f" {i}" if n > 1 else "")
            sonuc.append(_parca(ad, "bant" if desenli else "nakis", serit, v["serit_malzeme"],
                                v["serit_desen"] if desenli else "", yon="dikey" if eksen == 0 else "yatay",
                                desen_anahtar=("s", i) if desenli and v["serit_desen"] else None,
                                nakis="" if desenli else v["nakis"], motif=m, motifler=motifler))
            onceki = c + w / 2
        sonuc.append(_parca(f"Zemin {n + 1}", "zemin", kirp(orta, eksen, onceki, True), zemin))
    else:
        sonuc.append(_parca("Orta zemin", "zemin", orta, zemin))
    return [p for p in sonuc if len(p["poli"]) >= 3 and alan(p["poli"]) > 1]


_CEVIR = {"sol": "üst", "sağ": "alt", "üst": "sol", "alt": "sağ"}


def _halkali(v):
    ps = _halkali_yerel(v)
    if v["en"] <= v["boy"]:
        return ps
    for p in ps:  # yatay halı: x ↔ y
        p["poli"] = [(y, x) for x, y in p["poli"]]
        p["motifler"] = [(y, x) for x, y in p.get("motifler", [])]
        p["ad"] = re.sub(r"\((sol|sağ|üst|alt)", lambda e: "(" + _CEVIR[e.group(1)], p["ad"])
        if p.get("yon"):
            p["yon"] = "yatay" if p["yon"] == "dikey" else "dikey"
    return ps


def parcalar(v):
    """Tasarımın tüm parçaları; tablaya sığmayanlar bölünmüş, numaralı, kesim ölçüleriyle."""
    ham = {"halkali": _halkali, "cerceve": _cerceve, "oval_serit": _oval_serit, "yuvarlak": _yuvarlak, "seritler": _seritler,
           "izgara": _izgara, "elmas": _elmas, "yarim": _yarim}[v["duzen"]](v)
    sonuc = []
    for p in ham:
        if p["tur"] == "yay" or p.get("yay"):
            bolunmus = [p["poli"]]
        else:
            bolunmus = bol(p["poli"], v["pay"])
        for i, poli in enumerate(bolunmus):
            q = dict(p, poli=poli)
            x0, y0, x1, y1 = kutu(poli)
            if len(bolunmus) > 1:
                q["ad"] = f"{p['ad']} {i + 1}/{len(bolunmus)}"
                q["motifler"] = [(mx, my) for mx, my in p.get("motifler", []) if x0 <= mx < x1 and y0 <= my < y1]
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
    if v["duzen"] == "oval_serit" or (v["duzen"] == "halkali" and v["sekil"] == "oval"):
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


def _halkali_nakis(v):
    gruplar = {}
    for p in parcalar(v):
        if p["tur"] == "nakis" and p.get("motifler"):
            g = gruplar.setdefault((p["nakis"], p["motif"]), [])
            g.extend(p["motifler"])
    if not gruplar:
        return None
    satirlar = [{"motif": dict(NAKISLAR)[k], "olcu": round(m, 1), "adet": len(liste),
                 "tur": math.ceil(len(liste) / NAKIS_KAFA)} for (k, m), liste in gruplar.items()]
    adet = sum(s_["adet"] for s_ in satirlar)
    bos = sum(s_["tur"] * NAKIS_KAFA - s_["adet"] for s_ in satirlar)
    return {"motif": ", ".join(f"{s_['motif']} {s_['olcu']:g} cm" for s_ in satirlar), "olcu": satirlar[0]["olcu"],
            "adet": adet, "tur": sum(s_["tur"] for s_ in satirlar), "satirlar": satirlar,
            "oneri": f"Son turda {bos} kafa boş çalışır." if bos else None}


def _halkali_uyarilar(v):
    return [u["metin"] for u in halkali_uyari_listesi(v)]


def halkali_uyari_listesi(v):
    """Uyarılar, ekranda nerede gösterileceğiyle: adim (2 halkalar, 3 orta), halka no; teknik olanlar bayiye gösterilmez."""
    u = []
    ps = parcalar(v)
    ekle = lambda metin, adim, halka=None, teknik=False: u.append(  # noqa: E731
        {"metin": metin, "adim": adim, "halka": halka, "teknik": teknik})
    for i in range(1, v["halka_sayisi"] + 1):
        gen, tur = v[f"h{i}_gen"], v[f"h{i}_tur"]
        if gen < {"duz": 3, "desenli": 8, "nakisli": 12}[tur]:
            ekle(f"{i}. halkaya yer kalmadı ({gen:g} cm); halıyı büyütün ya da diğer halkaları daraltın.", 2, i)
    for h in halkalar(v):
        if h["tur"] == "nakisli" and h["gen"] >= 12 and not any(p.get("motifler") for p in ps if p.get("halka") == h["no"]):
            ekle(f"{h['no']}. halka nakış için çok dar.", 2, h["no"])
    if v["orta"] == "serit" and v["serit_tur"] == "nakisli" and not any(
            p.get("motifler") for p in ps if p["ad"].startswith("Nakışlı şerit")):
        ekle("Ortadaki şerit nakış için çok kısa ya da dar.", 3)
    panel = next((p for p in ps if p["ad"] == "Nakış paneli"), None)
    if panel and (panel["en"] < v["panel_en"] - 0.5 or panel["boy"] < v["panel_boy"] - 0.5):
        ekle(f"Nakış paneli ortaya sığmadığı için {panel['en']:g}×{panel['boy']:g} cm yapıldı.", 3)
    kucuk = [p for p in ps if min(p["en"], p["boy"]) < 4]
    if kucuk:
        ekle(f"{len(kucuk)} parça 4 cm'den dar; dikişi zor olabilir.", 2, teknik=True)
    return u


def kalan_yer(v):
    """Halkalara daha ne kadar genişlik verilebilir (cm); ortada en az 30 cm kalır."""
    return round(max(0.0, min(v["en"], v["boy"]) / 2 - 15 - halka_toplami(v)), 1)


def _halkali_montaj(v):
    oval = v["sekil"] == "oval"
    adimlar = ["Lazer: tüm parçaları malzemelerine göre kes (desen delikleri dahil); parça numaralarını arkalarına yaz."]
    n = _halkali_nakis(v)
    if n:
        adimlar.append(f"Nakış: nakışlı parçalara {n['adet']} motif işle ({NAKIS_KAFA} kafa, {n['tur']} tur).")
    if v["orta"] == "panel":
        adimlar.append("Orta: nakış panelini zemin parçalarının arasına zig-zag ile dik.")
    elif v["orta"] == "serit":
        adimlar.append("Orta: zemin parçalarını şeritlerle sırayla zig-zag ile birleştir.")
    if halkalar(v):
        adimlar.append("İçten dışa her halka: önce yay parçalarını birbirine, sonra düz yanlarla birlikte ortaya zig-zag ile dik."
                       if oval else
                       "İçten dışa her halka: önce kısa üst/alt parçaları, sonra boydan boya uzun yanları zig-zag ile dik.")
    adimlar.append(f"Kenar: {dict(KENARLAR)[v['kenar']]} ({dict(KENAR_RENKLERI)[v['kenar_renk']].lower()}) ile çevir.")
    return adimlar


def _halkali_ozet(v):
    p = [f"Suni deri parçalı halı – {dict(SEKILLER)[v['sekil']].lower()} {v['en']:g}×{v['boy']:g} cm"]
    for h in halkalar(v):
        tur = {"duz": "düz", "desenli": "lazer desenli", "nakisli": "nakışlı"}[h["tur"]]
        p.append(f"{h['no']}. halka {h['gen']:g} cm {tur} {MALZEME_AD[h['malzeme']].lower()}"
                 + (f" {h['desen']}" if h["desen"] else ""))
    orta = f"orta {MALZEME_AD[v['zemin']].lower()}"
    if v["orta"] == "panel":
        orta += f" + nakış paneli {v['panel_en']:g}×{v['panel_boy']:g} cm"
    elif v["orta"] == "serit":
        orta += (f" + {v['serit_adet']} {'enine' if v['serit_yon'] == 'enine' else 'boyuna'} "
                 f"{'desenli' if v['serit_tur'] == 'desenli' else 'nakışlı'} şerit {v['serit']:g} cm"
                 + (f" {v['serit_desen']}" if v["serit_tur"] == "desenli" and v["serit_desen"] else ""))
    p.append(orta)
    p.append(f"{dict(KENARLAR)[v['kenar']].lower()} {dict(KENAR_RENKLERI)[v['kenar_renk']].lower()}")
    if v.get("hazir"):
        p.append(f"({v['hazir']} esinli)")
    return " · ".join(p)


def _rastlar(adet, tohum):
    import random

    ana = random.Random(tohum)
    return [(i, random.Random(ana.randint(1, 10 ** 9))) for i in range(adet)]


def _halkali_fikir(i, rast, desen_kodlari, olcu):
    """Bir öneri: renk ailesinden açık/koyu sırayla halkalar; şekil, orta ve kenar karışık."""
    desenler = sorted(desen_kodlari)
    renkler = rast.choice(AILELER)[2]
    acik, koyu = renkler[0], renkler[-1]
    en, boy = olcu or rast.choice([(120, 180), (160, 230), (200, 290)])
    sekil = "oval" if i % 3 == 1 else "dikdortgen"
    v = {"duzen": "halkali", "sekil": sekil, "en": en, "boy": boy, "pay": 1,
         "halka_sayisi": rast.choice([1, 2, 2, 3, 3, 4]), "zemin": rast.choice([acik, renkler[1 % len(renkler)]]),
         "kenar": rast.choice(KENARLAR)[0], "kenar_renk": rast.choice(KENAR_RENKLERI)[0], "aralik": 4}
    turler = ["duz", "desenli", "nakisli"]
    for n in range(1, v["halka_sayisi"] + 1):
        tur = rast.choice(turler if desenler else ["duz", "nakisli"])
        v.update({f"h{n}_tur": tur, f"h{n}_gen": {"nakisli": rast.choice([20, 24]), "desenli": rast.choice([10, 12, 14])}.get(tur, rast.choice([6, 8, 10])),
                  f"h{n}_malzeme": koyu if n % 2 else rast.choice(renkler[:-1]),
                  f"h{n}_desen": rast.choice(desenler) if tur == "desenli" else "",
                  f"h{n}_nakis": rast.choice(MOTIFLER)[0]})
    orta = rast.choice(["duz", "panel", "serit"])
    v["orta"] = orta
    if orta == "panel":
        v.update(panel_en=rast.choice([40, 50]), panel_boy=rast.choice([60, 80]), panel_malzeme=koyu,
                 nakis=rast.choice(MOTIFLER)[0], motif=rast.choice([24, 30, 36]))
    elif orta == "serit":
        tur = "desenli" if desenler and rast.random() < 0.6 else "nakisli"
        v.update(serit_tur=tur, serit_yon=rast.choice(["boyuna", "enine"]), serit_adet=rast.choice([1, 1, 2, 3]),
                 serit=rast.choice([12, 16, 20]) if tur == "desenli" else rast.choice([24, 28]), serit_malzeme=koyu,
                 serit_desen=rast.choice(desenler) if desenler else "", nakis=rast.choice(MOTIFLER)[0])
    return temizle(v, desen_kodlari)


def nakis_bilgisi(v):
    if v["duzen"] == "halkali":
        return _halkali_nakis(v)
    if v["duzen"] != "oval_serit" or v["nakis"] == "yok":
        return None
    n = len(nakis_konumlari(v))
    return {"motif": dict(NAKISLAR)[v["nakis"]], "olcu": v["motif"], "adet": n,
            "tur": math.ceil(n / NAKIS_KAFA) if n else 0,
            "oneri": None if n % NAKIS_KAFA == 0 or n < NAKIS_KAFA else
            f"{n} motif {NAKIS_KAFA} kafaya tam bölünmüyor; {n - n % NAKIS_KAFA} ya da {n - n % NAKIS_KAFA + NAKIS_KAFA} motif makineyi boş çalıştırmaz."}


def uyarilar(v):
    if v["duzen"] == "halkali":
        return _halkali_uyarilar(v)
    u = []
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok" and v["motif"] > NAKIS_EN:
        u.append(f"Nakış motifi {NAKIS_EN}×{NAKIS_BOY} cm alanı aşıyor.")
    if v["duzen"] == "oval_serit" and v["nakis"] != "yok" and not nakis_konumlari(v):
        u.append("Şerit nakış motifi için çok kısa.")
    if v["duzen"] in IZGARALI:
        kucuk = [p for p in parcalar(v) if p["tur"] == "panel" and min(p["en"], p["boy"]) < 8]
        if kucuk:
            u.append(f"{len(kucuk)} parça 8 cm'den dar (kenarlarda kalan küçük parçalar); dikişi zor olabilir.")
    return u


def montaj_sirasi(v):
    if v["duzen"] == "halkali":
        return _halkali_montaj(v)
    kenar = dict(KENARLAR)[v["kenar"]]
    if v["duzen"] == "cerceve":
        adimlar = ["Lazer: tüm parçaları malzemelerine göre kes (desenli bantların delikleri dahil).",
                   "Desenli bantların altına desen altı malzemesini yerleştir.",
                   "İçten dışa: orta zemine üst/alt bantları, sonra yan bantları zig-zag ile ekle; her halka için tekrarla."]
    elif v["duzen"] == "oval_serit":
        adimlar = ["Lazer: zemin yarımlarını ve şeridi kes.",
                   "Nakış: şeride motifleri işle (7 kafa aynı anda)." if v["nakis"] != "yok" else "Şeridi hazırla.",
                   "Şeridi iki zemin yarımı arasına zig-zag ile dik."]
    elif v["duzen"] in IZGARALI:
        adimlar = ["Lazer: parçaları malzemelerine göre kes; parça numaralarını arkalarına yaz.",
                   "Planına göre parçaları önce sıra sıra, sonra sıraları birbirine zig-zag ile dik.",
                   "Dış bant varsa: üst/alt bantları, sonra yan bantları ekle."]
    else:
        adimlar = ["Lazer: orta diski ve halka yay parçalarını kes.",
                   "Desenli halka parçalarının altına desen altı malzemesini yerleştir.",
                   "Yay parçalarını kendi aralarında zig-zag ile birleştir, sonra diske ve dış halkaya dik."]
    adimlar.append(f"Kenar: {kenar} ({dict(KENAR_RENKLERI)[v['kenar_renk']].lower()}) ile çevir.")
    return adimlar


def ozet(v):
    if v["duzen"] == "halkali":
        return _halkali_ozet(v)
    d = dict((k, a) for k, a, _ in DUZENLER)[v["duzen"]]
    if v["duzen"] == "yuvarlak":
        olcu = f"Ø{v['cap']:g} cm"
    else:
        olcu = f"{v['en']:g}×{v['boy']:g} cm"
    p = [f"Suni deri parçalı halı – {d.replace('İ', 'i').lower()} {olcu}"]
    if v["duzen"] not in IZGARALI:
        p.append(f"zemin {MALZEME_AD[v['zemin']].lower()}")
    if v["duzen"] in IZGARALI:
        if v["duzen"] == "yarim":
            p.append(f"{'çapraz' if v['bolme'] == 'capraz' else 'düz'} bölme: {MALZEME_AD[v['zemin']].lower()} + "
                     f"{MALZEME_AD[v['ikinci']].lower()}")
        else:
            adet = len([q for q in parcalar(v) if q["tur"] == "panel"])
            olc = f"{v['serit_sayisi']} {v['yon']} şerit" if v["duzen"] == "seritler" else f"{v['hucre']:g} cm parça"
            p.append(f"{olc}, {adet} panel, {dict((k, a) for k, a, _ in AILELER)[v['aile']].lower()}, "
                     f"{dict(DIZILIMLER)[v['dizilim']].lower()}")
        if v["dis_bant"]:
            p.append(f"dış bant {v['dis_bant']:g} cm {MALZEME_AD[v['dis_malzeme']].lower()}"
                     + (f" {v['dis_desen']}" if v["dis_desen"] else ""))
    elif v["duzen"] == "cerceve":
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


def fikirler(adet=6, tohum=None, desen_kodlari=(), olcu=None):
    """'Bana fikir ver': atölye kurallarına uyan, birbirinden farklı rastgele tasarımlar."""
    return [_halkali_fikir(i, rast, desen_kodlari, olcu) for i, rast in _rastlar(adet, tohum)]


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
