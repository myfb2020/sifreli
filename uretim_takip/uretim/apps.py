from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ofis_yetkilerini_guncelle(sender, **kwargs):
    """Güncellemeyle yeni sayfalar gelince mevcut 'Ofis' grubu da yetkilerini alır."""
    from django.contrib.auth.models import Group

    from .hesaplar import OFIS_GRUBU, ofis_grubu

    if Group.objects.filter(name=OFIS_GRUBU).exists():
        ofis_grubu()


class UretimConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "uretim"

    def ready(self):
        from . import oturum  # noqa: F401  giriş/çıkış sinyallerini bağlar

        post_migrate.connect(ofis_yetkilerini_guncelle, sender=self)
