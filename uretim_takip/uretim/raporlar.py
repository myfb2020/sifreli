"""Personel ve aşama raporları için sorgular."""

from datetime import datetime, time, timedelta

from django.db.models import Count, DurationField, ExpressionWrapper, F, Sum
from django.utils import timezone

from .models import IslemKaydi


def _aralik(baslangic, bitis):
    tz = timezone.get_current_timezone()
    bas = timezone.make_aware(datetime.combine(baslangic, time.min), tz)
    son = timezone.make_aware(datetime.combine(bitis + timedelta(days=1), time.min), tz)
    return bas, son


def tamamlanan_islemler(baslangic, bitis):
    bas, son = _aralik(baslangic, bitis)
    return IslemKaydi.objects.filter(bitis__gte=bas, bitis__lt=son)


def _ozet(qs, *gruplar):
    sure = ExpressionWrapper(F("bitis") - F("baslangic"), output_field=DurationField())
    satirlar = (
        qs.values(*gruplar)
        .annotate(
            islem_sayisi=Count("id"),
            giris_kg=Sum("giris_kg"),
            cikis_kg=Sum("cikis_kg"),
            giris_m2=Sum("giris_m2"),
            cikis_m2=Sum("cikis_m2"),
            toplam_sure=Sum(sure),
        )
        .order_by(*gruplar)
    )
    sonuc = []
    for s in satirlar:
        s["fire_kg"] = s["giris_kg"] - s["cikis_kg"]
        s["fire_m2"] = s["giris_m2"] - s["cikis_m2"]
        s["fire_yuzde_m2"] = round(s["fire_m2"] / s["giris_m2"] * 100, 1) if s["giris_m2"] else None
        sonuc.append(s)
    return sonuc


def personel_ozeti(baslangic, bitis):
    """Her çalışanın bitirdiği işlemler. İşi başlatan kişi esas alınır."""
    return _ozet(tamamlanan_islemler(baslangic, bitis), "personel__ad_soyad")


def asama_ozeti(baslangic, bitis):
    return _ozet(tamamlanan_islemler(baslangic, bitis), "asama__sira", "asama__ad")


def sure_metni(sure):
    if sure is None:
        return "-"
    dakika = int(sure.total_seconds() // 60)
    return f"{dakika // 60} sa {dakika % 60} dk"
