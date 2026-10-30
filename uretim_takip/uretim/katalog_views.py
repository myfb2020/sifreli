"""Katalog: halı modelleri ve lazer desenleri (resimli), sipariş açarken seçilir."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.views.static import serve

from django.shortcuts import render

from .models import KatalogModeli, KatalogSerisi, LazerDeseni


@login_required
def medya(request, yol):
    """Yüklenen resimler yalnızca giriş yapanlara gösterilir; müşteri fotoğrafları bayilere gösterilmez."""
    if yol.startswith("siparis/") and getattr(request, "bayi", None) is not None:
        raise Http404
    yanit = serve(request, yol, document_root=settings.MEDIA_ROOT)
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


@login_required
def katalog(request):
    seriler = KatalogSerisi.objects.annotate(sayi=Count("modeller", filter=Q(modeller__aktif=True))).filter(sayi__gt=0)
    modeller = KatalogModeli.objects.filter(aktif=True).select_related("seri")
    seri = request.GET.get("seri", "")
    if seri.isdigit():
        modeller = modeller.filter(seri_id=seri)
    ara = request.GET.get("ara", "").strip()
    if ara:
        modeller = modeller.filter(Q(kod__icontains=ara.replace(".", "")) | Q(seri__ad__icontains=ara))
    return render(request, "uretim/katalog.html", {
        "seriler": seriler, "modeller": modeller, "seri": seri, "ara": ara, "katalog_sekme": "model",
    })


@login_required
def desenler(request):
    return render(request, "uretim/desenler.html",
                  {"desenler": LazerDeseni.objects.filter(aktif=True), "katalog_sekme": "desen"})


def secim_verisi():
    """Sipariş formu için: model kodları ve resim adresleri (önizleme)."""
    return {
        "katalog_modelleri": KatalogModeli.objects.filter(aktif=True).select_related("seri"),
        "lazer_desenleri": LazerDeseni.objects.filter(aktif=True),
    }
