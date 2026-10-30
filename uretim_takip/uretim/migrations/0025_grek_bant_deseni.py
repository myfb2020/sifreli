"""Yeni lazer deseni DB015: Grek bant (katalogdaki İpek Peluş modellerinin altın/gümüş çerçevesi)."""

import importlib

from django.db import migrations

resim_koy = importlib.import_module("uretim.migrations.0022_katalog_yukle").resim_koy


def yukle(apps, schema_editor):
    Desen = apps.get_model("uretim", "LazerDeseni")
    if not Desen.objects.filter(kod="DB015").exists():
        kayit = Desen(kod="DB015")
        resim_koy(kayit, "desen", "DB015.jpg")
        kayit.save()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0024_siparis_onay_durumu")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
