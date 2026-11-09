"""Bienca BN05 geri gelir (2026-11-09, kullanıcı): gri & siyah-gümüş varak; BN01 dokusu yenilendi (krem & altın)."""

from django.db import migrations


def ekle(apps, schema_editor):
    Renk = apps.get_model("uretim", "Renk")
    r, _ = Renk.objects.get_or_create(kod="BN05", defaults={"ad": "Gri & siyah-gümüş varak", "grup": "bienca", "sira": 5})
    r.aktif = True
    r.ad = r.ad or "Gri & siyah-gümüş varak"
    r.save()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0037_lazer_dxf_desenleri")]
    operations = [migrations.RunPython(ekle, migrations.RunPython.noop)]
