"""Üretim iş kuralları. Görünümler veritabanını doğrudan değiştirmez, buradan geçer."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    DeriDuzeltme, HamDeriGirisi, IslemKaydi, LotKaynagi, MalzemeHareketi, SistemAyari, UretimLotu,
)


@transaction.atomic
def islem_baslat(*, lot, asama, personel, aciklama="", makine=None):
    lot = UretimLotu.objects.select_for_update().get(pk=lot.pk)
    if lot.durum in ("tamamlandi", "iptal"):
        raise ValidationError(f"{lot} işi {lot.get_durum_display().lower()}, işlem başlatılamaz.")
    if lot.islemler.filter(bitis__isnull=True).exists():
        raise ValidationError(f"{lot} işinde zaten açık bir işlem var. Önce onu bitirin.")
    if makine is not None and makine.asama_id != asama.pk:
        raise ValidationError(f"{makine} makinesi “{asama.ad}” istasyonunda değil.")

    islem = IslemKaydi.objects.create(
        lot=lot,
        asama=asama,
        makine=makine,
        personel=personel,
        giris_kg=lot.mevcut_kg,
        giris_m2=lot.mevcut_m2,
        aciklama=aciklama,
    )
    lot.durum = "islemde"
    lot.son_asama = asama
    lot.save(update_fields=["durum", "son_asama"])

    if lot.siparis and lot.siparis.durum == "acik":
        lot.siparis.durum = "uretimde"
        lot.siparis.save(update_fields=["durum"])
    return islem


@transaction.atomic
def islem_bitir(*, islem, personel, cikis_kg, cikis_m2, aciklama="", malzemeler=()):
    """Aşamayı bitirir. malzemeler: [(malzeme, miktar), ...] bu aşamada kullanılan sarf malzemeleri."""
    islem = IslemKaydi.objects.select_for_update().select_related("lot", "asama").get(pk=islem.pk)
    if islem.bitis is not None:
        raise ValidationError("Bu işlem zaten bitirilmiş.")
    if cikis_kg < 0 or cikis_m2 < 0:
        raise ValidationError("Çıkış değerleri negatif olamaz.")

    islem.bitis = timezone.now()
    islem.bitiren = personel
    islem.cikis_kg = cikis_kg
    islem.cikis_m2 = cikis_m2
    if aciklama:
        islem.aciklama = f"{islem.aciklama}\n{aciklama}".strip()
    islem.save()

    for malzeme, miktar in malzemeler:
        if miktar and miktar > 0:
            MalzemeHareketi.objects.create(malzeme=malzeme, tur="kullanim", miktar=-miktar, islem=islem,
                                           personel=personel)

    lot = islem.lot
    lot.mevcut_kg = cikis_kg
    lot.mevcut_m2 = cikis_m2
    lot.durum = "bekliyor" if lot.asama_sonrasi(islem.asama) else "tamamlandi"
    lot.save(update_fields=["mevcut_kg", "mevcut_m2", "durum"])

    siparis = lot.siparis
    if siparis and lot.durum == "tamamlandi":
        if not siparis.lotlar.exclude(durum__in=["tamamlandi", "iptal"]).exists():
            siparis.durum = "tamamlandi"
            siparis.save(update_fields=["durum"])
    return islem


@transaction.atomic
def yeni_is_baslat(*, personel, siparis, kaynaklar, asama, aciklama="", makine=None, eski_stok=None):
    """Stoktan malzeme alarak yeni bir iş açar ve ilk aşamasını başlatır.

    kaynaklar: [(stok_lotu, kg, m2), ...]. Aynı stok lotu birden çok kez okutulduysa miktarlar toplanır.
    eski_stok: (malzeme_turu, kg, m2) — yalnızca geçiş döneminde, etiketsiz eski stoktan; stoktan düşülmez.
    """
    toplam = {}
    for stok, kg, m2 in kaynaklar:
        onceki = toplam.get(stok.pk, (stok, Decimal(0), Decimal(0)))
        toplam[stok.pk] = (stok, onceki[1] + (kg or 0), onceki[2] + (m2 or 0))
    eski_tur, eski_kg, eski_m2 = eski_stok or (None, Decimal(0), Decimal(0))
    eski_kg, eski_m2 = eski_kg or Decimal(0), eski_m2 or Decimal(0)
    if eski_tur is not None:
        if not SistemAyari.yukle().gecis_modu:
            raise ValidationError("Geçiş dönemi kapalı: iş yalnızca etiketli stok lotlarından başlatılabilir.")
        if eski_kg <= 0 and eski_m2 <= 0:
            raise ValidationError("Eski stoktan aldığınız m² (ya da kg) miktarını girin.")
    if not toplam and eski_tur is None:
        raise ValidationError("En az bir stok lotundan malzeme girin.")
    if siparis is not None and siparis.durum in ("sevk", "iptal"):
        raise ValidationError(f"{siparis} {siparis.get_durum_display().lower()}, bu siparişe iş açılamaz.")

    kilitli = {h.pk: h for h in HamDeriGirisi.objects.select_for_update().filter(pk__in=toplam)}
    hatalar = []
    for pk, (_, kg, m2) in toplam.items():
        stok = kilitli[pk]
        if kg <= 0 and m2 <= 0:
            hatalar.append(f"{stok.lot_no}: alınan kg veya m² girin.")
        if kg > stok.kalan_kg or m2 > stok.kalan_m2:
            hatalar.append(f"{stok.lot_no}: stokta {stok.kalan_kg} kg / {stok.kalan_m2} m² kaldı.")
    if hatalar:
        raise ValidationError(hatalar)

    lot = UretimLotu.objects.create(
        siparis=siparis,
        baslangic_kg=sum((kg for _, kg, _ in toplam.values()), Decimal(0)) + eski_kg,
        baslangic_m2=sum((m2 for _, _, m2 in toplam.values()), Decimal(0)) + eski_m2,
        eski_stok_turu=eski_tur,
    )
    LotKaynagi.objects.bulk_create(
        LotKaynagi(uretim_lotu=lot, ham_deri=kilitli[pk], kg=kg, m2=m2) for pk, (_, kg, m2) in toplam.items()
    )
    return islem_baslat(lot=lot, asama=asama, personel=personel, aciklama=aciklama, makine=makine)


# --- Stok hareketleri ---------------------------------------------------------


def malzeme_giris(*, malzeme, miktar, kullanici=None, tedarikci=None, aciklama=""):
    if miktar is None or miktar <= 0:
        raise ValidationError("Giriş miktarı sıfırdan büyük olmalı.")
    return MalzemeHareketi.objects.create(malzeme=malzeme, tur="giris", miktar=miktar, kullanici=kullanici,
                                          tedarikci=tedarikci, aciklama=aciklama)


@transaction.atomic
def malzeme_duzelt(*, malzeme, neden, miktar, kullanici=None, aciklama=""):
    """Sayımda miktar = sayılan gerçek stok (fark kaydedilir); diğer nedenlerde miktar = stoktan düşülecek."""
    if miktar is None or miktar < 0:
        raise ValidationError("Miktar negatif olamaz.")
    if neden == "sayim":
        fark = miktar - malzeme.stok
        if fark == 0:
            raise ValidationError("Sayılan miktar sistemdekiyle aynı, düzeltme gerekmiyor.")
    else:
        if miktar == 0:
            raise ValidationError("Düşülecek miktarı girin.")
        fark = -miktar
    return MalzemeHareketi.objects.create(malzeme=malzeme, tur=neden, miktar=fark, kullanici=kullanici,
                                          aciklama=aciklama)


@transaction.atomic
def deri_duzelt(*, ham_deri, neden, kg, m2, kullanici=None, aciklama=""):
    """Sayımda kg/m² = sayılan gerçek kalan; diğer nedenlerde kg/m² = stoktan düşülecek miktar."""
    ham_deri = HamDeriGirisi.objects.select_for_update().get(pk=ham_deri.pk)
    kg, m2 = kg or Decimal(0), m2 or Decimal(0)
    if kg < 0 or m2 < 0:
        raise ValidationError("Miktar negatif olamaz.")
    if neden == "sayim":
        fark_kg, fark_m2 = kg - ham_deri.kalan_kg, m2 - ham_deri.kalan_m2
        if not fark_kg and not fark_m2:
            raise ValidationError("Sayılan miktar sistemdekiyle aynı, düzeltme gerekmiyor.")
    else:
        if not kg and not m2:
            raise ValidationError("Düşülecek kg veya m² girin.")
        if kg > ham_deri.kalan_kg or m2 > ham_deri.kalan_m2:
            raise ValidationError(f"Stokta {ham_deri.kalan_kg} kg / {ham_deri.kalan_m2} m² var, daha fazlası düşülemez.")
        fark_kg, fark_m2 = -kg, -m2
    return DeriDuzeltme.objects.create(ham_deri=ham_deri, neden=neden, kg=fark_kg, m2=fark_m2,
                                       kullanici=kullanici, aciklama=aciklama)
