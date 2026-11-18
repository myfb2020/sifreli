import os, django, sys, textwrap
sys.path.insert(0, "/home/user/sifreli/uretim_takip")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fabrika.settings")
django.setup()
from PIL import Image, ImageDraw, ImageFont
from uretim.models import KatalogModeli
from uretim import parcali
S = "/tmp/claude-0/-home-user-sifreli/1ccdae7b-7b64-5555-9dfa-df34bce82c51/scratchpad"
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
FT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)

def foto(k):
    return Image.open(KatalogModeli.objects.get(kod=k).resim.path).convert("RGB")

def sayfa(baslik, ogeler, dosya, T=340, S_=4):
    H = int(T * 1.25); Y = H + 150
    satir = (len(ogeler) + S_ - 1) // S_
    im = Image.new("RGB", (S_ * T, 70 + satir * Y), "white"); d = ImageDraw.Draw(im)
    d.text((14, 16), baslik, font=FT, fill=(90, 60, 20))
    for j, (no, kod, metin, resim) in enumerate(ogeler):
        x, y = (j % S_) * T, 70 + (j // S_) * Y
        r = resim.copy(); r.thumbnail((T - 16, H - 16))
        im.paste(r, (x + (T - r.width) // 2, y + 44))
        tasar = " 🎨" if kod in parcali.SECILI_MODELLER else ""
        d.text((x + 8, y + 8), f"{no}. {kod}", font=FB, fill=(160, 20, 20) if tasar else (0, 0, 0))
        for i, l in enumerate(textwrap.wrap(metin, 28)[:5]):
            d.text((x + 8, y + H + 40 + i * 25), l, font=F, fill=(40, 40, 40))
        d.rectangle([x, y, x + T - 1, y + Y - 1], outline=(210, 210, 210))
    im.save(f"{OUT}/{dosya}", quality=84)

A = [("BNA-027", "Yakın çekim: halının tamamı yok, parlama var"),
     ("BNA-028", "Eğik çekim, kenarlar dalgalı, parlama"),
     ("PCH-004", "Üst kenar kesik, solda yabancı koyu şerit, yamuk"),
     ("PCH-007", "Köşelerde katlanmış parçalar, sol altta taşan altın parça"),
     ("PCH-009", "Bulanık; alt kısım farklı tonda"),
     ("PCH-010", "Bulanık; alt çeyrek farklı tonda"),
     ("PCH-015", "Üst bordür yok (kesik), üstte siyah şerit"),
     ("TOS-040", "Sağda halıya ait olmayan siyah şerit ve beyaz çizgi"),
     ("TOS-052", "Sağda ayrı bir koyu şerit (başka eşya)"),
     ("FDA-634", "Sağda ayrı bir siyah şerit"),
     ("BNA-021", "Sağda siyah şerit; desen tek yanda"),
     ("IPS-471", "Halı eğik/kayık çekilmiş"),
     ("IPS-482", "Ovalin iki yanı düz kesilmiş"),
     ("IPS-483", "İki yanı kesik, sağda gölge"),
     ("IPS-484", "Yuvarlağın sağ tarafı kesik"),
     ("TOS-060", "Küçük; sağ kenarda dağınık siyah tüyler")]
sayfa("A · Çıkarılmasını önerdiğim fotoğraflar  (kırmızı kod = tasarlanan)",
      [(i + 1, k, m, foto(k)) for i, (k, m) in enumerate(A)], "A_kotu_fotograflar.jpg")

B = [("RNO-006", "Gri stüdyo zemini (ötekiler beyaz), küçük görünüyor"),
     ("RNO-008", "Gri stüdyo zemini"),
     ("RNO-013", "Halının yalnız bir köşesi (yakın çekim)"),
     ("RNO-007", "Gri zemin, hafif perspektif. Düzleştirilmiş temiz hâli bende var"),
     ("RNO-009", "Gri zemin, küçük. Düzleştirilmiş hâli var"),
     ("RNO-011", "Gri zemin, soluk. Düzleştirilmiş hâli var"),
     ("IPS-460", "İki yanda gri şerit: başka halının üstünde çekilmiş gibi"),
     ("TOS-065", "Beyaz üstüne beyaz, çok soluk"),
     ("LTS-003", "Köşeler dağınık, alt kenar kesik"),
     ("PCH-001", "Kırışık ve sarımsı"),
     ("PCH-005", "Bulanık"),
     ("TKA-335", "Köşelerde beyaz lekeler"),
     ("IPS-466", "IPS-468 ile AYNI fotoğraf"),
     ("PCH-016", "PCH-006 ile AYNI fotoğraf"),
     ("DPT-553", "Neredeyse tamamen siyah, deseni görünmüyor (DPT-537 de)"),
     ("IPS-443", "Beyaz üstüne açık altın, zor seçiliyor (IPS-444/434 da)")]
sayfa("B · Zayıf fotoğraflar (düzeltilebilir / sizin kararınız)",
      [(i + 17, k, m, foto(k)) for i, (k, m) in enumerate(B)], "B_zayif_fotograflar.jpg")

K = f"{S}/bayi_tam"
C = [("BNA-001", "BNA-001_3.jpg", "Zemin Bienca BN02: kahve-beyaz dev lekeler, kirli duvar gibi (BNA-018, BNA-014 aynı)"),
     ("BNA-011", "BNA-011_3.jpg", "Bordür BN02 + zemin BN05: lekeli, karışık"),
     ("BNA-007", "BNA-007_4.jpg", "Zemin BN01: büyük altın sıçrama, ayna lekesi gibi"),
     ("PCH-002", "PCH-002_5.jpg", "Zemin siyah kadife: gri lekeler + ara bandın kutu kenarı belli"),
     ("IPS-476", "IPS-476_4.jpg", "Zemin varak altın: doku kare kare tekrar ediyor (duvar kâğıdı gibi)"),
     ("PCH-012", "PCH-012_3.jpg", "Oval + ara bant: fotoğraf gider, düz çizim; zeminde ve dış bantta düz çizgiler"),
     ("IPS-482", "IPS-482_4.jpg", "Oval: aynı çizgiler + bakır varak karo tekrarı"),
     ("IPS-465", "IPS-465_4.jpg", "Zemin antrasit: parça parça ton farkı, kutular belli"),
     ("PCH-003", "PCH-003_4.jpg", "Madalyon siyah: süslü madalyon düz siyah daire, delik gibi"),
     ("IPS-435", "IPS-435_2.jpg", "Bordür rengi değişince Grek deseni soluklaşıyor"),
     ("BNA-005", "BNA-005_2.jpg", "Bordür gri yapılınca lazer deseni neredeyse kayboluyor"),
     ("IPS-458", "IPS-458_5.jpg", "Zemin BN05: lekeli, madalyon kayboluyor")]
sayfa("C · Bayi gibi tasarlarken bozulanlar",
      [(i + 33, k, m, Image.open(f"{K}/{r}").convert("RGB")) for i, (k, r, m) in enumerate(C)], "C_tasarlarken_bozulanlar.jpg")
print("tamam")
