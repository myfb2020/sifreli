"""Stok lotu etiketleri için QR kod üretimi ve okutulan QR'ın doğru ekrana yönlendirilmesi.

QR kodun içinde lotun adresi (…/q/HD-2026-0001/) bulunur. Böylece telefonun kendi kamera
uygulamasıyla okutulduğunda da doğrudan ilgili ekran açılır.
"""

import segno
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import HamDeriGirisi, UretimLotu


def lot_adresi(request, lot):
    yol = reverse("qr_yonlendir", args=[lot.lot_no])
    if settings.SITE_ADRESI:
        return settings.SITE_ADRESI.rstrip("/") + yol
    return request.build_absolute_uri(yol)


def qr_svg(veri, olcek=4):
    return mark_safe(segno.make(veri, error="m").svg_inline(scale=olcek, border=2))


@login_required
def qr_yonlendir(request, lot_no):
    """Etiketler stok lotlarına basılır: okutulunca o lotun sayfası (devam eden işler, yeni iş) açılır.

    Eski sürümde işlere basılmış etiketler (UL-…) de çalışmaya devam eder.
    """
    lot_no = lot_no.upper()
    stok = HamDeriGirisi.objects.filter(lot_no=lot_no).first()
    if stok:
        return redirect("stok_detay", pk=stok.pk)
    lot = get_object_or_404(UretimLotu, lot_no=lot_no)
    acik = lot.acik_islem
    if acik:
        return redirect("islem_bitir", pk=acik.pk)
    if lot.durum == "bekliyor":
        return redirect(f"{reverse('islem_baslat')}?lot={lot.pk}")
    return redirect("lot_detay", pk=lot.pk)


@login_required
def qr_tara(request):
    # Kamera kullanılamazsa numara elle girilir.
    lot_no = request.GET.get("lot_no", "").strip().upper()
    if lot_no:
        if HamDeriGirisi.objects.filter(lot_no=lot_no).exists() or UretimLotu.objects.filter(lot_no=lot_no).exists():
            return redirect("qr_yonlendir", lot_no=lot_no)
        return render(request, "uretim/qr_tara.html", {"hata": f"“{lot_no}” numaralı stok lotu bulunamadı.", "lot_no": lot_no})
    return render(request, "uretim/qr_tara.html")


@login_required
def etiketler(request):
    """Seçilen stok lotlarının (?stok=1&stok=2) ya da stokta malı kalan tüm lotların etiketleri."""
    secilen = [s for s in request.GET.getlist("stok") if s.isdigit()]
    stoklar = HamDeriGirisi.objects.select_related("deri_turu", "tedarikci").order_by("lot_no")
    if secilen:
        stoklar = stoklar.filter(pk__in=secilen)
    else:
        stoklar = [s for s in stoklar if s.kalan_kg > 0 or s.kalan_m2 > 0]
    etiket_listesi = [{"stok": s, "qr": qr_svg(lot_adresi(request, s))} for s in stoklar]
    return render(request, "uretim/etiketler.html", {"etiketler": etiket_listesi})
