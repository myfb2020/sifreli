import sys, os, glob, json, numpy as np, rawpy
sys.path.insert(0, os.path.dirname(__file__)); import gelistir as g
ham, cikis = sys.argv[1], sys.argv[2]; os.makedirs(cikis, exist_ok=True)
WB1 = (2.1793, 1, 1.7932, 1); K1 = 0.2298
def oturum(n):
    n = int(n)
    return 1 if n < 1800 else (2 if n < 2140 else 3)
# oturum 2/3: o oturumdaki kamera beyaz ayarlarının ortancası (ışık sabit, makine her karede kaydırmış)
ort = {}
for y in sorted(glob.glob(ham + '/*.RAF')):
    with rawpy.imread(y) as r: w = r.camera_whitebalance
    ort.setdefault(oturum(os.path.basename(y)[4:8]), []).append((w[0] / w[1], w[2] / w[1]))
WB = {1: WB1}
for o in (2, 3):
    a = np.median(np.array(ort[o]), 0); WB[o] = (a[0], 1, a[1], 1)
json.dump({str(k): v for k, v in WB.items()}, open(cikis + '/wb.json', 'w'))
for y in sorted(glob.glob(ham + '/*.RAF')):
    n = os.path.basename(y)[4:8]; o = oturum(n)
    a = g.dogrusal(y, wb=WB[o], yarim=True)
    np.save(f'{cikis}/{n}.npy', (a / g.pozlama(y)).astype(np.float16))  # pozlamadan bağımsız doğrusal ışık
    print(n, o, flush=True)
