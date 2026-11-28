import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import doku_yap as d, pencere, gelistir as g, iki_sinif
from PIL import Image
kl, cikis, U = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(cikis, exist_ok=True)
KART = Image.open('/home/user/sifreli/is_belgeleri/kartela_foto/bienca_kartela.jpg').convert('RGB')
HEDEF = {'BN01': KART.crop((80, 215, 600, 535)), 'BN02': KART.crop((775, 315, 1040, 950)),
         'BN03': KART.crop((330, 720, 720, 950)), 'BN04': KART.crop((80, 1080, 600, 1380)),
         'BN05': Image.open(f'{U}/tasarim_varlik/doku/bienca_bn05.jpg').convert('RGB')}
# çekim, px/cm (oturum ve odak uzaklığından)
KAYNAK = {'BN01': ('1957', 65.0), 'BN02': ('2177', 65.0), 'BN03': ('1509', 93.0), 'BN04': ('2172', 24.0)}  # BN05: çekim yok, eski doku kalır
def esle(kaynak, hedef, kutu=24, sonum=0.6):
    """Açıklık sıra sıra karteladan; renk, kartelada aynı açıklık dilimindeki ortalama renk (fotoğraftaki
    yerel renk farkı yarı yarıya korunur): zemin kartela renginde, varak altın/gümüş kalır."""
    W = np.array([0.299, 0.587, 0.114], np.float32)
    Ys = kaynak @ W; Yt = hedef.reshape(-1, 3) @ W; t = hedef.reshape(-1, 3)
    sira = np.argsort(np.argsort(Ys.ravel(), kind='stable'), kind='stable') / (Ys.size - 1)
    Ty = np.sort(Yt); Yn = np.interp(sira, np.linspace(0, 1, Ty.size), Ty).reshape(Ys.shape)
    ts = np.argsort(np.argsort(Yt, kind='stable'), kind='stable') / (Yt.size - 1)
    out = np.empty_like(kaynak); k = kaynak.reshape(-1, 3); sr = sira
    oranp = k / np.maximum(Ys.ravel()[:, None], 1)
    son = np.empty_like(k)
    for i in range(kutu):
        a, b = i / kutu, (i + 1) / kutu + (1e-9 if i == kutu - 1 else 0)
        mt = (ts >= a) & (ts < b); ms = (sr >= a) & (sr < b)
        if not ms.any(): continue
        ro_t = t[mt].mean(0) / max(1, (t[mt] @ W).mean()) if mt.any() else np.ones(3)
        ro_s = oranp[ms].mean(0)
        son[ms] = ro_t * (oranp[ms] / np.maximum(ro_s, 1e-3)) ** sonum
    return np.clip(son * Yn.ravel()[:, None], 0, 255).reshape(kaynak.shape)
# zemin sınıfı fotoğrafta koyu mu açık mı, zemin rengi, varak rengi (kartela fotoğrafından)
SINIF = {'BN01': (('koyu', 'dcd9d1', 'd2b160'), {}), 'BN03': (('koyu', '8f989d', 'e2e5e7'), {}),
         'BN04': (('acik', 'dfdcd4', 'c9a14a'), dict(zemin_doku=0.5, yumusak=0.08, esik_kay=-0.3))}
bilgi = {}
for kod, (n, pxcm) in KAYNAK.items():
    a = np.load(f'{kl}/{n}.npy').astype(np.float32)
    y0, x0 = pencere.en_iyi(a, 1600); c = d.egim_duzle(a[y0:y0 + 1600, x0:x0 + 1600])
    c = c / np.percentile(c @ [0.2126, 0.7152, 0.0722], 99.5)
    if kod in SINIF:
        im = g.srgb(iki_sinif.boya(c, *SINIF[kod][0], **SINIF[kod][1]))
    else:
        foto = np.asarray(g.srgb(c), np.float32)
        im = Image.fromarray(np.clip(esle(foto, np.asarray(HEDEF[kod], np.float32)), 0, 255).astype(np.uint8))
    hedef_px = min(40.0, pxcm); w = round(1600 * hedef_px / pxcm)
    im = im.resize((w, w), Image.LANCZOS); im.save(f'{cikis}/{kod}.jpg', quality=90)
    bilgi[kod] = {'cekim': n, 'px_cm': hedef_px, 'cm': round(w / hedef_px, 1)}
    print(kod, n, im.size, bilgi[kod])
json.dump(bilgi, open(f'{cikis}/bilgi.json', 'w'), indent=1)
