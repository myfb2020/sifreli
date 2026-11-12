"""Katalog fotoğrafları beyaz zeminde (2026-11-11, kullanıcı): katalog_tohum/model'deki yeni fotoğraflar medyaya
yeni adla (katalog/model/b/KOD.jpg; tarayıcı eskisini önbellekten göstermesin) kopyalanır, eski dosya silinir.
Ofisin sonradan elle değiştirdiği fotoğraflara (adı farklı olanlar) dokunulmaz."""

from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

TOHUM = Path(__file__).resolve().parent.parent / "katalog_tohum" / "model"


def yenile(apps, schema_editor):
    Model = apps.get_model("uretim", "KatalogModeli")
    for m in Model.objects.exclude(resim=""):
        kaynak = TOHUM / f"{m.kod}.jpg"
        if m.resim.name != f"katalog/model/{m.kod}.jpg" or not kaynak.exists():
            continue
        yeni = f"katalog/model/b/{m.kod}.jpg"
        if not default_storage.exists(yeni):
            with open(kaynak, "rb") as f:
                default_storage.save(yeni, File(f))
        eski = m.resim.name
        m.resim.name = yeni
        m.save(update_fields=["resim"])
        try:
            default_storage.delete(eski)
        except OSError:
            pass


class Migration(migrations.Migration):
    dependencies = [("uretim", "0040_deniz_aslani")]
    operations = [migrations.RunPython(yenile, migrations.RunPython.noop)]
