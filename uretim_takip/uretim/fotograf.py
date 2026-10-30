"""Sipariş fotoğrafları: yüklenirken küçültülür (sunucuda yer kaplamasın), sipariş ve katalog modeline bağlanır."""

import io

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import KatalogModeli, KatalogSerisi, SiparisFotografi

UZUN_KENAR = 1600  # px; telefonda büyütünce yeterince net, dosya ~200 KB
MUSTERI_SERISI = "Müşteri modelleri"
MUSTERI_ONEKI = "MM"


class FotografHatasi(ValueError):
    pass


def kucult(dosya):
    """Yüklenen resmi döndürme bilgisine göre düzeltir, küçültür, JPEG yapar."""
    try:
        resim = Image.open(dosya)
        resim = ImageOps.exif_transpose(resim).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise FotografHatasi(f"“{getattr(dosya, 'name', 'dosya')}” bir resim değil.")
    resim.thumbnail((UZUN_KENAR, UZUN_KENAR), Image.LANCZOS)
    tampon = io.BytesIO()
    resim.save(tampon, "JPEG", quality=80, optimize=True)
    return tampon.getvalue()


def ekle(siparis, dosyalar):
    """Siparişe fotoğrafları ekler (en çok EN_COK). Eklenen sayıyı döndürür."""
    yer = SiparisFotografi.EN_COK - siparis.fotograflar.count()
    if len(dosyalar) > yer:
        raise FotografHatasi(f"Bir siparişe en çok {SiparisFotografi.EN_COK} fotoğraf eklenebilir"
                             f" (şu an {yer} yer var).")
    icerikler = [kucult(d) for d in dosyalar]  # önce hepsi denetlenir; biri bozuksa hiçbiri eklenmez
    for icerik in icerikler:
        kaydet(siparis, icerik)
    return len(icerikler)


def kaydet(siparis, icerik):
    foto = SiparisFotografi(siparis=siparis)
    foto.resim.save(f"{siparis.siparis_no}.jpg", ContentFile(icerik), save=True)
    return foto


@transaction.atomic
def modele_ekle(foto):
    """Fotoğraftan 'Müşteri modelleri' serisinde yeni katalog modeli (MM-001…); sipariş modelsizse ona bağlanır."""
    seri, _ = KatalogSerisi.objects.get_or_create(ad=MUSTERI_SERISI, defaults={"sira": 999})
    siparis = foto.siparis
    sira = max([int(k.rsplit("-", 1)[1]) for k in KatalogModeli.objects.filter(kod__startswith=f"{MUSTERI_ONEKI}-")
                .values_list("kod", flat=True) if k.rsplit("-", 1)[1].isdigit()] or [0]) + 1
    model = KatalogModeli(kod=f"{MUSTERI_ONEKI}-{sira:03d}", seri=seri,
                          notlar=f"{siparis.siparis_no} – {siparis.musteri}: {siparis.urun}")
    with foto.resim.open("rb") as f:
        model.resim.save(f"{model.kod}.jpg", ContentFile(f.read()), save=False)
    model.save()
    if siparis.katalog_modeli_id is None:
        siparis.katalog_modeli = model
        siparis.save(update_fields=["katalog_modeli"])
    return model
