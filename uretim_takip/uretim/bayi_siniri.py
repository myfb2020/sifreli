"""Bayi hesapları üretim ekranlarını göremez: yalnızca tasarım stüdyosu ve kendi siparişleri."""

from django.conf import settings
from django.shortcuts import redirect

from .models import hesap_bayisi

IZINLI = ("/bayi/", "/tasarim/", "/medya/", "/cikis/", "/giris/", "/static/", "/manifest.webmanifest", "/sw.js",
          "/cevrimdisi/", "/saglik/", "/davet/")
STUDYO = ("/tasarim/", "/tasarim/parcali/")  # tasarım stüdyoları yalnız yönetici (2026-11-05: bayiden kalktı)


def _eski_duzen():
    """Eski düzen (stüdyo bayiye açık) yalnız stüdyo testleri için ayardan açılır."""
    return getattr(settings, "STUDYO_BAYIYE_ACIK", False)


class BayiSiniri:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        kullanici = getattr(request, "user", None)
        if kullanici is not None and kullanici.is_authenticated and not kullanici.is_staff:
            bayi = hesap_bayisi(kullanici)
            request.bayi = bayi
            if bayi is not None and not request.path.startswith(IZINLI):
                return redirect("bayi_ana")
            if bayi is not None and request.path in STUDYO and (not _eski_duzen() or not bayi.studyo_acik):
                return redirect("bayi_siparis")
        else:
            request.bayi = None
        if request.path in STUDYO and not _eski_duzen() and kullanici is not None and kullanici.is_authenticated \
                and not kullanici.is_superuser:
            return redirect("bayi_siparis" if request.bayi is not None else "pano")
        return self.get_response(request)
