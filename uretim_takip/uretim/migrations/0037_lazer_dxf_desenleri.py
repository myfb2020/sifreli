"""Atölyenin lazer DXF desenleri LZ01–LZ08 (Bomba, Bulut, Dama, Kısa, Line, Rıva, Köşem, Mahsun)."""

import json
from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

VARLIK = Path(__file__).resolve().parent.parent / "tasarim_varlik"


def yukle(apps, schema_editor):
    Desen = apps.get_model("uretim", "LazerDeseni")
    bilgi = json.loads((VARLIK / "desen" / "desenler.json").read_text(encoding="utf-8"))
    for kod, b in bilgi.items():
        if b.get("tur") != "lz" or Desen.objects.filter(kod=kod).exists():
            continue
        kayit = Desen(kod=kod)
        yol = f"katalog/desen/{kod}.jpg"
        if default_storage.exists(yol):
            kayit.resim.name = yol
        else:
            with open(VARLIK / "desen_onizleme" / f"{kod}.jpg", "rb") as f:
                kayit.resim.save(f"{kod}.jpg", File(f), save=False)
        kayit.save()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0036_bn05_kaldir")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
