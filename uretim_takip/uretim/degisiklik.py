"""Değişiklik sayacı (2026-11-24, hız).

Programda bir kayıt eklenince, değişince ya da silinince `SistemAyari.degisiklik_no` bir artar. İstasyon tabletleri
20 sn'de bir yenilenirken sunucu önce yalnız bu sayıya bakar: sayı ve dakika aynıysa liste hiç hesaplanmaz.
Sayacı atlayan toplu güncellemeler (`.update()`) en çok bir dakika gecikmeyle görünür (anahtarda dakika var).
"""

from django.apps import apps
from django.db import DatabaseError, transaction
from django.db.models import F
from django.db.models.signals import m2m_changed, post_delete, post_save

SAYILMAYANLAR = {"oturumkaydi", "sistemayari"}  # giriş kaydı ekranı değiştirmez


def _artir():
    from .models import SistemAyari

    try:
        with transaction.atomic():  # sayaç yazılamazsa (ör. göç sırasında) kayıt yine olur; ekran en çok 1 dk geç yenilenir
            if not SistemAyari.objects.filter(pk=1).update(degisiklik_no=F("degisiklik_no") + 1):
                SistemAyari.yukle()
    except DatabaseError:
        pass


def _degisti(sender, **kwargs):
    meta = getattr(sender, "_meta", None)
    if meta is None or meta.app_label != "uretim" or meta.model_name in SAYILMAYANLAR or kwargs.get("raw"):
        return
    if "action" in kwargs and not kwargs["action"].startswith("post_"):
        return
    try:  # göçlerdeki geçmiş modeller (eski tablo yapısı) sayılmaz
        if apps.get_model(meta.app_label, meta.object_name) is not sender:
            return
    except LookupError:
        return
    _artir()  # kaydın kendi işlemi içinde: kayıt geri alınırsa sayaç da geri alınır


def numara():
    from .models import SistemAyari

    return SistemAyari.objects.filter(pk=1).values_list("degisiklik_no", flat=True).first() or 0


def bagla():
    post_save.connect(_degisti, dispatch_uid="degisiklik_kayit")
    post_delete.connect(_degisti, dispatch_uid="degisiklik_silme")
    m2m_changed.connect(_degisti, dispatch_uid="degisiklik_m2m")
