"""Peluş halının ilk istasyonu: Kaplama (pres)."""

from django.db import migrations


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    Makine = apps.get_model("uretim", "Makine")
    HaliTuru = apps.get_model("uretim", "HaliTuru")
    RotaAdimi = apps.get_model("uretim", "RotaAdimi")

    kaplama = Asama.objects.filter(ad__iexact="Kaplama").first()
    if kaplama is None:
        # Genel sırada Lazer kesimin hemen önüne; o numara doluysa en sona.
        lazer = Asama.objects.filter(ad="Lazer kesim").first()
        dolu = set(Asama.objects.values_list("sira", flat=True))
        sira = lazer.sira - 5 if lazer and lazer.sira - 5 not in dolu and lazer.sira > 5 else max(dolu, default=0) + 10
        kaplama = Asama.objects.create(ad="Kaplama", sira=sira)
    elif not kaplama.aktif:
        kaplama.aktif = True
        kaplama.save(update_fields=["aktif"])
    Makine.objects.get_or_create(ad="Pres", defaults={"asama": kaplama})

    pelus = HaliTuru.objects.filter(ad="Peluş halı").first()
    if pelus is None or pelus.adimlar.filter(asama=kaplama).exists():
        return
    # Mevcut adımlar bir sıra kayar, Kaplama ilk adım olur.
    for adim in pelus.adimlar.order_by("-sira"):
        adim.sira += 1
        adim.save(update_fields=["sira"])
    RotaAdimi.objects.create(hali_turu=pelus, asama=kaplama, sira=1)


class Migration(migrations.Migration):
    dependencies = [("uretim", "0010_oturum_kaydi")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
