"""Lot etiketleri için QR kod üretimi ve okutulan QR'ın doğru ekrana yönlendirilmesi.

QR kodun içinde lotun adresi (…/q/UL-2026-0001/) bulunur. Böylece telefonun kendi kamera
uygulamasıyla okutulduğunda da doğrudan ilgili ekran açılır.
"""

import segno
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import UretimLotu


def lot_adresi(request, lot):
    yol = reverse("qr_yonlendir", args=[lot.lot_no])
    if settings.SITE_ADRESI:
        return settings.SITE_ADRESI.rstrip("/") + yol
    return request.build_absolute_uri(yol)


def qr_svg(veri, olcek=4):
    return mark_safe(segno.make(veri, error="m").svg_inline(scale=olcek, border=2))


@login_required
def qr_yonlendir(request, lot_no):
    """Okutulan lota göre: açık işlem varsa bitir, sırada bekliyorsa başlat, değilse geçmişi göster."""
    lot = get_object_or_404(UretimLotu, lot_no=lot_no.upper())
    acik = lot.acik_islem
    if acik:
        return redirect("islem_bitir", pk=acik.pk)
    if lot.durum == "bekliyor":
        return redirect(f"{reverse('islem_baslat')}?lot={lot.pk}")
    return redirect("lot_detay", pk=lot.pk)


@login_required
def qr_tara(request):
    # Kamera kullanılamazsa lot no elle girilir.
    lot_no = request.GET.get("lot_no", "").strip().upper()
    if lot_no:
        if UretimLotu.objects.filter(lot_no=lot_no).exists():
            return redirect("qr_yonlendir", lot_no=lot_no)
        return render(request, "uretim/qr_tara.html", {"hata": f"“{lot_no}” numaralı lot bulunamadı.", "lot_no": lot_no})
    return render(request, "uretim/qr_tara.html")


@login_required
def etiketler(request):
    """Seçilen lotların (?lot=1&lot=2) ya da tüm aktif lotların yazdırılabilir etiketleri."""
    secilen = request.GET.getlist("lot")
    lotlar = UretimLotu.objects.select_related("ham_deri__deri_turu", "ham_deri__tedarikci", "siparis__musteri")
    if secilen:
        lotlar = lotlar.filter(pk__in=[s for s in secilen if s.isdigit()])
    else:
        lotlar = lotlar.exclude(durum__in=["tamamlandi", "iptal"])
    etiket_listesi = [{"lot": lot, "qr": qr_svg(lot_adresi(request, lot))} for lot in lotlar.order_by("lot_no")]
    return render(request, "uretim/etiketler.html", {"etiketler": etiket_listesi})
