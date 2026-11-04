"""Sipariş fotoğrafları: yüklenirken küçültülür (sunucuda yer kaplamasın), sipariş ve katalog modeline bağlanır."""

import io

from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import KatalogModeli, KatalogSerisi, SiparisFotografi

UZUN_KENAR = 1600  # px; telefonda büyütünce yeterince net, dosya ~200 KB
ARSIV_KENAR = 600  # px; sevk edileli ARSIV_GUN gün olmuş siparişin fotoğrafı bu boya indirilir (~40 KB)
ARSIV_GUN = 182
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


def arsiv_kucult(bugun=None):
    """Sevk edileli ~6 ay olmuş siparişlerin fotoğraflarını küçültür (silmez). (adet, kazanılan bayt) döner."""
    from datetime import timedelta

    from django.utils import timezone

    bugun = bugun or timezone.localdate()
    adet = kazanc = 0
    for foto in SiparisFotografi.objects.filter(kucultuldu=False, siparis__durum="sevk",
                                                siparis__sevk_tarihi__lte=bugun - timedelta(days=ARSIV_GUN)):
        try:
            eski = foto.resim.size
            with foto.resim.open("rb") as f:
                resim = Image.open(f)
                resim.load()
            resim = resim.convert("RGB")
            resim.thumbnail((ARSIV_KENAR, ARSIV_KENAR), Image.LANCZOS)
            tampon = io.BytesIO()
            resim.save(tampon, "JPEG", quality=70, optimize=True)
            ad = foto.resim.name
            foto.resim.delete(save=False)
            foto.resim.save(ad.rsplit("/", 1)[-1], ContentFile(tampon.getvalue()), save=False)
        except (OSError, UnidentifiedImageError, ValueError):
            foto.kucultuldu = True  # dosya yok/bozuk: bir daha denenmez
            foto.save(update_fields=["kucultuldu"])
            continue
        foto.kucultuldu = True
        foto.save(update_fields=["resim", "kucultuldu"])
        adet += 1
        kazanc += max(eski - foto.resim.size, 0)
    return adet, kazanc


def gunluk_arsiv_kucult():
    """Günde en çok bir kez çalışır (pano açılınca). Bugün çalıştıysa None, yoksa (adet, bayt)."""
    from django.utils import timezone

    from .models import SistemAyari

    bugun = timezone.localdate()
    ayar = SistemAyari.yukle()
    if ayar.son_foto_kucultme == bugun:
        return None
    SistemAyari.objects.filter(pk=ayar.pk).update(son_foto_kucultme=bugun)
    return arsiv_kucult(bugun)
