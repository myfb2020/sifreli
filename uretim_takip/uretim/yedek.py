"""SQLite veritabanının tutarlı bir kopyasını alır (sistem çalışırken de güvenlidir)."""

import sqlite3
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
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


def sadece_yonetici(gorunum):
    """Yalnızca süper kullanıcı (yönetici): tüm veriler ve personel PIN'leri bu sayfalardan geçer."""
    return user_passes_test(lambda u: u.is_active and u.is_superuser, login_url="admin:login")(gorunum)


@sadece_yonetici
def yedek_indir(request):
    gecici = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    gecici.close()
    yol = yedek_al(gecici.name)
    dosya = open(yol, "rb")
    yol.unlink()  # Açık dosya tanıtıcısı okunmaya devam eder (Linux).
    return FileResponse(dosya, as_attachment=True, filename=dosya_adi())


@sadece_yonetici
def gecis_modu_degistir(request):
    """Pano'daki düğme: geçiş dönemini açar/kapatır (yalnızca POST)."""
    from django.contrib import messages
    from django.shortcuts import redirect

    from .models import SistemAyari

    if request.method == "POST":
        ayar = SistemAyari.yukle()
        ayar.gecis_modu = not ayar.gecis_modu
        ayar.save(update_fields=["gecis_modu"])
        messages.success(request, "Geçiş dönemi açıldı: işler etiketsiz eski stoktan da başlatılabilir."
                         if ayar.gecis_modu else "Geçiş dönemi kapatıldı: işler yalnızca etiketli stoktan başlatılır.")
    return redirect("pano")
