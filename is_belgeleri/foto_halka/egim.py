"""Bordür sınırlarının fotoğraftaki eğikliğini ölçer (yalnız geliştirmede).

foto_halka.json'daki elle okunmuş her sınır, kenar boyunca 7 noktada ±2,5 cm içinde en güçlü renk değişimine
oturtulur; noktalardan sapanlar atılır, kalanlardan doğru çıkarılır ve sınır [baş, son] olarak yazılır (sol / sağ
kenarda baş = üst uç, üst / alt kenarda baş = sol uç). Oval / yuvarlak halılarda kenar eğri olduğundan ölçüm
değişmez. Elle okunan değer her zaman temel kalır: yeterli nokta bulunamazsa sınır olduğu gibi bırakılır.
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/egim.py [KOD,KOD…]
"""
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django  # noqa: E402

django.setup()
from PIL import Image  # noqa: E402

from uretim import foto_temel as ft  # noqa: E402

YOL = Path("uretim/tasarim_varlik/foto_halka.json")
ARA, ADIM, SERIT = 2.5, 0.25, 5.0  # cm: arama yarı genişliği, adım, örnek şeridin boyu
NOKTA = 7


def _orta(d):
    return d if isinstance(d, (int, float)) else (d[0] + d[1]) / 2


def _profil(foto, fx, fy, kenar, m, konum):
    """Sınırın elle okunan yeri m çevresinde (m−ARA … m+ARA) renkler; konum = kenar boyunca cm."""
    n = int(2 * ARA / ADIM) + 1
    a, b = m - ARA, m + ARA
    W, H = foto.size
    if kenar in ("sol", "sag"):
        y0, y1 = round((konum - SERIT / 2) * fy), round((konum + SERIT / 2) * fy)
        x0, x1 = (a * fx, b * fx) if kenar == "sol" else (W - b * fx, W - a * fx)
        d = list(foto.crop((round(x0), y0, round(x1), y1)).resize((n, 1), Image.BOX).getdata())
        return d if kenar == "sol" else d[::-1]
    x0, x1 = round((konum - SERIT / 2) * fx), round((konum + SERIT / 2) * fx)
    y0, y1 = (a * fy, b * fy) if kenar == "ust" else (H - b * fy, H - a * fy)
    d = list(foto.crop((x0, round(y0), x1, round(y1))).resize((1, n), Image.BOX).getdata())
    return d if kenar == "ust" else d[::-1]


def _bul(renk, m):
    g = [math.dist(renk[i + 2], renk[i - 2]) if 2 <= i < len(renk) - 2 else 0 for i in range(len(renk))]
    gmax = max(g) or 1
    en_iyi = max(range(len(g)), key=lambda i: g[i] - 0.12 * gmax * abs(i * ADIM - ARA))
    return (m - ARA + en_iyi * ADIM) if g[en_iyi] >= 25 else None


def _dogru(noktalar):
    """En küçük kareler; ortancadan 1,2 cm'den çok sapan noktalar atılır."""
    for _ in range(2):
        if len(noktalar) < 3:
            return None
        ts, xs = zip(*noktalar)
        tm, xm = sum(ts) / len(ts), sum(xs) / len(xs)
        pay = sum((t - tm) ** 2 for t in ts) or 1e-9
        e = sum((t - tm) * (x - xm) for t, x in noktalar) / pay
        k = xm - e * tm
        kalan = sorted(abs(x - (k + e * t)) for t, x in noktalar)
        orta = kalan[len(kalan) // 2]
        noktalar = [(t, x) for t, x in noktalar if abs(x - (k + e * t)) <= max(1.2, 2 * orta)]
    return (k, k + e) if len(noktalar) >= 4 else None


def olc(kod, kayit):
    v = ft.referans(kod)
    if v.get("sekil") == "oval":
        return kayit, []
    foto, _ = ft._foto(kod)
    fx, fy = foto.width / v["en"], foto.height / v["boy"]
    derin = max(_orta(d) for k in ("sol", "sag", "ust", "alt") for d in kayit[k][-1:]) if kayit["sol"] else 0
    sonuc, rapor = {}, []
    for kenar in ("sol", "sag", "ust", "alt"):
        uz = v["boy"] if kenar in ("sol", "sag") else v["en"]
        bas, son = derin + 6, uz - derin - 6
        if son - bas < 10:
            sonuc[kenar] = kayit[kenar]
            continue
        yeni = []
        for d in kayit[kenar]:
            m = _orta(d)
            noktalar = []
            for i in range(NOKTA):
                konum = bas + (son - bas) * i / (NOKTA - 1)
                x = _bul(_profil(foto, fx, fy, kenar, m, konum), m)
                if x is not None:
                    noktalar.append((konum / uz, x))
            dogru = _dogru(noktalar)
            if not dogru or abs(dogru[1] - dogru[0]) > 5:
                yeni.append(d)
                rapor.append(f"{kenar} {m:g}: değişmedi ({len(noktalar)} nokta)")
                continue
            a, b = round(dogru[0] * 4) / 4, round(dogru[1] * 4) / 4
            yeni.append(a if a == b else [a, b])
            if abs(a - m) > 0.6 or abs(b - m) > 0.6:
                rapor.append(f"{kenar} {m:g} → {a:g}…{b:g}")
        sonuc[kenar] = yeni
    return sonuc, rapor


def main():
    tum = json.loads(YOL.read_text())
    kodlar = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(tum)
    for kod in kodlar:
        tum[kod], rapor = olc(kod, tum[kod])
        print(kod, "; ".join(rapor) if rapor else "–")
    YOL.write_text("{\n" + ",\n".join(f'"{k}": {json.dumps(v)}' for k, v in sorted(tum.items())) + "\n}\n")


if __name__ == "__main__":
    main()
