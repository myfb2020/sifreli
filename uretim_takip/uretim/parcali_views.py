"""Parçalı (lego) suni deri tasarım: bayi ekranı, canlı önizleme, ofis için kesim listesi."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import parcali, parcali_gorsel
from .models import LazerDeseni, Tasarim
from .tasarim_views import (
    GonderForm, _bayi_gerekli, _boyut, _desen_kodlari, _jpeg, _tasarim_erisim, tasarim_gonder, tasarim_temizle,
)


def _temizle(veri):
    return parcali.temizle(veri, _desen_kodlari())


def hesap(v):
    """Ekranda ve kesim listesinde gösterilen üretim bilgileri."""
    ps = parcali.parcalar(v)
    rulo = parcali.rulo_yerlesimi(ps, v["pay"])
    return {
        "parcalar": [{"no": p["no"], "ad": p["ad"], "malzeme": parcali.MALZEME_AD[p["malzeme"]], "desen": p["desen"],
                      "kesim": f"{p['kesim_en']:g} × {p['kesim_boy']:g}", "m2": p["m2"], "istasyon": p["istasyon"]}
                     for p in ps],
        "rulo": [{"kod": m, "malzeme": parcali.MALZEME_AD[m], "metre": b["metre"], "m2": b["m2"], "adet": b["adet"]}
                 for m, b in rulo.items()],
        "nakis": parcali.nakis_bilgisi(v),
        "uyarilar": parcali.uyarilar(v),
        "montaj": parcali.montaj_sirasi(v),
        "kenar_m": round(parcali.cevre(parcali.dis_hat(v)) / 100, 2),
        "ozet": parcali.ozet(v),
        "alan": parcali.alan_m2(v),
    }


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
        veri = _temizle(kaynak.veri if kaynak else parcali.hazir_degerler(request.GET.get("hazir") or "P-1"))
    veri = _temizle(parcali.eskiden_cevir(veri))  # ekran yalnız halkalı yapıyı düzenler
    desenler = LazerDeseni.objects.filter(kod__in=_desen_kodlari())
    hazirlar = [{"kod": k, "ad": a, "deger": _temizle(parcali.hazir_degerler(k))} for k, a, _ in parcali.HAZIRLAR]
    halkalar = [{"no": i, "tur": veri[f"h{i}_tur"], "gen": veri[f"h{i}_gen"], "malzeme": veri[f"h{i}_malzeme"],
                 "desen": veri[f"h{i}_desen"], "nakis": veri[f"h{i}_nakis"],
                 "ad_malzeme": f"h{i}_malzeme", "ad_desen": f"h{i}_desen"} for i in range(1, parcali.EN_COK_HALKA + 1)]
    return render(request, "uretim/tasarim_parcali.html", {
        "form": form, "v": veri, "h": hesap(veri), "halkalar": halkalar, "malzemeler": parcali.MALZEMELER,
        "sekiller": parcali.SEKILLER, "halka_turleri": parcali.HALKA_TURLERI, "orta_turleri": parcali.ORTA_TURLERI,
        "serit_turleri": parcali.SERIT_TURLERI, "serit_yonleri": parcali.SERIT_YONLERI, "motifler": parcali.MOTIFLER,
        "kenarlar": parcali.KENARLAR, "kenar_renkleri": parcali.KENAR_RENKLERI, "desenler": desenler,
        "hazirlar": hazirlar, "hazir_json": {h["kod"]: h["deger"] for h in hazirlar}, "en_cok_halka": parcali.EN_COK_HALKA,
    })


@login_required
def onizleme(request):
    v = _temizle(request.GET)
    return JsonResponse({"v": v, **hesap(v)})


@login_required
def fikir(request):
    """'Bana fikir ver': kurallara uygun 6 farklı öneri (bayi ölçüsü korunur)."""
    try:
        olcu = (float(request.GET["en"]), float(request.GET["boy"]))
    except (KeyError, ValueError):
        olcu = None
    sonuc = []
    for v in parcali.fikirler(6, None, _desen_kodlari(), olcu):
        orta = dict(parcali.ORTA_TURLERI)[v["orta"]].lower()
        sonuc.append({"v": {k: ("" if d is None else d) for k, d in v.items()},
                      "baslik": f"{dict(parcali.SEKILLER)[v['sekil']]} · {v['halka_sayisi']} halka · orta {orta}"})
    return JsonResponse(sonuc, safe=False)


@login_required
def onizleme_resmi(request):
    return _jpeg(_temizle(request.GET), _boyut(request))


@login_required
def malzeme_ornegi(request, ad):
    if ad not in parcali.MALZEME_AD:
        raise Http404
    yanit = HttpResponse(parcali_gorsel.ornek(ad), content_type="image/jpeg")
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


def _parcali_tasarim(request, pk):
    tasarim = _tasarim_erisim(request, pk)
    veri = tasarim_temizle(tasarim.veri)
    if veri.get("tip") != "parcali":
        raise Http404
    return tasarim, veri


@login_required
def plan(request, pk):
    _, veri = _parcali_tasarim(request, pk)
    return HttpResponse(parcali_gorsel.plan_png(veri, _boyut(request, 700)), content_type="image/png")


@login_required
def kesim_listesi(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    tasarim, veri = _parcali_tasarim(request, pk)
    return render(request, "uretim/kesim_listesi.html", {
        "tasarim": tasarim, "v": veri, "h": hesap(veri), "adet": tasarim.adet,
        "dxf": reverse("tasarim_lazer", args=[tasarim.pk, "dxf"]),
    })
