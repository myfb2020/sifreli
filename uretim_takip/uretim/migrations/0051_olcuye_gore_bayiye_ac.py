"""Ölçüye göre doğru çizilen 40 katalog modeli bayiye açılır (2026-11-26, kullanıcı: 'modeli düzgün çıkanları bayiye
açalım'). Bayi bunları yalnız olduğu gibi sipariş eder (🎨 Tasarla yalnız 9 vitrin modelinde); ölçü yazınca resim o
ölçüde çizilir. Pasif modeller açılmaz."""

from django.db import migrations

ACILAN = [
    "BNA-001", "BNA-002", "BNA-003", "BNA-004", "BNA-005", "BNA-006", "BNA-007", "BNA-008", "BNA-009", "BNA-010",
    "BNA-011", "BNA-013", "BNA-014", "BNA-015", "BNA-016", "BNA-026",
    "IPS-435", "IPS-440", "IPS-448", "IPS-449", "IPS-451", "IPS-452", "IPS-455", "IPS-459", "IPS-460", "IPS-463",
    "IPS-465", "IPS-470", "IPS-473", "IPS-478",
    "PCH-003", "PCH-005", "PCH-006", "PCH-011", "PCH-012",
    "RNO-001", "RNO-003", "RNO-005", "RNO-007", "RNO-009",
]


def ac(apps, schema_editor):
    apps.get_model("uretim", "KatalogModeli").objects.filter(kod__in=ACILAN, aktif=True).update(bayiye_acik=True)


class Migration(migrations.Migration):
    dependencies = [("uretim", "0050_dxf_desenleri_2")]
    operations = [migrations.RunPython(ac, migrations.RunPython.noop)]
