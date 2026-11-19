"""Stoktan deri satışı: satış fişi (SF-…), birden çok stok lotu, adet (adetsiz stokta m²) stoktan düşer."""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font

from . import servisler
from .models import DeriSatisi, HamDeriGirisi, Musteri, sayi_metni, stok_bul, stok_no


def _tarih(deger):
    try:
        return date.fromisoformat(deger) if deger else None
    except ValueError:
        return None


def _sayi(deger):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(deger).replace(",", ".")) if str(deger).strip() else None
    except InvalidOperation:
        return None


@login_required
@permission_required("uretim.view_derisatisi", raise_exception=True)
def satis_listesi(request):
    bas, bit = _tarih(request.GET.get("bas")), _tarih(request.GET.get("bit"))
    ara = request.GET.get("ara", "").strip()
    fisler = DeriSatisi.objects.select_related("musteri").prefetch_related("hareketler__ham_deri__deri_turu")
    if bas:
        fisler = fisler.filter(tarih__gte=bas)
    if bit:
        fisler = fisler.filter(tarih__lte=bit)
    if ara:
        fisler = fisler.filter(Q(fis_no__icontains=ara) | Q(musteri__ad__icontains=ara) | Q(belge_no__icontains=ara)
                               | Q(hareketler__ham_deri__lot_no__icontains=ara)).distinct()
    fisler = list(fisler[:500])
    gecerli = [f for f in fisler if not f.iptal]
    toplam_adet = sum(f.toplam_adet for f in gecerli)
    toplam_m2 = sum(f.toplam_m2 for f in gecerli)
    if request.GET.get("excel"):
        return _excel(gecerli)
    return render(request, "uretim/satis_listesi.html", {
        "fisler": fisler, "bas": request.GET.get("bas", ""), "bit": request.GET.get("bit", ""), "ara": ara,
        "toplam_adet": toplam_adet, "toplam_m2": toplam_m2, "sorgu": request.GET.urlencode()})


def _excel(fisler):
    kitap = Workbook()
    sayfa = kitap.active
    sayfa.title = "Deri satışları"
    basliklar = ["Fiş no", "Tarih", "Müşteri", "İrsaliye / fatura", "Stok no", "Malzeme", "Tedarikçi", "Adet", "m²", "kg"]
    sayfa.append(basliklar)
    for h in sayfa[1]:
        h.font = Font(bold=True)
    for f in fisler:
        for d in f.satirlar():
            sayfa.append([f.fis_no, f.tarih, str(f.musteri), f.belge_no, d.ham_deri.lot_no, d.ham_deri.cesit_metni,
                          str(d.ham_deri.tedarikci), -d.adet or None, float(-d.m2), float(-d.kg)])
    for i, gen in enumerate((14, 12, 28, 18, 16, 30, 22, 8, 10, 10)):
        sayfa.column_dimensions[chr(65 + i)].width = gen
    yanit = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    yanit["Content-Disposition"] = f'attachment; filename="deri_satislari_{timezone.localdate():%Y%m%d}.xlsx"'
    kitap.save(yanit)
    return yanit


@login_required
@permission_required("uretim.add_derisatisi", raise_exception=True)
def satis_yeni(request):
    musteriler = Musteri.objects.order_by("ad")
    hatalar, veri = [], {}
    satirlar = []
    if request.method == "POST":
        veri = request.POST
        for no, adet, m2 in zip(veri.getlist("stok_no"), veri.getlist("adet"), veri.getlist("m2")):
            no = stok_no(no)
            if not no:
                continue
            satirlar.append({"stok_no": no, "adet": adet, "m2": m2})
        musteri = None
        yeni_ad = veri.get("yeni_musteri", "").strip()[:120]
        if yeni_ad:
            musteri = Musteri.objects.filter(ad__iexact=yeni_ad).first()
        elif veri.get("musteri"):
            musteri = Musteri.objects.filter(pk=veri.get("musteri")).first()
        if musteri is None and not yeni_ad:
            hatalar.append("Müşteriyi seçin ya da yeni müşterinin adını yazın.")
        kalemler = []
        for s in satirlar:
            stok = stok_bul(s["stok_no"])
            if stok is None:
                hatalar.append(f"“{s['stok_no']}” numaralı stok bulunamadı.")
                continue
            adet = _sayi(s["adet"])
            m2 = _sayi(s["m2"])
            if adet is not None and adet != int(adet):
                hatalar.append(f"{stok.lot_no}: adet tam sayı olmalı.")
                continue
            kalemler.append((stok, int(adet or 0), m2))
        if not satirlar:
            hatalar.append("En az bir stok numarası girin (etiketi okutun ya da yazın).")
        tarih = _tarih(veri.get("tarih")) or timezone.localdate()
        if not hatalar:
            try:
                if musteri is None:
                    musteri = Musteri.objects.create(ad=yeni_ad)
                satis = servisler.deri_sat(musteri=musteri, satirlar=kalemler, tarih=tarih,
                                           belge_no=veri.get("belge_no", "").strip()[:40],
                                           aciklama=veri.get("aciklama", "").strip()[:300], kullanici=request.user)
            except ValidationError as hata:
                hatalar.extend(hata.messages)
            else:
                adet = f"{satis.toplam_adet} adet · " if satis.toplam_adet else ""
                messages.success(request, f"{satis.fis_no} kaydedildi: {adet}{sayi_metni(satis.toplam_m2)} m² stoktan düşüldü.")
                return redirect("satis_detay", pk=satis.pk)
    elif request.GET.get("stok"):
        stok = HamDeriGirisi.objects.filter(pk=request.GET["stok"]).first() if request.GET["stok"].isdigit() else None
        if stok:
            satirlar = [{"stok_no": stok.lot_no, "adet": "", "m2": ""}]
    if not satirlar:
        satirlar = [{"stok_no": "", "adet": "", "m2": ""}]
    return render(request, "uretim/satis_yeni.html", {
        "musteriler": musteriler, "satirlar": satirlar, "hatalar": hatalar, "veri": veri,
        "bugun": timezone.localdate().isoformat()})


@login_required
@permission_required("uretim.view_derisatisi", raise_exception=True)
def satis_detay(request, pk):
    satis = get_object_or_404(DeriSatisi.objects.select_related("musteri", "kullanici", "iptal_eden"), pk=pk)
    if request.method == "POST":
        if not request.user.is_superuser:
            raise PermissionDenied
        try:
            servisler.deri_satis_iptal(satis=satis, kullanici=request.user, neden=request.POST.get("neden", "").strip())
        except ValidationError as hata:
            messages.error(request, " ".join(hata.messages))
        else:
            messages.success(request, f"{satis.fis_no} iptal edildi; mallar stoğa geri döndü.")
        return redirect("satis_detay", pk=satis.pk)
    return render(request, "uretim/satis_detay.html", {"satis": satis, "satirlar": satis.satirlar()})

