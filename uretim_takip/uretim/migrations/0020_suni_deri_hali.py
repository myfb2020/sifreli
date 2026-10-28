"""Suni deri halı rotası: Lazer kesim 1 / 2 → Zig-zag → Kenar dikişi / Biye."""

from django.db import migrations

ROTA = [(1, "Lazer kesim 1"), (1, "Lazer kesim 2"), (2, "Zig-zag"), (3, "Kenar dikişi"), (3, "Biye")]


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    HaliTuru = apps.get_model("uretim", "HaliTuru")
    RotaAdimi = apps.get_model("uretim", "RotaAdimi")

    hali, yeni = HaliTuru.objects.get_or_create(ad="Suni deri halı")
    if not yeni:
        return  # elle tanımlanmışsa dokunma
    for sira, ad in ROTA:
        asama = Asama.objects.filter(ad__iexact=ad).first()
        if asama is not None:
            RotaAdimi.objects.create(hali_turu=hali, asama=asama, sira=sira)


class Migration(migrations.Migration):
    dependencies = [("uretim", "0019_fason")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
