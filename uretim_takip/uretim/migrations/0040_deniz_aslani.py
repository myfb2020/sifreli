"""Stoğa yeni ana malzeme türü: Deniz aslanı (2026-11-10, kullanıcı)."""

from django.db import migrations


def ekle(apps, schema_editor):
    apps.get_model("uretim", "DeriTuru").objects.get_or_create(ad="Deniz aslanı")


class Migration(migrations.Migration):
    dependencies = [("uretim", "0039_is_adet_bolme")]
    operations = [migrations.RunPython(ekle, migrations.RunPython.noop)]
