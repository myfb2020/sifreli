from django.conf import settings
from django.core.management.base import BaseCommand

from uretim import ai_deneme


class Command(BaseCommand):
    help = "Yapay zeka rötuşu denemesi (3 model): sonuç medya/ai_deneme/karsilastirma.jpg"

    def add_arguments(self, parser):
        parser.add_argument("--yapay-zekasiz", action="store_true", help="yalnız doku boyaması (API çağrısı yok)")

    def handle(self, *args, **o):
        klasor = settings.MEDIA_ROOT / "ai_deneme"
        try:
            yol = ai_deneme.calistir(str(klasor), yapay_zeka=not o["yapay_zekasiz"])
        except RuntimeError as h:
            self.stderr.write(self.style.ERROR(str(h)))
            return
        self.stdout.write(self.style.SUCCESS(f"Hazır: {yol}"))
