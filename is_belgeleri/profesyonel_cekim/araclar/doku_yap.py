"""Doğrusal çekimden program dokusu: ışık eğimi düzlenir, ortalama renk hedefe çekilir."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); import gelistir as g
from PIL import Image

def lin(h):
    c = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def egim_duzle(a):
    L = a @ np.array([0.2126, 0.7152, 0.0722]); h, w = L.shape
    k = 16; kucuk = L[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k).mean((1, 3))
    yy, xx = np.mgrid[0:kucuk.shape[0], 0:kucuk.shape[1]]; yy = yy / kucuk.shape[0] - .5; xx = xx / kucuk.shape[1] - .5
    A = np.stack([np.ones_like(xx), xx, yy, xx * xx, yy * yy, xx * yy], -1).reshape(-1, 6)
    c, *_ = np.linalg.lstsq(A, np.log(np.maximum(kucuk, 1e-4)).ravel(), rcond=None)
    Y, X = np.mgrid[0:h, 0:w]; Y = Y / h - .5; X = X / w - .5
    yuzey = np.exp(c[1] * X + c[2] * Y + c[3] * X * X + c[4] * Y * Y + c[5] * X * Y)
    return a / yuzey[..., None]

def doku(a, hedef_hex=None, karisim=0.5):
    a = egim_duzle(a.astype(np.float32))
    m = a.reshape(-1, 3).mean(0)
    if hedef_hex:
        t = lin(hedef_hex); Lt = t @ [0.2126, 0.7152, 0.0722]; Lm = m @ [0.2126, 0.7152, 0.0722]
        foto = m * Lt / Lm
        hedef = karisim * t + (1 - karisim) * foto
        a = a * (hedef / m)
    return g.srgb(a)
