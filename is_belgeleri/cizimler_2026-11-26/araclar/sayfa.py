"""Klasördeki PNG'leri etiketli tabakaya dizer. python -I sayfa.py KLASOR CIKTI [sutun] [kutu]"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
k = Path(sys.argv[1]); sut = int(sys.argv[3]) if len(sys.argv) > 3 else 4; kutu = int(sys.argv[4]) if len(sys.argv) > 4 else 330
bilgi = json.loads((k / "bilgi.json").read_text()) if (k / "bilgi.json").exists() else {}
dosyalar = sorted(k.glob("*.png"))
f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
sat = (len(dosyalar) + sut - 1) // sut
S = Image.new("RGB", (sut * (kutu + 20) + 20, sat * (kutu + 60) + 20), "white"); d = ImageDraw.Draw(S)
for i, p in enumerate(dosyalar):
    im = Image.open(p).convert("RGB"); im.thumbnail((kutu, kutu))
    x, y = 20 + (i % sut) * (kutu + 20), 20 + (i // sut) * (kutu + 60)
    d.rectangle([x - 2, y - 2, x + kutu + 2, y + kutu + 2], outline=(200, 200, 200))
    S.paste(im, (x + (kutu - im.width) // 2, y + (kutu - im.height) // 2))
    b = bilgi.get(p.stem, {})
    d.text((x, y + kutu + 6), f"{i+1}. {p.stem[:34]}", fill="black", font=f)
    if b: d.text((x, y + kutu + 26), f"{b['en_cm']} × {b['boy_cm']} cm", fill=(90, 90, 90), font=f)
S.save(sys.argv[2], quality=88); print(S.size)
