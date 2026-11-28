import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import gelistir as g
from PIL import Image, ImageDraw, ImageFont
kl, cikis, liste, K = sys.argv[1], sys.argv[2], sys.argv[3].split(','), float(sys.argv[4])
etiket = dict(x.split('=') for x in sys.argv[5].split(',')) if len(sys.argv) > 5 else {}
f = ImageFont.load_default(size=26); W = 560; sut = 4
sat = (len(liste) + sut - 1) // sut
p = Image.new('RGB', (W * sut, (W + 70) * sat), 'white'); d = ImageDraw.Draw(p)
for k, n in enumerate(liste):
    a = np.load(f'{kl}/{n}.npy').astype(np.float32) * K; h, w, _ = a.shape
    c = a[h // 2 - 600:h // 2 + 600, w // 2 - 600:w // 2 + 600]
    im = g.srgb(c).resize((W, W), Image.LANCZOS)
    ort = np.array(g.srgb(c.mean((0, 1), keepdims=True)).getpixel((0, 0)))
    x, y = (k % sut) * W, (k // sut) * (W + 70); p.paste(im, (x, y))
    d.rectangle((x + W - 90, y + W + 5, x + W - 10, y + W + 60), fill=tuple(int(v) for v in ort))
    d.text((x + 5, y + W + 5), f'{n} {etiket.get(n, "")}', fill='black', font=f)
    d.text((x + 5, y + W + 35), '#%02x%02x%02x' % tuple(ort), fill='black', font=f)
p.save(cikis, quality=88)
