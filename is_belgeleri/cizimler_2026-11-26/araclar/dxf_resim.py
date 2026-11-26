"""DXF → siyah-beyaz önizleme PNG + ölçü (cm). Kullanım: python -I dxf_resim.py GIRDI_KLASORU CIKTI_KLASORU"""
import json, sys
from pathlib import Path
import ezdxf
from ezdxf import path as ezpath
from PIL import Image, ImageDraw
gir, cik = Path(sys.argv[1]), Path(sys.argv[2]); cik.mkdir(parents=True, exist_ok=True)
bilgi = {}
for dosya in sorted(gir.glob("*.dxf")):
    d = ezdxf.readfile(dosya)
    birim = d.header.get("$INSUNITS")
    cm = {4: 0.1, 5: 1.0, 6: 100.0, 1: 2.54}.get(birim, 0.1)
    konturlar, acik = [], 0
    for e in d.modelspace():
        try:
            p = ezpath.make_path(e)
        except Exception:
            continue
        for alt in p.sub_paths():
            pts = [(v.x * cm, v.y * cm) for v in alt.flattening(0.02 / cm)]
            if len(pts) > 1:
                konturlar.append(pts)
                if pts[0] != pts[-1] and abs(pts[0][0]-pts[-1][0]) + abs(pts[0][1]-pts[-1][1]) > 0.05: acik += 1
    xs = [x for k in konturlar for x, _ in k]; ys = [y for k in konturlar for _, y in k]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    olc = 900 / max(w, h)
    W, H = int(w * olc) + 20, int(h * olc) + 20
    im = Image.new("L", (W, H), 255); dr = ImageDraw.Draw(im)
    for k in konturlar:
        dr.line([((x - x0) * olc + 10, (y1 - y) * olc + 10) for x, y in k], fill=0, width=1)
    im.save(cik / (dosya.stem + ".png"))
    bilgi[dosya.stem] = {"en_cm": round(w, 1), "boy_cm": round(h, 1), "kontur": len(konturlar), "acik_kontur": acik,
                         "birim": birim, "katman": sorted({e.dxf.layer for e in d.modelspace()})[:6]}
    print(dosya.stem, bilgi[dosya.stem])
(cik / "bilgi.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1))
