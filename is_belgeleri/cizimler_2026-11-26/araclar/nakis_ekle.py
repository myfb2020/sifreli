"""Nakış dikiş dosyasından (DSZ) program motif maskesi (2026-11-26): 79.01 Çiçek dalı, 77.03 Grek harf.
Maske: L, 255 = iplik, 20 px/cm (en 40 cm → 800 px). Atlama/kesme ve 1,5 cm'den uzun geçiş dikişleri çizilmez.
Kullanım (pyembroidery kurulu Python): python -I nakis_ekle.py DSZ_KLASORU TASARIM_VARLIK"""
import sys
from pathlib import Path
import pyembroidery as pe
from PIL import Image, ImageDraw, ImageFilter

MOTIFLER = {"79.01": "00007901.DSZ", "77.03": "00007703.DSZ"}
PX_CM = 20
GECIS = 150  # 0,1 mm: daha uzun tek dikiş = geçiş ipliği


def maske(dosya):
    e = pe.read(str(dosya))
    x0, y0, x1, y1 = e.bounds()
    olc = PX_CM / 100  # 0,1 mm → px
    W, H = round((x1 - x0) * olc) + 1, round((y1 - y0) * olc) + 1
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    onceki = None
    for x, y, komut in e.stitches:
        k = komut & pe.COMMAND_MASK
        if k != pe.STITCH:
            onceki = None
            continue
        if onceki and abs(x - onceki[0]) + abs(y - onceki[1]) <= GECIS:
            d.line([((onceki[0] - x0) * olc, (onceki[1] - y0) * olc), ((x - x0) * olc, (y - y0) * olc)], fill=255, width=2)
        onceki = (x, y)
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))  # saten / dolgu dikişleri arası boşluk kapansın
    m = m.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))  # tek sıra geçiş / alt dikişleri silinsin
    return m, round((x1 - x0) / 100, 1), round((y1 - y0) / 100, 1)


def main():
    gir, varlik = Path(sys.argv[1]), Path(sys.argv[2])
    for kod, dosya in MOTIFLER.items():
        m, en, boy = maske(gir / dosya)
        m.save(varlik / "nakis" / f"{kod.replace('.', '_')}.png", optimize=True)
        print(kod, en, "×", boy, "cm", m.size)


if __name__ == "__main__":
    main()
