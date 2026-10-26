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


def makine_ozeti(baslangic, bitis):
    """Makine seçilerek yapılan işlemler: makine başına iş sayısı ve çalışma süresi."""
    qs = tamamlanan_islemler(baslangic, bitis).filter(makine__isnull=False)
    return _ozet(qs, "makine__asama__sira", "makine__ad")


def personel_istasyon_ozeti(baslangic, bitis):
    """Hangi çalışan hangi istasyonda kaç iş yaptı, ne kadar çalıştı."""
    return _ozet(tamamlanan_islemler(baslangic, bitis), "personel__ad_soyad", "asama__sira", "asama__ad")


def bekleme_suresi_ekle(islemler):
    """İşin bir önceki istasyonu bitirmesinden bu istasyonda başlamasına kadar geçen süreyi her işleme ekler.

    islemler aynı işe ait, başlangıca göre sıralı olmalı. İlk istasyon için bekleme yoktur (None).
    """
    onceki_bitis = None
    for islem in islemler:
        islem.bekleme = islem.baslangic - onceki_bitis if onceki_bitis else None
        onceki_bitis = islem.bitis
    return islemler


def bekleme_ozeti(baslangic, bitis):
    """İstasyonlar arası bekleme: bir istasyondan çıkan iş bir sonrakinde ne kadar sürede başlandı.

    Aralıkta başlayan işlemler esas alınır. Satırlar geçiş bazındadır (ör. Lazer kesim → Zig-zag).
    """
    bas, son = _aralik(baslangic, bitis)
    lot_idleri = IslemKaydi.objects.filter(baslangic__gte=bas, baslangic__lt=son).values("lot_id")
    islemler = (
        IslemKaydi.objects.filter(lot_id__in=lot_idleri).select_related("asama").order_by("lot_id", "baslangic")
    )
    gecisler = {}
    onceki = None
    for islem in islemler:
        if onceki and onceki.lot_id == islem.lot_id and onceki.bitis and bas <= islem.baslangic < son:
            bekleme = max(islem.baslangic - onceki.bitis, timedelta(0))
            anahtar = (onceki.asama.sira, islem.asama.sira, f"{onceki.asama.ad} → {islem.asama.ad}")
            gecisler.setdefault(anahtar, []).append(bekleme)
        onceki = islem
    sonuc = []
    for (_, _, ad), sureler in sorted(gecisler.items()):
        sonuc.append({
            "gecis": ad, "sayi": len(sureler),
            "ortalama": sum(sureler, timedelta(0)) / len(sureler), "en_uzun": max(sureler),
        })
    return sonuc
