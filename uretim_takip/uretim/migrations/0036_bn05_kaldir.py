"""Bienca 4 renktir: BN05 kaldırılır (kullanılmışsa yalnız pasif olur, eski sipariş yazısı kalır)."""

from django.db import migrations


def kaldir(apps, schema_editor):
    Renk = apps.get_model("uretim", "Renk")
    Siparis = apps.get_model("uretim", "Siparis")
    for r in Renk.objects.filter(kod="BN05"):
        if Siparis.objects.filter(renk=r).exists():
            r.aktif = False
            r.save(update_fields=["aktif"])
        else:
            r.delete()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0035_duzeltme_yetkisi")]
    operations = [migrations.RunPython(kaldir, migrations.RunPython.noop)]
