"""Katalog fotoğrafında madalyonun gerçek merkezi ve yarıçapı (yalnız geliştirmede).
Modelin beklenen merkezi (zemin ortası) ve yarıçapı çevresinde ±8 cm / ±25 % aranır: madalyon kenarında (çember
boyunca) içerisi ile dışarısı arasındaki renk farkı en büyük olan çember seçilir. Sonuç foto_halka.json'da
"madalyon": [x_cm, y_cm, r_cm] (fotoğraf, modelin katalog ölçüsüne oturtulmuş olarak).
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/madalyon_olc.py [KOD,KOD…]
"""
import json, math, os, sys
from pathlib import Path
sys.path.insert(0, "."); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django  # noqa: E402
django.setup()
from PIL import ImageFilter  # noqa: E402
from uretim import foto_temel as ft, parcali as pc  # noqa: E402

YOL = Path("uretim/tasarim_varlik/foto_halka.json")


def olc(kod):
    v = ft.referans(kod)
    if not ft._madalyonlu(v):
        return None
    foto, _ = ft._foto(kod)
    fx, fy = foto.width / v["en"], foto.height / v["boy"]
    k = ft._kenar_olculeri(kod, v)
    sol = sum(k["sol"][-1]) / 2 if k["sol"] else 0
    sag = sum(k["sag"][-1]) / 2 if k["sag"] else 0
    ust = sum(k["ust"][-1]) / 2 if k["ust"] else 0
    alt = sum(k["alt"][-1]) / 2 if k["alt"] else 0
    cx0, cy0 = (sol + v["en"] - sag) / 2, (ust + v["boy"] - alt) / 2
    r0 = v["madalyon_cap"] / 2 + (pc.MADALYON_CERCEVE if v.get("madalyon_cerceve") else 0)
    g = foto.filter(ImageFilter.GaussianBlur(1)).convert("RGB")
    W, H = g.size
    px = g.load()

    def renk(x, y):
        x, y = int(x * fx), int(y * fy)
        return px[min(W - 1, max(0, x)), min(H - 1, max(0, y))]

    def puan(cx, cy, r):
        top = 0
        for a in range(0, 360, 10):
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            i = renk(cx + (r - 1.2) * c, cy + (r - 1.2) * s)
            d = renk(cx + (r + 1.2) * c, cy + (r + 1.2) * s)
            top += math.dist(i, d)
        return top / 36

    en_iyi = (-1, cx0, cy0, r0)
    for adim, (dxs, rs) in enumerate((((-8, 8, 1.0), (0.75, 1.3, 0.05)), ((-1.0, 1.0, 0.25), (-0.04, 0.04, 0.01)))):
        bx, by, br = (cx0, cy0, r0) if adim == 0 else en_iyi[1:]
        n = int(round((dxs[1] - dxs[0]) / dxs[2]))
        for i in range(n + 1):
            for j in range(n + 1):
                cx, cy = bx + dxs[0] + i * dxs[2], by + dxs[0] + j * dxs[2]
                m = int(round((rs[1] - rs[0]) / rs[2]))
                for t in range(m + 1):
                    r = (r0 * (rs[0] + t * rs[2])) if adim == 0 else br * (1 + rs[0] + t * rs[2])
                    p = puan(cx, cy, r)
                    if p > en_iyi[0]:
                        en_iyi = (p, cx, cy, r)
    return [round(en_iyi[1], 2), round(en_iyi[2], 2), round(en_iyi[3], 2)], (round(cx0, 2), round(cy0, 2), r0)


def main():
    tum = json.loads(YOL.read_text())
    kodlar = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(tum)
    for kod in kodlar:
        s = olc(kod)
        if not s:
            continue
        tum[kod]["madalyon"] = s[0]
        print(kod, "ölçülen", s[0], "beklenen", s[1])
    YOL.write_text("{\n" + ",\n".join(f'"{k}": {json.dumps(v)}' for k, v in sorted(tum.items())) + "\n}\n")


if __name__ == "__main__":
    main()
