import sys
from PIL import Image, ImageDraw, ImageFont
kl, cikis, liste = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
f = ImageFont.load_default(size=26); W = 560; sut = 5
sat = (len(liste) + sut - 1) // sut
p = Image.new('RGB', (W * sut, (W + 40) * sat), 'white'); d = ImageDraw.Draw(p)
for k, n in enumerate(liste):
    im = Image.open(f'{kl}/DSCF{n}.jpg'); e = im.getexif().get_ifd(0x8769); im = im.convert('RGB'); w, h = im.size
    c = im.crop((w // 2 - 900, h // 2 - 900, w // 2 + 900, h // 2 + 900)).resize((W, W))
    x, y = (k % sut) * W, (k // sut) * (W + 40); p.paste(c, (x, y))
    t = e.get(33434); d.text((x + 5, y + W + 5), f'{n}  1/{round(1/t)} ISO{e.get(34855)}', fill='black', font=f)
p.save(cikis, quality=85)
