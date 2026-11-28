import sys, os, glob
from PIL import Image, ImageDraw, ImageFont
kl, cikis = sys.argv[1], sys.argv[2]
os.makedirs(cikis, exist_ok=True)
ds = sorted(glob.glob(kl + '/*.jpg'))
ust = 30; W, H = 330, 220
f = ImageFont.load_default(size=22)
for s in range(0, len(ds), ust):
    p = Image.new('RGB', (6 * W, 5 * (H + 26)), 'white'); d = ImageDraw.Draw(p)
    for k, y in enumerate(ds[s:s + ust]):
        im = Image.open(y); im.draft('RGB', (W * 2, H * 2)); im = im.convert('RGB'); im.thumbnail((W - 6, H - 6))
        x0, y0 = (k % 6) * W, (k // 6) * (H + 26)
        p.paste(im, (x0 + 3, y0 + 3)); d.text((x0 + 5, y0 + H), os.path.basename(y)[4:8], fill='black', font=f)
    p.save(f'{cikis}/sayfa_{s // ust + 1:02d}.jpg', quality=80)
print(len(ds))
