"""Katalog fotoğrafından bölge haritası: 1 dış kenar, 2 desenli bant, 3 orta (0 = dokunulmaz: zemin, delikler)."""
import cv2, numpy as np, sys, json
sys.path.insert(0, sys.argv[1]); from oto import hali, K
S = sys.argv[1]; CIK = S + '/kat/cikti'
import os; os.makedirs(CIK, exist_ok=True)
OZEL = json.load(open(S + '/kat/ozel.json')) if os.path.exists(S + '/kat/ozel.json') else {}

def enerji(im, m):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp = np.abs(g - cv2.GaussianBlur(g, (0, 0), 1.5)); e = cv2.GaussianBlur(hp, (0, 0), 6) * m
    return e / (np.percentile(e[m > 0], 98) + 1e-3)

def yap(k):
    im = cv2.imread(K + k + '.jpg'); oz = OZEL.get(k, {}); m = hali(im, oz.get('hull', True))
    if oz.get('ic_zemin'):  # halı beyaz fon üstünde: fonun rengine yakın pikseller çıkar
        Lb = cv2.cvtColor(im.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
        ys, xs = np.where(m > 0); fon = np.median(Lb[ys.min():ys.min() + 6, xs.min():xs.min() + 6].reshape(-1, 3), 0)
        f = (np.linalg.norm(cv2.GaussianBlur(Lb, (0, 0), 2) - fon, axis=2) > 10).astype(np.uint8) & m
        f = cv2.morphologyEx(f, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n_, lb_, st_, _ = cv2.connectedComponentsWithStats(f); f = (lb_ == 1 + np.argmax(st_[1:, 4])).astype(np.uint8)
        cs, _ = cv2.findContours(f, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); m = np.zeros_like(m)
        cv2.drawContours(m, [cv2.convexHull(max(cs, key=cv2.contourArea))], -1, 1, -1)
    if oz.get('oval'):  # oval halı: dikdörtgen sınırının içine çizilen stadyum
        ys, xs = np.where(m > 0); x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        r = (x1 - x0) // 2; cx = (x0 + x1) // 2; m = np.zeros_like(m)
        cv2.rectangle(m, (x0, y0 + r), (x1, y1 - r), 1, -1)
        cv2.circle(m, (cx, y0 + r), r, 1, -1); cv2.circle(m, (cx, y1 - r), r, 1, -1)
    m = cv2.erode(m, np.ones((3, 3), np.uint8))
    e = enerji(im, m)
    bant = ((e > oz.get('esik', 0.42)) & (m > 0)).astype(np.uint8)
    bant = cv2.morphologyEx(bant, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    bant = cv2.morphologyEx(bant, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    dusuk = (m > 0) & (bant == 0)
    n, lb, st, _ = cv2.connectedComponentsWithStats(dusuk.astype(np.uint8))
    h, w = m.shape; cx, cy = w // 2, h // 2
    orta = np.zeros_like(m)
    if 'orta' in oz:  # elle dikdörtgen
        x0, y0, x1, y1 = oz['orta']; orta[y0:y1, x0:x1] = 1; orta &= m
    elif 'orta_elips' in oz:
        cx_, cy_, ax, ay = oz['orta_elips']; cv2.ellipse(orta, (cx_, cy_), (ax, ay), 0, 0, 360, 1, -1); orta &= m
    elif n > 1:
        i = lb[cy, cx] if lb[cy, cx] else 1 + np.argmax(st[1:, 4])
        orta = (lb == i).astype(np.uint8)
        cs, _ = cv2.findContours(orta, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        orta = np.zeros_like(m); cv2.drawContours(orta, [max(cs, key=cv2.contourArea)], -1, 1, -1)
    dis = (dusuk & (orta == 0)).astype(np.uint8)
    dis = cv2.morphologyEx(dis, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    bant = ((m > 0) & (orta == 0) & (dis == 0)).astype(np.uint8)
    L = cv2.cvtColor(im.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)[..., 0]
    bl = cv2.GaussianBlur(L, (0, 0), 0.7)
    if bant.sum():
        esik = np.percentile(bl[bant > 0], oz.get('delik_yuzde', 22))
        delik = (bant > 0) & (bl < min(esik, oz.get('delik_L', 40)))
    else:
        delik = np.zeros_like(bant, bool)
    et = np.zeros(m.shape, np.uint8)
    if oz.get('tek_zemin'):
        orta = ((orta | dis) > 0).astype(np.uint8); dis[:] = 0
        if k in ('BNA-017', 'BNA-023'):  # tek malzeme, desen = delik: bütün halı tek bölge
            orta = m.copy(); bant[:] = 0
    if oz.get('dis_yok'):
        dis[:] = 0
    if dis.sum() > 0.01 * m.sum(): et[dis > 0] = 1
    else: bant |= dis
    et[(bant > 0) & ~delik] = 2
    et[orta > 0] = 3
    if k in ('BNA-017', 'BNA-023'):
        et[delik & (m > 0)] = 0
        bl2 = cv2.GaussianBlur(L, (0, 0), 0.7); et[(bl2 < 35) & (m > 0)] = 0
    cv2.imwrite(f'{CIK}/{k}.png', et)
    cv2.imwrite(f'{CIK}/{k}.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    renk = np.array([[0, 0, 0], [0, 0, 255], [0, 200, 0], [255, 0, 0]], np.uint8)
    kon = cv2.addWeighted(im, .5, renk[et], .5, 0)
    return cv2.resize(kon, (208, 254))

if __name__ == '__main__':
    kod = sys.argv[2:]; out = [yap(k) for k in kod]
    for i, k in enumerate(kod): cv2.putText(out[i], k, (4, 248), 0, .5, (255, 255, 255), 2)
    sat = [np.hstack(out[i:i + 8] + [np.zeros_like(out[0])] * (8 - len(out[i:i + 8]))) for i in range(0, len(out), 8)]
    cv2.imwrite(CIK + '/hepsi.jpg', np.vstack(sat))
