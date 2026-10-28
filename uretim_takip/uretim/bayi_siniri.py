"""Bayi hesapları üretim ekranlarını göremez: yalnızca tasarım stüdyosu ve kendi siparişleri."""

from django.shortcuts import redirect

from .models import hesap_bayisi

IZINLI = ("/bayi/", "/tasarim/", "/medya/", "/cikis/", "/giris/", "/static/", "/manifest.webmanifest", "/sw.js",
          "/cevrimdisi/", "/saglik/")


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
        else:
            request.bayi = None
        return self.get_response(request)
