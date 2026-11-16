"""Kullanıcının beton zemin üzerinde çektiği halı fotoğraflarını (tasarim_varlik/foto_model/KOD.jpg) düzleştirir
(yalnız geliştirmede): halı zeminden renk farkıyla ayrılır, dört köşe bulunur (elle verilebilir), perspektif
düzeltilip halı dikdörtgen olarak tasarim_varlik/foto_duz/KOD.jpg'e yazılır (foto_temel bunu katalog fotoğrafı
yerine kullanır). Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/duzle.py KOD[:x0,y0,x1,y1,x2,y2,x3,y3] …
köşe sırası: sol üst, sağ üst, sağ alt, sol alt.
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

KAYNAK = Path("uretim/tasarim_varlik/foto_model")
HEDEF = Path("uretim/tasarim_varlik/foto_duz")


def koseler(foto):
    k = foto.filter(ImageFilter.GaussianBlur(2))
    W, H = k.size
    zemin = [k.getpixel((x, y)) for x, y in ((5, 5), (W - 6, 5), (5, H - 6), (W - 6, H - 6))]
    z = tuple(sum(c[i] for c in zemin) // 4 for i in range(3))
    fark = ImageChops.difference(k, Image.new("RGB", k.size, z)).convert("L").point(lambda q: 255 if q > 28 else 0)
    fark = fark.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    # en büyük parça: ortadan taşma
    t = fark.copy()
    ImageDraw.floodfill(t, (W // 2, H // 2), 128)
    m = t.point(lambda q: 255 if q == 128 else 0)
    px = m.load()
    noktalar = [(x, y) for y in range(0, H, 2) for x in range(0, W, 2) if px[x, y]]
    su = min(noktalar, key=lambda p: p[0] + p[1])
    sa = max(noktalar, key=lambda p: p[0] - p[1])
    sga = max(noktalar, key=lambda p: p[0] + p[1])
    sla = min(noktalar, key=lambda p: p[0] - p[1])
    return [su, sa, sga, sla]


def duzle(foto, k, genislik=800):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = k
    w = ((x1 - x0) + (x2 - x3)) / 2
    h = ((y3 - y0) + (y2 - y1)) / 2
    G, Y = genislik, round(genislik * h / w)
    # PIL QUAD: hedef dikdörtgen ← kaynak dörtgen (sol üst, sol alt, sağ alt, sağ üst)
    return foto.transform((G, Y), Image.Transform.QUAD, (x0, y0, x3, y3, x2, y2, x1, y1), Image.BICUBIC)


def main():
    HEDEF.mkdir(parents=True, exist_ok=True)
    for arg in sys.argv[1:]:
        kod, _, elle = arg.partition(":")
        foto = Image.open(KAYNAK / f"{kod}.jpg").convert("RGB")
        k = [tuple(map(int, elle.split(",")[i:i + 2])) for i in range(0, 8, 2)] if elle else koseler(foto)
        duzle(foto, k).save(HEDEF / f"{kod}.jpg", quality=90)
        print(kod, k)


if __name__ == "__main__":
    main()
