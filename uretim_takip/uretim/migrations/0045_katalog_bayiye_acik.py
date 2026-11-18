"""Bayi gözüyle inceleme (2026-11-18, kullanıcı kararları):
1. Fotoğrafı kötü (kesik, eğik, yabancı şerit, bulanık…) 16 model ve başka modelle aynı fotoğraflı 2 model bayinin
   Sipariş ver sayfasından gizlenir (`bayiye_acik`); ofiste ve katalogda kalır, yönetim panelinden yeniden açılabilir.
2. Kullanıcının gri zeminde çektiği Rono fotoğrafları beyaz zeminli hâlleriyle değişir (katalog_tohum/beyaz,
   `is_belgeleri/katalog_beyaz/rono_beyaz.py`). Ofisin sonradan elle değiştirdiği fotoğraflara dokunulmaz.
"""

from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations, models

GIZLENEN = [
    "BNA-027", "BNA-028", "PCH-004", "PCH-007", "PCH-009", "PCH-010", "PCH-015", "TOS-040", "TOS-052", "FDA-634",
    "BNA-021", "IPS-471", "IPS-482", "IPS-483", "IPS-484", "TOS-060",
    "IPS-468", "PCH-016",  # IPS-466 / PCH-006 ile aynı fotoğraf
]
BEYAZ = Path(__file__).resolve().parent.parent / "katalog_tohum" / "beyaz"


def uygula(apps, schema_editor):
    Model = apps.get_model("uretim", "KatalogModeli")
    Model.objects.filter(kod__in=GIZLENEN).update(bayiye_acik=False)
    for kaynak in sorted(BEYAZ.glob("*.jpg")):
        kod = kaynak.stem
        m = Model.objects.filter(kod=kod).first()
        if m is None or m.resim.name not in ("", f"katalog/model/{kod}.jpg"):
            continue
        yeni = f"katalog/model/b/{kod}.jpg"
        if default_storage.exists(yeni):
            default_storage.delete(yeni)
        with open(kaynak, "rb") as f:
            default_storage.save(yeni, File(f))
        eski = m.resim.name
        m.resim.name = yeni
        m.save(update_fields=["resim"])
        if eski:
            try:
                default_storage.delete(eski)
            except OSError:
                pass


def geri(apps, schema_editor):
    apps.get_model("uretim", "KatalogModeli").objects.filter(kod__in=GIZLENEN).update(bayiye_acik=True)


class Migration(migrations.Migration):

    dependencies = [
        ("uretim", "0044_deri_satisi"),
    ]

    operations = [
        migrations.AddField(
            model_name="katalogmodeli",
            name="bayiye_acik",
            field=models.BooleanField(
                default=True,
                help_text="Kapalıysa model ofiste ve katalogda kalır, bayinin Sipariş ver sayfasında görünmez (ör. fotoğrafı kötü olan).",
                verbose_name="bayi sipariş sayfasında görünsün",
            ),
        ),
        migrations.RunPython(uygula, geri),
    ]
