"""Karşılaştırma tabakası. python -I karsilastir.py CIZIM_PNG_KLASORU CIKTI"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
C = Path(sys.argv[1])
F = lambda n: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", n)
FB = lambda n: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", n)
P = lambda k: C / "prog_desen" / f"{k}.png"
Y = lambda k: C / "yeni" / f"{k}.png"
PN = lambda k: C / "prog_nakis" / f"{k}.png"
YN = lambda k: C / "nakis" / f"{k}.png"
bolumler = [
 ("A · Programda var, dosya aynı → DOĞRU, değişmez", (225, 245, 225), [
   ("1", "LZ03 Dama", P("LZ03"), Y("DAMA_MODEL")), ("2", "LZ05 Line", P("LZ05"), Y("LINE_MODEL_120X180")),
   ("3", "LZ06 Rıva", P("LZ06"), Y("RIVA_DESEN")), ("4", "LZ07 Köşem", P("LZ07"), Y("KOSEM_MODEL"))]),
 ("B · Fotoğraftan çizilmiş, gerçek dosyası geldi → DEĞİŞSİN (eşleşmeyi onaylayın)", (255, 240, 215), [
   ("5", "DB015 Grek ↔ VERSACE", P("DB015"), Y("VERSACE_DESEN")), ("6", "DB003 ↔ DAMA", P("DB003"), Y("DAMA_MODEL")),
   ("7", "DB007 ↔ LINE", P("DB007"), Y("LINE_MODEL_120X180")), ("8", "DB013 ↔ YILDIZ", P("DB013"), Y("YILDIZ_DESEN_UFAK"))]),
 ("C · Programda yok, düz bordür deseni → EKLENSİN", (225, 235, 255), [
   ("9", "ADOBE 17,6×3,8", None, Y("ADOBE_MODEL")), ("10", "ÇİÇEK 8,6×17,7", None, Y("CICEK_DESEN")),
   ("11", "MAJOR 67,8×25", None, Y("MAJOR_DESEN_BOY")), ("12", "PRENSES 16,7×65", None, Y("PRENSES")),
   ("13", "TALL 10×10", None, Y("TALL_DESEN")), ("14", "TAMAMLAR 15×67", None, Y("TAMAMLAR_DESEN")),
   ("15", "YILDIZ 75×25", None, Y("YILDIZ_DESEN_UFAK")), ("16", "THERE (küçük parça)", None, Y("THERE_DESEN"))]),
 ("D · Köşe / yay / bütün halı → şimdilik yalnız dosya olarak saklanır", (238, 238, 238), [
   ("17", "BULUT (oval köşe)", P("LZ02"), Y("BULUT_DESEN")), ("18", "GİNG (yuvarlak)", None, Y("GING_MODEL")),
   ("19", "YENİ DAMLA 160×160", None, Y("YENI_DAMLA_MODEL_160x160")), ("20", "DENİZYILDIZI 114×300", None, Y("DENIZYILDIZI_DESEN"))]),
 ("E · Nakış: programda var, gerçek dikiş dosyası geldi → DÜZELSİN", (255, 240, 215), [
   ("21", "79.01 çiçek", PN("79_01"), YN("00007901")), ("22", "82.01", PN("82_01"), YN("00008201")),
   ("23", "77.03 GG (logo?)", PN("77_03"), YN("00007703"))]),
 ("F · Nakış: programda yok → EKLENSİN", (225, 235, 255), [
   ("24", "81.02 yay", PN("81_01"), YN("00008102")), ("25", "85.03 yay", None, YN("00008503")),
   ("26", "86.03 iki karo", None, YN("00008603")), ("27", "83.01–83.03 çizgi", None, YN("00008302"))]),
 ("G · KONMAYACAK", (255, 225, 225), [
   ("28", "78.01 marka logosu", None, YN("00007801")), ("29", "80.01 marka logosu", None, YN("00008001")),
   ("30", "83.04 dosya boş", None, None)]),
]
K = 170; KART = 2 * K + 30
sut = 4
satir_y = []
H = 30
for _, _, ogeler in bolumler:
    H += 50 + ((len(ogeler) + sut - 1) // sut) * (K + 60)
W = sut * (KART + 16) + 30
S = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(S)
y = 20
def kutu(p, x, y):
    d.rectangle([x, y, x + K, y + K], outline=(210, 210, 210), fill="white")
    if p is None or not Path(p).exists():
        d.text((x + K // 2 - 20, y + K // 2 - 8), "—", fill=(150, 150, 150), font=F(18)); return
    im = Image.open(p).convert("RGB"); im.thumbnail((K - 6, K - 6))
    S.paste(im, (x + (K - im.width) // 2, y + (K - im.height) // 2))
for baslik, renk, ogeler in bolumler:
    d.rectangle([10, y, W - 10, y + 36], fill=renk); d.text((20, y + 8), baslik, fill="black", font=FB(19)); y += 48
    for i, (no, ad, sol, sag) in enumerate(ogeler):
        x = 20 + (i % sut) * (KART + 16); yy = y + (i // sut) * (K + 60)
        kutu(sol, x, yy); kutu(sag, x + K + 10, yy)
        d.text((x, yy + K + 6), f"{no}. {ad}", fill="black", font=FB(15))
        d.text((x, yy + K + 26), "program  |  sizin dosya", fill=(120, 120, 120), font=F(12))
    y += ((len(ogeler) + sut - 1) // sut) * (K + 60)
S.save(sys.argv[2], quality=86); print(S.size)
