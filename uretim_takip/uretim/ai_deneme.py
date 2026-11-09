"""Yapay zeka DENEMESİ (programa bağlı değil): katalog fotoğrafının seçilen bölgesi (kenar / desenli bant / orta)
Stability AI 'search-and-recolor' ile yeniden renklendirilir; doku, desen, ışık fotoğraftan kalır. Sonuç bizim
bölge haritamızla sınırlanır (öteki bölgeler fotoğraftaki gibi). Anahtar .env → STABILITY_API_KEY."""
import io
import json
import os
import urllib.request
import uuid

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat
import urllib.error

from . import foto_model

ADRES = "https://api.stability.ai/v2beta/stable-image/edit/search-and-recolor"
BOLGE = {  # yapay zekaya bölgenin tarifi
    "kenar": "the thin outer border frame of the rug",
    "desen": "the laser cut lace patterned border band of the rug",
    "orta": "the large center field of the rug",
}
RENK = {
    "RN01": "light greyish mink suede", "RN02": "dark grey suede", "RN03": "cream beige suede",
    "RN04": "anthracite black suede", "RN05": "mink milky brown suede", "RN06": "dark chocolate brown suede",
    "RN07": "ecru off-white suede", "BN01": "white leather with silver and gold foil distressed print",
    "BN02": "grey leather with copper distressed foil print", "BN03": "grey leather with silver distressed foil print",
    "BN04": "cream leather with distressed gold foil AND silver foil patches mixed",
    "ALTIN": "shiny gold metallic leather", "GUMUS": "shiny silver metallic leather",
}

DENEMELER = [  # (model, değiştirilen bölgeler)
    ("RNO-004", {"desen": "RN04", "orta": "RN03"}),
    ("BNA-009", {"kenar": "RN06", "desen": "BN02", "orta": "BN01"}),
    ("BNA-001", {"kenar": "RN04", "desen": "GUMUS", "orta": "BN03"}),
]


def _cok_parcali(alanlar, resim):
    sinir = uuid.uuid4().hex
    govde = io.BytesIO()
    for ad, deger in alanlar.items():
        govde.write(f'--{sinir}\r\nContent-Disposition: form-data; name="{ad}"\r\n\r\n{deger}\r\n'.encode())
    tampon = io.BytesIO()
    resim.save(tampon, "PNG")
    govde.write(f'--{sinir}\r\nContent-Disposition: form-data; name="image"; filename="h.png"\r\n'
                f"Content-Type: image/png\r\n\r\n".encode())
    govde.write(tampon.getvalue() + f"\r\n--{sinir}--\r\n".encode())
    return govde.getvalue(), f"multipart/form-data; boundary={sinir}"


def renklendir(resim, bolge, renk):
    anahtar = os.environ.get("STABILITY_API_KEY", "").strip()
    if not anahtar:
        raise RuntimeError(".env dosyasında STABILITY_API_KEY yok")
    veri, tur = _cok_parcali({"prompt": RENK[renk] + ", realistic texture, same pattern",
                              "select_prompt": BOLGE[bolge], "grow_mask": "1", "output_format": "png"}, resim)
    istek = urllib.request.Request(ADRES, data=veri, method="POST", headers={
        "Authorization": f"Bearer {anahtar}", "Accept": "image/*", "Content-Type": tur})
    try:
        with urllib.request.urlopen(istek, timeout=120) as yanit:
            return Image.open(io.BytesIO(yanit.read())).convert("RGB").resize(resim.size, Image.LANCZOS)
    except urllib.error.HTTPError as h:
        raise RuntimeError(f"Stability hata {h.code}: {h.read()[:300].decode('utf-8', 'replace')}")
    except urllib.error.URLError as h:
        raise RuntimeError(f"Stability'ye bağlanılamadı: {h.reason}")


def degisen_maske(kod, secim, boyut):
    """Değişen bölgeler (biraz genişletilmiş, yumuşak kenarlı): yapay zeka yalnız buraya uygulanır."""
    _, harita, _ = foto_model._kaynak(kod, None)
    siralar = foto_model.MODELLER[kod].get("sira") or range(1, 10)
    maske = Image.new("L", harita.size, 0)
    for s, b in zip(siralar, foto_model.bolgeler(kod)):
        if b["anahtar"] in secim:
            maske = ImageChops.lighter(maske, harita.point(lambda v, s=s: 255 if v == s else 0))
    # 2. deneme: genişletme yok (değişmeyen komşu bölgeye taşmasın), yalnız yarım piksel yumuşatma
    return maske.filter(ImageFilter.GaussianBlur(0.8)).resize(boyut)


INCE = {"kenar", "cerceve"}  # ince çizgi / biye: yapay zeka tutamıyor → kendi boyamamız


def hedef_renk(deger):
    """Kartelanın gerçek rengi: Rono kartela rengi, Bienca / metal gerçek doku fotoğrafının ortalaması."""
    dosya = foto_model.DOKU / f"{foto_model.KARTELA[deger][0]}.jpg"
    if not deger.startswith("RN") and dosya.exists():
        return tuple(ImageStat.Stat(Image.open(dosya).convert("RGB")).mean)
    return foto_model._hex(foto_model.KARTELA[deger][2])


def ai_maskesi(once, sonra, kaba):
    """3. deneme: bölge haritamız kaba (komşu bölgeye taşıyor). Yapay zekanın gerçekten değiştirdiği pikseller
    (desen kenarlarını iyi izler) ile haritamızın biraz genişletilmiş hâlinin kesişimi kullanılır."""
    fark = ImageChops.difference(once, sonra).convert("L").filter(ImageFilter.GaussianBlur(1))
    degisen = fark.point(lambda v: 255 if v > 18 else 0).filter(ImageFilter.MaxFilter(3))
    alan = kaba.point(lambda v: 255 if v > 20 else 0).filter(ImageFilter.MaxFilter(7))
    return ImageChops.multiply(degisen, alan).filter(ImageFilter.GaussianBlur(0.8))


def renk_ayarla(resim, maske, hedef, oran=0.85, yalniz_parlaklik=False):
    """Bölgenin ortalama rengini kartela rengine çeker (kanal kanal çarpan): doku ve gölge kalır. Bienca / metal
    çok renkli (bakır + gri gibi): yalnız parlaklık ayarlanır, yapay zekanın tonu kalır."""
    sert = maske.point(lambda v: 255 if v > 128 else 0)
    if not sert.getbbox():
        return resim
    ort = ImageStat.Stat(resim, sert).mean
    if yalniz_parlaklik:
        k = (sum(hedef) / 3) / max(sum(ort) / 3, 4)
        hedef = [o * k for o in ort]
    kanallar = []
    for k, o, h in zip(resim.split(), ort, hedef):
        carpan = 1 + oran * (h / max(o, 4) - 1)
        kanallar.append(k.point(lambda v, c=carpan: max(0, min(255, round(v * c)))))
    return Image.composite(Image.merge("RGB", kanallar), resim, maske)


def calistir(klasor, yapay_zeka=True):
    os.makedirs(klasor, exist_ok=True)
    satirlar = []
    for kod, degisim in DENEMELER:
        asil = foto_model._kaynak(kod, None)[0]
        resimler = [("Katalog", asil)]
        if yapay_zeka:
            for ad, dosya in (("1. deneme", "Yapay_zeka"), ("2. deneme", "2_deneme")):
                onceki = os.path.join(klasor, f"{kod}_{dosya}.jpg")
                if os.path.exists(onceki):
                    resimler.append((ad, Image.open(onceki).convert("RGB")))
            sonuc = asil
            for bolge, renk in degisim.items():
                maske = degisen_maske(kod, {bolge: renk}, sonuc.size)
                if bolge in INCE:  # ince çizgi: fotoğraf boyaması
                    boyali = foto_model.boya(kod, foto_model.secim_temizle(kod, {bolge: renk}))
                    sonuc = Image.composite(boyali, sonuc, maske)
                    continue
                ai = renklendir(sonuc, bolge, renk)
                maske = ai_maskesi(sonuc, ai, maske)
                sonuc = Image.composite(ai, sonuc, maske)
                sonuc = renk_ayarla(sonuc, maske, hedef_renk(renk), oran=0.6,
                                    yalniz_parlaklik=not renk.startswith("RN"))
            resimler.append(("3. deneme", sonuc))
        for ad, r in resimler:
            if ad not in ("1. deneme", "2. deneme"):
                r.save(os.path.join(klasor, f"{kod}_{ad.replace(' ', '_').replace('.', '')}.jpg"), quality=92)
        satirlar.append((kod, degisim, resimler))
    # hepsi tek karşılaştırma resminde
    w, h = 330, 410
    sutun = max(len(r) for _, _, r in satirlar)
    tuval = Image.new("RGB", (sutun * w + 20, len(satirlar) * (h + 50) + 10), "white")
    c = ImageDraw.Draw(tuval)
    for i, (kod, degisim, resimler) in enumerate(satirlar):
        y = 10 + i * (h + 50)
        c.text((10, y), f"{kod}  " + json.dumps(degisim), fill="black")
        for j, (ad, r) in enumerate(resimler):
            k = r.copy(); k.thumbnail((w - 10, h - 30))
            tuval.paste(k, (10 + j * w, y + 18)); c.text((10 + j * w, y + 22 + k.height), ad, fill="black")
    yol = os.path.join(klasor, "karsilastirma.jpg")
    tuval.save(yol, quality=90)
    return yol
