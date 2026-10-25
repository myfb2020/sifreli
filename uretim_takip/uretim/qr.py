"""Stok lotu etiketleri için QR kod üretimi ve okutulan QR'ın doğru ekrana yönlendirilmesi.

QR kodun içinde lotun adresi (…/q/HD-2026-0001/) bulunur. Böylece telefonun kendi kamera
uygulamasıyla okutulduğunda da doğrudan ilgili ekran açılır.
"""

import segno
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.formats import localize
from django.utils.safestring import mark_safe

from .models import HamDeriGirisi, Malzeme, UretimLotu


def lot_adresi(request, lot):
    yol = reverse("qr_yonlendir", args=[lot.lot_no])
    if settings.SITE_ADRESI:
        return settings.SITE_ADRESI.rstrip("/") + yol
    return request.build_absolute_uri(yol)


def qr_svg(veri, olcek=4):
    return mark_safe(segno.make(veri, error="m").svg_inline(scale=olcek, border=2))


@login_required
def qr_yonlendir(request, lot_no):
    """Okutulan etikete göre: stok lotu → lot sayfası (devam eden işler, yeni iş), malzeme → malzeme sayfası.

    Eski sürümde işlere basılmış etiketler (UL-…) de çalışmaya devam eder.
    """
    lot_no = lot_no.upper()
    stok = HamDeriGirisi.objects.filter(lot_no=lot_no).first()
    if stok:
        return redirect("stok_detay", pk=stok.pk)
    malzeme = Malzeme.objects.filter(kod=lot_no).first()
    if malzeme:
        return redirect("malzeme_detay", pk=malzeme.pk)
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
        if (HamDeriGirisi.objects.filter(lot_no=lot_no).exists() or Malzeme.objects.filter(kod=lot_no).exists()
                or UretimLotu.objects.filter(lot_no=lot_no).exists()):
            return redirect("qr_yonlendir", lot_no=lot_no)
        return render(request, "uretim/qr_tara.html", {"hata": f"“{lot_no}” numaralı stok lotu ya da malzeme bulunamadı.", "lot_no": lot_no})
    return render(request, "uretim/qr_tara.html")


def _secilenler(request, ad):
    return [s for s in request.GET.getlist(ad) if s.isdigit()]


@login_required
def etiketler(request):
    """Stok lotu (?stok=1&stok=2) ve malzeme (?malzeme=3) etiketleri. ?kopya=N her etiketten N adet basar.

    Parametre yoksa stokta malı kalan tüm deri lotlarının etiketleri gelir.
    """
    try:
        kopya = min(50, max(1, int(request.GET.get("kopya", 1))))
    except ValueError:
        kopya = 1
    stok_idleri, malzeme_idleri = _secilenler(request, "stok"), _secilenler(request, "malzeme")

    etiket_listesi = []
    if stok_idleri or not malzeme_idleri:
        stoklar = HamDeriGirisi.objects.select_related("deri_turu", "tedarikci").order_by("lot_no")
        if stok_idleri:
            stoklar = stoklar.filter(pk__in=stok_idleri)
        else:
            stoklar = [s for s in stoklar if s.kalan_kg > 0 or s.kalan_m2 > 0]
        for s in stoklar:
            satirlar = [f"{s.deri_turu} · {s.get_kalite_display()}", str(s.tedarikci),
                        f"{localize(s.kg)} kg · {localize(s.m2)} m²" + (f" · {s.adet} adet" if s.adet else ""),
                        f"Giriş: {s.tarih:%d.%m.%Y}"]
            etiket_listesi.append({"no": s.lot_no, "satirlar": satirlar, "qr": qr_svg(lot_adresi(request, s))})
    if malzeme_idleri:
        for m in Malzeme.objects.filter(pk__in=malzeme_idleri).order_by("kod"):
            etiket_listesi.append({"no": m.kod, "baslik": m.ad,
                                   "satirlar": [m.get_kategori_display(), f"Birim: {m.get_birim_display()}"],
                                   "qr": qr_svg(lot_adresi(request, m))})
    etiket_listesi = [e for e in etiket_listesi for _ in range(kopya)]
    return render(request, "uretim/etiketler.html", {"etiketler": etiket_listesi, "kopya": kopya})
