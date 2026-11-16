"""Katalog modelinde fotoğraf esas (2026-11-16, kullanıcı: "seçilen model üzerinden yalnız seçilen bordürün rengi ve
modeli değişsin").

Bayi katalogdaki bir modelden başlayıp renk / desen / ölçü değiştirince halı baştan çizilmez: bayinin dokunmadığı
parçalar (zemin, madalyon, öteki bordürler, biye) katalog fotoğrafından gelir, yalnız değişen parça çizilir.
Fotoğraf çizimin ölçüsüne oturtulur: bordürler gerçek cm genişliğini korur (kenarlar boyuna uzar), orta esner,
madalyon yuvarlak kalır. Ara bant / düz bordür genişliği değişince fotoğraftaki bant esnetilir; yeni eklenen bordür
çizilir, çıkarılan bordür fotoğraftan silinir. Yalnız dikdörtgen ↔ oval değişince bütün halı çizilir (None döner).

Fotoğraftaki halı kutusu: tasarim_varlik/foto_kutu.json (is_belgeleri/katalog_beyaz/kutu_cikar.py). Fotoğraflar
eğik / perspektifli çekildiğinden her bordür sınırı her kenarda ayrı ölçülür ve kenar boyunca eğik bir doğru olarak
tutulur (foto_halka.json; is_belgeleri/foto_halka/): fotoğraf bir ağ ile esnetilerek bu sınırlar çizimdeki düz
yerlerine oturtulur.
"""
import json
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

from . import parcali as pc

_KLASOR = Path(__file__).parent
FOTO_KLASORU = _KLASOR / "katalog_tohum" / "model"
DUZ_KLASORU = _KLASOR / "tasarim_varlik" / "foto_duz"  # kullanıcının çektiği fotoğraflar, düzleştirilmiş (halı tam kare)
KUTU = json.loads((_KLASOR / "tasarim_varlik" / "foto_kutu.json").read_text())
# fotoğrafta her kenarda bordür sınırları (cm, kenardan içeri; fotoğraf katalog ölçüsüne oturtulmuş olarak): sayı
# (kenar boyunca aynı) ya da [baş, son]; sol / sağ kenarda baş = üst uç, üst / alt kenarda baş = sol uç
HALKA = json.loads((_KLASOR / "tasarim_varlik" / "foto_halka.json").read_text())
KOSE_ORANI = 0.0225  # beyaz_zemin.py: köşe yarıçapı fotoğraf genişliği × 0.045, iki kat büyük maskede → yarısı
ORTUSME_CM = 1.0  # değişen parça komşusunun üstüne bu kadar taşar: fotoğraftaki eski parçanın kenarı görünmesin
KALINTI_CM = 3.5  # bunun içinde fotoğrafta eski parçanın rengine benzeyen kalıntı aranır (eğri / kayık kenar)
KALINTI_ESIK = 22  # piksel eski parça rengine komşusundan bu kadar yakınsa kalıntı sayılır


def uygun_mu(kod):
    """Bu model fotoğraf esaslı gösterilebilir mi (fotoğrafı var, bordür sınırları fotoğrafta ölçüldü)."""
    if kod not in HALKA or kod not in pc.FOTO_RENK:
        return False
    return (DUZ_KLASORU / f"{kod}.jpg").exists() or (kod in KUTU and (FOTO_KLASORU / f"{kod}.jpg").exists())


def referans(kod, en=None, boy=None):
    """Modelin katalogdaki (fotoğraftaki) değerleri; en / boy verilirse o ölçüde."""
    from .parcali_views import _desen_kodlari

    d = pc.hazir_degerler(kod)
    if en:
        d = {**d, "en": en, "boy": boy}
    return pc.temizle(d, _desen_kodlari())


def _ogeler(v):
    """Kenardan içeri bordür / ara bantlar: [(kimlik, genişlik cm)] (kimlik 1, 2… ya da 'a1'…)."""
    return [(h["no"], h["gen"]) for h in pc.halkalar(v)]


def _grup_adi(no):
    return ("a", int(no[1:])) if isinstance(no, str) else ("h", no)


def _madalyonlu(v):
    return v.get("orta") == "duz" and v.get("madalyon") != "yok"


def degisenler(v, b):
    """Bayinin değiştirdiği (çizimden gelecek) parça grupları: ('h', i) bordür, ('a', i) ara bant, 'zemin',
    'madalyon', 'mcerceve', 'serit', 'panel', 'kenar'. Genişliği değişen düz bordür / ara bant fotoğraftan
    esnetilir; desenli / nakışlı bordürün genişliği değişince deseni bozulmasın diye çizilir."""
    d = set()
    fark = lambda *a: any(v.get(x) != b.get(x) for x in a)  # noqa: E731
    eski = dict(_ogeler(b))
    for no, gen in _ogeler(v):
        if no not in eski:  # yeni eklenen bordür / ara bant
            d.add(_grup_adi(no))
            continue
        if isinstance(no, str):
            continue
        on = f"h{no}_"
        tur = v.get(on + "tur")
        if fark(on + "tur", on + "malzeme") or (tur == "desenli" and fark(on + "desen", "desen_alti")) or (
                tur == "nakisli" and fark(on + "nakis", "iplik")) or (tur == "nakisli" and gen != eski[no]):
            d.add(("h", no))
    if fark("zemin"):
        d |= {"zemin"} | {("a", i) for i in range(1, pc.EN_COK_HALKA)}
    if fark("orta"):
        d |= {"zemin", "serit", "panel", "madalyon", "mcerceve"}
    serit_alan = ("serit_tur", "serit_malzeme", "serit_desen", "serit_yon", "serit_adet", "serit", "aralik")
    if v.get("orta") == "serit" and fark(*serit_alan, *(("nakis", "iplik") if v.get("serit_tur") == "nakisli" else ())):
        d |= {"serit", "zemin"}
    if v.get("orta") == "panel" and fark("panel_malzeme", "nakis", "iplik", "motif_adet", "panel_en", "panel_boy"):
        d |= {"panel", "zemin"}
    if _madalyonlu(v):
        if not _madalyonlu(b) or bool(v.get("madalyon_cerceve")) != bool(b.get("madalyon_cerceve")) or fark(
                "madalyon", "madalyon_malzeme") or (v.get("madalyon") == "nakisli" and fark("madalyon_motif", "iplik")):
            d |= {"madalyon", "mcerceve"}
        elif fark("madalyon_cerceve"):
            d.add("mcerceve")
    if fark("kenar", "kenar_renk"):
        d.add("kenar")
    ilk = _ogeler(v)[:1]
    if ilk and _grup_adi(ilk[0][0]) in d:
        d.add("kenar")  # dış bordür değişince fotoğraftaki eski bordür biye şeridinden görünmesin: biye de çizilir
    return d


def renklenecekler(v, b):
    """Yalnız malzemesi (rengi) değişen desenli bordürler: deseni fotoğraftan kalır, malzemesi yeniden renklenir
    (2026-11-16, bayi denemesi: rengi değişen desenli bordür bizim desenimizle çiziliyor, şablon gibi görünüyordu)."""
    eski = dict(_ogeler(b))
    sonuc = {}
    for no, _ in _ogeler(v):
        if isinstance(no, str) or no not in eski:
            continue
        on = f"h{no}_"
        if (v.get(on + "tur") == b.get(on + "tur") == "desenli" and v.get(on + "desen") == b.get(on + "desen")
                and v.get("desen_alti") == b.get("desen_alti") and v.get(on + "malzeme") != b.get(on + "malzeme")):
            sonuc[("h", no)] = (b[on + "malzeme"], v[on + "malzeme"])
    return sonuc


def _yerel_ortalama(resim_L, maske, r):
    """Maskeli bölgede yerel (r piksel yarıçaplı) ortalama: maske dışı pikseller hesaba girmez."""
    from PIL import ImageMath

    pay = Image.composite(resim_L, Image.new("L", resim_L.size, 0), maske).filter(ImageFilter.GaussianBlur(r))
    payda = maske.filter(ImageFilter.GaussianBlur(r))
    return ImageMath.lambda_eval(lambda a: a["convert"](a["p"] * 255 / (a["q"] + 0.5), "L"),
                                 p=pay.convert("F"), q=payda.convert("F"))


def _yeniden_renkle(foto, bolge, eski_mal, yeni_mal, px):
    """Fotoğraftaki desenli bordürde malzeme (desen delikleri dışı) yeni malzemenin dokusuyla değiştirilir; delikler
    ve kabartma fotoğraftan kalır. Malzeme / delik ayrımı YEREL eşikle (fotoğraftaki ışık farkı bordürün bir yanını
    öbür yanından ayırmasın); hangi küme malzeme, eski malzemenin gerçek doku rengine yakınlıkla. Yeni rengin
    parlaklığı da yerel ortalamaya göre düzlenir: bordür baştan sona aynı tonda olur."""
    from . import hali_gorsel as hg
    from . import parcali_gorsel as pg

    if not bolge.getbbox():
        return foto
    W, H = foto.size
    L = foto.convert("L")
    yerel = _yerel_ortalama(L, bolge, max(3, px * 4))
    acik = ImageChops.multiply(ImageChops.subtract(L, yerel).point(lambda q: 255 if q > 0 else 0), bolge)
    koyu = ImageChops.subtract(bolge, acik)
    acik = acik.filter(ImageFilter.MedianFilter(3))
    koyu = ImageChops.subtract(bolge, acik)

    def doku(ad, boyut=(64, 64)):
        if ad in ("altin", "gumus"):
            return hg.malzeme(ad, boyut, 3)
        return pg.malzeme_dokusu(ad, boyut, 3)

    hedef = ImageStat.Stat(doku(eski_mal)).mean

    def uzak(m):
        if not m.getbbox():
            return 10 ** 9
        return sum((a - b) ** 2 for a, b in zip(ImageStat.Stat(foto, m).mean, hedef))

    malzeme = acik if uzak(acik) <= uzak(koyu) else koyu
    top = max(1, sum(bolge.histogram()[128:]))
    if sum(malzeme.histogram()[128:]) < 0.2 * top:  # küme çok küçük: ayrım güvenilmez, bütün bölge malzeme
        malzeme = bolge
    yeni = doku(yeni_mal, foto.size) if yeni_mal not in ("altin", "gumus") else hg.malzeme(yeni_mal, foto.size, px)
    # kabartma / gölge: pikselin malzemenin yerel ortalamasına oranı (geniş ışık farkı silinir)
    mort = _yerel_ortalama(L, malzeme, max(3, px * 6))
    from PIL import ImageMath
    isik = ImageMath.lambda_eval(
        lambda a: a["convert"](a["min"](a["max"](a["l"] * 128 / (a["m"] + 1), 80), 185), "L"),
        l=L.convert("F"), m=mort.convert("F"))
    yeni = ImageChops.multiply(yeni, Image.merge("RGB", (isik,) * 3)).point(lambda q: min(255, q * 2))
    malzeme = malzeme.filter(ImageFilter.GaussianBlur(max(0.4, px * 0.06)))
    return Image.composite(yeni, foto, malzeme)


def _grup(p):
    if p.get("halka") is not None:
        return _grup_adi(p["halka"])
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
    duz = DUZ_KLASORU / f"{kod}.jpg"
    if duz.exists():  # düzleştirilmiş fotoğraf: bütün resim halı, köşeler keskin
        resim = Image.open(duz).convert("RGB")
        return resim, round(resim.width / 160)
    resim = Image.open(FOTO_KLASORU / f"{kod}.jpg").convert("RGB")
    x0, y0, x1, y1, _ = KUTU[kod]
    return resim.crop((x0, y0, x1, y1)), round(resim.width * KOSE_ORANI)


def _cizgi(d):
    """Ölçü: sayı (kenar boyunca aynı) ya da [baş, son] (kenarın iki ucunda; arası doğru)."""
    return (float(d), float(d)) if isinstance(d, (int, float)) else (float(d[0]), float(d[1]))


def _deger(c, t):
    return c[0] + (c[1] - c[0]) * t


def _kenar_olculeri(kod, ref):
    """Fotoğrafta her kenarda bordür sınırları ((baş, son) cm); ölçülmemişse modelin kendi sınırları."""
    model = [h["d"] + h["gen"] for h in pc.halkalar(ref)]
    olcu = HALKA.get(kod, {})
    sonuc = {}
    for k in ("sol", "sag", "ust", "alt"):
        cizgiler, onceki = [], (0.0, 0.0)
        for d in (olcu[k] if len(olcu.get(k, [])) == len(model) else model):
            c = _cizgi(d)
            onceki = (max(c[0], onceki[0] + 0.5), max(c[1], onceki[1] + 0.5))  # sınırlar iç içe geçmesin
            cizgiler.append(onceki)
        sonuc[k] = cizgiler
    return sonuc


def _eslestir(ref_oge, hedef_oge, sinirlar):
    """Bir kenarda [(fotoğraf çizgisi, çizimde cm)] düğümleri, dış kenardan zeminin başına. Fotoğrafta olmayan
    (yeni) bordür / ara bant fotoğrafta sıfır genişlik alır (çizimden gelir); çizimde olmayan (çıkarılan) bordürün
    fotoğraftaki yeri sıfıra iner."""
    yer, onceki = {}, (0.0, 0.0)
    for (no, _), son in zip(ref_oge, sinirlar):
        yer[no] = (onceki, son)
        onceki = son
    foto_zemin = onceki
    dugum, simdi, t = [((0.0, 0.0), 0.0)], (0.0, 0.0), 0.0
    for no, gen in hedef_oge:
        if no in yer:
            bas, son = yer[no]
            if bas != simdi:
                dugum.append((bas, t))
            t += gen
            dugum.append((son, t))
            simdi = son
        else:
            t += gen
            dugum.append((simdi, t))
    if simdi != foto_zemin:
        dugum.append((foto_zemin, t))
    return dugum


def _eksen(bas, son, kaynak_uz, k_kaynak, hedef_uz, px):
    """Bir eksenin düğümleri: [(t → kaynak px, hedef px)]; t öteki eksendeki konum (0–1)."""
    dugum = [(lambda t, c=c: _deger(c, t) * k_kaynak, round(cm * px)) for c, cm in bas]
    a, b = round(bas[-1][1] * px), hedef_uz - round(son[-1][1] * px)
    ca, cb = bas[-1][0], son[-1][0]
    n = max(2, round((b - a) / px / 20))  # orta her 20 cm'de bölünür (eğik kenarlar izlensin)
    for i in range(1, n):
        f = i / n
        dugum.append((lambda t, f=f: (1 - f) * _deger(ca, t) * k_kaynak + f * (kaynak_uz - _deger(cb, t) * k_kaynak),
                      round(a + (b - a) * f)))
    dugum += [(lambda t, c=c: kaynak_uz - _deger(c, t) * k_kaynak, hedef_uz - round(cm * px))
              for c, cm in reversed(son)]
    return dugum


def _esnet(foto, xk, yk, hedef):
    """Fotoğrafı ağ ile esnetir: çizimdeki her düğüm fotoğraftaki karşılığından gelir; fotoğrafta eğik duran
    bordür sınırları çizimde düz oturur."""
    W, H = hedef
    kaynak = [[(xk[i][0](yk[j][1] / H), yk[j][0](xk[i][1] / W)) for j in range(len(yk))] for i in range(len(xk))]
    veri = []
    for i in range(len(xk) - 1):
        for j in range(len(yk) - 1):
            kutu = (xk[i][1], yk[j][1], xk[i + 1][1], yk[j + 1][1])
            if kutu[2] <= kutu[0] or kutu[3] <= kutu[1]:
                continue
            (x0, y0), (x1, y1) = kaynak[i][j], kaynak[i][j + 1]
            (x2, y2), (x3, y3) = kaynak[i + 1][j + 1], kaynak[i + 1][j]
            veri.append((kutu, (x0, y0, x1, y1, x2, y2, x3, y3)))
    return foto.transform(hedef, Image.Transform.MESH, veri, Image.BICUBIC)


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
    ro, ho = _ogeler(ref), _ogeler(v)
    d = {k: _eslestir(ro, ho, kenar[k]) for k in kenar}
    xk = _eksen(d["sol"], d["sag"], foto.width, fx, W, px)
    yk = _eksen(d["ust"], d["alt"], foto.height, fy, H, px)
    if _madalyonlu(ref):
        # madalyon esnetilmeden önce fotoğraftan alınır (yeri yakındaki zeminle kapatılır), sonra esnemiş halının
        # ortasına yuvarlak konur; çapı değiştiyse büyütülür / küçültülür, kaldırıldıysa konmaz
        zs, zu = _deger(d["sol"][-1][0], .5) * fx, _deger(d["ust"][-1][0], .5) * fy
        zg, za = foto.width - _deger(d["sag"][-1][0], .5) * fx, foto.height - _deger(d["alt"][-1][0], .5) * fy
        r = ref["madalyon_cap"] / 2 + (pc.MADALYON_CERCEVE if ref.get("madalyon_cerceve") else 0) + 1.5
        cx, cy = (zs + zg) / 2, (zu + za) / 2
        olcum = HALKA.get(kod, {}).get("madalyon")
        if olcum:  # fotoğrafta ölçülmüş madalyon merkezi (zemin ortasında değilse içeriği kayık görünüyordu)
            mx, my, mr = olcum
            if v["en"] > v["boy"]:  # yatay: fotoğraf çevrildi
                mx, my = my, mx
            cx, cy = mx * fx, my * fy
            r = max(r, mr + 1.5)
        kutu = (round(cx - r * fx), round(cy - r * fy), round(cx + r * fx), round(cy + r * fy))
        madalyon = foto.crop(kutu)
        foto = _madalyonu_sil(foto, kutu, (zs, zu, zg, za))
    yerlesik = _esnet(foto, xk, yk, (W, H))
    if _madalyonlu(ref) and _madalyonlu(v):
        cap = max(2, round(2 * r * px * v["madalyon_cap"] / ref["madalyon_cap"]))
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
    if v.get("sekil") != b.get("sekil"):  # dikdörtgen ↔ oval: fotoğraf uymaz, bütün halı çizilir
        return None
    if v.get("sekil") == "oval" and [no for no, _ in _ogeler(v)] != [no for no, _ in _ogeler(b)]:
        return None  # ovalde bordür / ara bant eklenip çıkarılınca fotoğraf eğri kenarlarda bozuluyor: çizilir
    degisen = degisenler(v, b)
    renkle = renklenecekler(v, b)
    degisen = degisen - set(renkle)
    ilk = _ogeler(v)[:1]
    if ilk and _grup_adi(ilk[0][0]) not in degisen and v.get("kenar") == b.get("kenar") and \
            v.get("kenar_renk") == b.get("kenar_renk"):
        degisen.discard("kenar")  # dış bordür yalnız yeniden renklendiyse biye fotoğraftan kalır
    px = uzun_kenar / max(v["en"], v["boy"])
    W, H = int(round(v["en"] * px)), int(round(v["boy"] * px))
    foto, kose_cm = fotograf_yerlesimi(kod, v, px)
    if renkle:
        olc0 = lambda poli: [(x * px, y * px) for x, y in poli]  # noqa: E731
        for grup, (eski_mal, yeni_mal) in renkle.items():
            bolge = Image.new("L", (W, H), 0)
            for p in pc.parcalar(v):
                if _grup(p) == grup:
                    ImageDraw.Draw(bolge).polygon(olc0(p["poli"]), fill=255)
            foto = _yeniden_renkle(foto, bolge, eski_mal, yeni_mal, px)
    oval = v.get("sekil") == "oval"
    tuval = pg.ciz(v, uzun_kenar, kose_cm=3 if oval else kose_cm)
    pay = (tuval.width - W) // 2

    # fotoğraftan gelecek yerler: değişmeyen parçalar; değişen parça komşusunun üstüne ORTUSME_CM taşar
    maske, cizilen = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    olc = lambda poli: [(x * px, y * px) for x, y in poli]  # noqa: E731
    # bitişik bordürlerin arasına yeni eklenen ara bant zemin malzemesindendir: zemin değişmediyse fotoğraftaki
    # zeminin dokusundan doldurulur (çizim dokusu fotoğraftaki zeminden farklı görünür)
    eski = {no for no, _ in _ogeler(b)}
    yeni_ara = set() if "zemin" in degisen else {
        _grup_adi(no) for no, _ in _ogeler(v) if isinstance(no, str) and no not in eski}
    ara, zemin = Image.new("L", (W, H), 0), Image.new("L", (W, H), 0)
    for p in pc.parcalar(v):
        g = _grup(p)
        hedef = ara if g in yeni_ara else cizilen if g in degisen else maske
        ImageDraw.Draw(hedef).polygon(olc(p["poli"]), fill=255)
        if g == "zemin" and g not in degisen:
            ImageDraw.Draw(zemin).polygon(olc(p["poli"]), fill=255)
    degisen = degisen - yeni_ara
    dis = Image.new("L", (W, H), 0)
    if oval:
        ImageDraw.Draw(dis).polygon(olc(pc.dis_hat(v)), fill=255)
    else:
        ImageDraw.Draw(dis).rounded_rectangle((0, 0, W - 1, H - 1), radius=max(3, int(px * kose_cm)), fill=255)
    if cizilen.getbbox():
        cizilen = cizilen.filter(ImageFilter.MaxFilter(2 * max(1, round(px * ORTUSME_CM)) + 1))
        maske = ImageChops.subtract(maske, cizilen)
        # eski bordürden kalan kayık kenar: fotoğrafta komşu parçanın renginden doldurulur
        for kalinti, bolge in _kalintilar(v, degisen, foto, px, (W, H)):
            foto = _doldur(foto, ImageChops.multiply(maske, bolge), ImageChops.multiply(kalinti, maske), px)
    bozuk = _bos_seritler(kod, b, v, px, (W, H))
    if bozuk[0].getbbox() or bozuk[1].getbbox():
        # yeni eklenen bordür / ara bant fotoğrafta yok: o sütun ve satırlarda dıştaki bordürler tek piksel sütunundan
        # uzar (çizgi çizgi); aynı bordürün boyunca kaydırılmış gerçek dokusuyla doldurulur
        for yon, serit in enumerate(bozuk):
            delik = ImageChops.multiply(ImageChops.subtract(serit, ara), maske)
            if delik.getbbox():
                foto = _boyunca_doldur(foto, ImageChops.subtract(maske, ImageChops.lighter(*bozuk)), delik, px, yon)
    if ara.getbbox():
        # yeni ara bant zemin malzemesindendir: fotoğraftaki zeminin temiz bir parçası (madalyon ve bordürlerden
        # uzak) aynalanarak döşenir; kaydırarak doldurma madalyon / bordür parçalarını da kopyalıyordu
        doku = _zemin_dokusu(foto, zemin, px, (W, H))
        if doku is not None:
            foto = Image.composite(doku, foto, ara)
        maske = ImageChops.lighter(maske, ara)
    # biye / lanfel şeridi: kenar değişmediyse fotoğraftan, değiştiyse çizimden
    serit = ImageChops.subtract(dis, _ic_hat(dis, max(3, int(px * 2.2)), W, H))
    if "kenar" in degisen:
        maske = ImageChops.subtract(maske, serit)
    else:
        maske = ImageChops.lighter(maske, serit)
    maske = ImageChops.multiply(maske, dis).filter(ImageFilter.GaussianBlur(max(0.6, px * 0.25)))
    maske = ImageChops.multiply(maske, dis)  # yumuşatma halının dışına taşmasın
    tuval.paste(foto, (pay, pay), maske)
    return tuval


def _zemin_dokusu(foto, zemin, px, boyut):
    """Zeminin üst bölümünden (madalyonun üstü) temiz bir parça, aynalı döşenerek bütün tuvali kaplar."""
    ic = zemin.filter(ImageFilter.MinFilter(2 * max(1, round(px * 3)) + 1))
    kutu = ic.getbbox()
    if not kutu:
        return None
    x0, y0, x1, y1 = kutu
    w, h = x1 - x0, y1 - y0
    p = (round(x0 + 0.15 * w), round(y0 + 0.06 * h), round(x1 - 0.15 * w), round(y0 + 0.26 * h))
    if p[2] - p[0] < 8 or p[3] - p[1] < 8:
        return None
    parca = foto.crop(p)
    if ImageStat.Stat(ic.crop(p)).mean[0] < 200:  # parça zeminin dışına taşıyor (dar / oval zemin)
        p = (round(x0 + 0.3 * w), round(y0 + 0.3 * h), round(x1 - 0.3 * w), round(y0 + 0.4 * h))
        parca = foto.crop(p)
    pw, ph = parca.size
    ikili = Image.new("RGB", (pw * 2, ph * 2))
    ikili.paste(parca, (0, 0))
    ikili.paste(ImageOps.mirror(parca), (pw, 0))
    ikili.paste(ImageOps.flip(parca), (0, ph))
    ikili.paste(ImageOps.flip(ImageOps.mirror(parca)), (pw, ph))
    tuval = Image.new("RGB", boyut)
    for y in range(0, boyut[1], ikili.height):
        for x in range(0, boyut[0], ikili.width):
            tuval.paste(ikili, (x, y))
    return tuval


def _bos_seritler(kod, b, v, px, boyut):
    """Fotoğrafta karşılığı olmayan (yeni eklenen öğenin) sütunları ve satırları: (sütun maskesi, satır maskesi)."""
    W, H = boyut
    sutun, satir = Image.new("L", boyut, 0), Image.new("L", boyut, 0)
    ref = referans(kod)
    dugum = _eslestir(_ogeler(ref), _ogeler(v), _kenar_olculeri(kod, ref)["sol"])
    for (k0, t0), (k1, t1) in zip(dugum, dugum[1:]):
        if k0 == k1 and t1 > t0:
            a, z = round(t0 * px), round(t1 * px)
            c = ImageDraw.Draw(sutun)
            c.rectangle((a, 0, z, H), fill=255)
            c.rectangle((W - z, 0, W - a, H), fill=255)
            c = ImageDraw.Draw(satir)
            c.rectangle((0, a, W, z), fill=255)
            c.rectangle((0, H - z, W, H - a), fill=255)
    return sutun, satir


def _boyunca_doldur(foto, gecerli, delik, px, yon):
    """Delik, yon 0'da yatay (sütun deliği), 1'de dikey kaydırılmış geçerli pikselle doldurulur."""
    W, H = foto.size
    sonuc = foto
    # doku halının ortasına doğru alınır: dışa doğru kaydırmak köşedeki öteki kenarın bandını (gönye / uç uca
    # birleşen bordür) kopyalıyordu
    yari = Image.new("L", (W, H), 0)
    yari.paste(255, (0, 0, W // 2, H) if yon == 0 else (0, 0, W, H // 2))
    for isaret, bolge in ((1, yari), (-1, ImageOps.invert(yari))):
        kalan = ImageChops.multiply(delik, bolge)
        for cm in (8, 15, 25, 40, 60):
            if not kalan.getbbox():
                break
            s = isaret * round(px * cm)
            dx, dy = (s, 0) if yon == 0 else (0, s)
            kaynak, uygun = _kaydir(foto, -dx, -dy), _kaydir(gecerli, -dx, -dy)
            tamam = ImageChops.multiply(kalan, uygun.point(lambda q: 255 if q > 200 else 0))
            sonuc = Image.composite(kaynak, sonuc, tamam)
            kalan = ImageChops.subtract(kalan, tamam)
    return sonuc


def _ic_sekil(v, d, px, boyut):
    """Halının d cm içeriden geçen eşinin içi (maske)."""
    m = Image.new("L", boyut, 0)
    if d < 0:
        d = 0
    W, H = boyut
    if v.get("sekil") == "oval":
        poli = pc.stadyum_ofset(v["en"], v["boy"], d) if 2 * d < min(v["en"], v["boy"]) else []
        if len(poli) >= 3:
            ImageDraw.Draw(m).polygon([(x * px, y * px) for x, y in poli], fill=255)
    elif 2 * d * px < min(W, H):
        ImageDraw.Draw(m).rectangle((d * px, d * px, W - 1 - d * px, H - 1 - d * px), fill=255)
    return m


def _kalintilar(v, degisen, foto, px, boyut):
    """Fotoğraftaki eski bordürün kayık / eğri kenarından kalanlar: değişen bordürün iki yanında, komşu parçanın
    (zemin, öteki bordür) renk dağılımına uymayan pikseller (eski bordürün rengi, desen delikleri).
    Sonuç: [(kalıntı maskesi, komşu parçanın bölgesi)]; kalıntı yalnız kendi parçasının dokusuyla doldurulur (dar bir
    bantta öteki parçanın — ör. siyah desenli bordürün — dokusu kopyalanmasın)."""
    sonuc = []
    parcalar = [(h["d"], h["d"] + h["gen"], _grup_adi(h["no"])) for h in pc.halkalar(v)]
    D = parcalar[-1][1] if parcalar else 0.0
    parcalar.append((D, 10 ** 4, "zemin"))
    sekil = lambda d: _ic_sekil(v, d, px, boyut)  # noqa: E731
    fark = lambda a, b: ImageChops.subtract(a, b)  # noqa: E731
    for j, (d, e, grup) in enumerate(parcalar):
        if grup not in degisen:
            continue
        yanlar = []
        if j > 0:  # içe doğru: dıştaki komşu [ks, d]
            ks = parcalar[j - 1][0]
            yanlar.append((ks, d, (max(d - KALINTI_CM, ks), d - ORTUSME_CM), True))
        if j + 1 < len(parcalar):  # dışa doğru: içteki komşu [e, ke]
            ke = parcalar[j + 1][1]
            yanlar.append((e, ke, (e + ORTUSME_CM, min(e + KALINTI_CM, ke)), False))
        for ks, ke, bant, ic in yanlar:
            if bant[1] - bant[0] < 0.2:
                continue
            # komşunun renk örneği: kalıntı bandının ötesi, yalnız komşu parçanın içinden (dar parçada bütün parçası)
            komsu = (max(ks + 0.3, bant[0] - 3), bant[0]) if ic else (bant[1], min(ke - 0.3, bant[1] + 3))
            if komsu[1] - komsu[0] < 0.8:
                komsu = (ks + 0.3, ke - 0.3) if ke < 10 ** 3 else komsu
            yer, km = fark(sekil(bant[0]), sekil(bant[1])), fark(sekil(komsu[0]), sekil(komsu[1]))
            if not yer.getbbox() or not km.getbbox():
                continue
            ist = ImageStat.Stat(foto, km)
            ort = tuple(round(c) for c in ist.mean)
            sapma = sum(ist.stddev) / 3
            uzak = ImageChops.difference(foto, Image.new("RGB", boyut, ort)).convert("L")
            esik = max(KALINTI_ESIK, 2.5 * sapma)
            aykiri = uzak.point(lambda q: 255 if q > esik else 0)
            gen = e - d
            eski = ImageStat.Stat(foto, fark(sekil(d + 0.7), sekil(e - 0.7))).mean if 1.4 < gen < 10 ** 3 else None
            if eski:  # desenli zeminde: rengi eski bordüre zeminden belirgin biçimde yakın pikseller de kalıntı
                yakin = ImageChops.difference(foto, Image.new("RGB", boyut, tuple(round(c) for c in eski))).convert("L")
                aykiri = ImageChops.lighter(aykiri, ImageChops.subtract(uzak, yakin).point(
                    lambda q: 255 if q > KALINTI_ESIK else 0))
            aykiri = ImageChops.multiply(aykiri, yer).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(5))
            aykiri = ImageChops.multiply(aykiri, yer)
            if aykiri.getbbox():
                bolge = fark(sekil(ks), sekil(ke)) if ke < 10 ** 3 else sekil(ks)
                sonuc.append((aykiri, bolge))
    return sonuc


def _kaydir(resim, dx, dy):
    """Resmi (dx, dy) kaydırır; dışarıda kalan yer boş (siyah) olur."""
    t = Image.new(resim.mode, resim.size, 0)
    t.paste(resim, (dx, dy))
    return t


def _doldur(foto, gecerli, delik, px, mesafeler=None):
    """Delik pikselleri fotoğrafın geçerli yerinden doldurulur: önce gerçek doku (halının kenarına dik, mesafeler cm
    kadar kaydırılarak; artı = içeri, eksi = dışarı; dokusu ve rengi korunur), olmazsa çevrenin yumuşak ortalaması."""
    if not delik.getbbox():
        return foto
    from PIL import ImageMath

    W, H = foto.size
    gecerli = ImageChops.subtract(gecerli, delik)
    # her piksel en yakın kenara göre: sol, sağ, üst, alt üçgen bölgeler
    bolgeler = {}
    for ad, poli in (("sol", [(0, 0), (W / 2, H / 2), (0, H)]), ("sag", [(W, 0), (W / 2, H / 2), (W, H)]),
                     ("ust", [(0, 0), (W / 2, H / 2), (W, 0)]), ("alt", [(0, H), (W / 2, H / 2), (W, H)])):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon([(round(x), round(y)) for x, y in poli], fill=255)
        bolgeler[ad] = m
    yon = {"sol": (1, 0), "sag": (-1, 0), "ust": (0, 1), "alt": (0, -1)}
    sonuc = foto
    if mesafeler is None:  # kalıntı: önce içeri, sonra dışarı; iki uzaklıkta
        mesafeler = [(KALINTI_CM + 1.5) * k for k in (1, -1, 2, -2)] + [2.5, -2.5, 1.5, -1.5]  # dar parça: yakından
    for kat in mesafeler:
        s = round(px * abs(kat))
        for ad, (ux, uy) in yon.items():
            bolge = ImageChops.multiply(delik, bolgeler[ad])
            if not bolge.getbbox():
                continue
            dx, dy = ux * s * (1 if kat > 0 else -1), uy * s * (1 if kat > 0 else -1)
            # piksel (x, y) kaynağını (x + dx, y + dy)'den alır: kaynak resmi (-dx, -dy) kaydırılır
            kaynak, uygun = _kaydir(foto, -dx, -dy), _kaydir(gecerli, -dx, -dy)
            tamam = ImageChops.multiply(bolge, uygun.point(lambda q: 255 if q > 200 else 0))
            sonuc = Image.composite(kaynak, sonuc, tamam)
            delik = ImageChops.subtract(delik, tamam)
        if not delik.getbbox():
            return sonuc
    # köşeler: dik kaydırmayla geçerli yere ulaşmayan noktalar çapraz (merkeze doğru) kaydırılır
    for kat in mesafeler:
        if kat <= 0:
            continue
        s = round(px * kat)
        for (ux, uy), kutu in (((1, 1), (0, 0, W // 2, H // 2)), ((-1, 1), (W // 2, 0, W, H // 2)),
                               ((1, -1), (0, H // 2, W // 2, H)), ((-1, -1), (W // 2, H // 2, W, H))):
            bolge = Image.new("L", (W, H), 0)
            bolge.paste(255, kutu)
            bolge = ImageChops.multiply(delik, bolge)
            if not bolge.getbbox():
                continue
            kaynak, uygun = _kaydir(foto, -ux * s, -uy * s), _kaydir(gecerli, -ux * s, -uy * s)
            tamam = ImageChops.multiply(bolge, uygun.point(lambda q: 255 if q > 200 else 0))
            sonuc = Image.composite(kaynak, sonuc, tamam)
            delik = ImageChops.subtract(delik, tamam)
        if not delik.getbbox():
            return sonuc
    for r in (px * 0.8, px * 2, px * 5):  # kalan: çevrenin yumuşak ortalaması
        mL = gecerli.filter(ImageFilter.GaussianBlur(r))
        m = mL.convert("F")
        kanal = []
        for k in foto.split():
            c = Image.composite(k, Image.new("L", foto.size, 0), gecerli).filter(ImageFilter.GaussianBlur(r)).convert("F")
            kanal.append(ImageMath.lambda_eval(lambda a: a["convert"](a["c"] * 255 / (a["m"] + 0.01), "L"), c=c, m=m))
        tamam = ImageChops.multiply(delik, mL.point(lambda q: 255 if q > 8 else 0))
        sonuc = Image.composite(Image.merge("RGB", kanal), sonuc, tamam)
        delik = ImageChops.subtract(delik, tamam)
        if not delik.getbbox():
            break
    return sonuc


def _ic_hat(dis, b, W, H):
    """Dış hattın b piksel içeriden geçen eşi (resim kenarına dayanan hat da aşınır)."""
    genis = ImageOps.expand(dis, b + 2, 0).filter(ImageFilter.MinFilter(b * 2 + 1))
    return genis.crop((b + 2, b + 2, b + 2 + W, b + 2 + H))
