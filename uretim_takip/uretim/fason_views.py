"""Fason: malzemeleri preslenmeye gönderme ve birleşik malzemeyi teslim alma."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import servisler
from .forms import FasonGonderForm, FasonTeslimForm, KaynakFormSet
from .models import FasonIsi


@login_required
def fason_listesi(request):
    durum = request.GET.get("durum", "fasonda")
    isler = FasonIsi.objects.select_related("fasoncu", "hedef_tur", "gelen_lot").prefetch_related("gonderimler")
    if durum != "hepsi":
        isler = isler.filter(durum=durum)
    return render(request, "uretim/fason_listesi.html", {"isler": isler[:300], "durum": durum, "stok_sekme": "fason"})


@login_required
@permission_required("uretim.add_fasonisi", raise_exception=True)
def fason_gonder(request):
    baslangic = [{"stok_no": request.GET["stok"].strip().upper()}] if request.GET.get("stok") else []
    form = FasonGonderForm(request.POST or None)
    satirlar = KaynakFormSet(request.POST or None, initial=baslangic, prefix="kaynak")
    if request.method == "POST" and form.is_valid() and satirlar.is_valid():
        kaynaklar = [
            (s.cleaned_data["stok"], s.cleaned_data.get("kg"), s.cleaned_data.get("m2"))
            for s in satirlar if s.cleaned_data.get("stok")
        ]
        try:
            fason = servisler.fasona_gonder(
                fasoncu=form.fasoncu_bul(), hedef_tur=form.cleaned_data["hedef_tur"], kaynaklar=kaynaklar,
                kullanici=request.user, notlar=form.cleaned_data["notlar"],
            )
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(request, f"{fason.no} fasona gönderildi; gönderilen miktarlar stoktan düştü.")
            return redirect("fason_detay", pk=fason.pk)
    return render(request, "uretim/fason_gonder.html", {"form": form, "satirlar": satirlar})


@login_required
def fason_detay(request, pk):
    fason = get_object_or_404(FasonIsi.objects.select_related("fasoncu", "hedef_tur", "gelen_lot", "kullanici"), pk=pk)
    form = None
    if fason.durum == "fasonda" and request.user.has_perm("uretim.change_fasonisi"):
        ust = servisler.ust_katman(fason)
        form = FasonTeslimForm(request.POST or None, initial={
            "m2": fason.katman_m2 or None, "renk": ust.renk if ust else "", "model": ust.model if ust else "",
        })
        if request.method == "POST" and form.is_valid():
            v = form.cleaned_data
            try:
                lot = servisler.fason_teslim_al(fason=fason, m2=v["m2"], kg=v["kg"], adet=v["adet"], renk=v["renk"],
                                                model=v["model"], kullanici=request.user, notlar=v["notlar"])
            except ValidationError as hata:
                form.add_error(None, hata)
            else:
                messages.success(request, f"{lot.lot_no} stok lotu açıldı ({lot.cesit_metni}). "
                                          "Etiketini basıp malın üzerine yapıştırın.")
                return redirect("stok_detay", pk=lot.pk)
    return render(request, "uretim/fason_detay.html",
                  {"fason": fason, "gidenler": fason.gidenler(), "form": form, "stok_sekme": "fason"})


@require_POST
@login_required
@permission_required("uretim.change_fasonisi", raise_exception=True)
def fason_iptal(request, pk):
    fason = get_object_or_404(FasonIsi, pk=pk)
    try:
        servisler.fason_iptal(fason=fason)
    except ValidationError as hata:
        messages.error(request, " ".join(hata.messages))
    else:
        messages.success(request, f"{fason.no} iptal edildi; gönderilen miktarlar stoğa geri döndü.")
    return redirect("fason_detay", pk=fason.pk)
