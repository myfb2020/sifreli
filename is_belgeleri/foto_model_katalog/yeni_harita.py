import cv2, numpy as np, sys
U, CIK = sys.argv[1], sys.argv[2]
def lab(im): return cv2.cvtColor(im.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
def kaydet(k, im, et):
    cv2.imwrite(f'{CIK}/{k}.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 86]); cv2.imwrite(f'{CIK}/{k}.png', et)
    renk = np.array([[0,0,0],[0,0,255],[0,200,0],[255,0,0]], np.uint8)
    cv2.imwrite(f'{CIK}/k_{k}.jpg', cv2.resize(cv2.addWeighted(im,.5,renk[et],.5,0), None, fx=.5, fy=.5))
def duzle(f, kose, W, H, pay=12):
    im = cv2.imread(f'{U}/{f}-image.jpg')
    M = cv2.getPerspectiveTransform(np.float32(kose), np.float32([[pay,pay],[W-pay,pay],[W-pay,H-pay],[pay,H-pay]]))
    return cv2.warpPerspective(im, M, (W, H), borderMode=cv2.BORDER_REPLICATE), pay
def bant_orta(im, hali, delik_esik):
    """Delikler (koyu/fon) → bant halkası; içi orta."""
    L = cv2.GaussianBlur(lab(im)[..., 0], (0, 0), 1)
    yerel = cv2.GaussianBlur(L, (0, 0), 12)
    delik = ((L < yerel - delik_esik) & (hali > 0)).astype(np.uint8)
    yogun = cv2.GaussianBlur(delik.astype(np.float32), (0, 0), 18)
    bant = (yogun > 0.06).astype(np.uint8) & hali
    bant = cv2.morphologyEx(bant, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    ic = ((hali > 0) & (bant == 0)).astype(np.uint8)
    n, lb, st, _ = cv2.connectedComponentsWithStats(ic)
    h, w = ic.shape; orta = (lb == lb[h // 2, w // 2]).astype(np.uint8)
    x, y, ww, hh = cv2.boundingRect(orta); orta = np.zeros_like(orta); orta[y:y+hh, x:x+ww] = 1
    return delik, bant, orta

# BNA-027: krem + yoğun altın Bienca, lazer desen bant (foto 1)
im, p = duzle('9edb3643', [[170,210],[1392,203],[1432,1822],[96,1812]], 900, 1180)
hali = np.zeros(im.shape[:2], np.uint8); hali[p:-p, p:-p] = 1
bant = np.zeros_like(hali); bant[79:1055, 70:830] = 1
orta = np.zeros_like(hali); orta[186:940, 190:700] = 1; bant[orta > 0] = 0
L = cv2.GaussianBlur(lab(im)[..., 0], (0, 0), 1); yerel = cv2.GaussianBlur(L, (0, 0), 6)
renk = lab(im); doy = np.hypot(renk[..., 1], renk[..., 2])
# delik: koyu (alttaki zemin) ya da altın varaksız düz beyaz/gri (tahta) ve keskin kenarlı
delik = (((L < yerel - 12) | ((doy < 4) & (np.abs(L - yerel) > 6))) & (bant > 0)).astype(np.uint8)
delik = cv2.morphologyEx(delik, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
et = hali.copy(); et[bant > 0] = 2; et[delik > 0] = 0; et[orta > 0] = 3
kaydet('BNA-027', im, et)

# BNA-028: altın biye + Bienca + lazer desen (foto 8), dik çevrilir
im, p = duzle('210b65e6', [[256,370],[1724,394],[1736,1360],[280,1376]], 1200, 812)
im = cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)
hali = np.zeros(im.shape[:2], np.uint8); hali[p:-p, p:-p] = 1
biye = hali.copy(); b = p + 34; biye[b:-b, b:-b] = 0
icm = hali.copy(); icm[:b] = 0; icm[-b:] = 0; icm[:, :b] = 0; icm[:, -b:] = 0
delik, bant, orta = bant_orta(im, icm, 14)
bant &= (orta == 0)
et = hali.copy(); et[bant > 0] = 2; et[(delik > 0) & (bant > 0)] = 0; et[orta > 0] = 3; et[biye > 0] = 1
kaydet('BNA-028', im, et)

# RNO-013: nakışlı Rono yakın görünüm (foto 6): motif kutuları kenar yoğunluğundan, iplik kutu içinde açık çizgiler
im = cv2.imread(f'{U}/dd0bae02-image.jpg'); im = cv2.resize(im, (900, 1200), interpolation=cv2.INTER_AREA)
Lb = lab(im); L = Lb[..., 0]
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0, 3), cv2.Sobel(g, cv2.CV_32F, 0, 1, 3))
e = cv2.GaussianBlur(mag, (0, 0), 12); e = e / np.percentile(e, 99)
kutu = (e > 0.8).astype(np.uint8)
kutu = cv2.morphologyEx(kutu, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
n, lb, st, _ = cv2.connectedComponentsWithStats(kutu)
motif = np.zeros_like(kutu)
for i in range(1, n):
    if st[i, 4] > 6000:
        cs, _ = cv2.findContours((lb == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(motif, [cv2.convexHull(cs[0])], -1, 1, -1)
fark = L - cv2.GaussianBlur(L, (0, 0), 7)
iplik = ((fark > 2.5) & (motif > 0)).astype(np.uint8)
iplik = cv2.morphologyEx(iplik, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
iplik = cv2.morphologyEx(iplik, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
et = np.ones(im.shape[:2], np.uint8); et[iplik > 0] = 2
kaydet('RNO-013', im, et)
print('motif kutusu', n - 1)
