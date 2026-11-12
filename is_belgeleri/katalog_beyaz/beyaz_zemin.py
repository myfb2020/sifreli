"""Katalog fotoğraflarındaki koyu deri zemini beyaza çevirir (yalnız geliştirmede çalıştırılır, Pillow yeter).

Zemin = fotoğrafın köşelerine bağlı, koyu ve kabarcıklı (deri dokulu) bölge. Halı = geri kalan en büyük parça;
kenarı yumuşatılır, beyaz zemine hafif gölgeyle konur. Emin olunamayan fotoğraf (halı çok küçük / çok büyük çıktıysa)
olduğu gibi bırakılır ve listelenir.
Kullanım: python beyaz_zemin.py KAYNAK_KLASOR HEDEF_KLASOR
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

BEYAZ = (252, 251, 249)


def hali_maskesi(foto):
    w, h = foto.size
    gri = foto.convert("L")
    yum = gri.filter(ImageFilter.GaussianBlur(2))
    # deri zemin: koyu + ince kabarcık dokusu (yerel sapma yüksek); düz siyah peluş / kürk bundan ayrılır
    sapma = ImageChops.difference(gri, gri.filter(ImageFilter.GaussianBlur(2.5))).filter(ImageFilter.GaussianBlur(3))
    koyu = yum.point(lambda q: 255 if q < 78 else 0)
    zemin = koyu
    zemin = zemin.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    # köşelerden taşır: yalnız kenara bağlı koyu bölge zemindir
    tuval = Image.new("L", (w + 2, h + 2), 255)
    tuval.paste(zemin, (1, 1))
    ImageDraw.floodfill(tuval, (0, 0), 128)
    bagli = tuval.crop((1, 1, w + 1, h + 1)).point(lambda q: 255 if q == 128 else 0)
    hali = ImageChops.invert(bagli)
    hali = hali.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))  # ince çıkıntıları at
    return hali, sapma


OVAL = {"BNA-010", "BNA-012", "BNA-015", "BNA-016", "IPS-469", "IPS-482", "IPS-483", "PCH-001", "PCH-009", "PCH-010",
        "PCH-012"}
YUVARLAK = {"IPS-484", "IPS-485", "SPC-734", "SPC-735", "SPC-736", "SPC-737", "TOS-064", "TOS-065", "TOS-066", "TOS-067",
            "TOS-068", "TOS-069"}


# koyu kenarı zemine karışıp yanlış kutu bulunanlar (gözle bakıldı): ortak çerçeveyle kesilir
SABLONLA = {"DPT-536", "DPT-538", "IPS-480", "TOS-039", "TOS-040", "PCH-002"}


def saglam_kutu(maske, esik):
    """Halının kutusu: dolu piksel oranı eşiği geçen ilk/son sütun ve satır (dışarıdaki lekeler ve içeri sızan koyu
    bölgeler kutuyu bozmaz)."""
    w, h = maske.size
    sutun = list(maske.resize((w, 1), Image.BOX).getdata())
    satir = list(maske.resize((1, h), Image.BOX).getdata())
    xs = [i for i, q in enumerate(sutun) if q > 255 * esik]
    ys = [i for i, q in enumerate(satir) if q > 255 * esik]
    if not xs or not ys:
        return None
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def cevir(foto, kod, sablon=None):
    """(yeni resim, durum) – durum: 'kesildi' | 'sablon' | 'birakildi'. Halı düzgün bir şekille kesilir:
    dikdörtgen (yuvarlak köşeli), oval ya da yuvarlak; şeklin yeri fotoğraftan bulunur."""
    w, h = foto.size
    duz = kod not in OVAL and kod not in YUVARLAK
    kutu = saglam_kutu(hali_maskesi(foto)[0], 0.3 if duz else 0.06)
    oran = (kutu[2] - kutu[0]) * (kutu[3] - kutu[1]) / (w * h) if kutu else 0
    durum = "kesildi"
    if not kutu or oran < 0.42 or oran > 0.95 or kod in SABLONLA:
        if sablon is None or not duz:
            return foto, "birakildi"
        kutu = [round(a * b) for a, b in zip(sablon, (w, h, w, h))]  # koyu halı zemine karışmış: ortak çerçeve
        durum = "sablon"
    x0, y0, x1, y1 = kutu[0] + 1, kutu[1] + 1, kutu[2] - 2, kutu[3] - 2
    maske = Image.new("L", (w * 2, h * 2), 0)
    c = ImageDraw.Draw(maske)
    kutu2 = (x0 * 2, y0 * 2, x1 * 2, y1 * 2)
    if kod in YUVARLAK:
        c.ellipse(kutu2, fill=255)
    else:
        c.rounded_rectangle(kutu2, radius=round(w * 0.045) if duz else min(x1 - x0, y1 - y0), fill=255)
    maske = maske.resize((w, h), Image.LANCZOS)
    sonuc = Image.new("RGB", (w, h), BEYAZ)
    golge = Image.new("L", (w, h), 0)
    golge.paste(maske, (3, 5))
    golge = golge.filter(ImageFilter.GaussianBlur(9)).point(lambda q: int(q * 0.38))
    sonuc = Image.composite(Image.new("RGB", (w, h), (40, 34, 28)), sonuc, golge)
    sonuc.paste(foto, (0, 0), maske)
    return sonuc, durum


def main(kaynak, hedef):
    kaynak, hedef = Path(kaynak), Path(hedef)
    hedef.mkdir(parents=True, exist_ok=True)
    dosyalar = sorted(kaynak.glob("*.jpg"))
    kutular = []  # emin olunan dikdörtgen halıların ortak çerçevesi (oran olarak, ortanca)
    for d in dosyalar:
        if d.stem in OVAL or d.stem in YUVARLAK:
            continue
        f = Image.open(d).convert("RGB")
        k = saglam_kutu(hali_maskesi(f)[0], 0.6)
        if k and 0.55 < (k[2] - k[0]) * (k[3] - k[1]) / (f.width * f.height) < 0.9:
            kutular.append([k[0] / f.width, k[1] / f.height, k[2] / f.width, k[3] / f.height])
    sablon = [sorted(k[i] for k in kutular)[len(kutular) // 2] for i in range(4)] if kutular else None
    sayim = {}
    for d in dosyalar:
        yeni, durum = cevir(Image.open(d).convert("RGB"), d.stem, sablon)
        sayim.setdefault(durum, []).append(d.stem)
        yeni.save(hedef / d.name, quality=90)
    for durum, liste in sayim.items():
        print(durum, len(liste), " ".join(liste) if durum != "kesildi" else "")
    print("şablon", [round(a, 3) for a in sablon] if sablon else None)


if __name__ == "__main__":
    main(*sys.argv[1:3])
