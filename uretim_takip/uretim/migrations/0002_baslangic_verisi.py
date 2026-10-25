from django.db import migrations

ASAMALAR = [
    "Tasnif / kalite ayırma",
    "Islatma / yıkama",
    "Tabaklama",
    "Kurutma",
    "Tıraş / germe",
    "Kesim",
    "Dikim / birleştirme",
    "Astar / taban",
    "Son işlem (tarama, kenar)",
    "Kalite kontrol",
    "Paketleme",
]

DERI_TURLERI = ["Koyun", "Kuzu", "Keçi", "Dana / inek", "Tavşan"]


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    DeriTuru = apps.get_model("uretim", "DeriTuru")
    for sira, ad in enumerate(ASAMALAR, start=1):
        Asama.objects.get_or_create(ad=ad, defaults={"sira": sira * 10})
    for ad in DERI_TURLERI:
        DeriTuru.objects.get_or_create(ad=ad)


class Migration(migrations.Migration):
    dependencies = [("uretim", "0001_ilk")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
