"""Stok lotları ve stoktan yeni iş başlatma."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import servisler, uyarilar
from .views import geri_don
from .forms import KaynakFormSet, StokGirisForm, YeniIsForm
from .models import HamDeriGirisi, Malzeme, SistemAyari, UretimLotu


@login_required
def islem_merkezi(request):
    bekleyen = (
        UretimLotu.objects.filter(durum="bekliyor", son_asama__isnull=False)
        .select_related("siparis__musteri", "son_asama")
        .order_by("siparis__teslim_tarihi", "olusturma")
    )
    return render(request, "uretim/islem_merkezi.html", {"bekleyen": bekleyen})


@login_required
def yeni_is(request):
    baslangic_satirlar = []
    if request.GET.get("stok"):
        baslangic_satirlar = [{"stok_no": request.GET["stok"].strip().upper()}]
    gecis_modu = SistemAyari.yukle().gecis_modu
    form = YeniIsForm(request.POST or None, initial={"siparis": request.GET.get("siparis")}, gecis_modu=gecis_modu)
    satirlar = KaynakFormSet(request.POST or None, initial=baslangic_satirlar, prefix="kaynak")

    if request.method == "POST" and form.is_valid() and satirlar.is_valid():
        kaynaklar = [
            (s.cleaned_data["stok"], s.cleaned_data.get("kg"), s.cleaned_data.get("m2"))
            for s in satirlar if s.cleaned_data.get("stok")
        ]
        v = form.cleaned_data
        try:
            islem = servisler.yeni_is_baslat(
                personel=v["personel"], siparis=v["siparis"], kaynaklar=kaynaklar, asama=v["asama"],
                aciklama=v["aciklama"], makine=v.get("makine"), eski_stok=form.eski_stok(),
            )
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(
                request, f"{islem.personel} – {islem.lot} işi açıldı ({islem.lot.kaynak_listesi}), "
                         f"“{islem.asama.ad}” başladı."
            )
            return geri_don(request, "pano")
    return render(request, "uretim/yeni_is.html", {"form": form, "satirlar": satirlar, "gecis_modu": gecis_modu})


def cesit_onerileri():
    """Stok formlarında renk / model kutularına öneri listesi."""
    def liste(alan):
        return (HamDeriGirisi.objects.exclude(**{alan: ""}).order_by(alan).values_list(alan, flat=True).distinct()[:200])
    return {"renk_onerileri": liste("renk"), "model_onerileri": liste("model")}


@login_required
def stok_bilgi(request, lot_no):
    """Yeni iş ekranında okutulan stok lotunun özeti."""
    stok = HamDeriGirisi.objects.filter(lot_no=lot_no.upper()).select_related("deri_turu", "tedarikci").first()
    if stok is None:
        malzeme = Malzeme.objects.filter(kod=lot_no.upper()).first()
        return JsonResponse({"bulundu": False, "malzeme": malzeme.ad if malzeme else None}, status=404)
    return JsonResponse({
        "bulundu": True, "lot_no": stok.lot_no, "deri_turu": stok.cesit_metni, "kalite": stok.get_kalite_display(),
        "tedarikci": str(stok.tedarikci), "kalan_kg": str(stok.kalan_kg), "kalan_m2": str(stok.kalan_m2),
    })


@login_required
def stok_listesi(request):
    durum = request.GET.get("durum", "stokta")
    stoklar = HamDeriGirisi.objects.select_related("tedarikci", "deri_turu").prefetch_related("cikislar", "duzeltmeler")
    ara = request.GET.get("ara", "").strip()
    if ara:
        stoklar = stoklar.filter(Q(lot_no__icontains=ara) | Q(tedarikci__ad__icontains=ara) | Q(deri_turu__ad__icontains=ara)
                                 | Q(renk__icontains=ara) | Q(model__icontains=ara))
    satirlar = []
    for s in stoklar[:500]:
        kullanilan_kg = sum((c.kg for c in s.cikislar.all()), 0) - sum((d.kg for d in s.duzeltmeler.all()), 0)
        kullanilan_m2 = sum((c.m2 for c in s.cikislar.all()), 0) - sum((d.m2 for d in s.duzeltmeler.all()), 0)
        kalan_kg, kalan_m2 = s.kg - kullanilan_kg, s.m2 - kullanilan_m2
        bitti = kalan_kg <= 0 and kalan_m2 <= 0
        if (durum == "stokta" and bitti) or (durum == "bitti" and not bitti):
            continue
        yuzde = round(kullanilan_m2 / s.m2 * 100) if s.m2 else 0
        satirlar.append({"stok": s, "kalan_kg": kalan_kg, "kalan_m2": kalan_m2, "yuzde": min(100, yuzde)})
    ozet = sorted(uyarilar.deri_ozeti().values(), key=lambda o: o["tur"].ad)
    for o in ozet:
        o["azaldi"] = o["tur"].min_kg is not None and o["kalan_kg"] < o["tur"].min_kg
    return render(request, "uretim/stok_listesi.html", {"satirlar": satirlar, "durum": durum, "ara": ara, "ozet": ozet})


@login_required
def stok_detay(request, pk):
    stok = get_object_or_404(HamDeriGirisi.objects.select_related("tedarikci", "deri_turu"), pk=pk)
    cikislar = stok.cikislar.select_related("uretim_lotu__siparis__musteri", "uretim_lotu__son_asama")
    duzeltmeler = stok.duzeltmeler.select_related("kullanici")
    aktif = list(stok.aktif_isler())
    for lot in aktif:
        lot.acik = lot.acik_islem
    return render(request, "uretim/stok_detay.html",
                  {"stok": stok, "aktif": aktif, "cikislar": cikislar, "duzeltmeler": duzeltmeler})


@login_required
@permission_required("uretim.add_hamderigirisi", raise_exception=True)
def stok_yeni(request):
    form = StokGirisForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        stok = form.save()
        messages.success(request, f"{stok.lot_no} stok lotu kaydedildi. Etiketini basıp malın üzerine yapıştırın.")
        return redirect("stok_detay", pk=stok.pk)
    return render(request, "uretim/stok_yeni.html", {"form": form, **cesit_onerileri()})
