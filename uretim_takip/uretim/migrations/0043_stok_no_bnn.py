"""Stok lot numaraları HD-… → BNN-… (kullanıcı 2026-11-17; aynı sıra numarası, eski etiketler models.stok_no ile çalışır)."""
from django.db import migrations


def ileri(apps, schema_editor):
    HamDeriGirisi = apps.get_model("uretim", "HamDeriGirisi")
    for h in HamDeriGirisi.objects.filter(lot_no__startswith="HD-"):
        yeni = "BNN-" + h.lot_no[3:]
        if not HamDeriGirisi.objects.filter(lot_no=yeni).exists():
            HamDeriGirisi.objects.filter(pk=h.pk).update(lot_no=yeni)


def geri(apps, schema_editor):
    HamDeriGirisi = apps.get_model("uretim", "HamDeriGirisi")
    for h in HamDeriGirisi.objects.filter(lot_no__startswith="BNN-"):
        eski = "HD-" + h.lot_no[4:]
        if not HamDeriGirisi.objects.filter(lot_no=eski).exists():
            HamDeriGirisi.objects.filter(pk=h.pk).update(lot_no=eski)


class Migration(migrations.Migration):
    dependencies = [("uretim", "0042_is_olculeri")]
    operations = [migrations.RunPython(ileri, geri)]
