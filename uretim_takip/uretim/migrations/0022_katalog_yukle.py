"""Katalog 2026 PDF'inden çıkarılan seriler, modeller (resimli) ve lazer desenleri."""

import json
from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage
from django.db import migrations

TOHUM = Path(__file__).resolve().parent.parent / "katalog_tohum"


def resim_koy(kayit, klasor, dosya):
    """Resim medya klasöründe zaten varsa (yeniden kurulum, testler) kopyalanmaz, var olan kullanılır."""
    yol = f"katalog/{klasor}/{dosya}"
    if default_storage.exists(yol):
        kayit.resim.name = yol
    else:
        with open(TOHUM / klasor / dosya, "rb") as f:
            kayit.resim.save(dosya, File(f), save=False)


def yukle(apps, schema_editor):
    Seri = apps.get_model("uretim", "KatalogSerisi")
    Model = apps.get_model("uretim", "KatalogModeli")
    Desen = apps.get_model("uretim", "LazerDeseni")
    HaliTuru = apps.get_model("uretim", "HaliTuru")
    veri = json.loads((TOHUM / "katalog.json").read_text(encoding="utf-8"))

    seriler = {}
    for sira, ad in enumerate(veri["seriler"], 1):
        seriler[ad], _ = Seri.objects.get_or_create(ad=ad, defaults={"sira": sira * 10})
    lazerli = HaliTuru.objects.filter(ad="Lazerli halı").first()
    if lazerli and "Lazerli Toskana" in seriler and seriler["Lazerli Toskana"].hali_turu_id is None:
        seriler["Lazerli Toskana"].hali_turu = lazerli
        seriler["Lazerli Toskana"].save(update_fields=["hali_turu"])

    for m in veri["modeller"]:
        if Model.objects.filter(kod=m["kod"]).exists():
            continue
        kayit = Model(kod=m["kod"], seri=seriler[m["seri"]])
        resim_koy(kayit, "model", m["dosya"])
        kayit.save()
    for d in veri["desenler"]:
        if Desen.objects.filter(kod=d["kod"]).exists():
            continue
        kayit = Desen(kod=d["kod"])
        resim_koy(kayit, "desen", d["dosya"])
        kayit.save()


class Migration(migrations.Migration):
    dependencies = [("uretim", "0021_katalog")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
