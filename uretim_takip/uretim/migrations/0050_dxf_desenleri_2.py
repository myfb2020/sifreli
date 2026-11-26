"""Kullanıcının DXF lazer desenleri (2026-11-26): DB003/DB007/DB013/DB015 fotoğraftan çizilmişti → gerçek kesim dosyası;
yeni LZ09–LZ15 (Adobe, Çiçek, Major, Prenses, Tall, Tamamlar, There). Desen resimleri tasarim_varlik/desen_onizleme'den."""

from pathlib import Path

from django.core.files import File
from django.db import migrations

VARLIK = Path(__file__).resolve().parent.parent / "tasarim_varlik"
DEGISEN = ["DB003", "DB007", "DB013", "DB015"]
YENI = ["LZ09", "LZ10", "LZ11", "LZ12", "LZ13", "LZ14", "LZ15"]


def yukle(apps, schema_editor):
    Desen = apps.get_model("uretim", "LazerDeseni")
    for kod in DEGISEN + YENI:
        kayit = Desen.objects.filter(kod=kod).first()
        if kayit is None:
            kayit = Desen(kod=kod)
        elif kod in YENI:
            continue
        with open(VARLIK / "desen_onizleme" / f"{kod}.jpg", "rb") as f:
            kayit.resim.save(f"{kod}_dxf.jpg", File(f), save=False)
        kayit.save()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0049_degisiklik_sayaci")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
