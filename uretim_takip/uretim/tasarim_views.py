"""Tasarım stüdyosu: bayi halısını tasarlar ve gönderir; ofis onaylayınca sipariş açılır."""

from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import tasarim_cizim as cizim
from .forms import HaliTuruAlani
from .models import HaliTuru, LazerDeseni, Siparis, Tasarim, UretimLotu


def _desenler():
    return LazerDeseni.objects.filter(aktif=True)


def _temizle(veri):
    return cizim.temizle(veri, set(_desenler().values_list("kod", flat=True)))


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


class GonderForm(forms.Form):
    adet = forms.IntegerField(label="Adet", min_value=1, max_value=999, initial=1)
    istenen_tarih = forms.DateField(label="İstenen teslim tarihi (isteğe bağlı)", required=False,
                                    widget=forms.DateInput(attrs={"type": "date"}))
    notlar = forms.CharField(label="Not (isteğe bağlı)", required=False, max_length=1000,
                             widget=forms.Textarea(attrs={"rows": 2}))


@login_required
def studyo(request):
    bayi = _bayi_gerekli(request)
    form = GonderForm(request.POST or None)
    if request.method == "POST":
        veri = _temizle(request.POST)
        if form.is_valid():
            tasarim = Tasarim.objects.create(
                musteri=bayi, kullanici=request.user, veri=veri, adet=form.cleaned_data["adet"],
                istenen_tarih=form.cleaned_data["istenen_tarih"], notlar=form.cleaned_data["notlar"],
            )
            messages.success(request, f"{tasarim.no} tasarımınız gönderildi. Onaylanınca üretime alınacak.")
            return redirect("bayi_ana")
    else:
        kaynak = Tasarim.objects.filter(pk=request.GET.get("kaynak") or 0, musteri=bayi).first()
        veri = _temizle(kaynak.veri if kaynak else cizim.VARSAYILAN)
    return render(request, "uretim/tasarim_studyo.html", {
        "form": form, "v": veri, "svg": cizim.svg_onizleme(veri), "ozet": cizim.ozet(veri),
        "alan": cizim.alan_m2(veri), "sekiller": cizim.SEKILLER, "motifler": cizim.MOTIFLER,
        "madalyonlar": cizim.MADALYONLAR, "renkler": cizim.RENKLER, "desenler": _desenler(),
    })


@login_required
def onizleme(request):
    """Stüdyoda her değişiklikte çağrılır: sunucuda çizilen SVG ve özet."""
    veri = _temizle(request.GET)
    return JsonResponse({"svg": cizim.svg_onizleme(veri), "ozet": cizim.ozet(veri), "alan": cizim.alan_m2(veri),
                         "v": veri})


@login_required
def resim(request, pk):
    tasarim = _tasarim_erisim(request, pk)
    yanit = HttpResponse(cizim.svg_onizleme(_temizle(tasarim.veri)), content_type="image/svg+xml")
    yanit["Cache-Control"] = "private, max-age=86400"
    return yanit


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
    yanit["Content-Disposition"] = f'attachment; filename="{tasarim.no}.{tur}"'
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


# --- Ofis tarafı ---------------------------------------------------------------


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def talepler(request):
    durum = request.GET.get("durum", "gonderildi")
    qs = Tasarim.objects.select_related("musteri", "siparis")
    if durum in dict(Tasarim.DURUMLAR):
        qs = qs.filter(durum=durum)
    return render(request, "uretim/tasarim_talepleri.html", {
        "tasarimlar": qs[:200], "durum": durum, "durumlar": Tasarim.DURUMLAR,
    })


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


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def talep_detay(request, pk):
    tasarim = _tasarim_erisim(request, pk)
    veri = _temizle(tasarim.veri)
    form = None
    if tasarim.durum == "gonderildi" and request.user.has_perm("uretim.add_siparis"):
        teslim = tasarim.istenen_tarih or timezone.localdate() + timedelta(days=14)
        form = OnayForm(request.POST or None, initial={"teslim_tarihi": teslim})
        if request.method == "POST":
            if request.POST.get("islem") == "reddet":
                tasarim.durum = "reddedildi"
                tasarim.ofis_notu = request.POST.get("ofis_notu", "")[:1000]
                tasarim.save(update_fields=["durum", "ofis_notu"])
                messages.info(request, f"{tasarim.no} reddedildi.")
                return redirect("tasarim_talepleri")
            if form.is_valid():
                siparis = tasarim_onayla(tasarim, veri, **form.cleaned_data)
                messages.success(request, f"{tasarim.no} onaylandı, {siparis.siparis_no} siparişi açıldı.")
                return redirect("siparis_detay", pk=siparis.pk)
    return render(request, "uretim/tasarim_detay.html", {
        "tasarim": tasarim, "svg": cizim.svg_onizleme(veri), "ozet": cizim.ozet(veri), "alan": cizim.alan_m2(veri),
        "form": form,
    })


@transaction.atomic
def tasarim_onayla(tasarim, veri, *, hali_turu, teslim_tarihi, ofis_notu=""):
    desen = LazerDeseni.objects.filter(kod=veri["desen_kodu"]).first() if veri["desen_kodu"] else None
    siparis = Siparis.objects.create(
        musteri=tasarim.musteri, hali_turu=hali_turu, urun=f"Tasarım {tasarim.no}: {cizim.ozet(veri)}"[:200],
        adet=tasarim.adet, toplam_m2=Decimal(str(cizim.alan_m2(veri))) * tasarim.adet, teslim_tarihi=teslim_tarihi,
        lazer_deseni=desen, notlar=tasarim.notlar,
    )
    tasarim.durum = "onaylandi"
    tasarim.siparis = siparis
    tasarim.ofis_notu = ofis_notu
    tasarim.save(update_fields=["durum", "siparis", "ofis_notu"])
    return siparis

