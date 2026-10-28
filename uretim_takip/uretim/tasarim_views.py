"""Tasarım stüdyosu: bayi halısını katalogdaki yapıya göre tasarlar ve gönderir.

Gönderilen tasarım "Onay bekliyor" durumunda bir sipariş olur; ofis siparişin sayfasından onaylar ya da reddeder.
"""

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import hali_gorsel
from . import tasarim_cizim as cizim
from .forms import HaliTuruAlani
from .models import HaliTuru, KatalogModeli, LazerDeseni, Siparis, Tasarim, UretimLotu


def _desen_kodlari():
    return set(LazerDeseni.objects.filter(aktif=True).values_list("kod", flat=True)) & set(hali_gorsel.desen_bilgisi())


def _temizle(veri):
    return cizim.temizle(veri, _desen_kodlari())


def _bayi_gerekli(request):
    if getattr(request, "bayi", None) is None:
        raise PermissionDenied("Bu sayfa bayi hesapları içindir.")
    return request.bayi


def _tasarim_erisim(request, pk):
    """Bayi yalnızca kendi tasarımını, diğer hesaplar hepsini görür."""
    tasarim = get_object_or_404(Tasarim.objects.select_related("musteri", "siparis"), pk=pk)
    if getattr(request, "bayi", None) is not None and tasarim.musteri_id != request.bayi.pk:
        raise PermissionDenied
    return tasarim


def _jpeg(veri, boyut):
    yanit = HttpResponse(hali_gorsel.jpeg(veri, boyut), content_type="image/jpeg")
    yanit["Cache-Control"] = "private, max-age=86400"
    return yanit


def _boyut(request, varsayilan=900):
    try:
        return min(max(int(request.GET.get("b", varsayilan)), 120), 1400)
    except ValueError:
        return varsayilan


class GonderForm(forms.Form):
    adet = forms.IntegerField(label="Adet", min_value=1, max_value=999, initial=1)
    istenen_tarih = forms.DateField(label="İstenen teslim tarihi (isteğe bağlı)", required=False,
                                    widget=forms.DateInput(attrs={"type": "date"}))
    notlar = forms.CharField(label="Not (isteğe bağlı)", required=False, max_length=1000,
                             widget=forms.Textarea(attrs={"rows": 2}))


@transaction.atomic
def tasarim_gonder(*, bayi, kullanici, veri, adet, istenen_tarih=None, notlar=""):
    """Bayinin tasarımı: 'Onay bekliyor' durumunda sipariş + tasarım kaydı."""
    teslim = istenen_tarih or timezone.localdate() + timedelta(days=21)
    desen = LazerDeseni.objects.filter(kod=veri["dis_desen"] or veri["ic_desen"]).first() \
        if (veri["dis_desen"] or veri["ic_desen"]) else None
    siparis = Siparis.objects.create(
        musteri=bayi, durum="onay", urun=f"Bayi tasarımı {veri['en']:g}×{veri['boy']:g} cm" + (f" ({veri['katalog']} esinli)" if veri["katalog"] else ""), adet=adet,
        toplam_m2=Decimal(str(cizim.alan_m2(veri))) * adet, teslim_tarihi=teslim, lazer_deseni=desen, notlar=notlar,
        katalog_modeli=KatalogModeli.objects.filter(kod=veri["katalog"]).first() if veri["katalog"] else None,
    )
    return Tasarim.objects.create(musteri=bayi, kullanici=kullanici, veri=veri, adet=adet, istenen_tarih=istenen_tarih,
                                  notlar=notlar, siparis=siparis)


@login_required
def studyo(request):
    bayi = _bayi_gerekli(request)
    form = GonderForm(request.POST or None)
    if request.method == "POST":
        veri = _temizle(request.POST)
        if form.is_valid():
            tasarim = tasarim_gonder(bayi=bayi, kullanici=request.user, veri=veri, **form.cleaned_data)
            messages.success(request, f"Tasarımınız gönderildi ({tasarim.siparis.siparis_no}). "
                                      "Onaylanınca üretime alınacak; durumunu bu sayfadan izleyebilirsiniz.")
            return redirect("bayi_ana")
    else:
        kaynak = Tasarim.objects.filter(pk=request.GET.get("kaynak") or 0, musteri=bayi).first()
        if kaynak:
            veri = _temizle(kaynak.veri)
        else:
            veri = _temizle(cizim.hazir_degerler(request.GET.get("katalog") or cizim.HAZIRLAR[0][0]))
    modeller = {m.kod: m for m in KatalogModeli.objects.filter(kod__in=cizim.HAZIR)}
    hazirlar = []
    for kod, ad, _ in cizim.HAZIRLAR:
        deger = cizim.temizle(cizim.hazir_degerler(kod), _desen_kodlari())
        model = modeller.get(kod)
        if model and model.resim and not (hali_gorsel.VARLIK / "hazir" / f"{kod}.jpg").exists():
            resim = model.resim.url
        else:  # atölye fotoğrafı ya da (fotoğraf yoksa) programın çizdiği önizleme
            resim = reverse("tasarim_hazir_resmi", args=[kod])
        hazirlar.append({"kod": kod, "ad": ad, "resim": resim, "deger": deger})
    desenler = LazerDeseni.objects.filter(kod__in=_desen_kodlari())
    return render(request, "uretim/tasarim_studyo.html", {
        "form": form, "v": veri, "ozet": cizim.ozet(veri), "alan": cizim.alan_m2(veri), "hazirlar": hazirlar,
        "sekiller": cizim.SEKILLER, "bantlar": cizim.BANTLAR, "zeminler": cizim.ZEMINLER, "altlar": cizim.ALTLAR,
        "modeller": cizim.MODELLER, "suni_zeminler": cizim.SUNI_ZEMINLER, "biyeler": cizim.BIYELER,
        "desenler": desenler, "hazir_json": {h["kod"]: h["deger"] for h in hazirlar},
    })


@login_required
def onizleme(request):
    """Stüdyoda her değişiklikte: temizlenmiş değerler, özet ve alan (görsel ayrıca onizleme.jpg'den)."""
    veri = _temizle(request.GET)
    return JsonResponse({"ozet": cizim.ozet(veri), "alan": cizim.alan_m2(veri), "v": veri})


@login_required
def onizleme_resmi(request):
    return _jpeg(_temizle(request.GET), _boyut(request))


@login_required
def doku(request, ad):
    if ad not in dict(cizim.ZEMINLER + cizim.SUNI_ZEMINLER):
        raise Http404
    yanit = FileResponse(open(hali_gorsel.VARLIK / "doku" / f"{ad}.jpg", "rb"), content_type="image/jpeg")
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


@login_required
def hazir_resmi(request, kod):
    yol = hali_gorsel.VARLIK / "hazir" / f"{kod}.jpg"
    if kod not in cizim.HAZIR:
        raise Http404
    if not yol.exists():
        return _jpeg(_temizle(cizim.hazir_degerler(kod)), 300)
    yanit = FileResponse(open(yol, "rb"), content_type="image/jpeg")
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


@login_required
def resim(request, pk):
    tasarim = _tasarim_erisim(request, pk)
    return _jpeg(_temizle(tasarim.veri), _boyut(request))


@login_required
def lazer_dosyasi(request, pk, tur):
    if not request.user.is_staff:
        raise PermissionDenied
    if tur not in ("dxf", "svg"):
        raise Http404
    tasarim = _tasarim_erisim(request, pk)
    veri = _temizle(tasarim.veri)
    if tur == "dxf":
        icerik, mime = cizim.dxf(veri, f"{tasarim.no} {tasarim.musteri}"), "application/dxf"
    else:
        icerik, mime = cizim.svg_lazer(veri), "image/svg+xml"
    yanit = HttpResponse(icerik, content_type=mime)
    yanit["Content-Disposition"] = f'attachment; filename="{tasarim.siparis.siparis_no if tasarim.siparis else tasarim.no}.{tur}"'
    return yanit


@login_required
def bayi_ana(request):
    bayi = _bayi_gerekli(request)
    tasarimlar = (
        Tasarim.objects.filter(musteri=bayi)
        .select_related("siparis")
        .prefetch_related(Prefetch("siparis__lotlar", queryset=UretimLotu.objects.select_related("son_asama")))
    )
    satirlar = [(t, t.siparis.ilerleme() if t.siparis else None) for t in tasarimlar[:100]]
    return render(request, "uretim/bayi_ana.html", {"satirlar": satirlar})


# --- Ofis: sipariş sayfasından onay / ret ---------------------------------------


class OnayForm(forms.Form):
    hali_turu = HaliTuruAlani(queryset=HaliTuru.objects.filter(aktif=True), label="Halı türü",
                              empty_label="— Halı türü seçin —", help_text="İş bu türün istasyonlarından geçer.")
    teslim_tarihi = forms.DateField(label="Teslim tarihi", widget=forms.DateInput(attrs={"type": "date"},
                                                                                 format="%Y-%m-%d"))
    ofis_notu = forms.CharField(label="Bayiye not (isteğe bağlı)", required=False, max_length=1000,
                                widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["hali_turu"].required = HaliTuru.objects.filter(aktif=True).exists()


def onay_formu(siparis, data=None):
    hali_turu = siparis.hali_turu
    tasarim = getattr(siparis, "tasarim", None)
    if hali_turu is None and tasarim and tasarim.veri.get("model") == "suni":
        hali_turu = HaliTuru.objects.filter(ad="Suni deri halı", aktif=True).first()
    return OnayForm(data, initial={"teslim_tarihi": siparis.teslim_tarihi, "hali_turu": hali_turu.pk if hali_turu else None},
                    prefix="onay")


@require_POST
@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_onay(request, pk):
    siparis = get_object_or_404(Siparis.objects.select_related("tasarim"), pk=pk, durum="onay")
    tasarim = getattr(siparis, "tasarim", None)
    if request.POST.get("islem") == "reddet":
        siparis.durum = "iptal"
        siparis.save(update_fields=["durum"])
        if tasarim:
            tasarim.durum = "reddedildi"
            tasarim.ofis_notu = request.POST.get("onay-ofis_notu", "")[:1000]
            tasarim.save(update_fields=["durum", "ofis_notu"])
        messages.info(request, f"{siparis.siparis_no} reddedildi; bayi notunuzu görür.")
        return redirect("siparis_detay", pk=siparis.pk)
    form = onay_formu(siparis, request.POST)
    if not form.is_valid():
        messages.error(request, "Onay için halı türünü ve teslim tarihini girin.")
        return redirect("siparis_detay", pk=siparis.pk)
    siparis.durum = "acik"
    siparis.hali_turu = form.cleaned_data["hali_turu"]
    siparis.teslim_tarihi = form.cleaned_data["teslim_tarihi"]
    siparis.save(update_fields=["durum", "hali_turu", "teslim_tarihi"])
    if tasarim:
        tasarim.durum = "onaylandi"
        tasarim.ofis_notu = form.cleaned_data["ofis_notu"]
        tasarim.save(update_fields=["durum", "ofis_notu"])
    messages.success(request, f"{siparis.siparis_no} onaylandı; iş istasyon ekranlarına düştü.")
    return redirect("siparis_detay", pk=siparis.pk)
