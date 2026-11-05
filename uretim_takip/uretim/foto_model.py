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
from PIL import Image, ImageChops, ImageFilter, ImageStat

from . import parcali

KLASOR = Path(__file__).resolve().parent / "tasarim_varlik" / "foto_model"
DOKU = Path(__file__).resolve().parent / "tasarim_varlik" / "doku"
ONBELLEK_SINIR = 600  # önbellekte en çok bu kadar boyanmış resim kalır

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
}
# fotoğrafta desenli (eskitme/varak) olan bölgeler: başka renge geçince fotoğrafın deseni değil kartelanın dokusu görünür
DESENLI_ASIL = {"BN01", "BN02", "BN03", "BN04"}


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


def bolgeler(kod):
    return [dict(zip(("anahtar", "ad", "tur", "varsayilan", "rol"), b)) for b in MODELLER[kod]["bolgeler"]]


def secim_temizle(kod, veri):
    """Gelen seçimi (dict) doğrular; geçersiz/eksik bölgeler fotoğraftaki renkte kalır."""
    sonuc = {}
    for b in bolgeler(kod):
        deger = str((veri or {}).get(b["anahtar"], "")).strip()
        sonuc[b["anahtar"]] = deger if deger in secenekler(b["tur"]) else b["varsayilan"]
    return sonuc


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
    return " · ".join(parcalar)


# --- Boyama ------------------------------------------------------------------------------


@lru_cache(maxsize=16)
def _kaynak(kod, genislik):
    foto = Image.open(KLASOR / f"{kod}.jpg").convert("RGB")
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
    tuval = Image.new("RGB", boyut)
    for y in range(0, boyut[1], doku.height):
        for x in range(0, boyut[0], doku.width):
            tuval.paste(doku, (x, y))
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


@lru_cache(maxsize=16)
def _bn_paleti(anahtar):
    """Bienca dokusunun koyu ve açık tonu (eskitme deseni bu iki ton arasında)."""
    doku = Image.open(DOKU / f"{anahtar}.jpg").convert("RGB")
    doku.thumbnail((200, 200))
    pikseller = sorted(doku.getdata(), key=sum)
    n = max(1, len(pikseller) // 7)
    koyu = [sum(p[i] for p in pikseller[:n]) / n for i in range(3)]
    acik = [sum(p[i] for p in pikseller[-n:]) / n for i in range(3)]
    return koyu, acik


def _yuzdelik(gri, maske, alt, ust):
    hist = gri.histogram(mask=maske)
    toplam = sum(hist) or 1
    sinirlar, birikim = [], 0
    hedefler = [toplam * alt, toplam * ust]
    for v, n in enumerate(hist):
        birikim += n
        while hedefler and birikim >= hedefler[0]:
            sinirlar.append(v)
            hedefler.pop(0)
    return (sinirlar + [0, 255])[:2]


def boya(kod, secim, genislik=None):
    """Seçilen renklerle boyanmış PIL resmi."""
    model = MODELLER[kod]
    foto, harita, gri = _kaynak(kod, genislik)
    asil_en = _kaynak(kod, None)[0].width
    px_cm = model["px_cm"] * foto.width / asil_en
    yumusak_gri = gri.filter(ImageFilter.GaussianBlur(max(2, foto.width / 90)))
    sonuc = foto.copy()
    for sira, b in enumerate(bolgeler(kod), 1):
        deger = secim.get(b["anahtar"], b["varsayilan"])
        if deger == b["varsayilan"]:
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
        elif deger.startswith("BN"):
            koyu, acik = _bn_paleti(KARTELA[deger][0])
            if desenli:  # fotoğraftaki eskitme deseni yeni Bienca'nın iki tonuyla
                alt, ust = _yuzdelik(gri, maske, 0.04, 0.96)
                aralik = max(1, ust - alt)
                katman = Image.merge("RGB", [gri.point(_lut(lambda v, k=k, a=a: k + (a - k) * min(1, max(0, (v - alt) / aralik))))
                                             for k, a in zip(koyu, acik)])
            else:
                doku = _doku(KARTELA[deger][0], round(px_cm * 2.5, 2), foto.size)
                yum_ort, _ = _bolge_olcusu(yumusak_gri, maske)
                ort_renk = Image.new("RGB", foto.size, tuple(round((k + a) / 2) for k, a in zip(koyu, acik)))
                doku = Image.blend(doku, ort_renk, 0.3)
                katman = _carp(doku, yumusak_gri.point(_lut(lambda v: 128 * _carpan(v, yum_ort, 0.6, 1.25))))
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


def anahtar(kod, secim, genislik):
    ozet = hashlib.sha1(json.dumps([kod, sorted(secim.items()), genislik]).encode()).hexdigest()[:16]
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


def fikirler(kod, adet=6):
    """Modelin yapısı aynı, kartela renkleri farklı 6 takım (fotoğraftakine benzeyenler atlanır)."""
    bl = bolgeler(kod)
    asil = secim_temizle(kod, {})
    sonuc = []
    for zemin, vurgu, ikinci in TAKIMLAR:
        secim = {}
        for b in bl:
            secenek = secenekler(b["tur"])
            if b["rol"] == "iplik":
                secim[b["anahtar"]] = "kahve" if zemin in ACIK or vurgu in ACIK else "bej"
                continue
            istenen = {"zemin": zemin, "vurgu": vurgu, "ikinci": ikinci, "metal": vurgu}[b["rol"]]
            if istenen not in secenek:
                istenen = "ALTIN" if b["rol"] == "metal" else ikinci
            if b["rol"] == "metal" and istenen not in METALLER:
                istenen = METALLER[len(sonuc) % 2]
            secim[b["anahtar"]] = istenen if istenen in secenek else b["varsayilan"]
        if secim != asil and secim not in sonuc:
            sonuc.append(secim)
        if len(sonuc) == adet:
            break
    return sonuc


def istemci_verisi(resim_adresleri):
    """Bayi ekranı için: model → bölgeler, seçenekler (resim/renk), fikirler."""
    veri = {}
    for kod, model in MODELLER.items():
        bl = []
        for b in bolgeler(kod):
            sec = []
            for deger in secenekler(b["tur"]):
                if b["tur"] == IPLIK:
                    sec.append({"k": deger, "ad": IPLIK_RENK[deger][0], "hex": IPLIK_RENK[deger][1]})
                elif deger in METALLER:
                    sec.append({"k": deger, "ad": KARTELA[deger][1], "hex": KARTELA[deger][2]})
                else:
                    sec.append({"k": deger, "ad": f"{deger} {KARTELA[deger][1]}", "resim": resim_adresleri.get(deger, ""),
                                "hex": KARTELA[deger][2]})
            bl.append({"anahtar": b["anahtar"], "ad": b["ad"], "varsayilan": b["varsayilan"], "secenekler": sec})
        veri[kod] = {"ad": model["ad"], "bolgeler": bl, "fikirler": fikirler(kod)}
    return veri
