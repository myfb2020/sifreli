"""Bienca: fotoğraf zemin ve varak diye iki sınıfa ayrılır (yumuşak geçişli), her sınıf kendi hedef rengine
boyanır; sınıf içindeki ışık farkı (doku) fotoğraftan korunur."""
import numpy as np, cv2
def lin(h):
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def boya(c, zemin_sinif, zemin_hex, varak_hex, zemin_doku=0.6, varak_doku=1.0, karisim_foto=0.15, yumusak=0.35, esik_kay=0.0):
    L = c @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    l = np.log(np.maximum(L, 1e-5)); g = ((l - l.min()) / (np.ptp(l) + 1e-9) * 255).astype(np.uint8)
    esik, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    t = esik / 255 * np.ptp(l) + l.min() + esik_kay * np.std(l); gen = np.std(l) * yumusak
    acik = 1 / (1 + np.exp(-(l - t) / max(gen, 1e-3)))  # 1 = açık sınıf
    acik = cv2.GaussianBlur(acik.astype(np.float32), (0, 0), 0.8)
    zm = (1 - acik) if zemin_sinif == 'koyu' else acik
    out = np.zeros_like(c)
    for m, hx, dk in ((zm, zemin_hex, zemin_doku), (1 - zm, varak_hex, varak_doku)):
        w = m > 0.5; ort = np.exp(np.log(np.maximum(L[w], 1e-5)).mean()) if w.any() else 1
        hedef = lin(hx); Lh = hedef @ np.array([0.2126, 0.7152, 0.0722])
        oran = (L / ort) ** dk  # sınıf içi doku
        renk_foto = c / np.maximum(L[..., None], 1e-5) * Lh
        renk = (1 - karisim_foto) * hedef + karisim_foto * renk_foto
        out += m[..., None] * renk * oran[..., None]
    return out
