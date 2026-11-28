import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import doku_yap as d
from PIL import Image
kl, cikis = sys.argv[1], sys.argv[2]; os.makedirs(cikis, exist_ok=True)
PXCM = 128  # yarım boy çekim (dokuma sıklığından)
R = {'RN01': ('1461', 'a09489', 'acik_gri_keten'), 'RN02': ('1493', '676361', 'gri_keten'), 'RN03': ('1471', 'bfad99', 'krem_keten'),
     'RN04': ('1477', '2b2c30', 'antrasit_keten'), 'RN05': ('1466', '7c6d5a', 'vizon_keten'), 'RN06': ('1487', '513b32', 'kahve_keten'),
     'RN07': ('1482', 'd3cbc2', 'beyaz_keten')}
for kod, (n, hx, ad) in R.items():
    a = np.load(f'{kl}/{n}.npy').astype(np.float32); h, w, _ = a.shape
    import pencere; y0, x0 = pencere.en_iyi(a, 1792); c = a[y0:y0 + 1792, x0:x0 + 1792]  # 14 × 14 cm
    im = d.doku(c, hx)
    im.save(f'{cikis}/{kod}_tam.jpg', quality=92)  # 128 px/cm
    print(kod, im.size)
