"""Eğiklik tutarlılığı (yalnız geliştirmede; egim.py / kalibre.py'den sonra).

Fotoğraf eğik çekildiyse bir kenardaki bütün bordür sınırları aynı yöne, yaklaşık aynı miktarda eğilir. Bir kenarda
sınırların eğikliklerinin ortancası alınır (en çok 2,5 cm); ortancadan 1 cm'den çok sapan sınır kendi ortalaması
çevresinde ortanca eğiklikle yeniden yazılır. Sınırlar iç içe geçmesin diye sıra korunur.
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/tutarlilik.py
"""
import json
from pathlib import Path

YOL = Path("uretim/tasarim_varlik/foto_halka.json")


def uc(d):
    return (float(d), float(d)) if isinstance(d, (int, float)) else (float(d[0]), float(d[1]))


def yaz(a, b):
    a, b = round(a * 4) / 4, round(b * 4) / 4
    return a if abs(a - b) < 0.3 else [a, b]


def main():
    tum = json.loads(YOL.read_text())
    for kod, kenarlar in sorted(tum.items()):
        rapor = []
        for kenar, lst in kenarlar.items():
            cizgi = [uc(d) for d in lst]
            if not cizgi:
                continue
            egim = sorted(b - a for a, b in cizgi)
            orta = egim[len(egim) // 2]
            orta = max(-2.5, min(2.5, orta))
            yeni = []
            for (a, b), eski in zip(cizgi, lst):
                if abs((b - a) - orta) > 1.0:
                    m = (a + b) / 2
                    a, b = m - orta / 2, m + orta / 2
                if yeni:
                    pa, pb = uc(yeni[-1])
                    a, b = max(a, pa + 0.5), max(b, pb + 0.5)
                yeni.append(yaz(a, b))
                if yeni[-1] != eski:
                    rapor.append(f"{kenar}: {eski}→{yeni[-1]}")
            kenarlar[kenar] = yeni
        if rapor:
            print(kod, "; ".join(rapor))
    YOL.write_text("{\n" + ",\n".join(f'"{k}": {json.dumps(v)}' for k, v in sorted(tum.items())) + "\n}\n")


if __name__ == "__main__":
    main()
