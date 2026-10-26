"""Fabrikanın gerçek istasyonları, makineleri ve halı türlerine göre istasyon sıraları.

Eski genel aşamalar silinmez (geçmiş kayıtlar onlara bağlı), yalnızca pasif yapılır.
"""

from django.db import migrations

# (istasyon, makineler)
ISTASYONLAR = [
    ("Nakış", ["Nakış makinesi"]),
    ("Lazer kesim", ["Lazer 1", "Lazer 2"]),
    ("Zig-zag", ["Zig-zag 1", "Zig-zag 2"]),
    ("Biye", ["Biye makinesi"]),
    ("Lanfel", ["Lanfel makinesi"]),
]

# Aynı sıra numarası = alternatif (ya biri ya diğeri).
ROTALAR = {
    "Lazerli halı": [(1, "Lazer kesim"), (2, "Zig-zag"), (3, "Biye"), (3, "Lanfel")],
    "Nakışlı halı": [(1, "Nakış"), (2, "Lazer kesim"), (3, "Zig-zag"), (4, "Biye"), (4, "Lanfel")],
    "Peluş halı": [(1, "Lazer kesim"), (2, "Zig-zag")],
}


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    Makine = apps.get_model("uretim", "Makine")
    HaliTuru = apps.get_model("uretim", "HaliTuru")
    RotaAdimi = apps.get_model("uretim", "RotaAdimi")

    en_buyuk = max(Asama.objects.values_list("sira", flat=True), default=0)
    sira = (en_buyuk // 100 + 1) * 100
    yeniler = {}
    for ad, makineler in ISTASYONLAR:
        asama = Asama.objects.filter(ad__iexact=ad).first()
        if asama is None:
            sira += 10
            asama = Asama.objects.create(ad=ad, sira=sira)
        elif not asama.aktif:
            asama.aktif = True
            asama.save(update_fields=["aktif"])
        yeniler[ad] = asama
        for makine in makineler:
            Makine.objects.get_or_create(ad=makine, defaults={"asama": asama})
    Asama.objects.exclude(pk__in=[a.pk for a in yeniler.values()]).update(aktif=False)

    for tur_adi, adimlar in ROTALAR.items():
        tur, _ = HaliTuru.objects.get_or_create(ad=tur_adi)
        for adim_sira, istasyon in adimlar:
            RotaAdimi.objects.get_or_create(hali_turu=tur, asama=yeniler[istasyon], defaults={"sira": adim_sira})


class Migration(migrations.Migration):
    dependencies = [("uretim", "0006_hali_turu_ve_makine")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
