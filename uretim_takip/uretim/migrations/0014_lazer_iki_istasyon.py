"""Lazer kesim iki ayrı istasyon olur: Lazer kesim 1 (Lazer 1) ve Lazer kesim 2 (Lazer 2).

Rotalarda ikisi aynı sıradadır (ya biri ya diğeri): iş iki lazerin ekranına da düşer, boşta olan alır.
"""

from django.db import migrations


def yukle(apps, schema_editor):
    Asama = apps.get_model("uretim", "Asama")
    Makine = apps.get_model("uretim", "Makine")
    RotaAdimi = apps.get_model("uretim", "RotaAdimi")

    lazer1 = Asama.objects.filter(ad__in=["Lazer kesim", "Lazer kesim 1"]).order_by("ad").first()
    if lazer1 is None:
        return
    if lazer1.ad != "Lazer kesim 1":
        lazer1.ad = "Lazer kesim 1"
        lazer1.save(update_fields=["ad"])

    lazer2 = Asama.objects.filter(ad="Lazer kesim 2").first()
    if lazer2 is None:
        lazer2 = Asama.objects.create(
            ad="Lazer kesim 2", sira=max(Asama.objects.values_list("sira", flat=True)) + 1000,
            azami_sure_saat=lazer1.azami_sure_saat, azami_bekleme_saat=lazer1.azami_bekleme_saat,
        )
    # İki lazer listelerde en üstte ve yan yana: diğer aktif istasyonlardan önceki iki boş sıra numarası.
    digerleri = Asama.objects.filter(aktif=True).exclude(pk__in=[lazer1.pk, lazer2.pk])
    en_kucuk = min(digerleri.values_list("sira", flat=True), default=1000)
    dolu = set(Asama.objects.exclude(pk__in=[lazer1.pk, lazer2.pk]).values_list("sira", flat=True))
    bos = [s for s in range(en_kucuk - 1, 0, -1) if s not in dolu][:2]
    if len(bos) == 2:
        lazer1.sira, lazer2.sira = bos[1] + 100000, bos[0] + 100000  # benzersizlik çakışmasın diye önce geçici
        lazer1.save(update_fields=["sira"])
        lazer2.save(update_fields=["sira"])
        lazer1.sira, lazer2.sira = bos[1], bos[0]
        lazer1.save(update_fields=["sira"])
        lazer2.save(update_fields=["sira"])
    # İkinci lazer makinesi kendi istasyonuna geçer.
    Makine.objects.filter(ad="Lazer 2").update(asama=lazer2)

    for adim in RotaAdimi.objects.filter(asama=lazer1):
        RotaAdimi.objects.get_or_create(hali_turu_id=adim.hali_turu_id, asama=lazer2, defaults={"sira": adim.sira})


class Migration(migrations.Migration):
    dependencies = [("uretim", "0013_alter_asama_sira")]
    operations = [migrations.RunPython(yukle, migrations.RunPython.noop)]
