"""Nakış dosyası (DSZ/DST…) → PNG + ölçü. python -I dsz_resim.py GIRDI CIKTI"""
import json, sys
from pathlib import Path
import pyembroidery as pe
from PIL import Image, ImageDraw
gir, cik = Path(sys.argv[1]), Path(sys.argv[2]); cik.mkdir(parents=True, exist_ok=True)
bilgi = {}
for p in sorted(gir.iterdir()):
    try:
        e = pe.read(str(p))
    except Exception as h:
        print(p.name, "OKUNAMADI", h); continue
    if e is None or not e.stitches:
        print(p.name, "boş"); continue
    x0, y0, x1, y1 = e.bounds()  # 0.1 mm
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        print(p.name, "ölçüsüz", e.bounds(), len(e.stitches)); continue
    w, h = (x1 - x0) / 100, (y1 - y0) / 100  # cm
    olc = 700 / max(x1 - x0, y1 - y0)
    im = Image.new("RGB", (int((x1 - x0) * olc) + 20, int((y1 - y0) * olc) + 20), "white"); d = ImageDraw.Draw(im)
    renkler = [(30, 30, 30), (180, 120, 20), (40, 90, 170), (170, 40, 40), (40, 140, 60), (120, 60, 150)]
    ri, onceki = 0, None
    for x, y, komut in e.stitches:
        k = komut & pe.COMMAND_MASK
        if k == pe.COLOR_CHANGE: ri += 1; onceki = None; continue
        if k in (pe.JUMP, pe.TRIM, pe.STOP, pe.END): onceki = None; continue
        nok = ((x - x0) * olc + 10, (y - y0) * olc + 10)
        if onceki: d.line([onceki, nok], fill=renkler[ri % len(renkler)], width=1)
        onceki = nok
    ad = p.stem
    im.save(cik / f"{ad}.png")
    bilgi[ad] = {"en_cm": round(w, 1), "boy_cm": round(h, 1), "dikis": len(e.stitches), "renk": e.count_color_changes() + 1}
    print(ad, bilgi[ad])
(cik / "bilgi.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1))
