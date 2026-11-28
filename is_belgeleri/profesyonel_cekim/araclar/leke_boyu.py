import sys, json, numpy as np
from PIL import Image
sys.path.insert(0, __import__('os').path.dirname(__file__)); import pencere
def uzunluk(g):
    g = g - g.mean(); g = g / (g.std() + 1e-9)
    F = np.fft.fft2(g); ac = np.real(np.fft.ifft2(F * np.conj(F))) / g.size
    ac = np.fft.fftshift(ac); h, w = ac.shape; y, x = np.indices(ac.shape); r = np.hypot(x - w / 2, y - h / 2).astype(int)
    prof = np.bincount(r.ravel(), ac.ravel()) / np.bincount(r.ravel())
    return float(np.argmax(prof < 0.5))  # özilişkinin yarıya düştüğü uzaklık (px)
D, kl = sys.argv[1], sys.argv[2]; olc = json.load(open(D + '/olcek.json'))
for kod, n, hip in [x.split('=') for x in sys.argv[3].split(',')]:
    ad = 'bienca_' + kod.lower(); e = np.asarray(Image.open(f'{D}/{ad}.jpg').convert('L'), float)
    pe = e.shape[1] / olc[ad]; le = uzunluk(e[:min(e.shape), :min(e.shape)]) / pe
    a = np.load(f'{kl}/{n}.npy').astype(np.float32); y0, x0 = pencere.en_iyi(a, 1600)
    g = np.sqrt(np.maximum(a[y0:y0 + 1600, x0:x0 + 1600].mean(2), 0)); ln = uzunluk(g)
    print(kod, n, f'eski leke {le:.2f} cm', f'yeni leke {ln:.0f} px', '-> px/cm', round(ln / le, 1), '| varsayım', hip)
