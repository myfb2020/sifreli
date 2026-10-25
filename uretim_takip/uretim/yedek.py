"""SQLite veritabanının tutarlı bir kopyasını alır (sistem çalışırken de güvenlidir)."""

import sqlite3
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse
from django.utils import timezone


def veritabani_yolu():
    return Path(settings.DATABASES["default"]["NAME"])


def yedek_al(hedef):
    kaynak = sqlite3.connect(veritabani_yolu())
    try:
        kopya = sqlite3.connect(hedef)
        try:
            kaynak.backup(kopya)
        finally:
            kopya.close()
    finally:
        kaynak.close()
    return Path(hedef)


def dosya_adi():
    return f"uretim_yedek_{timezone.localtime():%Y-%m-%d_%H%M}.sqlite3"


@staff_member_required
def yedek_indir(request):
    gecici = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    gecici.close()
    yol = yedek_al(gecici.name)
    dosya = open(yol, "rb")
    yol.unlink()  # Açık dosya tanıtıcısı okunmaya devam eder (Linux).
    return FileResponse(dosya, as_attachment=True, filename=dosya_adi())
