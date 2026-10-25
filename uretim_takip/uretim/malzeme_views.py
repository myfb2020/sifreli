"""Deri dışı malzemeler ve stok düzeltmeleri."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import servisler
from .forms import DeriDuzeltmeForm, MalzemeDuzeltmeForm, MalzemeForm, MalzemeGirisForm
from .models import HamDeriGirisi, Malzeme


@login_required
def malzeme_listesi(request):
    kategori = request.GET.get("kategori", "")
    malzemeler = Malzeme.objects.filter(aktif=True)
    if kategori:
        malzemeler = malzemeler.filter(kategori=kategori)
    satirlar = [{"m": m, "stok": m.stok} for m in malzemeler]
    for s in satirlar:
        s["azaldi"] = s["m"].min_stok is not None and s["stok"] < s["m"].min_stok
    satirlar.sort(key=lambda s: not s["azaldi"])
    return render(request, "uretim/malzeme_listesi.html", {
        "satirlar": satirlar, "kategori": kategori, "kategoriler": Malzeme.KATEGORILER,
        "azalan": sum(1 for s in satirlar if s["azaldi"]),
    })


@login_required
def malzeme_detay(request, pk):
    malzeme = get_object_or_404(Malzeme, pk=pk)
    hareketler = malzeme.hareketler.select_related("islem__lot", "islem__asama", "personel", "kullanici", "tedarikci")[:200]
    return render(request, "uretim/malzeme_detay.html", {"malzeme": malzeme, "hareketler": hareketler})


@login_required
@permission_required("uretim.add_malzeme", raise_exception=True)
def malzeme_yeni(request):
    form = MalzemeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        malzeme = form.save()
        messages.success(request, f"“{malzeme.ad}” eklendi. Şimdi stoğa giriş yapabilirsiniz.")
        return redirect(f"{reverse('malzeme_giris')}?malzeme={malzeme.pk}")
    return render(request, "uretim/basit_form.html", {
        "form": form, "baslik": "+ Yeni Malzeme", "geri": "malzeme_listesi",
        "aciklama": "Kimyasal, iplik, astar gibi sarf malzemesini tanımlayın. "
                    "“En az stok” girerseniz stok bunun altına düşünce uyarı verilir.",
    })


@login_required
@permission_required("uretim.add_malzemehareketi", raise_exception=True)
def malzeme_giris(request):
    form = MalzemeGirisForm(request.POST or None, initial={"malzeme": request.GET.get("malzeme")})
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        servisler.malzeme_giris(malzeme=v["malzeme"], miktar=v["miktar"], kullanici=request.user,
                                tedarikci=v["tedarikci"], aciklama=v["aciklama"])
        messages.success(request, f"{v['malzeme'].ad}: {v['miktar']} {v['malzeme'].get_birim_display()} stoğa eklendi.")
        return redirect("malzeme_detay", pk=v["malzeme"].pk)
    return render(request, "uretim/basit_form.html", {
        "form": form, "baslik": "+ Malzeme Girişi", "geri": "malzeme_listesi",
        "aciklama": "Gelen malzemeyi stoğa ekleyin. Listede yoksa önce “Yeni malzeme” ile tanımlayın.",
    })


@login_required
@permission_required("uretim.add_malzemehareketi", raise_exception=True)
def malzeme_duzelt(request, pk):
    malzeme = get_object_or_404(Malzeme, pk=pk)
    form = MalzemeDuzeltmeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            servisler.malzeme_duzelt(malzeme=malzeme, neden=v["neden"], miktar=v["miktar"], kullanici=request.user,
                                     aciklama=v["aciklama"])
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(request, f"{malzeme.ad} stoğu düzeltildi. Yeni stok: {malzeme.stok} {malzeme.get_birim_display()}")
            return redirect("malzeme_detay", pk=malzeme.pk)
    return render(request, "uretim/basit_form.html", {
        "form": form, "baslik": f"Stok Düzeltme – {malzeme.ad}", "geri_adres": malzeme.pk, "geri": "malzeme_detay",
        "aciklama": f"Sistemdeki stok: {malzeme.stok} {malzeme.get_birim_display()}. "
                    "Sayım farkında sayılan gerçek miktarı, fire/iade/diğer için stoktan düşülecek miktarı yazın.",
    })


@login_required
@permission_required("uretim.add_deriduzeltme", raise_exception=True)
def deri_duzelt(request, pk):
    stok = get_object_or_404(HamDeriGirisi, pk=pk)
    form = DeriDuzeltmeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            servisler.deri_duzelt(ham_deri=stok, neden=v["neden"], kg=v["kg"], m2=v["m2"], kullanici=request.user,
                                  aciklama=v["aciklama"])
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(request, f"{stok.lot_no} düzeltildi. Kalan: {stok.kalan_kg} kg / {stok.kalan_m2} m²")
            return redirect("stok_detay", pk=stok.pk)
    return render(request, "uretim/basit_form.html", {
        "form": form, "baslik": f"Stok Düzeltme – {stok.lot_no}", "geri_adres": stok.pk, "geri": "stok_detay",
        "aciklama": f"Sistemde kalan: {stok.kalan_kg} kg / {stok.kalan_m2} m². "
                    "Sayım farkında sayılan gerçek kalanı, fire/iade/diğer için stoktan düşülecek miktarı yazın.",
    })
