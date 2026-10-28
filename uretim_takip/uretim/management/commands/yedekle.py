"""Veritabanının yedeğini yedekler/ klasörüne alır ve aynı türden eski yedekleri temizler.

  python manage.py yedekle                                  # uretim_yedek_… (son 14 tutulur)
  python manage.py yedekle --onek gunluk                    # günlük zamanlanmış görev için
  python manage.py yedekle --onek guncelleme_oncesi --tut 10  # kurulum.sh güncellemeden önce
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from uretim.yedek import dosya_adi, yedek_al


class Command(BaseCommand):
    help = "Veritabanını yedekler klasörüne kopyalar ve en yeni N yedeği tutar."

    def add_arguments(self, parser):
        parser.add_argument("--klasor", default=str(Path(settings.BASE_DIR) / "yedekler"))
        parser.add_argument("--onek", default="", help="dosya adı öneki (gunluk, guncelleme_oncesi, ...)")
        parser.add_argument("--tut", type=int, default=14, help="Saklanacak yedek sayısı (varsayılan 14)")

    def handle(self, *args, klasor, onek, tut, **opts):
        klasor = Path(klasor)
        klasor.mkdir(parents=True, exist_ok=True)
        if onek:
            ad, desen = f"{onek}_{timezone.localtime():%Y-%m-%d_%H%M%S}.sqlite3", f"{onek}_*.sqlite3"
        else:
            ad, desen = dosya_adi(), "uretim_yedek_*.sqlite3"
        yol = yedek_al(klasor / ad)
        eskiler = sorted(klasor.glob(desen))[:-tut] if tut > 0 else []
        for eski in eskiler:
            eski.unlink()
        self.stdout.write(self.style.SUCCESS(f"Yedek alındı: {yol.name} ({len(eskiler)} eski yedek silindi)"))
