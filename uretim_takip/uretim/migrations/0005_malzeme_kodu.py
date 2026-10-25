from django.db import migrations, models


def kod_ver(apps, schema_editor):
    """Var olan malzemelere sırayla MZ-0001, MZ-0002… kodu verir."""
    Malzeme = apps.get_model("uretim", "Malzeme")
    for sira, malzeme in enumerate(Malzeme.objects.order_by("pk"), start=1):
        malzeme.kod = f"MZ-{sira:04d}"
        malzeme.save(update_fields=["kod"])


class Migration(migrations.Migration):
    dependencies = [("uretim", "0004_malzeme_ve_istasyon")]

    operations = [
        migrations.AddField(
            model_name="malzeme",
            name="kod",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(kod_ver, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="malzeme",
            name="kod",
            field=models.CharField(
                blank=True, help_text="Etiketteki kod; boşsa otomatik verilir.", max_length=20, unique=True
            ),
        ),
    ]
