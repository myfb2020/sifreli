import sys, json, numpy as np
from PIL import Image
sys.path.insert(0, __import__('os').path.dirname(__file__)); import pencere
def radyal(g, pxcm):
    g = g - g.mean(); n = min(g.shape); g = g[:n, :n] * np.outer(np.hanning(n), np.hanning(n))
    F = np.abs(np.fft.fftshift(np.fft.fft2(g))) ** 2
    y, x = np.indices(F.shape); r = np.hypot(x - n / 2, y - n / 2) / n * pxcm  # devir / cm
    kenar = np.geomspace(0.15, 6, 40); v = []
    for a, b in zip(kenar[:-1], kenar[1:]):
        m = (r >= a) & (r < b); v.append(np.log(F[m].mean() + 1e-9) if m.any() else np.nan)
    v = np.array(v); return v - np.nanmean(v)
D, kl = sys.argv[1], sys.argv[2]
olc = json.load(open(D + '/olcek.json'))
for kod, n in [x.split('=') for x in sys.argv[3].split(',')]:
    ad = 'bienca_' + kod.lower(); e = Image.open(f'{D}/{ad}.jpg').convert('L'); e = np.asarray(e, float)
    pe = e.shape[1] / olc[ad]; ref = radyal(e, pe)
    a = np.load(f'{kl}/{n}.npy').astype(np.float32); y0, x0 = pencere.en_iyi(a, 1600)
    g = np.sqrt(np.maximum(a[y0:y0 + 1600, x0:x0 + 1600].mean(2), 0)); g = g / g.mean()
    best = None
    for p in np.geomspace(15, 200, 120):
        v = radyal(g, p); m = ~np.isnan(v) & ~np.isnan(ref)
        hata = np.mean((v[m] - ref[m]) ** 2)
        if best is None or hata < best[0]: best = (hata, p)
    print(kod, n, 'eski px/cm', round(pe, 1), '-> yeni tahmini px/cm', round(best[1], 1), 'hata', round(best[0], 3))
