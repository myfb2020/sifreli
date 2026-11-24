"""Fikir ver aday renk takımları: her vitrin modeli için 12 numaralı öneri, sayfa sayfa (kullanıcı seçecek)."""
import io, json, os, sys
sys.path.insert(0, "."); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django
django.setup()
from PIL import Image, ImageDraw, ImageFont
from uretim import parcali as p, foto_temel, parcali_gorsel
from uretim.tasarim_views import _desen_kodlari

CIKIS = sys.argv[1]
YOK = {"pelus_pembe", "pelus_taba", "pelus_lacivert"}
for aile in p.AILE_MALZEMELERI.values():
    for k in aile:
        aile[k] = [m for m in aile[k] if m not in YOK]
KOTU = {("BNA-018", "bienca_bn01", "bienca_bn05"), ("BNA-018", "bienca_bn04", "gumus")}  # kullanıcı notu
desen = _desen_kodlari()
def ad(k):
    a = (p.MALZEME_AD.get(k) or p.KENAR_AD.get(k) or k).split(" (")[0]
    if a.startswith(("Bienca ", "Rono ")):
        return a.split(" ")[1]  # BN04, RN06
    return a
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 19)
kalin = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
veri = {}
for kod in p.BAYI_VITRINI:
    adaylar, gorulen = [], set()
    for tohum in range(40):
        for v in p.fikirler(6, tohum, desen, (160, 230), katalog=kod):
            anahtar = tuple(v.get(a) for a in p.MALZEME_ALANLARI + ["kenar_renk"])
            if anahtar in gorulen or (kod, v["zemin"], v["kenar_renk"]) in KOTU:
                continue
            gorulen.add(anahtar); adaylar.append(v)
        if len(adaylar) >= 12:
            break
    adaylar = adaylar[:12]
    W, H = 330, 400
    sayfa = Image.new("RGB", (4 * W + 40, 3 * (H + 100) + 110), (250, 249, 246))
    d = ImageDraw.Draw(sayfa)
    d.text((24, 24), f"{kod} – Fikir ver önerileri (beğendiklerinizin numarasını yazın)", font=kalin, fill=(40, 30, 20))
    veri[kod] = []
    for i, v in enumerate(adaylar):
        x, y = 20 + (i % 4) * W, 100 + (i // 4) * (H + 100)
        im = foto_temel.bilesik(v, 440) or parcali_gorsel.ciz(v, 440)
        im.thumbnail((W - 20, H - 10))
        sayfa.paste(im, (x + (W - im.width) // 2, y + (H - im.height) // 2))
        bordur = ", ".join(dict.fromkeys(ad(v[f"h{j}_malzeme"]) for j in range(1, v["halka_sayisi"] + 1)))
        d.text((x + 6, y + H + 4), f"{i + 1}.", font=kalin, fill=(150, 110, 30))
        satir = [f"zemin {ad(v['zemin'])}", f"bordür {bordur}",
                 f"kenar {ad(v['kenar_renk'])}" + (f" · mad. {ad(v['madalyon_malzeme'])}" if v["madalyon"] != "yok" else "")]
        for j, t in enumerate(satir):
            d.text((x + 62, y + H + 4 + j * 24), t, font=font, fill=(40, 30, 20))
        veri[kod].append({a: v[a] for a in p.MALZEME_ALANLARI + ["kenar_renk", "madalyon_cerceve"] if a in v})
    sayfa.save(f"{CIKIS}/{kod}.jpg", quality=86)
    print(kod, len(adaylar))
json.dump(veri, open(f"{CIKIS}/adaylar.json", "w"), ensure_ascii=False, indent=1)
sayfalar = [Image.open(f"{CIKIS}/{k}.jpg").convert("RGB") for k in p.BAYI_VITRINI]
sayfalar[0].save(f"{CIKIS}/fikir_onerileri.pdf", save_all=True, append_images=sayfalar[1:], resolution=120)
