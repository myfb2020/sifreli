from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from uretim.yedek import dosya_adi, yedek_al


class Command(BaseCommand):
    help = "Veritabanını yedekler klasörüne kopyalar ve en yeni N yedeği tutar."

    def add_arguments(self, parser):
        parser.add_argument("--klasor", default=str(Path(settings.BASE_DIR) / "yedekler"))
        parser.add_argument("--tut", type=int, default=14, help="Saklanacak yedek sayısı (varsayılan 14)")

    def handle(self, *args, klasor, tut, **opts):
        klasor = Path(klasor)
        klasor.mkdir(parents=True, exist_ok=True)
        yol = yedek_al(klasor / dosya_adi())
        eskiler = sorted(klasor.glob("uretim_yedek_*.sqlite3"))[:-tut] if tut > 0 else []
        for eski in eskiler:
            eski.unlink()
        self.stdout.write(self.style.SUCCESS(f"Yedek alındı: {yol} ({len(eskiler)} eski yedek silindi)"))
