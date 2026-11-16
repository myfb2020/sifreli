"""Fotoğraf esaslı görünüm için ölçüm kontrolü (yalnız geliştirmede).

uretim/tasarim_varlik/foto_halka.json: her katalog modelinde fotoğrafın dört kenarında bordür sınırları (cm, kenardan
içeri, fotoğraf modelin katalog ölçüsüne oturtulmuş olarak). Değerler cetvelli şeritlerden gözle okunur
(--cetvel); kontrol resminde kırmızı dikdörtgenler fotoğraftaki bordür sınırlarının üstüne düşmeli, mavi daire
madalyonun üstüne.
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/kontrol.py KOD,KOD… HEDEF_KLASOR [--cetvel]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django  # noqa: E402

django.setup()
from PIL import Image, ImageDraw  # noqa: E402

from uretim import foto_temel as ft  # noqa: E402
from uretim import parcali as pc  # noqa: E402

K = 3  # kontrol resminde cm başına piksel


def kontrol_resmi(kod):
    v = ft.referans(kod)
    foto, _ = ft._foto(kod)
    foto = foto.resize((round(v["en"] * K), round(v["boy"] * K)))
    d = ImageDraw.Draw(foto)
    W, H = foto.size
    olcu = ft._kenar_olculeri(kod, v)  # her sınır kenar boyunca (baş, son): eğik çizgi olarak çizilir
    renk = [(255, 0, 0), (0, 160, 255), (0, 200, 0), (255, 0, 255), (255, 160, 0)]
    for i in range(len(olcu["sol"])):
        r = renk[i % len(renk)]
        (sa, sb), (ga, gb) = olcu["sol"][i], olcu["sag"][i]
        (ua, ub), (aa, ab) = olcu["ust"][i], olcu["alt"][i]
        d.line((sa * K, 0, sb * K, H), fill=r, width=1)
        d.line((W - ga * K, 0, W - gb * K, H), fill=r, width=1)
        d.line((0, ua * K, W, ub * K), fill=r, width=1)
        d.line((0, H - aa * K, W, H - ab * K), fill=r, width=1)
    olcu = {k: [(a + b) / 2 for a, b in x] for k, x in olcu.items()}
    if v.get("orta") == "duz" and v.get("madalyon") != "yok":
        n = len(olcu["sol"])
        cx = ((olcu["sol"][-1] if n else 0) + v["en"] - (olcu["sag"][-1] if n else 0)) / 2
        cy = ((olcu["ust"][-1] if n else 0) + v["boy"] - (olcu["alt"][-1] if n else 0)) / 2
        r = v["madalyon_cap"] / 2 + (pc.MADALYON_CERCEVE if v.get("madalyon_cerceve") else 0)
        d.ellipse(((cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K), outline=(0, 90, 255))
    d.text((4, 4), kod, fill=(255, 0, 0))
    return foto


def cetvel(kod, uz=70, k=8, yuk=12):
    """Dört kenardan içeri 70 cm'lik şeritler (sol, sağ, üst, alt) + ortanın 60 cm'si, cm cetvelli; mavi çentik =
    modelin şimdiki bordür sınırları."""
    v = ft.referans(kod)
    foto, _ = ft._foto(kod)
    fx, fy = foto.width / v["en"], foto.height / v["boy"]
    oval = v.get("sekil") == "oval"
    ym = (v["boy"] / 2 - yuk / 2 if oval else v["boy"] / 2 - 25) * fy
    xm = (v["en"] / 2 - yuk / 2 if oval else v["en"] / 2 - 45) * fx
    seritler = [
        foto.crop((0, round(ym), round(uz * fx), round(ym + yuk * fy))),
        foto.crop((foto.width - round(uz * fx), round(ym), foto.width, round(ym + yuk * fy))).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT),
        foto.crop((round(xm), 0, round(xm + yuk * fx), round(uz * fy))).transpose(Image.Transpose.TRANSPOSE),
        foto.crop((round(xm), foto.height - round(uz * fy), round(xm + yuk * fx), foto.height)).transpose(
            Image.Transpose.TRANSPOSE).transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    ]
    orta = foto.crop((round((v["en"] / 2 - 30) * fx), round((v["boy"] / 2 - 30) * fy),
                      round((v["en"] / 2 + 30) * fx), round((v["boy"] / 2 + 30) * fy))).resize((240, 240))
    sh = yuk * k
    t = Image.new("RGB", (uz * k + 260, max(4 * (sh + 3) + 40, 280)), "white")
    d = ImageDraw.Draw(t)
    for i, s in enumerate(seritler):
        t.paste(s.resize((uz * k, sh), Image.BICUBIC), (0, 20 + i * (sh + 3)))
    alt = 20 + 4 * (sh + 3)
    for cm in range(uz + 1):
        u = 14 if cm % 5 == 0 else 5
        d.line((cm * k, 20, cm * k, 20 + u), fill=(255, 0, 0))
        d.line((cm * k, alt - u, cm * k, alt), fill=(255, 0, 0))
        if cm % 5 == 0:
            d.text((cm * k + 1, 4), str(cm), fill=(255, 0, 0))
    for h in pc.halkalar(v):
        x = (h["d"] + h["gen"]) * k
        d.polygon([(x - 4, alt + 10), (x + 4, alt + 10), (x, alt + 1)], fill=(0, 70, 255))
    t.paste(orta, (uz * k + 15, 20))
    for cm in range(0, 61, 5):
        x = uz * k + 15 + cm * 4
        d.line((x, 20, x, 26 if cm % 10 else 32), fill=(255, 0, 0))
    d.text((uz * k + 15, 4), f"{kod} {v['sekil'][:3]} mad {v.get('madalyon')} {v.get('madalyon_cap'):g}",
           fill=(0, 0, 255))
    return t


def main():
    kodlar, hedef = sys.argv[1].split(","), Path(sys.argv[2])
    hedef.mkdir(parents=True, exist_ok=True)
    if "--cetvel" in sys.argv:  # üçer model bir sayfada
        for n in range(0, len(kodlar), 3):
            parcalar = [cetvel(kod) for kod in kodlar[n:n + 3]]
            sayfa = Image.new("RGB", (parcalar[0].width, sum(p.height + 8 for p in parcalar)), "white")
            y = 0
            for p in parcalar:
                sayfa.paste(p, (0, y))
                y += p.height + 8
            sayfa.save(hedef / f"cetvel_{n // 3 + 1:02d}.png")
        return
    for kod in kodlar:
        kontrol_resmi(kod).save(hedef / f"{kod}.png")


if __name__ == "__main__":
    main()
