"""Kullanıcının DXF lazer desenlerini programa çevirir (2026-11-26).
DB003 ← DAMA, DB007 ← LINE, DB013 ← YILDIZ UFAK, DB015 ← VERSACE (fotoğraftan çizilmişlerin yerine gerçek kesim dosyası);
yeni LZ09 ADOBE, LZ10 ÇİÇEK, LZ11 MAJOR, LZ12 PRENSES, LZ13 TALL, LZ14 TAMAMLAR, LZ15 THERE.
Çıktı: tasarim_varlik/desen/KOD.png (L, 255 = delik, 40 px/cm, uzun kenar yatay), desenler.json, desen_onizleme/KOD.jpg.
Kullanım (ezdxf kurulu bir Python ile): python -I desen_ekle.py DXF_KLASORU TASARIM_VARLIK"""
import json, sys
from pathlib import Path
import ezdxf
from ezdxf import path as ezpath
from PIL import Image, ImageChops, ImageDraw

DESENLER = {  # kod: (dosya, ad)
    "DB003": ("DAMA_MODEL.dxf", "Dama"), "DB007": ("LINE_MODEL_120X180.dxf", "Line"),
    "DB013": ("YILDIZ_DESEN_UFAK.dxf", "Yıldız"), "DB015": ("VERSACE_DESEN.dxf", "Grek"),
    "LZ09": ("ADOBE_MODEL.dxf", "Adobe"), "LZ10": ("CICEK_DESEN.dxf", "Çiçek"), "LZ11": ("MAJOR_DESEN_BOY.dxf", "Major"),
    "LZ12": ("PRENSES.dxf", "Prenses"), "LZ13": ("TALL_DESEN.dxf", "Tall"), "LZ14": ("TAMAMLAR_DESEN.dxf", "Tamamlar"),
    "LZ15": ("THERE_DESEN.dxf", "There"),
}
PX_CM = 40
BIRIM = {4: 0.1, 5: 1.0, 6: 100.0}  # DXF $INSUNITS → cm


def konturlar(dosya):
    d = ezdxf.readfile(dosya)
    cm = BIRIM.get(d.header.get("$INSUNITS"), 0.1)
    sonuc = []
    for e in d.modelspace():
        if e.dxftype() in ("IMAGE", "TEXT", "MTEXT", "DIMENSION", "POINT", "INSERT"):
            continue  # resim çerçevesi, yazı, ölçü: kesim değil
        try:
            p = ezpath.make_path(e)
        except Exception:
            continue
        for alt in p.sub_paths():
            pts = [(v.x * cm, v.y * cm) for v in alt.flattening(0.01 / cm)]
            if len(pts) > 2:
                sonuc.append(pts)
    return sonuc


def maske(dosya):
    ks = konturlar(dosya)
    # kılavuz / ölçü çizgileri (çok ince uzun konturlar) kesim değildir: atılır, ölçü kalanlardan alınır
    def ince(k):
        kx = [x for x, _ in k]; ky = [y for _, y in k]
        return min(max(kx) - min(kx), max(ky) - min(ky)) < 0.2 and max(max(kx) - min(kx), max(ky) - min(ky)) > 3
    ks = [k for k in ks if not ince(k)]
    xs = [x for k in ks for x, _ in k]; ys = [y for k in ks for _, y in k]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    # desenin dış çerçevesi (köşe sayısı az, alanın büyük kısmı) varsa yalnız içi alınır: ölçü okları/rakamlar dışarıda kalır
    kutu = lambda k: (min(x for x, _ in k), min(y for _, y in k), max(x for x, _ in k), max(y for _, y in k))
    adaylar = [kutu(k) for k in ks if len(k) <= 6]
    adaylar = [c for c in adaylar if (c[2] - c[0]) * (c[3] - c[1]) >= 0.4 * (x1 - x0) * (y1 - y0)]
    if adaylar:
        c = max(adaylar, key=lambda c: (c[2] - c[0]) * (c[3] - c[1]))
        icerde = [k for k in ks if all(c[0] - 0.05 <= x <= c[2] + 0.05 and c[1] - 0.05 <= y <= c[3] + 0.05 for x, y in k)]
        if len(icerde) >= 0.7 * len(ks):
            ks = icerde
            x0, y0, x1, y1 = c
    w, h = x1 - x0, y1 - y0
    # dış sınır (bütün alanı kaplayan çerçeve) ve çerçeveye yakın uzun ince çizgiler (ölçü/kılavuz) delik değildir
    ks = [k for k in ks if not ((max(x for x, _ in k) - min(x for x, _ in k)) > 0.97 * w and
                                (max(y for _, y in k) - min(y for _, y in k)) > 0.97 * h)]
    W, H = round(w * PX_CM), round(h * PX_CM)
    m = Image.new("L", (W, H), 0)
    for k in ks:  # çift/tek kuralı: iç içe konturda iç kısım yeniden dolu olur
        tek = Image.new("L", (W, H), 0)
        ImageDraw.Draw(tek).polygon([((x - x0) * PX_CM, (y1 - y) * PX_CM) for x, y in k], fill=255)
        m = ImageChops.logical_xor(m.convert("1"), tek.convert("1")).convert("L")
    if H > W:
        m = m.rotate(90, expand=True); w, h = h, w
    return m, round(w, 1), round(h, 1)


def onizleme(m, cik):
    """Seçim düğmesi resmi: bej bant üstünde koyu delikler, 3 tekrar (eski LZ önizlemeleriyle aynı görünüş)."""
    yuk = 120
    tek = m.resize((max(2, round(m.width * yuk / m.height)), yuk), Image.LANCZOS)
    adet = max(1, min(4, round(520 / tek.width))) if tek.width < 520 else 1
    serit = Image.new("L", (tek.width * adet, yuk), 0)
    for i in range(adet):
        serit.paste(tek, (i * tek.width, 0))
    if serit.width > 900:
        serit = serit.crop((0, 0, 900, yuk))
    bej = Image.new("RGB", serit.size, (214, 203, 180)); koyu = Image.new("RGB", serit.size, (40, 34, 28))
    Image.composite(koyu, bej, serit).save(cik, quality=90)


def main():
    gir, varlik = Path(sys.argv[1]), Path(sys.argv[2])
    bilgi_yol = varlik / "desen" / "desenler.json"
    bilgi = json.loads(bilgi_yol.read_text(encoding="utf-8"))
    for kod, (dosya, ad) in DESENLER.items():
        m, boy, en = maske(gir / dosya)
        m.save(varlik / "desen" / f"{kod}.png", optimize=True)
        onizleme(m, varlik / "desen_onizleme" / f"{kod}.jpg")
        bilgi[kod] = {"tur": "lz", "ad": ad, "en_cm": en, "boy_cm": boy, "alan": False,
                      "bant": m.height, "periyot": m.width, "kaynak": dosya}
        print(kod, ad, en, "×", boy, "cm", m.size)
    bilgi_yol.write_text(json.dumps(bilgi, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
