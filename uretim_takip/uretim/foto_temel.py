"""Katalog modelinde fotoğraf esas (2026-11-16, kullanıcı: "seçilen model üzerinden yalnız seçilen bordürün rengi ve
modeli değişsin").

Bayi katalogdaki bir modelden başlayıp renk / desen değiştirince halı baştan çizilmez: bayinin dokunmadığı parçalar
(zemin, madalyon, öteki bordürler, biye) katalog fotoğrafından gelir, yalnız değişen parça çizilir. Fotoğraf çizimin
ölçüsüne oturtulur: bordürler gerçek cm genişliğini korur (kenarlar boyuna uzar), orta esner, madalyon yuvarlak kalır. Halının yapısı değiştiyse (bordür eklendi / çıkarıldı, genişlik, şekil, orta türü) fotoğraf
artık uymaz: o zaman bütün halı çizilir (None döner).

Fotoğraftaki halı kutusu: tasarim_varlik/foto_kutu.json (is_belgeleri/katalog_beyaz/kutu_cikar.py); fotoğraf
kayık / perspektifli olduğundan her kenarın bordür sınırları ayrı ölçülür (foto_halka.json) ve fotoğraf parça parça
esnetilerek bu sınırlar çizimdeki yerlerine oturtulur.
"""
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import parcali as pc

_KLASOR = Path(__file__).parent
FOTO_KLASORU = _KLASOR / "katalog_tohum" / "model"
KUTU = json.loads((_KLASOR / "tasarim_varlik" / "foto_kutu.json").read_text())
# fotoğrafta her kenarda bordür sınırları (cm, kenardan içeri; fotoğraf katalog ölçüsüne oturtulmuş olarak), gözle
# ölçüldü: is_belgeleri/foto_halka/kontrol.py ile kırmızı çizgiler fotoğraftaki sınırların üstüne düşmeli
HALKA = json.loads((_KLASOR / "tasarim_varlik" / "foto_halka.json").read_text())
KOSE_ORANI = 0.0225  # beyaz_zemin.py: köşe yarıçapı fotoğraf genişliği × 0.045, iki kat büyük maskede → yarısı
ARKA = (252, 251, 249)

# halının yapısı: bunlardan biri değişince fotoğraf uymaz, bütün halı çizilir
_YAPI = ("duzen", "sekil", "orta", "halka_sayisi", "serit_yon", "serit_adet", "serit", "aralik", "motif_adet",
         "panel_en", "panel_boy")


def uygun_mu(kod):
    """Bu model fotoğraf esaslı gösterilebilir mi (fotoğrafı var, bordür sınırları fotoğrafta ölçüldü)."""
    return kod in KUTU and kod in HALKA and kod in pc.FOTO_RENK and (FOTO_KLASORU / f"{kod}.jpg").exists()


def _yapi(v):
    n = int(v.get("halka_sayisi") or 0)
    y = [v.get(a) for a in _YAPI]
    y += [v.get(f"h{i}_gen") for i in range(1, n + 1)] + [v.get(f"a{i}_gen") for i in range(1, n)]
    mad = v.get("orta") == "duz" and v.get("madalyon") != "yok"
    y += [mad, v.get("madalyon_cap") if mad else None, bool(v.get("madalyon_cerceve")) if mad else None]
    return y


def referans(kod, en=None, boy=None):
    """Modelin katalogdaki (fotoğraftaki) değerleri; en / boy verilirse o ölçüde."""
    from .parcali_views import _desen_kodlari

    d = pc.hazir_degerler(kod)
    if en:
        d = {**d, "en": en, "boy": boy}
    return pc.temizle(d, _desen_kodlari())


def degisenler(v, b):
    """Bayinin değiştirdiği parça grupları: ('h', i) bordür, ('a', i) ara bant, 'zemin', 'madalyon', 'mcerceve',
    'serit', 'panel', 'kenar'."""
    d = set()
    fark = lambda *a: any(v.get(x) != b.get(x) for x in a)  # noqa: E731
    for i in range(1, int(v.get("halka_sayisi") or 0) + 1):
        on = f"h{i}_"
        tur = v.get(on + "tur")
        if fark(on + "tur", on + "malzeme") or (tur == "desenli" and fark(on + "desen", "desen_alti")) or (
                tur == "nakisli" and fark(on + "nakis", "iplik")):
            d.add(("h", i))
    if fark("zemin"):
        d |= {"zemin"} | {("a", i) for i in range(1, pc.EN_COK_HALKA)}
    if v.get("madalyon") != "yok" and (fark("madalyon", "madalyon_malzeme") or (
            v.get("madalyon") == "nakisli" and fark("madalyon_motif", "iplik"))):
        d.add("madalyon")
    if fark("madalyon_cerceve"):
        d.add("mcerceve")
    if fark("serit_tur", "serit_malzeme", "serit_desen") or (v.get("serit_tur") == "nakisli" and fark("nakis", "iplik")):
        d.add("serit")
    if fark("panel_malzeme", "nakis", "iplik"):
        d.add("panel")
    if fark("kenar", "kenar_renk"):
        d.add("kenar")
    return d


def _grup(p):
    if p.get("halka") is not None:
        no = p["halka"]
        return ("a", int(no[1:])) if isinstance(no, str) else ("h", no)
    ad = p["ad"]
    if ad.startswith("Madalyon çerçevesi"):
        return "mcerceve"
    if ad.startswith("Madalyon"):
        return "madalyon"
    if "şerit" in ad:
        return "serit"
    if ad.startswith("Nakış paneli"):
        return "panel"
    return "zemin"


@lru_cache(maxsize=8)
def _foto(kod):
    """Fotoğraftaki halı (kutusundan kesilmiş) ve köşe yarıçapı (fotoğraf pikseli)."""
    resim = Image.open(FOTO_KLASORU / f"{kod}.jpg").convert("RGB")
    x0, y0, x1, y1, _ = KUTU[kod]
    return resim.crop((x0, y0, x1, y1)), round(resim.width * KOSE_ORANI)


def _kenar_olculeri(kod, ref):
    """Fotoğrafta her kenarda bordür sınırları (fotoğraf cm'i, kenardan içeri); ölçülmemişse modelin kendi sınırları."""
    model = [h["d"] + h["gen"] for h in pc.halkalar(ref)]
    olcu = HALKA.get(kod, {})
    return {k: (olcu[k] if len(olcu.get(k, [])) == len(model) else model) for k in ("sol", "sag", "ust", "alt")}


def _esnet(foto, xk, yk, hedef):
    """Parça parça doğrusal esnetme: kaynak düğümler (xk[0], yk[0]) hedef düğümlere (xk[1], yk[1]) oturur."""
    veri = []
    for i in range(len(xk[1]) - 1):
        for j in range(len(yk[1]) - 1):
            kutu = (xk[1][i], yk[1][j], xk[1][i + 1], yk[1][j + 1])
            if kutu[2] <= kutu[0] or kutu[3] <= kutu[1]:
                continue
            x0, x1, y0, y1 = xk[0][i], xk[0][i + 1], yk[0][j], yk[0][j + 1]
            veri.append((kutu, (x0, y0, x0, y1, x1, y1, x1, y0)))
    return foto.transform(hedef, Image.Transform.MESH, veri, Image.BICUBIC)


def _dugumler(kenar_bas, kenar_son, model, uzunluk, k_kaynak, k_hedef, hedef_uz):
    """Bir eksende kaynak (fotoğraf px) ve hedef (çizim px) düğümleri; içte kalan sınırlar sırayla."""
    kaynak = [0.0] + [d * k_kaynak for d in kenar_bas] + [uzunluk - d * k_kaynak for d in reversed(kenar_son)] + [uzunluk]
    hedef = [0] + [round(d * k_hedef) for d in model] + [hedef_uz - round(d * k_hedef) for d in reversed(model)] + [hedef_uz]
    return kaynak, hedef


def fotograf_yerlesimi(kod, v, px):
    """Fotoğraftaki halı, çizimin ölçüsünde (W×H): her bordür sınırı çizimdeki yerine oturur; köşe yarıçapı (cm)."""
    ref = referans(kod)
    foto, kose_px = _foto(kod)
    ref_en, ref_boy = ref["en"], ref["boy"]
    kenar = _kenar_olculeri(kod, ref)
    if v["en"] > v["boy"]:  # yatay halı: çizim x ↔ y çevirir, fotoğraf da
        foto = foto.transpose(Image.Transpose.TRANSPOSE)
        ref_en, ref_boy = ref_boy, ref_en
        kenar = {"sol": kenar["ust"], "ust": kenar["sol"], "sag": kenar["alt"], "alt": kenar["sag"]}
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    fx, fy = foto.width / ref_en, foto.height / ref_boy  # fotoğrafta cm başına piksel
    kose_cm = kose_px / min(fx, fy)
    model = [h["d"] + h["gen"] for h in pc.halkalar(v)]
    xk = _dugumler(kenar["sol"], kenar["sag"], model, foto.width, fx, px, W)
    yk = _dugumler(kenar["ust"], kenar["alt"], model, foto.height, fy, px, H)
    madalyonlu = ref.get("orta") == "duz" and ref.get("madalyon") != "yok"
    if madalyonlu:
        # madalyon esnetilmeden önce fotoğraftan alınır (yeri yakındaki zeminle kapatılır), sonra esnemiş halının
        # ortasına yuvarlak ve gerçek ölçüsünde konur
        n = len(model)
        r = ref["madalyon_cap"] / 2 + (pc.MADALYON_CERCEVE if ref.get("madalyon_cerceve") else 0) + 1.5
        cx, cy = (xk[0][n] + xk[0][n + 1]) / 2, (yk[0][n] + yk[0][n + 1]) / 2
        kutu = (round(cx - r * fx), round(cy - r * fy), round(cx + r * fx), round(cy + r * fy))
        madalyon = foto.crop(kutu)
        foto = _madalyonu_sil(foto, kutu, (xk[0][n], yk[0][n], xk[0][n + 1], yk[0][n + 1]))
    yerlesik = _esnet(foto, xk, yk, (W, H))
    if madalyonlu:
        cap = max(2, round(2 * r * px))
        yerlesik.paste(madalyon.resize((cap, cap), Image.BICUBIC), ((W - cap) // 2, (H - cap) // 2), _daire(cap))
    return yerlesik, kose_cm


def _daire(cap):
    maske = Image.new("L", (cap * 2, cap * 2), 0)
    ImageDraw.Draw(maske).ellipse((0, 0, cap * 2 - 1, cap * 2 - 1), fill=255)
    return maske.resize((cap, cap), Image.LANCZOS)


def _madalyonu_sil(foto, kutu, zemin):
    """Madalyonun yerini zeminin başka bir yerinden (yukarı / aşağı / yana kaydırılmış) bir parçayla kapatır."""
    x0, y0, x1, y1 = kutu
    g, y = x1 - x0, y1 - y0
    zx0, zy0, zx1, zy1 = zemin
    adaylar = [(0, -round(y * 1.15)), (0, round(y * 1.15)), (-round(g * 1.15), 0), (round(g * 1.15), 0)]
    for dx, dy in adaylar:
        if zx0 <= x0 + dx and x1 + dx <= zx1 and zy0 <= y0 + dy and y1 + dy <= zy1:
            break
    else:
        return foto  # zemin dar: madalyon olduğu gibi kalır (üstüne yenisi konur)
    sonuc = foto.copy()
    yama = foto.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
    maske = _daire(max(g, y)).resize((g, y)).filter(ImageFilter.GaussianBlur(max(1, g / 40)))
    sonuc.paste(yama, (x0, y0), maske)
    return sonuc


def bilesik(v, uzun_kenar=900):
    """Fotoğraf esaslı görüntü (PIL Image) ya da None (bu tasarım için uygun değil: bütün halı çizilir)."""
    from . import parcali_gorsel as pg

    kod = v.get("katalog") or ""
    if v.get("duzen") != "halkali" or not uygun_mu(kod):
        return None
    b = referans(kod, v["en"], v["boy"])
    if _yapi(v) != _yapi(b):
        return None
    degisen = degisenler(v, b)
    px = uzun_kenar / max(v["en"], v["boy"])
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    foto, kose_cm = fotograf_yerlesimi(kod, v, px)
    oval = v.get("sekil") == "oval"
    tuval = pg.ciz(v, uzun_kenar, kose_cm=3 if oval else kose_cm)
    pay = (tuval.width - W) // 2

    # fotoğraftan gelecek yerler: değişmeyen parçalar
    maske = Image.new("L", (W, H), 0)
    c = ImageDraw.Draw(maske)
    olc = lambda poli: [(x * px, y * px) for x, y in poli]  # noqa: E731
    for p in pc.parcalar(v):
        if _grup(p) not in degisen:
            c.polygon(olc(p["poli"]), fill=255)
    dis = Image.new("L", (W, H), 0)
    if oval:
        ImageDraw.Draw(dis).polygon(olc(pc.dis_hat(v)), fill=255)
    else:
        ImageDraw.Draw(dis).rounded_rectangle((0, 0, W - 1, H - 1), radius=max(3, int(px * kose_cm)), fill=255)
    # biye / lanfel şeridi: kenar değişmediyse fotoğraftan, değiştiyse çizimden
    b_px = max(3, int(px * 2.2))
    ic = _ic_hat(dis, b_px, W, H)
    serit = ImageChops.subtract(dis, ic)
    if "kenar" in degisen:
        maske = ImageChops.subtract(maske, serit)
    else:
        maske = ImageChops.lighter(maske, serit)
    maske = ImageChops.multiply(maske, dis).filter(ImageFilter.GaussianBlur(max(0.6, px * 0.25)))
    maske = ImageChops.multiply(maske, dis)  # yumuşatma halının dışına taşmasın
    tuval.paste(foto, (pay, pay), maske)
    return tuval


def _ic_hat(dis, b, W, H):
    """Dış hattın b piksel içeriden geçen eşi (resim kenarına dayanan hat da aşınır)."""
    from PIL import ImageOps

    genis = ImageOps.expand(dis, b + 2, 0).filter(ImageFilter.MinFilter(b * 2 + 1))
    return genis.crop((b + 2, b + 2, b + 2 + W, b + 2 + H))
