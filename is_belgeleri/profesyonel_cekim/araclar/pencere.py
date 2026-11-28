import numpy as np
def en_iyi(a, boy, k=32):
    """Arka plan (düz kâğıt) girmeyen, dokulu en iyi kare pencere: penceredeki blok sapmasının alt yüzdeliği en yüksek."""
    L = a.astype(np.float32).mean(2); h, w = L.shape
    b = L[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k)
    s = b.std((1, 3)) / np.maximum(b.mean((1, 3)), 1e-4)
    n = boy // k; best = None
    for y in range(0, s.shape[0] - n + 1):
        for x in range(0, s.shape[1] - n + 1):
            v = np.percentile(s[y:y + n, x:x + n], 3)
            if best is None or v > best[0]: best = (v, y * k, x * k)
    return best[1], best[2]
