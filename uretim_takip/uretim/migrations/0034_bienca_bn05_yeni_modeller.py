"""Bienca BN05 (krem & yoğun altın), BN02 adı (bakır eskitme); fotoğraflı yeni modeller BNA-027, BNA-028, RNO-013."""

from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

KLASOR = Path(__file__).resolve().parent.parent / "tasarim_varlik" / "foto_model"
MODELLER = {
    "BNA-027": ("Bienca", "Krem & altın Bienca · lazer desenli bant"),
    "BNA-028": ("Bienca", "Bienca · lazer desenli bant · altın biye"),
    "RNO-013": ("Rono", "Nakışlı Rono · Grek madalyon sıraları"),
}


def yukle(apps, schema_editor):
    Renk = apps.get_model("uretim", "Renk")
    Renk.objects.get_or_create(kod="BN05", defaults={"ad": "Krem & yoğun altın eskitme", "grup": "bienca", "sira": 5})
    Renk.objects.filter(kod="BN02").update(ad="Bakır eskitme / gri")
    Seri = apps.get_model("uretim", "KatalogSerisi")
    Model = apps.get_model("uretim", "KatalogModeli")
    for kod, (seri_ad, ad) in MODELLER.items():
        if Model.objects.filter(kod=kod).exists():
            continue
        seri = Seri.objects.filter(ad__iexact=seri_ad).first() or Seri.objects.create(
            ad=seri_ad, sira=100, kartela=seri_ad.lower())
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
    dependencies = [("uretim", "0033_islem_stok_dusumu")]
    operations = [migrations.RunPython(yukle, geri)]
