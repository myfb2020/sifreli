"""Katalog: halı modelleri ve lazer desenleri (resimli), sipariş açarken seçilir."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.static import serve

from django.shortcuts import get_object_or_404, redirect, render

from .models import KatalogModeli, KatalogSerisi, LazerDeseni


@login_required
def medya(request, yol):
    """Yüklenen resimler yalnızca giriş yapanlara gösterilir; müşteri fotoğrafları bayilere gösterilmez."""
    bayi = getattr(request, "bayi", None)
    if yol.startswith("siparis/") and bayi is not None:
        from .models import SiparisFotografi  # bayi yalnız kendi siparişinin fotoğraflarını görür
        if not SiparisFotografi.objects.filter(resim=yol, siparis__musteri=bayi, siparis__bayide_gizli=False).exists():
            raise Http404
    yanit = serve(request, yol, document_root=settings.MEDIA_ROOT)
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


@login_required
def katalog(request):
    # pasif model (2026-11-23: fotoğrafı kötü): bayide ve stüdyoda görünmez; ofis 'Pasif modeller'de görür, siparişte seçebilir
    pasif = request.GET.get("pasif") == "1" and request.user.is_staff
    seriler = KatalogSerisi.objects.annotate(sayi=Count("modeller", filter=Q(modeller__aktif=not pasif))).filter(sayi__gt=0)
    modeller = KatalogModeli.objects.filter(aktif=not pasif).select_related("seri")
    seri = request.GET.get("seri", "")
    if seri.isdigit():
        modeller = modeller.filter(seri_id=seri)
    ara = request.GET.get("ara", "").strip()
    if ara:
        modeller = modeller.filter(Q(kod__icontains=ara.replace(".", "")) | Q(seri__ad__icontains=ara))
    return render(request, "uretim/katalog.html", {
        "seriler": seriler, "modeller": modeller, "seri": seri, "ara": ara, "katalog_sekme": "model", "pasif": pasif,
        "pasif_sayi": KatalogModeli.objects.filter(aktif=False).count() if request.user.is_staff else 0,
    })


@login_required
@require_POST
def katalog_model_durum(request, pk):
    """Ofis/yönetici: modeli pasif ↔ aktif yapar ya da bayide göster/gizle (iyi fotoğraf gelince açmak için)."""
    if not request.user.is_staff:
        raise Http404
    m = get_object_or_404(KatalogModeli, pk=pk)
    alan = request.POST.get("alan")
    if alan == "aktif":
        m.aktif = not m.aktif
        if not m.aktif:
            m.bayiye_acik = False
        messages.success(request, f"{m.kod} {'aktif yapıldı (stüdyoda görünür)' if m.aktif else 'pasif yapıldı'}.")
    elif alan == "bayi" and m.aktif:
        m.bayiye_acik = not m.bayiye_acik
        messages.success(request, f"{m.kod} bayide {'görünür' if m.bayiye_acik else 'gizli'}.")
    m.save(update_fields=["aktif", "bayiye_acik"])
    geri = request.POST.get("geri", "")
    if not url_has_allowed_host_and_scheme(geri, allowed_hosts={request.get_host()}):
        geri = reverse("katalog")
    return redirect(geri)


@login_required
def desenler(request):
    return render(request, "uretim/desenler.html",
                  {"desenler": LazerDeseni.objects.filter(aktif=True), "katalog_sekme": "desen"})


def secim_verisi():
    """Sipariş formu için: model kodları ve resim adresleri (önizleme)."""
    return {
        # pasif modeller de seçilebilir (yalnız bayide ve stüdyoda gizli)
        "katalog_modelleri": KatalogModeli.objects.select_related("seri").order_by("-aktif", "seri__sira", "kod"),
        "lazer_desenleri": LazerDeseni.objects.filter(aktif=True),
    }
