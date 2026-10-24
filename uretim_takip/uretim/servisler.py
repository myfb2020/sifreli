"""Üretim iş kuralları. Görünümler veritabanını doğrudan değiştirmez, buradan geçer."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import IslemKaydi, UretimLotu


@transaction.atomic
def islem_baslat(*, lot, asama, personel, aciklama=""):
    lot = UretimLotu.objects.select_for_update().get(pk=lot.pk)
    if lot.durum in ("tamamlandi", "iptal"):
        raise ValidationError(f"{lot} lotu {lot.get_durum_display().lower()}, işlem başlatılamaz.")
    if lot.islemler.filter(bitis__isnull=True).exists():
        raise ValidationError(f"{lot} lotunda zaten açık bir işlem var. Önce onu bitirin.")

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
