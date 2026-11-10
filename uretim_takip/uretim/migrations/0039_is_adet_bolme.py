"""İşte halı adedi + bölünen iş (2026-11-09, kullanıcı): aynı ölçüdeki halılar her istasyondan tek tek geçebilir."""

import django.db.models.deletion
from django.db import migrations, models


def adetleri_doldur(apps, schema_editor):
    UretimLotu = apps.get_model("uretim", "UretimLotu")
    for lot in UretimLotu.objects.filter(kalem__isnull=False).select_related("kalem"):
        if lot.kalem.adet and lot.kalem.adet > 1:
            lot.adet = lot.kalem.adet
            lot.save(update_fields=["adet"])


class Migration(migrations.Migration):
    dependencies = [("uretim", "0038_bn05_geri")]
    operations = [
        migrations.AddField(model_name="uretimlotu", name="adet", field=models.PositiveIntegerField(
            default=1, help_text="Bu işte birlikte giden halı sayısı; bitenler ayrı işe bölünüp geçer.",
            verbose_name="halı adedi")),
        migrations.AddField(model_name="uretimlotu", name="ana_lot", field=models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bolunenler",
            to="uretim.uretimlotu", verbose_name="bölündüğü iş")),
        migrations.RunPython(adetleri_doldur, migrations.RunPython.noop),
    ]
