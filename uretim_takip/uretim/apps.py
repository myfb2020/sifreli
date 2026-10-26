from django.apps import AppConfig


class UretimConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "uretim"

    def ready(self):
        from . import oturum  # noqa: F401  giriş/çıkış sinyallerini bağlar
