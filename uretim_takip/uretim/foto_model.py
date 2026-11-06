"""Fotoğraflı modeller: gerçek halı fotoğrafı + bölge haritası.

Bayi modelin her bölgesine (zemin, bant, desen, nakış ipliği…) kartela rengi seçer; fotoğraf o renklerle boyanır.
Doku, gölge, dikiş ve parlaklık fotoğraftan gelir, yalnız renk değişir. Yalnız Pillow kullanılır.

Bölge haritası (``<KOD>.png``): her pikselde bölge sırası (1, 2, 3…), 0 = dokunulmaz (zemin, delik, süs).
Haritalar geliştirmede ``is_belgeleri/foto_model_maske.py`` ile üretildi.
"""

import hashlib
import io
import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from . import parcali

KLASOR = Path(__file__).resolve().parent / "tasarim_varlik" / "foto_model"
DOKU = Path(__file__).resolve().parent / "tasarim_varlik" / "doku"
ONBELLEK_SINIR = 600
SURUM = 5  # boyama yöntemi değişince önbellek yenilensin  # önbellekte en çok bu kadar boyanmış resim kalır

# bölge türleri: hangi renkler seçilebilir
MALZEME, DESEN, IPLIK = "malzeme", "desen", "iplik"

MODELLER = {
    "RNO-006": {"ad": "Oval · Grek nakış şeridi", "px_cm": 529 / 160, "bolgeler": [
        ("zemin", "Zemin", MALZEME, "RN03", "zemin"),
        ("serit", "Nakış şeridi", MALZEME, "RN07", "vurgu"),
        ("iplik", "Nakış ipliği", IPLIK, "bej", "iplik")]},
    "RNO-007": {"ad": "Lazer desenli bant · çift çerçeve", "px_cm": 500 / 160, "bolgeler": [
        ("cerceve", "Çerçeve ve iç şerit", MALZEME, "RN02", "ikinci"),
        ("desen", "Lazer desenli bant", DESEN, "RN04", "vurgu"),
        ("orta", "Orta", MALZEME, "RN07", "zemin")]},
    "RNO-008": {"ad": "Kesik köşe · hasır desen halka", "px_cm": 564 / 160, "bolgeler": [
        ("dis", "Dış bant", MALZEME, "RN06", "zemin"),
        ("desen", "Hasır desen halka ve biye", DESEN, "RN03", "vurgu"),
        ("orta", "Orta", MALZEME, "RN06", "zemin")]},
    "RNO-009": {"ad": "Altın lazer desenli çerçeve", "px_cm": 475 / 160, "bolgeler": [
        ("cerceve", "Dış çerçeve ve ince çizgi", DESEN, "ALTIN", "metal"),
        ("desen", "Lazer desenli bant", DESEN, "ALTIN", "metal"),
        ("orta", "Orta", MALZEME, "RN07", "zemin")]},
    "RNO-010": {"ad": "Gönye köşe · Bienca eskitme bant", "px_cm": 657 / 160, "bolgeler": [
        ("dis", "Dış bant", MALZEME, "RN06", "zemin"),
        ("bant", "Eskitme bant", MALZEME, "BN02", "vurgu"),
        ("orta", "Orta", MALZEME, "RN06", "zemin")]},
    "RNO-011": {"ad": "Gönye köşe · eskitme bant · biye", "px_cm": 668 / 160, "bolgeler": [
        ("kenar", "Biye", MALZEME, "RN03", "zemin"),
        ("bant", "Eskitme bant", MALZEME, "BN03", "vurgu"),
        ("orta", "Orta", MALZEME, "RN03", "zemin")]},
    "RNO-012": {"ad": "Gönye köşe · iç içe iki bant", "px_cm": 660 / 160, "bolgeler": [
        ("zemin", "Zemin ve ara bant", MALZEME, "RN02", "zemin"),
        ("bant", "İki bant", MALZEME, "RN04", "vurgu")]},
    "RNO-013": {"ad": "Nakışlı Rono · Grek madalyon sıraları (yakın görünüm)", "px_cm": 14.5, "bolgeler": [
        ("zemin", "Zemin", MALZEME, "RN03", "zemin"),
        ("iplik", "Nakış ipliği", IPLIK, "bej", "iplik")]},
    "BNA-027": {"ad": "Krem & altın Bienca · lazer desenli bant", "px_cm": 7.3, "bolgeler": [
        ("dis", "Dış kenar", MALZEME, "BN05", "ikinci"),
        ("desen", "Lazer desenli bant", DESEN, "BN05", "vurgu"),
        ("orta", "Orta", MALZEME, "BN05", "zemin")]},
    "BNA-028": {"ad": "Bienca · lazer desenli bant · altın biye", "px_cm": 11, "bolgeler": [
        ("kenar", "Biye", DESEN, "ALTIN", "metal"),
        ("desen", "Lazer desenli bant", DESEN, "BN01", "vurgu"),
        ("orta", "Orta", MALZEME, "BN01", "zemin")]},
}
# Katalogdaki Rono / Bienca fotoğrafları (bölge haritası is_belgeleri/foto_model_maske.py düzeninde, yarı otomatik):
# fotoğraf katalog_tohum/model'den okunur; "sira" haritadaki bölge numaraları (1 dış kenar, 2 desenli bant, 3 orta).
KATALOG = Path(__file__).resolve().parent / "katalog_tohum" / "model"
for _kod, _m in json.loads((KLASOR / "katalog.json").read_text(encoding="utf-8")).items():
    MODELLER.setdefault(_kod, {"ad": "", "px_cm": _m["px_cm"], "kaynak": "katalog", "sira": _m["sira"],
                               "bolgeler": [tuple(b) for b in _m["bolgeler"]]})
# Lazer deseni değiştirilebilen dikdörtgen çerçeveli modeller (bant bölgesi) ve nakış motifi değiştirilebilenler
DESEN_DEGISIR = {k: "desen" for k in (
    "BNA-001", "BNA-002", "BNA-003", "BNA-004", "BNA-005", "BNA-006", "BNA-007", "BNA-008", "BNA-009", "BNA-011",
    "BNA-013", "BNA-014", "BNA-018", "BNA-019", "BNA-026", "RNO-001", "RNO-003", "RNO-004", "RNO-005")}
DESEN_DEGISIR.update({"RNO-009": "desen", "BNA-027": "desen", "BNA-028": "desen"})
NAKIS_DEGISIR = {"RNO-006": ("serit", "iplik")}  # (şerit bölgesi, iplik bölgesi)
# Nakış yalnız Rono üzerine: çerçeveli modellerde bant "nakışlı Rono bant" olabilir (motif + iplik seçilir)
NAKISLI_BANT = {**DESEN_DEGISIR, "RNO-010": "bant", "RNO-011": "bant"}
# Nakışlı Rono yakın görünüm: motif kutuları (900 px fotoğrafta x0, y0, x1, y1); değişiklikte motifler yeniden işlenir
NAKIS_KUTULARI = {"RNO-013": [tuple(round(v * 1.19) for v in k) for k in (
    (140, 0, 262, 95), (150, 115, 258, 235), (150, 262, 262, 380), (143, 410, 265, 532), (133, 568, 268, 702),
    (110, 745, 265, 905), (470, 38, 605, 187), (483, 205, 612, 345), (496, 375, 635, 510), (508, 548, 660, 692),
    (523, 735, 690, 895))]}
NAKIS_BOSLUK = {"RNO-013": (357, 524)}  # motifsiz zemin şeridi (x aralığı): silinen motifin yerine buradan doku
# fotoğrafta desenli (eskitme/varak) olan bölgeler: başka renge geçince fotoğrafın deseni değil kartelanın dokusu görünür
DESENLI_ASIL = {"BN01", "BN02", "BN03", "BN04", "BN05"}


def _kartela():
    """{kod: (malzeme anahtarı, ad, hex)} – Rono RN01–07, Bienca BN01–04, Altın."""
    sonuc = {}
    for anahtar in parcali.KARTELA_MALZEMELERI["RNO"] + parcali.KARTELA_MALZEMELERI["BNA"]:
        ad = parcali.MALZEME_AD[anahtar]
        kod = re.search(r"\b([RB]N\d\d)\b", ad).group(1)
        sonuc[kod] = (anahtar, ad.split(kod, 1)[1].strip() or ad, parcali.MALZEME_HEX[anahtar])
    sonuc["ALTIN"] = ("altin", "Altın", parcali.MALZEME_HEX["altin"])
    sonuc["GUMUS"] = ("gumus", "Gümüş", parcali.MALZEME_HEX["gumus"])
    return sonuc


KARTELA = _kartela()
METALLER = ["ALTIN", "GUMUS"]
IPLIK_RENK = {k: (ad, hex_) for k, ad, hex_ in parcali.IPLIKLER}


def secenekler(tur):
    if tur == IPLIK:
        return list(IPLIK_RENK)
    kodlar = [k for k in KARTELA if k not in METALLER]
    return kodlar + METALLER if tur == DESEN else kodlar


def bolge_secenekleri(b):
    """Bölgenin seçilebilen renkleri: zemin kendi ailesinde (Rono → RN01–07, Bienca → BN), bantlarda Rono ya da
    Bienca, lazer desenli bant ve biyede ayrıca altın / gümüş; nakış ipliği ayrı."""
    if b["tur"] == IPLIK:
        return list(IPLIK_RENK)
    rono = [k for k in KARTELA if k.startswith("RN")]
    bienca = [k for k in KARTELA if k.startswith("BN")]
    if b["rol"] == "zemin":
        return bienca if b["varsayilan"].startswith("BN") else rono
    return rono + bienca + (METALLER if b["tur"] == DESEN else [])


def nakis_motifleri():
    return list(parcali.MOTIF)


def bolgeler(kod):
    return [dict(zip(("anahtar", "ad", "tur", "varsayilan", "rol"), b)) for b in MODELLER[kod]["bolgeler"]]


def secim_temizle(kod, veri):
    """Gelen seçimi (dict) doğrular; geçersiz/eksik bölgeler fotoğraftaki renkte kalır."""
    sonuc = {}
    for b in bolgeler(kod):
        deger = str((veri or {}).get(b["anahtar"], "")).strip()
        sonuc[b["anahtar"]] = deger if deger in bolge_secenekleri(b) else b["varsayilan"]
    if kod in DESEN_DEGISIR:
        deger = str((veri or {}).get("desen_kodu", "")).strip()
        sonuc["desen_kodu"] = deger if deger in lazer_desenleri() else ""
    if kod in NAKIS_DEGISIR or kod in NAKIS_KUTULARI:
        deger = str((veri or {}).get("motif", "")).strip()
        sonuc["motif"] = deger if deger in parcali.MOTIF else ""
    if kod in NAKISLI_BANT:
        motif = str((veri or {}).get("nakis_motif", "")).strip()
        iplik = str((veri or {}).get("nakis_iplik", "")).strip()
        sonuc["nakis_motif"] = motif if motif in parcali.MOTIF else ""
        sonuc["nakis_iplik"] = iplik if iplik in IPLIK_RENK else "bej"
        if sonuc["nakis_motif"]:  # nakış yalnız Rono'ya işlenir: bant Rono olur, lazer deseni olmaz
            bant = NAKISLI_BANT[kod]
            if not sonuc[bant].startswith("RN"):  # Bienca / metal → parlaklığı en yakın Rono
                sonuc[bant] = min((k for k in KARTELA if k.startswith("RN")),
                                  key=lambda k: abs(_parlaklik(k) - _parlaklik(sonuc[bant])))
            sonuc["desen_kodu"] = ""
    return sonuc


def lazer_desenleri():
    from . import hali_gorsel
    return [k for k in sorted(hali_gorsel.desen_bilgisi()) if k not in parcali.GIZLI_DESENLER]


def renk_adi(tur, deger):
    if tur == IPLIK:
        return f"{IPLIK_RENK[deger][0]} iplik"
    if deger in METALLER:
        return KARTELA[deger][1]
    return f"{deger} {KARTELA[deger][1]}"


def metin(kod, secim):
    """Sipariş için kısa renk yazısı: 'Zemin RN03 · Bant RN04 · Nakış ipliği Bej'."""
    parcalar = []
    for b in bolgeler(kod):
        deger = secim[b["anahtar"]]
        parcalar.append(f"{b['ad']}: {IPLIK_RENK[deger][0] if b['tur'] == IPLIK else deger}")
    if secim.get("desen_kodu"):
        parcalar.append(f"Lazer deseni: {secim['desen_kodu']}")
    if secim.get("motif"):
        parcalar.append(f"Nakış: {secim['motif']} {parcali.MOTIF[secim['motif']]['ad']}")
    if secim.get("nakis_motif"):
        parcalar.append(f"Nakışlı bant: {secim['nakis_motif']} {parcali.MOTIF[secim['nakis_motif']]['ad']}, "
                        f"{IPLIK_RENK[secim['nakis_iplik']][0].lower()} iplik")
    return " · ".join(parcalar)


# --- Boyama ------------------------------------------------------------------------------


@lru_cache(maxsize=16)
def _kaynak(kod, genislik):
    klasor = KATALOG if MODELLER[kod].get("kaynak") == "katalog" else KLASOR
    foto = Image.open(klasor / f"{kod}.jpg").convert("RGB")
    harita = Image.open(KLASOR / f"{kod}.png").convert("L")
    if genislik and genislik < foto.width:
        boy = round(foto.height * genislik / foto.width)
        foto = foto.resize((genislik, boy), Image.LANCZOS)
        harita = harita.resize((genislik, boy), Image.NEAREST)
    return foto, harita, foto.convert("L")


@lru_cache(maxsize=32)
def _doku(anahtar, px_cm, boyut):
    """Malzeme dokusunu gerçek ölçeğinde (cm) döşer."""
    yol = DOKU / f"{anahtar}.jpg"
    if not yol.exists():
        return None
    olcek = json.loads((DOKU / "olcek.json").read_text(encoding="utf-8"))
    doku = Image.open(yol).convert("RGB")
    en = max(16, round(olcek.get(anahtar, 12) * px_cm))
    doku = doku.resize((en, max(16, round(doku.height * en / doku.width))), Image.LANCZOS)
    from PIL import ImageOps
    # aynalayarak döşenir: karo dikişleri görünmez
    ikili = Image.new("RGB", (doku.width * 2, doku.height * 2))
    ikili.paste(doku, (0, 0)); ikili.paste(ImageOps.mirror(doku), (doku.width, 0))
    ikili.paste(ImageOps.flip(doku), (0, doku.height)); ikili.paste(ImageOps.flip(ImageOps.mirror(doku)), (doku.width, doku.height))
    tuval = Image.new("RGB", boyut)
    for y in range(0, boyut[1], ikili.height):
        for x in range(0, boyut[0], ikili.width):
            tuval.paste(ikili, (x, y))
    return tuval


@lru_cache(maxsize=32)
def _bienca_kapla(anahtar, kutu, boyut):
    """Bienca baskısı halıda tekrar etmeyen büyük bir desendir: doku bölgeyi tek parça olarak kaplar (dar bantta
    dokunun bir dilimi görünür)."""
    doku = Image.open(DOKU / f"{anahtar}.jpg").convert("RGB")
    w, h = max(1, kutu[2] - kutu[0]), max(1, kutu[3] - kutu[1])
    if w > h * 2.2 or h > w * 2.2:  # ince uzun bant: dokuyu uzun kenar boyunca
        k = max(w, h) / max(doku.width, doku.height)
        if (w > h) != (doku.width > doku.height):
            doku = doku.rotate(90, expand=True)
    k = max(w / doku.width, h / doku.height)
    doku = doku.resize((max(1, round(doku.width * k)), max(1, round(doku.height * k))), Image.LANCZOS)
    tuval = Image.new("RGB", boyut, tuple(round(c) for c in ImageStat.Stat(doku).mean))
    tuval.paste(doku, (kutu[0] - (doku.width - w) // 2, kutu[1] - (doku.height - h) // 2))
    return tuval


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lut(fonk):
    return [max(0, min(255, round(fonk(v)))) for v in range(256)]


def _bolge_olcusu(gri, maske):
    st = ImageStat.Stat(gri, maske)
    ort = max(8.0, st.mean[0])
    return ort, st.stddev[0] / ort


def _carpan(v, ort, guc, ust=1.6):
    return max(0.45, min(ust, 1 - guc + guc * v / ort))


def _boya_duz(gri, ort, renk, guc):
    """Düz renk; fotoğrafın dokusu ve gölgesi guc oranında korunur. Koyu fotoğraf açık renge boyanınca
    ışık parlamaları kırpılır (yoksa açık halı cam gibi parlar)."""
    hedef = sum(renk) / 3
    ust = 1.6 if hedef <= ort * 1.4 else 1.22
    if hedef > ort * 1.4:
        guc *= 0.6
    return Image.merge("RGB", [gri.point(_lut(lambda v, c=c: c * _carpan(v, ort, guc, ust))) for c in renk])


def _carp(resim, golge):
    """resim × golge/128 (golge tek kanal, 128 = değişmez)."""
    return ImageChops.multiply(resim, Image.merge("RGB", (golge,) * 3)).point(lambda x: min(255, x * 2))


def boya(kod, secim, genislik=None):
    """Seçilen renklerle boyanmış PIL resmi."""
    model = MODELLER[kod]
    foto, harita, gri = _kaynak(kod, genislik)
    asil_en = _kaynak(kod, None)[0].width
    px_cm = model["px_cm"] * foto.width / asil_en
    yumusak_gri = gri.filter(ImageFilter.GaussianBlur(max(3, foto.width / 25)))  # yalnız ışık, desen değil
    sonuc = foto.copy()
    siralar = model.get("sira") or range(1, len(model["bolgeler"]) + 1)
    numara = {b["anahtar"]: s for s, b in zip(siralar, bolgeler(kod))}
    atla = set()
    if secim.get("desen_kodu") and kod in DESEN_DEGISIR:
        atla |= _desen_degistir(sonuc, harita, gri, kod, secim, numara)
    if secim.get("motif") and kod in NAKIS_DEGISIR:
        atla |= _motif_degistir(sonuc, harita, gri, kod, secim, numara)
    if kod in NAKIS_KUTULARI and secim != secim_temizle(kod, {}):
        harita = _kutulara_nakis(sonuc, harita, gri, kod, secim, foto.width / _kaynak(kod, None)[0].width)
        atla.add("iplik")
    if secim.get("nakis_motif") and kod in NAKISLI_BANT:
        atla |= _nakisli_bant(sonuc, harita, gri, kod, secim, numara, px_cm)
    if atla:  # değiştirilen yerlerin ışığı yeni resimden (eski motifin izi kalmasın)
        gri = sonuc.convert("L")
        yumusak_gri = gri.filter(ImageFilter.GaussianBlur(max(3, foto.width / 25)))
    for sira, b in zip(siralar, bolgeler(kod)):
        deger = secim.get(b["anahtar"], b["varsayilan"])
        if deger == b["varsayilan"] or b["anahtar"] in atla:
            continue  # fotoğraftaki gibi
        maske = harita.point(lambda v, s=sira: 255 if v == s else 0)
        if not maske.getbbox():
            continue
        ort, oynaklik = _bolge_olcusu(gri, maske)
        # açık/koyu farkı ne olursa olsun yeni renkte doku aynı yoğunlukta görünsün (koyu → açık geçişte parlama olmasın)
        guc = min(0.85, 0.14 / max(oynaklik, 0.01))
        desenli = b["varsayilan"] in DESENLI_ASIL
        if b["tur"] == IPLIK:
            katman = _boya_duz(gri, ort, _hex(IPLIK_RENK[deger][1]), min(0.8, guc * 1.5))
        elif deger in METALLER:
            katman = _boya_duz(gri, ort, _hex(KARTELA[deger][2]), min(1.0, guc * 1.8))
        elif deger.startswith("BN"):  # gerçek Bienca dokusu (atölye fotoğrafı, gerçek ölçüde), ışık fotoğraftan
            doku = _bienca_kapla(KARTELA[deger][0], _kutu(maske), foto.size)
            yum_ort, _ = _bolge_olcusu(yumusak_gri, maske)
            katman = _carp(doku, yumusak_gri.point(_lut(lambda v: 128 * _carpan(v, yum_ort, 0.6, 1.2))))
        else:
            renk = _hex(KARTELA[deger][2])
            if desenli:  # fotoğraftaki eskitme silinir: ışık fotoğraftan, doku keten
                yum_ort, _ = _bolge_olcusu(yumusak_gri, maske)
                katman = _boya_duz(yumusak_gri, yum_ort, renk, 0.6)
                doku = _doku(KARTELA[deger][0], round(px_cm, 2), foto.size)
                if doku is not None:
                    dg = doku.convert("L")
                    d_ort = max(8.0, ImageStat.Stat(dg).mean[0])
                    katman = _carp(katman, dg.point(_lut(lambda v: 128 * _carpan(v, d_ort, 0.7))))
            else:
                katman = _boya_duz(gri, ort, renk, guc)
        sonuc.paste(katman, mask=maske.filter(ImageFilter.GaussianBlur(0.7)))
    return sonuc


def _secilen_renk(kod, b, secim, foto, maske):
    deger = secim.get(b["anahtar"], b["varsayilan"])
    if deger == b["varsayilan"]:
        return tuple(round(c) for c in ImageStat.Stat(foto, maske).mean)
    if b["tur"] == IPLIK:
        return _hex(IPLIK_RENK[deger][1])
    return _hex(KARTELA[deger][2])


def _isik(gri, maske, boyut):
    """Fotoğraftaki genel ışık (desensiz): 128 = ortalama."""
    yum = gri.filter(ImageFilter.GaussianBlur(max(3, boyut[0] / 25)))
    ort = max(8.0, ImageStat.Stat(yum, maske).mean[0])
    return yum.point(_lut(lambda v: 128 * _carpan(v, ort, 0.7, 1.3)))


def _kutu(maske):
    return maske.getbbox() or (0, 0, 1, 1)


def _desen_degistir(sonuc, harita, gri, kod, secim, numara):
    """Dikdörtgen çerçevedeki lazer desenini başka bir DB deseniyle değiştirir (bant rengi korunur ya da seçilen)."""
    from . import hali_gorsel
    anahtar_ = DESEN_DEGISIR[kod]
    s_bant, s_orta = numara.get(anahtar_), numara.get("orta")
    if not s_bant or not s_orta:
        return set()
    bant = harita.point(lambda v: 255 if v == s_bant else 0)
    orta = harita.point(lambda v: 255 if v == s_orta else 0)
    dis = _kutu(bant.filter(ImageFilter.MaxFilter(5)))
    ic = _kutu(orta)
    genislik = max(6, round(((ic[0] - dis[0]) + (dis[2] - ic[2]) + (ic[1] - dis[1]) + (dis[3] - ic[3])) / 4))
    W, H = dis[2] - dis[0], dis[3] - dis[1]
    delik = hali_gorsel._kenar_desen_maskesi(secim["desen_kodu"], (W, H), genislik)
    bolge = Image.new("L", sonuc.size, 0)
    ImageDraw.Draw(bolge).rectangle(dis, fill=255)
    ImageDraw.Draw(bolge).rectangle((dis[0] + genislik, dis[1] + genislik, dis[2] - genislik, dis[3] - genislik), fill=0)
    bolge = ImageChops.multiply(bolge, harita.point(lambda v: 255 if v != s_orta else 0))
    delik_tam = Image.new("L", sonuc.size, 0)
    delik_tam.paste(delik, (dis[0], dis[1]))
    b = next(x for x in bolgeler(kod) if x["anahtar"] == anahtar_)
    renk = _secilen_renk(kod, b, secim, sonuc, bant)
    isik = _isik(gri, bolge, sonuc.size)
    malzeme = _carp(Image.new("RGB", sonuc.size, renk), isik)
    if secim.get(b["anahtar"], b["varsayilan"]) in METALLER or b["varsayilan"] in METALLER:
        malzeme = _carp(malzeme, gri.point(_lut(lambda v: 128 * _carpan(v, 128, 0.25, 1.3))))
    # delikten görünen: fotoğraftaki deliklerin (bant içi dokunulmaz pikseller) ortalama rengi
    eski_delik = ImageChops.multiply(bolge, harita.point(lambda v: 255 if v == 0 else 0))
    delik_renk = tuple(round(c * 0.9) for c in ImageStat.Stat(sonuc, eski_delik).mean) if eski_delik.getbbox() else (35, 32, 30)
    delik_katman = _carp(Image.new("RGB", sonuc.size, delik_renk), isik)
    bant_katman = Image.composite(delik_katman, malzeme, delik_tam.filter(ImageFilter.GaussianBlur(0.5)))
    sonuc.paste(bant_katman, mask=bolge.filter(ImageFilter.GaussianBlur(0.6)))
    return {anahtar_}


def _motif_degistir(sonuc, harita, gri, kod, secim, numara):
    """Nakış şeridindeki motifi başka bir motifle değiştirir (şerit ve iplik renkleri seçilen ya da fotoğraftaki)."""
    from . import parcali_gorsel
    a_serit, a_iplik = NAKIS_DEGISIR[kod]
    s_serit, s_iplik = numara[a_serit], numara[a_iplik]
    serit = harita.point(lambda v: 255 if v in (s_serit, s_iplik) else 0)
    kutu = _kutu(serit)
    bl = {b["anahtar"]: b for b in bolgeler(kod)}
    zemin_renk = _secilen_renk(kod, bl[a_serit], secim, sonuc, harita.point(lambda v: 255 if v == s_serit else 0))
    iplik_renk = _secilen_renk(kod, bl[a_iplik], secim, sonuc, harita.point(lambda v: 255 if v == s_iplik else 0))
    isik = _isik(gri, serit, sonuc.size)
    katman = _carp(Image.new("RGB", sonuc.size, zemin_renk), isik)
    motif = parcali_gorsel.nakis_maskesi(secim["motif"])
    h = round((kutu[3] - kutu[1]) * 0.82)
    w = max(1, round(motif.width * h / motif.height))
    if w > (kutu[2] - kutu[0]) * 0.9:
        w = round((kutu[2] - kutu[0]) * 0.9); h = max(1, round(motif.height * w / motif.width))
    motif = motif.resize((w, h), Image.LANCZOS)
    aralik = max(4, round(h * 0.18))
    adet = max(1, ((kutu[2] - kutu[0]) - aralik) // (w + aralik))
    bas = kutu[0] + ((kutu[2] - kutu[0]) - adet * w - (adet - 1) * aralik) // 2
    motifler = Image.new("L", sonuc.size, 0)
    for i in range(adet):
        motifler.paste(motif, (bas + i * (w + aralik), kutu[1] + ((kutu[3] - kutu[1]) - h) // 2))
    iplik = _carp(Image.new("RGB", sonuc.size, iplik_renk), isik)
    # iplik kabartması: motif kenarında hafif gölge
    golge = motifler.filter(ImageFilter.GaussianBlur(1.2)).point(lambda v: 255 - v // 4)
    katman = _carp(katman, golge.point(lambda v: v // 2))
    katman = Image.composite(iplik, katman, motifler)
    sonuc.paste(katman, mask=serit.filter(ImageFilter.GaussianBlur(0.6)))
    return {a_serit, a_iplik}


@lru_cache(maxsize=4)
def _saten(boyut):
    """Saten dikiş dokusu: sık çapraz iplik çizgileri (128 = değişmez)."""
    tile = Image.new("L", (12, 12), 128)
    d = ImageDraw.Draw(tile)
    for i in range(-12, 24, 3):
        d.line([(i, 0), (i + 12, 12)], fill=150, width=1)
    tuval = Image.new("L", boyut)
    for y in range(0, boyut[1], 12):
        for x in range(0, boyut[0], 12):
            tuval.paste(tile, (x, y))
    return tuval.filter(ImageFilter.GaussianBlur(0.4))


def _nakis_isle(sonuc, motif, iplik_rgb, olcek=1.0):
    """Motif maskesini (L, 255 = iplik) sonuca kabarık nakış olarak işler: kumaşa gölge, ipliğe ışık + saten doku."""
    boyut = sonuc.size
    k = max(1, round(2 * olcek))
    yum = motif.filter(ImageFilter.GaussianBlur(max(0.8, 1.6 * olcek)))
    golge = ImageChops.offset(motif.filter(ImageFilter.GaussianBlur(max(1, 2.5 * olcek))), k, k + 1)
    sonuc.paste(_carp(sonuc, golge.point(lambda v: round(128 - v * 0.22))), mask=golge.point(lambda v: min(255, v * 2)))
    isik = sonuc.convert("L").filter(ImageFilter.GaussianBlur(max(3, boyut[0] / 25)))
    ort = max(8.0, ImageStat.Stat(isik, motif).mean[0])
    parlak = ImageChops.subtract(yum, ImageChops.offset(yum, k, k)).point(lambda v: round(v * 0.5))
    karanlik = ImageChops.subtract(ImageChops.offset(yum, k, k), yum).point(lambda v: round(v * 0.6))
    kabartma = ImageChops.subtract(ImageChops.add(Image.new("L", boyut, 128), parlak), karanlik)
    katman = _carp(Image.new("RGB", boyut, iplik_rgb), isik.point(_lut(lambda v: 128 * _carpan(v, ort, 0.5, 1.2))))
    katman = _carp(_carp(katman, kabartma), _saten(boyut))
    sonuc.paste(katman, mask=motif.filter(ImageFilter.GaussianBlur(0.5)))


def _motif_yerlestir(maske, kod, kutu, oran=0.92, dondur=False):
    """Motifi kutuya (oranı korunarak, ortalanmış) yerleştirir."""
    from . import parcali_gorsel
    m = parcali_gorsel.nakis_maskesi(kod)
    if dondur:
        m = m.rotate(90, expand=True)
    w, h = kutu[2] - kutu[0], kutu[3] - kutu[1]
    k = min(w * oran / m.width, h * oran / m.height)
    m = m.resize((max(1, round(m.width * k)), max(1, round(m.height * k))), Image.LANCZOS)
    maske.paste(m, (kutu[0] + (w - m.width) // 2, kutu[1] + (h - m.height) // 2), m)


def _kutulara_nakis(sonuc, harita, gri, kod, secim, olcek):
    """Nakışlı Rono fotoğrafında eski motifleri siler (motifsiz zeminden doku), seçilen motifi seçilen iplikle işler.
    Yeni bölge haritasını döndürür (1 zemin, 2 iplik)."""
    bx0, bx1 = (round(v * olcek) for v in NAKIS_BOSLUK[kod])
    motifler = Image.new("L", sonuc.size, 0)
    for kutu in NAKIS_KUTULARI[kod]:
        x0, y0, x1, y1 = (round(v * olcek) for v in kutu)
        p = round(8 * olcek)
        x0, y0, x1, y1 = max(0, x0 - p), max(0, y0 - p), min(sonuc.width, x1 + p), min(sonuc.height, y1 + p)
        yama = sonuc.crop((bx0, y0, bx1, y1)).resize((x1 - x0, y1 - y0), Image.LANCZOS)
        yumusak = Image.new("L", yama.size, 0)
        ImageDraw.Draw(yumusak).rectangle((p // 2, p // 2, yama.width - p // 2, yama.height - p // 2), fill=255)
        sonuc.paste(yama, (x0, y0), yumusak.filter(ImageFilter.GaussianBlur(max(1, p / 3))))
        _motif_yerlestir(motifler, secim.get("motif") or "61.01", (x0 + p, y0 + p, x1 - p, y1 - p))
    _nakis_isle(sonuc, motifler, _hex(IPLIK_RENK[secim["iplik"]][1]), olcek * 1.5)
    yeni = Image.new("L", sonuc.size, 1)
    yeni.paste(2, mask=motifler.point(lambda v: 255 if v > 100 else 0))
    return yeni


def _nakisli_bant(sonuc, harita, gri, kod, secim, numara, px_cm):
    """Çerçeve bandı Rono olur, üstüne seçilen motif dört kenar boyunca dizilerek işlenir."""
    anahtar_ = NAKISLI_BANT[kod]
    s_bant, s_orta = numara.get(anahtar_), numara.get("orta")
    if not s_bant or not s_orta:
        return set()
    bant = harita.point(lambda v: 255 if v == s_bant else 0)
    orta = harita.point(lambda v: 255 if v == s_orta else 0)
    dis = _kutu(bant.filter(ImageFilter.MaxFilter(5)))
    ic = _kutu(orta)
    g = max(6, round(((ic[0] - dis[0]) + (dis[2] - ic[2]) + (ic[1] - dis[1]) + (dis[3] - ic[3])) / 4))
    bolge = Image.new("L", sonuc.size, 0)
    ImageDraw.Draw(bolge).rectangle(dis, fill=255)
    ImageDraw.Draw(bolge).rectangle((dis[0] + g, dis[1] + g, dis[2] - g, dis[3] - g), fill=0)
    bolge = ImageChops.multiply(bolge, harita.point(lambda v: 255 if v != s_orta else 0))
    rn = secim[anahtar_]
    isik = _isik(gri, bolge, sonuc.size)
    katman = _carp(Image.new("RGB", sonuc.size, _hex(KARTELA[rn][2])), isik)
    doku = _doku(KARTELA[rn][0], round(px_cm, 2), sonuc.size)
    if doku is not None:
        dg = doku.convert("L")
        d_ort = max(8.0, ImageStat.Stat(dg).mean[0])
        katman = _carp(katman, dg.point(_lut(lambda v: 128 * _carpan(v, d_ort, 0.7))))
    sonuc.paste(katman, mask=bolge.filter(ImageFilter.GaussianBlur(0.6)))
    # motifler: kısa kenar bant genişliğinin %72'si, aralarında küçük boşluk; yan kenarlarda şerit motifi dik döner
    bilgi = parcali.MOTIF[secim["nakis_motif"]]
    uzun, kisa = max(bilgi["en"], bilgi["boy"]), min(bilgi["en"], bilgi["boy"])
    h = g * 0.72
    w = h * uzun / kisa if bilgi["tur"] == "serit" else h * bilgi["en"] / bilgi["boy"]
    aralik = max(3, h * 0.25)
    motifler = Image.new("L", sonuc.size, 0)

    def diz(bas, son, sabit, yatay):
        adet = max(1, int((son - bas + aralik) // (w + aralik)))
        bos = (son - bas - adet * w - (adet - 1) * aralik) / 2
        for i in range(adet):
            a = bas + bos + i * (w + aralik)
            kutu = (a, sabit, a + w, sabit + h) if yatay else (sabit, a, sabit + h, a + w)
            _motif_yerlestir(motifler, secim["nakis_motif"], tuple(round(v) for v in kutu), 1.0,
                             dondur=not yatay and bilgi["tur"] == "serit")

    pay = (g - h) / 2
    diz(dis[0] + pay, dis[2] - pay, dis[1] + pay, True)
    diz(dis[0] + pay, dis[2] - pay, dis[3] - g + pay, True)
    diz(dis[1] + g, dis[3] - g, dis[0] + pay, False)
    diz(dis[1] + g, dis[3] - g, dis[2] - g + pay, False)
    _nakis_isle(sonuc, ImageChops.multiply(motifler, bolge), _hex(IPLIK_RENK[secim["nakis_iplik"]][1]),
                max(0.5, sonuc.width / 600))
    return {anahtar_}


def anahtar(kod, secim, genislik):
    ozet = hashlib.sha1(json.dumps([kod, sorted(secim.items()), genislik, SURUM]).encode()).hexdigest()[:16]
    return f"{kod}_{ozet}_{genislik or 0}.jpg"


def jpeg(kod, secim, genislik=None):
    """Boyanmış resmin JPEG baytları (diskte önbelleklenir)."""
    klasor = Path(settings.MEDIA_ROOT) / "foto_model"
    yol = klasor / anahtar(kod, secim, genislik)
    if yol.exists():
        return yol.read_bytes()
    tampon = io.BytesIO()
    boya(kod, secim, genislik).save(tampon, "JPEG", quality=84, optimize=True)
    veri = tampon.getvalue()
    try:
        klasor.mkdir(parents=True, exist_ok=True)
        yol.write_bytes(veri)
        dosyalar = sorted(klasor.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
        for eski in dosyalar[:-ONBELLEK_SINIR]:
            eski.unlink(missing_ok=True)
    except OSError:
        pass  # önbellek yazılamazsa resim yine gönderilir
    return veri


# --- Fikir ver ----------------------------------------------------------------------------

# (zemin, vurgu, ikinci) uyumlu kartela takımları; vurgu bölgesi metal olabilir
TAKIMLAR = [
    ("RN03", "RN06", "RN05"), ("RN07", "RN04", "RN01"), ("RN01", "RN04", "RN02"), ("RN06", "BN02", "RN05"),
    ("RN07", "BN04", "RN03"), ("RN02", "RN07", "RN01"), ("RN05", "RN06", "RN03"), ("RN04", "BN01", "RN02"),
    ("RN03", "BN03", "RN01"), ("RN06", "RN03", "RN05"), ("RN07", "ALTIN", "RN03"), ("RN04", "RN03", "RN02"),
]
ACIK = {"RN03", "RN07", "RN01", "BN01", "BN04", "ALTIN", "GUMUS"}


def _parlaklik(kod):
    r, g, b = _hex(KARTELA[kod][2])
    return 0.3 * r + 0.59 * g + 0.11 * b


def _aileden(kod, aile):
    """Takımdaki rengi istenen kartela ailesinde (RN / BN) en yakın parlaklıktaki renge çevirir."""
    if kod in METALLER or kod.startswith(aile):
        return kod
    adaylar = [k for k in KARTELA if k.startswith(aile)]
    return min(adaylar, key=lambda k: abs(_parlaklik(k) - _parlaklik(kod)))


# Lazer desenli bantlar fikirde açık / metalik renk alır (koyuda delikler kaybolur)
DESEN_FIKIR = ["GUMUS", "ALTIN", "BN01", "RN07", "BN04", "RN03", "BN03", "GUMUS"]


def fikirler(kod, adet=6):
    """Modelin yapısı aynı, kartela renkleri farklı 6 takım (fotoğraftakine benzeyenler atlanır).
    Fotoğrafta Bienca olan zemin Bienca'da, Rono olan Rono'da kalır."""
    bl = bolgeler(kod)
    asil = secim_temizle(kod, {})
    sonuc = []
    for sira, (zemin, vurgu, ikinci) in enumerate(TAKIMLAR):
        secim = {}
        for b in bl:
            secenek = bolge_secenekleri(b)
            if b["rol"] == "iplik":
                secim[b["anahtar"]] = "kahve" if zemin in ACIK or vurgu in ACIK else "bej"
                continue
            if b["rol"] in ("metal",) or (b["rol"] == "vurgu" and b["tur"] == DESEN):
                istenen = DESEN_FIKIR[sira % len(DESEN_FIKIR)]
                if b["rol"] == "metal" and istenen not in METALLER:
                    istenen = METALLER[sira % 2]
            else:
                istenen = {"zemin": zemin, "vurgu": vurgu, "ikinci": ikinci}[b["rol"]]
                if b["varsayilan"] not in METALLER:
                    istenen = _aileden(istenen, b["varsayilan"][:2])
            secim[b["anahtar"]] = istenen if istenen in secenek else b["varsayilan"]
        if secim != asil and secim not in sonuc:
            sonuc.append(secim)
        if len(sonuc) == adet:
            break
    return sonuc


def istemci_verisi(resim_adresleri):
    from django.urls import reverse

    """Bayi ekranı için: model → bölgeler, seçenekler (resim/renk), fikirler."""
    veri = {}
    for kod, model in MODELLER.items():
        bl = []
        for b in bolgeler(kod):
            sec = []
            for deger in bolge_secenekleri(b):
                if b["tur"] == IPLIK:
                    sec.append({"k": deger, "ad": IPLIK_RENK[deger][0], "hex": IPLIK_RENK[deger][1]})
                elif deger in METALLER:
                    sec.append({"k": deger, "ad": KARTELA[deger][1], "hex": KARTELA[deger][2]})
                else:
                    sec.append({"k": deger, "ad": f"{deger} {KARTELA[deger][1]}", "resim": resim_adresleri.get(deger, ""),
                                "hex": KARTELA[deger][2]})
            bl.append({"anahtar": b["anahtar"], "ad": b["ad"], "varsayilan": b["varsayilan"], "secenekler": sec})
        ek = []
        if kod in DESEN_DEGISIR:
            ek.append({"anahtar": "desen_kodu", "ad": "Lazer deseni", "varsayilan": "", "secenekler":
                       [{"k": "", "ad": "Fotoğraftaki"}] + [{"k": d, "ad": d, "resim": reverse("tasarim_desen_onizleme", args=[d])}
                                                             for d in lazer_desenleri()]})
        if kod in NAKISLI_BANT:
            ek.append({"anahtar": "nakis_motif", "ad": "Nakışlı bant (Rono üstüne nakış)", "varsayilan": "", "secenekler":
                       [{"k": "", "ad": "Nakış yok"}] + [{"k": m, "ad": parcali.MOTIF[m]["ad"],
                                                          "resim": reverse("parcali_motif", args=[m])} for m in parcali.MOTIF]})
            ek.append({"anahtar": "nakis_iplik", "ad": "Nakış ipliği", "varsayilan": "bej", "secenekler":
                       [{"k": k, "ad": a, "hex": h} for k, (a, h) in IPLIK_RENK.items()]})
        if kod in NAKIS_DEGISIR or kod in NAKIS_KUTULARI:
            ek.append({"anahtar": "motif", "ad": "Nakış motifi", "varsayilan": "", "secenekler":
                       [{"k": "", "ad": "Fotoğraftaki"}] + [{"k": m, "ad": parcali.MOTIF[m]["ad"],
                                                              "resim": reverse("parcali_motif", args=[m])} for m in parcali.MOTIF]})
        veri[kod] = {"ad": model["ad"], "bolgeler": bl + ek, "fikirler": fikirler(kod)}
    return veri
