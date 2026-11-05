"""Fotoğraflı modeller için temiz fotoğraf + bölge haritası (etiket PNG) üretir. Yalnız geliştirmede çalışır (OpenCV)."""
import cv2, numpy as np, sys, os
CIK = sys.argv[1] if len(sys.argv) > 1 else 'cikti'
os.makedirs(CIK, exist_ok=True)

def oku(k): return cv2.imread(k + '.jpg')
def lab(im): return cv2.cvtColor(im.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
def dik(sh, x0, y0, x1, y1, kes=0):
    """Dikdörtgen (köşeleri kes kadar 45° kesik) maskesi."""
    m = np.zeros(sh[:2], np.uint8)
    if kes <= 0:
        m[y0:y1, x0:x1] = 1; return m
    p = np.array([[x0 + kes, y0], [x1 - kes, y0], [x1, y0 + kes], [x1, y1 - kes], [x1 - kes, y1], [x0 + kes, y1],
                  [x0, y1 - kes], [x0, y0 + kes]], np.int32)
    cv2.fillPoly(m, [p], 1); return m
def stadyum(sh, x0, y0, x1, y1):
    m = np.zeros(sh[:2], np.uint8); r = (x1 - x0) / 2; cx = (x0 + x1) / 2
    cv2.rectangle(m, (x0, int(y0 + r)), (x1, int(y1 - r)), 1, -1)
    cv2.circle(m, (int(cx), int(y0 + r)), int(r), 1, -1); cv2.circle(m, (int(cx), int(y1 - r)), int(r), 1, -1)
    return m
def kaydet(k, im, et):
    cv2.imwrite(f'{CIK}/{k}.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 88])
    cv2.imwrite(f'{CIK}/{k}.png', et.astype(np.uint8))
    # kontrol görüntüsü
    renk = np.array([[0, 0, 0], [0, 0, 255], [0, 200, 0], [255, 0, 0], [0, 220, 220], [220, 0, 220]], np.uint8)
    kon = cv2.addWeighted(im, .45, renk[et], .55, 0)
    cv2.imwrite(f'{CIK}/kontrol_{k}.jpg', cv2.resize(kon, None, fx=.5, fy=.5))
def zemin_doldur(im, maske, kayma):
    """Maskelenen yeri (pirinç köşe) yatayda kaydırılmış zemin dokusuyla doldurur, kenarı yumuşatır."""
    kaynak = np.roll(im, kayma, axis=1)
    yum = cv2.GaussianBlur(cv2.dilate(maske, np.ones((5, 5), np.uint8)).astype(np.float32), (0, 0), 2)[..., None]
    return (im * (1 - yum) + kaynak * yum).astype(np.uint8)

def zemin_doldur2(im, maske, dy):
    kaynak = np.roll(im, dy, axis=0)
    yum = cv2.GaussianBlur(cv2.dilate(maske, np.ones((7, 7), np.uint8)).astype(np.float32), (0, 0), 2)[..., None]
    return (im * (1 - yum) + kaynak * yum).astype(np.uint8)

# RNO-006: oval, Grek nakış şeridi
k = 'RNO-006'; im = oku(k); L = lab(im)
hali = stadyum(im.shape, 137, 180, 667, 1019) & (L[..., 2] > 5).astype(np.uint8)
hali = cv2.morphologyEx(hali, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
hali = stadyum(im.shape, 138, 181, 666, 1018) | 0  # şekil temiz, zemin sızmasın
serit = np.zeros_like(hali); serit[803:891] = 1; serit &= hali
bl = cv2.GaussianBlur(L[..., 0], (0, 0), 1)
iplik = serit & (bl < np.percentile(bl[serit > 0], 60) - 3).astype(np.uint8)
iplik[:, :170] = 0; iplik[:, 635:] = 0
et = hali.astype(np.uint8); et[serit > 0] = 2; et[iplik > 0] = 3
kaydet(k, im, et)

# RNO-007: siyah lazer desen bant, gümüş çerçeve, krem orta; pirinç köşeler gümüşe çevrilir
k = 'RNO-007'; im = oku(k); L = lab(im)
hali = dik(im.shape, 150, 148, 650, 1019)
pirinc = ((L[..., 2] > 14) & (L[..., 0] > 35)).astype(np.uint8)
# köşe parçalarının taşan yerleri (halı dışı) zeminle doldurulur, halı içindekiler gümüşleşir
kose = np.zeros_like(pirinc)
for (x0, y0) in [(138, 135), (590, 135), (138, 945), (590, 945)]:
    kose[y0:y0 + 85, x0:x0 + 75] = 1
kose[135:1032, 138:156] = 1; kose[135:1032, 644:664] = 1; kose[135:152, 138:664] = 1; kose[1015:1032, 138:664] = 1
yakin = cv2.dilate(hali, np.ones((61, 61), np.uint8))
disari = ((kose | (cv2.dilate((L[..., 2] > 8).astype(np.uint8), np.ones((9, 9), np.uint8)) & yakin)) & (1 - hali)).astype(np.uint8)
ustk = disari.copy(); ustk[600:] = 0; altk = disari.copy(); altk[:600] = 0
im = cv2.inpaint(im, cv2.dilate(disari, np.ones((5, 5), np.uint8)), 6, cv2.INPAINT_TELEA)
im = (im.astype(np.int16) + (np.random.default_rng(1).normal(0, 2.2, im.shape[:2])[..., None] * cv2.dilate(disari, np.ones((5, 5), np.uint8))[..., None])).clip(0, 255).astype(np.uint8)
ic = cv2.dilate(hali, np.ones((9, 9), np.uint8)) & (dik(im.shape, 168, 165, 631, 999) == 0)  # bant içi altın süsler kalır
imL = lab(im); g = imL.copy(); g[..., 1] = 0; g[..., 2] = 0
gri = (cv2.cvtColor(g, cv2.COLOR_LAB2BGR) * 255).clip(0, 255).astype(np.uint8)
im[ic > 0] = gri[ic > 0]; L = lab(im)
bant = dik(im.shape, 168, 165, 631, 999) - dik(im.shape, 219, 219, 581, 943)
bl = cv2.GaussianBlur(L[..., 0], (0, 0), 0.8)
siyah = bant & (bl < 30).astype(np.uint8)
susler = bant & ((L[..., 2] > 14) & (L[..., 0] > 30)).astype(np.uint8)
susler = cv2.dilate(susler, np.ones((7, 7), np.uint8))
orta = dik(im.shape, 235, 235, 563, 926)
et = hali.astype(np.uint8)          # 1 = gümüş çerçeve (dış şerit + iç şerit + desen delikleri)
et[siyah > 0] = 2                   # 2 = lazer desenli bant
et[orta > 0] = 3                    # 3 = orta
et[susler > 0] = 0
kaydet(k, im, et)

# RNO-008: kesik köşe (sekizgen), hasır desen halka; pirinç köşe plakaları zeminle doldurulur
k = 'RNO-008'; im = oku(k); L = lab(im)
KES = {0: 94, 3: 92, 46: 66, 96: 52}
def sek(x0, y0, x1, y1, d):  # dış sekizgenden d içeri ofset (köşe kesikleri fotoğraftan ölçüldü)
    return dik(im.shape, x0 + d, y0 + d, x1 - d, y1 - d, KES[d])
dis = sek(121, 187, 685, 993, 0)
def doldur(im, maske, dy, dx):
    kaynak = np.roll(np.roll(im, dy, axis=0), dx, axis=1)
    yum = cv2.GaussianBlur(cv2.dilate(maske, np.ones((7, 7), np.uint8)).astype(np.float32), (0, 0), 2.5)[..., None]
    return (im * (1 - yum) + kaynak * yum).astype(np.uint8)
yan = np.zeros_like(dis); yan[172:1008, 98:122] = 1
im = doldur(im, yan, 0, 32)
yan = np.zeros_like(dis); yan[172:1008, 684:708] = 1
im = doldur(im, yan, 0, -32)
ust = np.zeros_like(dis); ust[176:420, 118:688] = 1; ust &= (1 - dis)
alt = np.zeros_like(dis); alt[760:1006, 118:688] = 1; alt &= (1 - dis)
im = doldur(im, ust, 112, 0); im = doldur(im, alt, -112, 0)
L = lab(im)
halka = sek(121, 187, 685, 993, 46) - sek(121, 187, 685, 993, 96)
bl = cv2.GaussianBlur(L[..., 0], (0, 0), 0.8)
acik = (bl > 48).astype(np.uint8)
kenar = dis - sek(121, 187, 685, 993, 3)
et = dis.astype(np.uint8)                       # 1 = dış bant ve orta (aynı malzeme ayrı bölge aşağıda)
et[sek(121, 187, 685, 993, 96) > 0] = 3          # 3 = orta
et[(halka & acik) > 0] = 2                       # 2 = hasır desen
et[(halka & (1 - acik)) > 0] = 0                 # delikler: altı görünür, dokunulmaz
et[(kenar & acik) > 0] = 2                       # dış biye desenle aynı renk
acik2 = cv2.dilate(((bl > 42) & (dis > 0)).astype(np.uint8) & cv2.morphologyEx((et == 2).astype(np.uint8), cv2.MORPH_DILATE, np.ones((9, 9), np.uint8)), np.ones((3, 3), np.uint8))
et[(acik2 > 0) & ((et == 1) | (et == 3))] = 2   # halkanın açık kenar biyesi
kaydet(k, im, et)

# RNO-009: altın çerçeve + altın lazer desen bant + ince altın çizgi + krem orta
k = 'RNO-009'; im = oku(k); L = lab(im)
hali = dik(im.shape, 164, 245, 639, 976)
cerceve = hali - dik(im.shape, 172, 253, 631, 967)
cizgi = dik(im.shape, 231, 305, 573, 911) - dik(im.shape, 239, 313, 565, 903)
bant = dik(im.shape, 172, 253, 631, 967) - dik(im.shape, 231, 305, 573, 911)
bl = cv2.GaussianBlur(L[..., 0], (0, 0), 0.8)
desen = bant & (bl > 45).astype(np.uint8)
et = np.zeros(im.shape[:2], np.uint8)
et[desen > 0] = 2; et[(cerceve | cizgi) > 0] = 1
et[dik(im.shape, 239, 313, 565, 903) > 0] = 3
kaydet(k, im, et)

# RNO-010: koyu dış bant + Bienca eskitme bant + koyu orta
k = 'RNO-010'; im = oku(k)
et = dik(im.shape, 74, 79, 731, 1120).astype(np.uint8)
et[dik(im.shape, 132, 138, 672, 1061) > 0] = 2
et[dik(im.shape, 189, 195, 614, 1004) > 0] = 3
kaydet(k, im, et)

# RNO-011: biye + Bienca eskitme bant + bej orta
k = 'RNO-011'; im = oku(k)
et = dik(im.shape, 117, 131, 785, 1078).astype(np.uint8)
et[dik(im.shape, 129, 143, 768, 1063) > 0] = 2
et[dik(im.shape, 197, 214, 697, 993) > 0] = 3
kaydet(k, im, et)

# RNO-012: gri zemin + iki siyah simli bant
k = 'RNO-012'; im = oku(k); L = lab(im)
hali = np.zeros(im.shape[:2], np.uint8)
cv2.fillPoly(hali, [np.array([[138, 110], [776, 108], [790, 1130], [112, 1132]], np.int32)], 1)
bl = cv2.GaussianBlur(L[..., 0], (0, 0), 4)
siyah = hali & (bl < 38).astype(np.uint8)
siyah = cv2.morphologyEx(siyah, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
et = hali.astype(np.uint8); et[siyah > 0] = 2
kaydet(k, im, et)
print('tamam')
