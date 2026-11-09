from django.conf import settings
from django.core.management.base import BaseCommand

from uretim import ai_deneme


class Command(BaseCommand):
    help = "Yapay zeka rötuşu denemesi (3 model): sonuç medya/ai_deneme/karsilastirma.jpg"

    def add_arguments(self, parser):
        parser.add_argument("--yapay-zekasiz", action="store_true", help="API çağrısı yok (yalnız çizim / boyama)")
        parser.add_argument("--parcali", action="store_true", help="parçalı çizime son rötuş (seçili 10 model)")
        parser.add_argument("--guc", type=float, default=0.22, help="yapay zeka gücü (0.15–0.35)")
        parser.add_argument("--model", nargs="*", help="yalnız bu modeller (örn. RNO-004 BNA-009)")

    def handle(self, *args, **o):
        klasor = settings.MEDIA_ROOT / "ai_deneme"
        try:
            if o["parcali"]:
                yol = ai_deneme.parcali_calistir(str(klasor), o["model"], o["guc"], not o["yapay_zekasiz"],
                                                 lambda m: self.stdout.write(m))
            else:
                yol = ai_deneme.calistir(str(klasor), yapay_zeka=not o["yapay_zekasiz"])
        except RuntimeError as h:
            self.stderr.write(self.style.ERROR(str(h)))
            return
        self.stdout.write(self.style.SUCCESS(f"Hazır: {yol}"))
