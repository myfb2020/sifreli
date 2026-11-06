"""Lazer desen DXF'lerini (kesim konturları) programın desen şeridine çevirir: L PNG, 255 = delik.
Uzun kenar yatay; kısa kenar = bant genişliği. Kullanım: python lazer_dxf_cevir.py girdi_klasoru cikti_klasoru"""
import json, sys
from pathlib import Path
import ezdxf
from ezdxf import path as ezpath
from PIL import Image, ImageDraw

DESENLER = {  # dosya adı parçası → (kod, ad)
    "BOMBA": ("LZ01", "Bomba"), "BULUT": ("LZ02", "Bulut"), "DAMA": ("LZ03", "Dama"), "KI_A": ("LZ04", "Kısa"),
    "LI_NE": ("LZ05", "Line"), "RI_VA": ("LZ06", "Rıva"), "KO_S_EM": ("LZ07", "Köşem"), "MAHSUN": ("LZ08", "Mahsun"),
}
PX_CM = 40
gir, cik = Path(sys.argv[1]), Path(sys.argv[2]); cik.mkdir(parents=True, exist_ok=True)
bilgi = {}
for dosya in sorted(gir.glob("*.dxf")):
    eslesen = next((v for k, v in DESENLER.items() if k in dosya.name), None)
    if not eslesen:
        continue
    kod, ad = eslesen
    d = ezdxf.readfile(dosya)
    cm = 0.1 if d.header.get("$INSUNITS") == 4 else 1.0  # mm → cm
    konturlar = []
    for e in d.modelspace():
        try:
            p = ezpath.make_path(e)
        except Exception:
            continue
        for alt in p.sub_paths():
            pts = [(v.x * cm, v.y * cm) for v in alt.flattening(0.01 / cm)]
            if len(pts) > 2:
                konturlar.append(pts)
    xs = [x for k in konturlar for x, _ in k]; ys = [y for k in konturlar for _, y in k]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    # dış sınır çizgisi (bütün alanı kaplayan dikdörtgen) delik değildir
    konturlar = [k for k in konturlar if not ((max(x for x, _ in k) - min(x for x, _ in k)) > 0.97 * w and
                                              (max(y for _, y in k) - min(y for _, y in k)) > 0.97 * h)]
    W, H = round(w * PX_CM), round(h * PX_CM)
    m = Image.new("L", (W, H), 0)
    for k in konturlar:  # çift/tek kuralı: iç içe konturda iç kısım yeniden dolu olur
        tek = Image.new("L", (W, H), 0)
        ImageDraw.Draw(tek).polygon([((x - x0) * PX_CM, (y1 - y) * PX_CM) for x, y in k], fill=255)
        m = Image.frombytes("L", m.size, bytes(a ^ b for a, b in zip(m.tobytes(), tek.tobytes())))
    if H > W:
        m = m.rotate(90, expand=True); w, h = h, w
    m.save(cik / f"{kod}.png", optimize=True)
    bilgi[kod] = {"ad": ad, "boy_cm": round(w, 1), "en_cm": round(h, 1), "kaynak": dosya.name}
    print(kod, ad, bilgi[kod], len(konturlar))
(cik / "lazer.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1), encoding="utf-8")
