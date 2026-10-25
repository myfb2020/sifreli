"""Telefona 'uygulama' olarak kurulabilmek için manifest ve service worker."""

import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache

# Önbellek sürümü: statik dosyalar değişince artırın, telefonlar yenisini indirir.
SURUM = "v2"


def manifest(request):
    return JsonResponse(
        {
            "name": "Üretim Takip",
            "short_name": "Üretim",
            "description": "Deri / kürk halı üretim takibi",
            "lang": "tr",
            "start_url": reverse("pano"),
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#f6f2ee",
            "theme_color": "#7a4b2a",
            "icons": [
                {"src": static("uretim/ikon/ikon-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": static("uretim/ikon/ikon-512.png"), "sizes": "512x512", "type": "image/png"},
                {"src": static("uretim/ikon/ikon-maskable-512.png"), "sizes": "512x512", "type": "image/png",
                 "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "QR Okut", "url": reverse("qr_tara")},
                {"name": "İşlem Başlat", "url": reverse("islem_baslat")},
            ],
        },
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False},
    )


@never_cache
def service_worker(request):
    onbellek = [
        reverse("cevrimdisi"),
        static("uretim/vendor/jsQR.js"),
        static("uretim/tarayici.js"),
        static("uretim/ikon/ikon-192.png"),
    ]
    js = render(request, "uretim/sw.js", {"surum": SURUM, "onbellek": json.dumps(onbellek)}).content
    yanit = HttpResponse(js, content_type="application/javascript")
    yanit["Service-Worker-Allowed"] = "/"
    return yanit


def cevrimdisi(request):
    return render(request, "uretim/cevrimdisi.html")
