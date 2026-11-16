"""Katalog fotoğraflarında halının kutusu (beyaz zemine çevirirken kullanılan kutunun aynısı) → foto_kutu.json.

beyaz_zemin.py fotoğrafları koyu deri zeminden keserken halının yerini kaydetmemişti; bu betik aynı hesabı eski
(git geçmişindeki koyu zeminli) fotoğraflarda yeniden yapar. Yalnız geliştirmede çalıştırılır.
Kullanım: python kutu_cikar.py ESKI_FOTO_KLASORU HEDEF_JSON
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from beyaz_zemin import OVAL, SABLONLA, YUVARLAK, hali_maskesi, saglam_kutu  # noqa: E402


def main(kaynak, hedef):
    dosyalar = sorted(Path(kaynak).glob("*.jpg"))
    kutular = []
    for d in dosyalar:
        if d.stem in OVAL or d.stem in YUVARLAK:
            continue
        f = Image.open(d).convert("RGB")
        k = saglam_kutu(hali_maskesi(f)[0], 0.6)
        if k and 0.55 < (k[2] - k[0]) * (k[3] - k[1]) / (f.width * f.height) < 0.9:
            kutular.append([k[0] / f.width, k[1] / f.height, k[2] / f.width, k[3] / f.height])
    sablon = [sorted(k[i] for k in kutular)[len(kutular) // 2] for i in range(4)]
    sonuc = {}
    for d in dosyalar:
        f = Image.open(d).convert("RGB")
        w, h = f.size
        duz = d.stem not in OVAL and d.stem not in YUVARLAK
        kutu = saglam_kutu(hali_maskesi(f)[0], 0.3 if duz else 0.06)
        oran = (kutu[2] - kutu[0]) * (kutu[3] - kutu[1]) / (w * h) if kutu else 0
        if not kutu or oran < 0.42 or oran > 0.95 or d.stem in SABLONLA:
            if not duz:
                continue
            kutu = [round(a * b) for a, b in zip(sablon, (w, h, w, h))]
        sekil = "yuvarlak" if d.stem in YUVARLAK else "oval" if d.stem in OVAL else "dikdortgen"
        sonuc[d.stem] = [kutu[0] + 1, kutu[1] + 1, kutu[2] - 2, kutu[3] - 2, sekil]
    Path(hedef).write_text(json.dumps(sonuc, indent=0, sort_keys=True))
    print(len(sonuc), "kutu")


if __name__ == "__main__":
    main(*sys.argv[1:3])
