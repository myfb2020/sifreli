"""Peluş halının son adımı: Biye ya da Kenar dikişi."""

from django.db import migrations


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    HaliTuru = apps.get_model("uretim", "HaliTuru")
    RotaAdimi = apps.get_model("uretim", "RotaAdimi")

    kenar = Asama.objects.filter(ad__iexact="Kenar dikişi").first()
    if kenar is None:
        sira = max(Asama.objects.values_list("sira", flat=True), default=0) + 10
        kenar = Asama.objects.create(ad="Kenar dikişi", sira=sira)
    pelus = HaliTuru.objects.filter(ad="Peluş halı").first()
    biye = Asama.objects.filter(ad="Biye").first()
    if pelus is None:
        return
    son = max(pelus.adimlar.values_list("sira", flat=True), default=0) + 1
    for asama in (biye, kenar):
        if asama is not None:
            RotaAdimi.objects.get_or_create(hali_turu=pelus, asama=asama, defaults={"sira": son})


class Migration(migrations.Migration):
    dependencies = [("uretim", "0008_stok_giris_birimi")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
