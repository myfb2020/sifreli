"""Kullanıcının gri zeminde çektiği Rono fotoğraflarını katalogdaki öteki fotoğraflar gibi beyaz zemine koyar
(2026-11-18, kullanıcı: "beyaz zeminle değiştirilsin"). Yalnız geliştirmede çalışır (OpenCV gerekir).
- Düzleştirilmiş olanlar (tasarim_varlik/foto_duz/KOD.jpg): halı resmin tamamı → doğrudan beyaz zemine.
- RNO-006 (oval) ve RNO-008 (kesik köşe): gri zeminden grabCut ile ayrılır.
Çıktı: uretim/katalog_tohum/beyaz/KOD.jpg (migration 0046 medyaya kopyalar).
Kullanım (uretim_takip içinde): python ../is_belgeleri/katalog_beyaz/rono_beyaz.py
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

UR = Path("uretim")
CIKTI = UR / "katalog_tohum" / "beyaz"
ZEMIN = (252, 251, 249)
EN, BOY = 800, 978  # katalogdaki fotoğraflarla aynı oran (520 × 636)


def beyaza_koy(halı: Image.Image, maske: Image.Image) -> Image.Image:
    """Halıyı (maskesiyle) beyaz tuvale ortalar, hafif gölge ekler."""
    kutu = maske.getbbox()
    halı, maske = halı.crop(kutu), maske.crop(kutu)
    o = min(EN * 0.86 / halı.width, BOY * 0.88 / halı.height)
    boyut = (round(halı.width * o), round(halı.height * o))
    halı, maske = halı.resize(boyut, Image.LANCZOS), maske.resize(boyut, Image.LANCZOS)
    x, y = (EN - boyut[0]) // 2, (BOY - boyut[1]) // 2
    tuval = Image.new("RGB", (EN, BOY), ZEMIN)
    golge = Image.new("L", (EN, BOY), 0)
    golge.paste(maske.point(lambda v: v * 0.45), (x + 4, y + 9))
    golge = golge.filter(ImageFilter.GaussianBlur(11))
    tuval = Image.composite(Image.new("RGB", (EN, BOY), (120, 112, 104)), tuval, golge)
    tuval.paste(halı, (x, y), maske)
    return tuval


def yuvarlak_kose(boyut, r):
    m = Image.new("L", boyut, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, boyut[0] - 1, boyut[1] - 1], r, fill=255)
    return m


def zeminden_ayir(yol: Path, kenar=0.06):
    """Gri zemin + ortadaki halı: grabCut (kenar şeridi kesin zemin, orta olası halı)."""
    im = cv2.imread(str(yol))
    h, w = im.shape[:2]
    maske = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    b = int(min(h, w) * kenar)
    maske[:b, :] = maske[-b:, :] = cv2.GC_BGD
    maske[:, :b] = maske[:, -b:] = cv2.GC_BGD
    # zemine renkçe çok benzeyen (doygunluğu düşük, açık gri) pikseller olası zemin
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    kenar_ort = np.median(np.concatenate([im[:b].reshape(-1, 3), im[-b:].reshape(-1, 3)]), axis=0)
    fark = np.linalg.norm(im.astype(float) - kenar_ort, axis=2)
    maske[(fark < 18) & (maske == cv2.GC_PR_FGD)] = cv2.GC_PR_BGD
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(im, maske, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
    on = np.where((maske == cv2.GC_FGD) | (maske == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # en büyük parça + delikleri doldur + kenarı yumuşat
    sayi, etiket, ist, _ = cv2.connectedComponentsWithStats(on)
    en_buyuk = 1 + int(np.argmax(ist[1:, cv2.CC_STAT_AREA]))
    on = np.where(etiket == en_buyuk, 255, 0).astype(np.uint8)
    konturlar, _ = cv2.findContours(on, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    dolu = np.zeros_like(on)
    cv2.drawContours(dolu, konturlar, -1, 255, -1)
    dolu = cv2.morphologyEx(dolu, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    dolu = cv2.GaussianBlur(dolu, (5, 5), 0)
    return Image.open(yol).convert("RGB"), Image.fromarray(dolu)


def main():
    CIKTI.mkdir(parents=True, exist_ok=True)
    for kod in ("RNO-007", "RNO-009", "RNO-010", "RNO-011", "RNO-012"):
        halı = Image.open(UR / "tasarim_varlik" / "foto_duz" / f"{kod}.jpg").convert("RGB")
        beyaza_koy(halı, yuvarlak_kose(halı.size, round(halı.width / 160))).save(CIKTI / f"{kod}.jpg", quality=90)
    for kod in ("RNO-006", "RNO-008"):
        halı, maske = zeminden_ayir(UR / "tasarim_varlik" / "foto_model" / f"{kod}.jpg")
        beyaza_koy(halı, maske).save(CIKTI / f"{kod}.jpg", quality=90)
        maske.save(f"/tmp/{kod}_maske.png")
    print("tamam:", sorted(p.name for p in CIKTI.glob("*.jpg")))


if __name__ == "__main__":
    main()
