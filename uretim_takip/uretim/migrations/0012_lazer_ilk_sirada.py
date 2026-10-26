"""İstasyon listesinde Lazer kesim en üstte görünsün."""

from django.db import migrations


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    lazer = Asama.objects.filter(ad="Lazer kesim").first()
    if lazer is None:
        return
    aktifler = Asama.objects.filter(aktif=True).exclude(pk=lazer.pk)
    en_kucuk = min(aktifler.values_list("sira", flat=True), default=lazer.sira)
    if lazer.sira < en_kucuk:
        return
    dolu = set(Asama.objects.values_list("sira", flat=True))
    yeni = next((s for s in range(en_kucuk - 1, 0, -1) if s not in dolu), None)
    if yeni is not None:
        lazer.sira = yeni
        lazer.save(update_fields=["sira"])


class Migration(migrations.Migration):
    dependencies = [("uretim", "0011_kaplama")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
