import cv2, numpy as np, json, sys
U, CIK = sys.argv[1], sys.argv[2]
L = [  # kod, ad, en mm, boy mm, tür, dosya, kutu (x0,y0,x1,y1), eşik
 ("60.01", "Grek şerit", 400, 100, "serit", "d1c8a567", (605, 285, 1275, 440), 50),
 ("60.03", "Grek köşe", 107.1, 100.2, "tek", "d1c8a567", (1305, 175, 1695, 552), 50),
 ("60.04", "Çift Grek şerit", 400, 300, "serit", "d1c8a567", (1710, 205, 2485, 520), 50),
 ("61.01", "Grek madalyon", 114.5, 114.7, "tek", "d1c8a567", (118, 618, 502, 988), 50),
 ("65.01", "Zincir", 397, 32.3, "serit", "d1c8a567", (543, 756, 1272, 848), 50),
 ("79.01", "Çiçek dalı", 400, 132.3, "serit", "d1c8a567", (930, 1115, 1230, 1285), 50),
 ("81.01", "Dalgalı örgü", 400, 180, "serit", "d1c8a567", (1708, 1100, 2470, 1312), 50),
 ("56.01", "Bienna Fur logo", 149.9, 149.7, "tek", "c19f011d", (320, 255, 1020, 945), 30),
 ("57.01", "Elmas kafes", 400.1, 249.9, "tek", "c19f011d", (1330, 278, 2188, 905), 30),
 ("62.01", "Madalyon şeridi", 399.8, 98, "serit", "c19f011d", (190, 1222, 1197, 1508), 30),
 ("82.01", "Dalgalı örgü (dar)", 100, 179.9, "tek", "c19f011d", (1268, 1163, 2205, 1557), 30),
 ("68.01", "İnce Grek şerit", 399.9, 60, "serit", "1e66fdff", (1252, 497, 2256, 677), 25),
 ("75.01", "Grek madalyon panelleri", 399.8, 430, "tek", "1e66fdff", (355, 1040, 995, 1668), 25),
 ("77.03", "Grek harf (G)", 400, 180, "serit", "1e66fdff", (1243, 1116, 2236, 1590), 25),
]
bilgi = {}
for kod, ad, en, boy, tur, f, (x0, y0, x1, y1), esik in L:
    im = cv2.imread(f"{U}/{f}-image.jpg")[y0:y1, x0:x1].astype(np.int16)
    b, r = im[..., 0], im[..., 2]
    m = ((b - r > esik) & (r < 150)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    ys, xs = np.where(m > 0); m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = cv2.copyMakeBorder(m, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=0)
    k = 800 / max(m.shape)
    m = cv2.resize(m, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC); m = ((m > 110) * 255).astype(np.uint8)
    m = cv2.GaussianBlur(m, (0, 0), 0.8)
    cv2.imwrite(f"{CIK}/{kod.replace('.', '_')}.png", m)
    bilgi[kod] = [ad, round(en / 10, 1), round(boy / 10, 1), tur]
    print(kod, m.shape)
json.dump(bilgi, open(f"{CIK}/motifler.json", "w"), ensure_ascii=False, indent=1)
