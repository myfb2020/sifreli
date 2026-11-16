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
    olcu = ft._kenar_olculeri(kod, v)
    for i in range(len(olcu["sol"])):
        d.rectangle((olcu["sol"][i] * K, olcu["ust"][i] * K, W - olcu["sag"][i] * K, H - olcu["alt"][i] * K),
                    outline=(255, 0, 0))
    if v.get("orta") == "duz" and v.get("madalyon") != "yok":
        n = len(olcu["sol"])
        cx = ((olcu["sol"][-1] if n else 0) + v["en"] - (olcu["sag"][-1] if n else 0)) / 2
        cy = ((olcu["ust"][-1] if n else 0) + v["boy"] - (olcu["alt"][-1] if n else 0)) / 2
        r = v["madalyon_cap"] / 2 + (pc.MADALYON_CERCEVE if v.get("madalyon_cerceve") else 0)
        d.ellipse(((cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K), outline=(0, 90, 255))
    d.text((4, 4), kod, fill=(255, 0, 0))
    return foto


def cetvel(kod, uz=70, k=8):
    """Dört kenardan içeri 70 cm'lik şeritler (sol, sağ, üst, alt) + ortanın 60 cm'si, cm cetvelli."""
    v = ft.referans(kod)
    foto, _ = ft._foto(kod)
    fx, fy = foto.width / v["en"], foto.height / v["boy"]
    ym, xm = (v["boy"] / 2 - 25) * fy, (v["en"] / 2 - 45) * fx
    seritler = [
        foto.crop((0, round(ym), round(uz * fx), round(ym + 20 * fy))),
        foto.crop((foto.width - round(uz * fx), round(ym), foto.width, round(ym + 20 * fy))).transpose(
            Image.Transpose.FLIP_LEFT_RIGHT),
        foto.crop((round(xm), 0, round(xm + 20 * fx), round(uz * fy))).transpose(Image.Transpose.TRANSPOSE),
        foto.crop((round(xm), foto.height - round(uz * fy), round(xm + 20 * fx), foto.height)).transpose(
            Image.Transpose.TRANSPOSE).transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    ]
    orta = foto.crop((round((v["en"] / 2 - 30) * fx), round((v["boy"] / 2 - 30) * fy),
                      round((v["en"] / 2 + 30) * fx), round((v["boy"] / 2 + 30) * fy))).resize((300, 300))
    t = Image.new("RGB", (uz * k + 320, 4 * (20 * k + 4) + 40), "white")
    d = ImageDraw.Draw(t)
    for i, s in enumerate(seritler):
        t.paste(s.resize((uz * k, 20 * k), Image.BICUBIC), (0, 20 + i * (20 * k + 4)))
    alt = 20 + 4 * (20 * k + 4)
    for cm in range(uz + 1):
        u = 20 if cm % 5 == 0 else 6
        d.line((cm * k, 20, cm * k, 20 + u), fill=(255, 0, 0))
        d.line((cm * k, alt - u, cm * k, alt), fill=(255, 0, 0))
        if cm % 5 == 0:
            d.text((cm * k + 1, 4), str(cm), fill=(255, 0, 0))
    t.paste(orta, (uz * k + 20, 20))
    for cm in range(0, 61, 5):
        x = uz * k + 20 + cm * 5
        d.line((x, 20, x, 30 if cm % 10 else 36), fill=(255, 0, 0))
    d.text((uz * k + 20, 4), f"{kod} {v['en']:g}x{v['boy']:g} madalyon {v.get('madalyon')} {v.get('madalyon_cap'):g}",
           fill=(0, 0, 255))
    return t


def main():
    kodlar, hedef = sys.argv[1].split(","), Path(sys.argv[2])
    hedef.mkdir(parents=True, exist_ok=True)
    for kod in kodlar:
        (cetvel(kod) if "--cetvel" in sys.argv else kontrol_resmi(kod)).save(hedef / f"{kod}.png")


if __name__ == "__main__":
    main()
