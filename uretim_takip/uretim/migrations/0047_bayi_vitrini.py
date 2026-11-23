"""Bayi vitrini (2026-11-23, kullanıcı kararları):
1. Fotoğrafı kötü 45 model PASİF: bayide ve tasarım stüdyolarında görünmez; ofis katalogunda 'Pasif modeller'de durur,
   ofis siparişinde seçilebilir; iyi fotoğraf gelince katalogdan 'Aktif yap'.
2. Bayi Suni deri Sipariş ver'de yalnız 9 model (parcali.BAYI_VITRINI); öteki suni deri modelleri bayiden gizlenir.
   Deri/kürk tarafı ve 'Müşteri modelleri' değişmez.
"""

from django.db import migrations

PASIF = (
    ["BNA-025", "BNA-027", "BNA-028", "RNO-013"]
    + [f"PCH-{n:03d}" for n in (1, 2, 4, 7, 8, 9, 10, 13, 14, 15, 16)]
    + [f"TOS-{n:03d}" for n in (34, 40, 44, 48, 54, 60, 61, 63, 65, 66, 67, 68)]
    + ["TKK-238", "TKA-334", "TKA-338", "TKA-339"]
    + [f"IPS-{n}" for n in (453, 454, 458, 466, 467, 468, 471, 475, 479, 481, 482, 483, 484, 485)]
)
VITRIN = ["BNA-018", "BNA-019", "IPS-442", "IPS-457", "IPS-476", "RNO-004", "RNO-010", "RNO-011", "RNO-012"]
SUNI_SERILER = {"rono", "bienca", "ipek peluş", "peluche"}


def _kucuk(ad):
    return ad.replace("İ", "i").replace("I", "ı").lower()


def uygula(apps, schema_editor):
    Model = apps.get_model("uretim", "KatalogModeli")
    Model.objects.filter(kod__in=PASIF).update(aktif=False, bayiye_acik=False)
    for m in Model.objects.select_related("seri").exclude(kod__in=VITRIN):
        if _kucuk(m.seri.ad) in SUNI_SERILER and m.bayiye_acik:
            m.bayiye_acik = False
            m.save(update_fields=["bayiye_acik"])
    Model.objects.filter(kod__in=VITRIN).update(aktif=True, bayiye_acik=True)


def geri(apps, schema_editor):
    apps.get_model("uretim", "KatalogModeli").objects.filter(kod__in=PASIF).update(aktif=True)


class Migration(migrations.Migration):

    dependencies = [
        ("uretim", "0046_toplu_stok"),
    ]

    operations = [
        migrations.RunPython(uygula, geri),
    ]
