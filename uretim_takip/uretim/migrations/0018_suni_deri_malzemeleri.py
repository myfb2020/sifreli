"""Suni deri halı ana malzemeleri ve fasonda birleştirilen malzemeler."""

from django.db import migrations

TEKIL = ["Keçe", "Süet", "Rona", "Suni deri"]
BILESIK = ["3'lü lamine (Keçe+Süet+Rona)", "3'lü lamine (Keçe+Süet+Suni deri)", "Halı tabanı (Keçe+Süet)"]


def yukle(apps, schema_editor):
    DeriTuru = apps.get_model("uretim", "DeriTuru")
    for ad in TEKIL:
        DeriTuru.objects.get_or_create(ad=ad)
    for ad in BILESIK:
        DeriTuru.objects.update_or_create(ad=ad, defaults={"bilesik": True})


class Migration(migrations.Migration):
    dependencies = [("uretim", "0017_malzeme_turu_cesit")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
