"""Üretim iş kuralları. Görünümler veritabanını doğrudan değiştirmez, buradan geçer."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import HamDeriGirisi, IslemKaydi, LotKaynagi, UretimLotu


@transaction.atomic
def islem_baslat(*, lot, asama, personel, aciklama=""):
    lot = UretimLotu.objects.select_for_update().get(pk=lot.pk)
    if lot.durum in ("tamamlandi", "iptal"):
        raise ValidationError(f"{lot} işi {lot.get_durum_display().lower()}, işlem başlatılamaz.")
    if lot.islemler.filter(bitis__isnull=True).exists():
        raise ValidationError(f"{lot} işinde zaten açık bir işlem var. Önce onu bitirin.")

    islem = IslemKaydi.objects.create(
        lot=lot,
        asama=asama,
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
def islem_bitir(*, islem, personel, cikis_kg, cikis_m2, aciklama=""):
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

    lot = islem.lot
    lot.mevcut_kg = cikis_kg
    lot.mevcut_m2 = cikis_m2
    lot.durum = "tamamlandi" if islem.asama.son_asama_mi else "bekliyor"
    lot.save(update_fields=["mevcut_kg", "mevcut_m2", "durum"])

    siparis = lot.siparis
    if siparis and lot.durum == "tamamlandi":
        if not siparis.lotlar.exclude(durum__in=["tamamlandi", "iptal"]).exists():
            siparis.durum = "tamamlandi"
            siparis.save(update_fields=["durum"])
    return islem


@transaction.atomic
def yeni_is_baslat(*, personel, siparis, kaynaklar, asama, aciklama=""):
    """Stoktan malzeme alarak yeni bir iş açar ve ilk aşamasını başlatır.

    kaynaklar: [(stok_lotu, kg, m2), ...]. Aynı stok lotu birden çok kez okutulduysa miktarlar toplanır.
    """
    toplam = {}
    for stok, kg, m2 in kaynaklar:
        onceki = toplam.get(stok.pk, (stok, Decimal(0), Decimal(0)))
        toplam[stok.pk] = (stok, onceki[1] + (kg or 0), onceki[2] + (m2 or 0))
    if not toplam:
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
        baslangic_kg=sum((kg for _, kg, _ in toplam.values()), Decimal(0)),
        baslangic_m2=sum((m2 for _, _, m2 in toplam.values()), Decimal(0)),
    )
    LotKaynagi.objects.bulk_create(
        LotKaynagi(uretim_lotu=lot, ham_deri=kilitli[pk], kg=kg, m2=m2) for pk, (_, kg, m2) in toplam.items()
    )
    return islem_baslat(lot=lot, asama=asama, personel=personel, aciklama=aciklama)
