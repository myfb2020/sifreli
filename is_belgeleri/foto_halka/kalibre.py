"""Bordür sınırlarını fotoğraftan düz renk istatistiğiyle düzeltir (yalnız geliştirmede; egim.py'den sonra).

Bir sınırın bir yanı düz renkli (zemin, düz bant: renk sapması küçük) ise, o yandan sınıra doğru satır satır
bakılır: satırdaki piksellerin %8'den fazlası düz rengin dağılımına uymuyorsa düz parça bitmiştir. Kenarın ilk ve
son üçte birinde ayrı ölçülür → [baş, son]. Eski değerden 6 cm'den çok sapan sonuç kabul edilmez.
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/kalibre.py [KOD,KOD…]
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django  # noqa: E402

django.setup()
from PIL import Image, ImageChops, ImageStat  # noqa: E402

from uretim import foto_temel as ft  # noqa: E402
from uretim import parcali as pc  # noqa: E402

YOL = Path("uretim/tasarim_varlik/foto_halka.json")
ADIM = 0.25
DUZ_SAPMA = 16  # bundan küçük renk sapması: düz parça
ORAN = 0.08


def _serit(foto, fx, fy, kenar, a, b, u0, u1):
    """Kenardan a..b cm derinlik, kenar boyunca u0..u1 (0–1) bölgesi; satırlar derinlik sırasıyla (döndürülmüş)."""
    W, H = foto.size
    if kenar == "sol":
        k = foto.crop((round(a * fx), round(u0 * H), round(b * fx), round(u1 * H))).transpose(Image.Transpose.ROTATE_90)
        return k.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if kenar == "sag":
        k = foto.crop((W - round(b * fx), round(u0 * H), W - round(a * fx), round(u1 * H)))
        return k.transpose(Image.Transpose.ROTATE_90)
    if kenar == "ust":
        return foto.crop((round(u0 * W), round(a * fy), round(u1 * W), round(b * fy)))
    k = foto.crop((round(u0 * W), H - round(b * fy), round(u1 * W), H - round(a * fy)))
    return k.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def _istatistik(foto, fx, fy, kenar, a, b, u0, u1):
    s = _serit(foto, fx, fy, kenar, a, b, u0, u1)
    st = ImageStat.Stat(s)
    return tuple(st.mean), sum(st.stddev) / 3


def _uymayan(foto, fx, fy, kenar, a, b, u0, u1, ort, sapma):
    """a..b derinliğinde her ADIM satırı için uymayan piksel oranı."""
    s = _serit(foto, fx, fy, kenar, a, b, u0, u1)
    n = max(1, round((b - a) / ADIM))
    s = s.resize((max(8, s.width // 2), n), Image.BOX) if s.height >= n else s.resize((max(8, s.width // 2), n))
    uzak = ImageChops.difference(s, Image.new("RGB", s.size, tuple(round(c) for c in ort))).convert("L")
    esik = max(22, 2.8 * sapma)
    ikili = uzak.point(lambda q: 255 if q > esik else 0)
    return [v / 255 for v in ikili.resize((1, n), Image.BOX).getdata()]


def olc_sinir(foto, fx, fy, kenar, eski, ic_duz, dis_duz, u0, u1, w_ic, w_dis):
    """eski: (yaklaşık) sınır cm. ic_duz / dis_duz: sınırın iç (merkeze doğru) / dış yanı düz mü; w_ic / w_dis: o
    yandaki parçanın genişliği (örnek ve arama o parçanın içinde kalır)."""
    sonuc = []
    a = eski - min(6, max(1.5, w_dis * 0.8))
    b = eski + min(6, max(1.5, w_ic * 0.8))
    if ic_duz:
        ort, sap = _istatistik(foto, fx, fy, kenar, eski + min(6.5, w_ic * 0.3), eski + min(12, w_ic * 0.8), u0, u1)
        if sap < DUZ_SAPMA:
            oran = _uymayan(foto, fx, fy, kenar, a, b, u0, u1, ort, sap)
            for i in range(len(oran) - 1, -1, -1):  # içeriden dışa: düz rengin bittiği ilk satır
                if all(o > ORAN for o in oran[max(0, i - 3):i + 1]):
                    sonuc.append(a + (i + 1) * ADIM)
                    break
    if dis_duz and eski - min(12, w_dis * 0.8) > 0.5:
        ort, sap = _istatistik(foto, fx, fy, kenar, eski - min(12, w_dis * 0.8), eski - min(6.5, w_dis * 0.3), u0, u1)
        if sap < DUZ_SAPMA:
            oran = _uymayan(foto, fx, fy, kenar, a, b, u0, u1, ort, sap)
            for i in range(len(oran)):  # dışarıdan içe
                if all(o > ORAN for o in oran[i:i + 4]):
                    sonuc.append(a + i * ADIM)
                    break
    sonuc = [x for x in sonuc if abs(x - eski) <= 6]
    return round(sum(sonuc) / len(sonuc) * 4) / 4 if sonuc else None


def _orta(d):
    return d if isinstance(d, (int, float)) else (d[0] + d[1]) / 2


def olc(kod, kayit):
    v = ft.referans(kod)
    if v.get("sekil") == "oval":
        return kayit, []
    foto, _ = ft._foto(kod)
    fx, fy = foto.width / v["en"], foto.height / v["boy"]
    hs = pc.halkalar(v)
    duz = [h["tur"] == "duz" for h in hs] + [v.get("orta") == "duz"]  # her öğe + zemin
    gen = [h["gen"] for h in hs] + [40]
    rapor, yeni = [], {}
    for kenar in ("sol", "sag", "ust", "alt"):
        satir = []
        for i, d in enumerate(kayit[kenar]):
            m = d if isinstance(d, (int, float)) else None
            bas_son = []
            for j, (u0, u1) in enumerate(((0.18, 0.38), (0.62, 0.82))):
                e = _deger_uc(d, j)
                x = olc_sinir(foto, fx, fy, kenar, e, duz[i + 1], duz[i], u0, u1, gen[i + 1], gen[i])
                bas_son.append(x if x is not None else e)
            a, b = bas_son
            # parçanın genişliği modeldekinden çok saparsa yeni ölçü yanlıştır: eskisi kalır
            onceki = satir[-1] if satir else 0.0
            for j in (0, 1):
                o = _deger_uc(onceki, j) if satir else 0.0
                yeni_w, eski_w, model_w = bas_son[j] - o, _deger_uc(d, j) - o, gen[i]
                if abs(yeni_w - model_w) > max(2.0, 0.35 * model_w) and abs(yeni_w - model_w) > abs(eski_w - model_w):
                    bas_son[j] = _deger_uc(d, j)
            a, b = bas_son
            yeni_d = a if abs(a - b) < 0.3 else [a, b]
            if yeni_d != d:
                rapor.append(f"{kenar}{i + 1} {d}→{yeni_d}")
            satir.append(yeni_d)
            del m
        yeni[kenar] = satir
    return yeni, rapor


def _deger_uc(d, j):
    return float(d) if isinstance(d, (int, float)) else float(d[j])


def main():
    tum = json.loads(YOL.read_text())
    kodlar = sys.argv[1].split(",") if len(sys.argv) > 1 else sorted(tum)
    for kod in kodlar:
        tum[kod], rapor = olc(kod, tum[kod])
        print(kod, "; ".join(rapor) if rapor else "–")
    YOL.write_text("{\n" + ",\n".join(f'"{k}": {json.dumps(v)}' for k, v in sorted(tum.items())) + "\n}\n")


if __name__ == "__main__":
    main()
