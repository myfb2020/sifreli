"""Gerçek fotoğraflı Rono modelleri RNO-006…RNO-012 (bayi renklerini fotoğraf üzerinde seçer)."""

from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

KLASOR = Path(__file__).resolve().parent.parent / "tasarim_varlik" / "foto_model"
MODELLER = {
    "RNO-006": "Oval · Grek nakış şeridi",
    "RNO-007": "Lazer desenli bant · çift çerçeve",
    "RNO-008": "Kesik köşe · hasır desen halka",
    "RNO-009": "Altın lazer desenli çerçeve",
    "RNO-010": "Gönye köşe · Bienca eskitme bant",
    "RNO-011": "Gönye köşe · eskitme bant · biye",
    "RNO-012": "Gönye köşe · iç içe iki bant",
}


def yukle(apps, schema_editor):
    Seri = apps.get_model("uretim", "KatalogSerisi")
    Model = apps.get_model("uretim", "KatalogModeli")
    seri = Seri.objects.filter(ad__iexact="Rono").first()
    if seri is None:
        seri = Seri.objects.create(ad="Rono", sira=110, kartela="rono")
    for kod, ad in MODELLER.items():
        if Model.objects.filter(kod=kod).exists():
            continue
        kayit = Model(kod=kod, seri=seri, notlar=ad)
        yol = f"katalog/model/{kod}.jpg"
        if default_storage.exists(yol):
            kayit.resim.name = yol
        else:
            with open(KLASOR / f"{kod}.jpg", "rb") as f:
                kayit.resim.save(f"{kod}.jpg", File(f), save=False)
        kayit.save()


def geri(apps, schema_editor):
    apps.get_model("uretim", "KatalogModeli").objects.filter(kod__in=MODELLER, siparis__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0031_kartela_bayi_tamir")]
    operations = [migrations.RunPython(yukle, geri)]
