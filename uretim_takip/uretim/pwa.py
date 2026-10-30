"""Telefona 'uygulama' olarak kurulabilmek için manifest ve service worker."""

import json

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from .models import Siparis, SiparisFotografi

# Önbellek sürümü: statik dosyalar değişince artırın, telefonlar yenisini indirir.
SURUM = "v5"


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
            "background_color": "#fcfbf9",
            "theme_color": "#fcfbf9",
            "icons": [
                {"src": static("uretim/ikon/ikon-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": static("uretim/ikon/ikon-512.png"), "sizes": "512x512", "type": "image/png"},
                {"src": static("uretim/ikon/ikon-maskable-512.png"), "sizes": "512x512", "type": "image/png",
                 "purpose": "maskable"},
            ],
            # Android: WhatsApp vb.'de fotoğrafı "Paylaş" ile doğrudan siparişe gönderme
            "share_target": {
                "action": reverse("paylas"), "method": "POST", "enctype": "multipart/form-data",
                "params": {"files": [{"name": "fotograflar", "accept": ["image/*"]}]},
            },
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
    js = render(request, "uretim/sw.js", {"surum": SURUM, "onbellek": json.dumps(onbellek),
                                          "paylas": reverse("paylas")}).content
    yanit = HttpResponse(js, content_type="application/javascript")
    yanit["Service-Worker-Allowed"] = "/"
    return yanit


def cevrimdisi(request):
    return render(request, "uretim/cevrimdisi.html")


@csrf_exempt  # paylaşım POST'u dışarıdan gelir; burada hiçbir şey kaydedilmez
@login_required
@permission_required("uretim.add_siparis", raise_exception=True)
def paylas(request):
    """Paylaşılan fotoğraflar: yeni sipariş mi, var olan siparişe mi? (Fotoğrafları service worker saklar.)

    Service worker yoksa (uygulama kurulmamış) POST doğrudan buraya gelir; o zaman kullanıcı yeniden denemeye yönlendirilir.
    """
    siparisler = (Siparis.objects.filter(durum__in=["onay", "acik", "uretimde"]).select_related("musteri")
                  .order_by("-tarih", "-siparis_no")[:60])
    return render(request, "uretim/paylas.html", {"siparisler": siparisler, "en_cok": SiparisFotografi.EN_COK,
                                                  "dogrudan": request.method == "POST"})
