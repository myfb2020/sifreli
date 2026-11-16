"""bayi_siparis_denemesi.js çıktısını denetler ve resim sayfaları yapar (yalnız geliştirmede).
Her adımda: sunucunun çizimden aldığı parçalar = bayinin o ana kadar dokunduğu parçalar mı? Gönderilen siparişin
tasarımı son ekranla aynı mı, siparişin resmi ekrandakiyle aynı mı?
Kullanım (uretim_takip içinde): python ../is_belgeleri/foto_halka/bayi_siparis_rapor.py KLASOR
"""
import io, json, os, sys
sys.path.insert(0, "."); os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
import django  # noqa: E402
django.setup()
from django.http import QueryDict  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat  # noqa: E402
from uretim import foto_temel as ft, parcali_gorsel as pg  # noqa: E402
from uretim.models import Siparis  # noqa: E402
from uretim.parcali_views import _temizle  # noqa: E402
from uretim.tasarim_views import tasarim_temizle  # noqa: E402

K = sys.argv[1]
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
satirlar, rapor = [], []
for l in open(f"{K}/sonuc.jsonl"):
    k = json.loads(l)
    kod, notlar = k["kod"], list(k["sorunlar"])
    if k.get("gonderim") != "gönderildi":
        notlar.append(f"sipariş: {k.get('gonderim')}")
    ims = [("katalog", Image.open(f"uretim/katalog_tohum/model/{kod}.jpg").convert("RGB"))]
    son_v = None
    for a in k["adimlar"]:
        v = _temizle(QueryDict(a["q"]))
        son_v = v
        if a["sira"] and ft.uygun_mu(kod):
            if ft.bilesik(v, 300) is None:
                notlar.append(f"adım {a['sira']} ({a['ad']}): bütün halı çizimden")
        ims.append((f"{a['sira']}. {a['ad']}", Image.open(f"{K}/{kod}_{a['sira']}.jpg").convert("RGB")))
    sp = Siparis.objects.filter(notlar=f"deneme {kod}").order_by("-pk").first()
    if sp and getattr(sp, "tasarim", None):
        veri = tasarim_temizle(sp.tasarim.veri)
        if son_v is not None:
            fark = sorted(a for a in set(veri) | set(son_v) if a not in ("hazir",) and veri.get(a) != son_v.get(a))
            if fark:
                notlar.append(f"siparişe giden tasarım ekrandan farklı: {fark[:6]}")
        ims.append((f"sipariş {sp.siparis_no}", Image.open(io.BytesIO(pg.jpeg(veri, 700))).convert("RGB")))
    elif k.get("gonderim") == "gönderildi":
        notlar.append("sipariş kaydı bulunamadı")
    rapor.append((kod, notlar))
    H = 300
    t = Image.new("RGB", (sum(round(i.width * H / i.height) + 6 for _, i in ims) + 90, H + 26), "white")
    d = ImageDraw.Draw(t); d.text((4, H // 2), kod, font=F, fill=(0, 0, 0)); x = 90
    for ad, i in ims:
        i = i.resize((round(i.width * H / i.height), H)); t.paste(i, (x, 24)); d.text((x + 2, 3), ad[:34], font=F, fill=(0, 0, 0)); x += i.width + 6
    satirlar.append(t)
for n in range(0, len(satirlar), 4):
    grp = satirlar[n:n + 4]
    T = Image.new("RGB", (max(s.width for s in grp), sum(s.height + 10 for s in grp)), "white"); y = 0
    for s in grp:
        T.paste(s, (0, y)); y += s.height + 10
    T.save(f"{K}/sayfa_{n // 4:02d}.jpg", quality=80)
for kod, notlar in rapor:
    print(kod, "–" if not notlar else " ; ".join(notlar))
