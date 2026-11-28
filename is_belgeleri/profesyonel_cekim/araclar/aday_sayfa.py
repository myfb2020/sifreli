import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import gelistir as g, pencere
from PIL import Image, ImageDraw, ImageFont
kl, cikis = sys.argv[1], sys.argv[2]
satirlar = [x.split(':') for x in sys.argv[3].split(';')]
F = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; f = ImageFont.truetype(F, 24); fb = ImageFont.truetype(F.replace('Sans', 'Sans-Bold'), 26)
W = 380; sut = 3
p = Image.new('RGB', (W * sut + 20 * (sut - 1), len(satirlar) * (W + 80)), 'white'); d = ImageDraw.Draw(p)
for i, (n, yazi) in enumerate(satirlar):
    a = np.load(f'{kl}/{n}.npy').astype(np.float32)
    y0, x0 = pencere.en_iyi(a, 1600)
    c = a[y0:y0 + 1600, x0:x0 + 1600]
    L = c @ np.array([0.2126, 0.7152, 0.0722]); c = c * (0.30 / np.percentile(L, 55))
    big = g.srgb(c)
    parca = [big.resize((W, W), Image.LANCZOS), big.crop((0, 0, 800, 800)).resize((W, W), Image.LANCZOS),
             Image.open(f'{kl}/../onizleme/DSCF{n}.jpg').convert('RGB').resize((W, int(W * 2944 / 4416)), Image.LANCZOS)]
    y = i * (W + 80)
    for j, im in enumerate(parca): p.paste(im, (j * (W + 20), y + 40))
    d.text((0, y + 5), f'Çekim {n}', fill='black', font=fb); d.text((230, y + 7), yazi, fill='#333', font=f)
p.save(cikis, quality=86); print(p.size)
