"""Parçalı (lego) suni deri tasarım: bayi ekranı, canlı önizleme, ofis için kesim listesi."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import parcali, parcali_gorsel
from .models import KatalogModeli, LazerDeseni, Tasarim
from .tasarim_views import (
    GonderForm, _bayi_gerekli, ek_olculer, _boyut, _desen_kodlari, _jpeg, _tasarim_erisim, tasarim_gonder, tasarim_temizle,
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


def _grup(k):
    """Malzemenin kartela grubu: 'RNO', 'BNA', ince çizgi için 'metal' ya da '' (yalnız serbest tasarımda)."""
    for on, liste in parcali.KARTELA_MALZEMELERI.items():
        if k in liste:
            return on
    return "metal" if k in parcali.METALIK else ""


def _gruplu_malzemeler():
    return [(k, ad, hex_, _grup(k)) for k, ad, hex_ in parcali.MALZEMELER]


def bayi_hesap(v):
    """Bayi ekranı için yalnız gerekenler: özet, teknik olmayan uyarılar (yeriyle), halkalara kalan yer."""
    return {"ozet": parcali.ozet(v),
            "uyarilar": [u for u in parcali.halkali_uyari_listesi(v) if not u["teknik"]],
            "kalan_yer": parcali.kalan_yer(v), "madalyon_en_cok": parcali.madalyon_en_cok(v)}


@login_required
def studyo(request):
    bayi = _bayi_gerekli(request)
    form = GonderForm(request.POST or None)
    if request.method == "POST" and bayi is None:
        messages.error(request, "Yönetici önizlemesi: tasarım buradan gönderilemez.")
        return redirect(request.path)
    if request.method == "POST":
        veri = _temizle(request.POST)
        ek = ek_olculer(request.POST)
        if isinstance(ek, str):
            form.add_error(None, ek)
        if not veri.get("aynen") and veri.get("duzen") == "halkali":  # olduğu gibi siparişte katalog fotoğrafı gider
            for u in parcali.halkali_uyari_listesi(veri):
                if u["engel"]:
                    form.add_error(None, u["metin"])
            # model ailesinin dışında malzeme (ekranda zaten gizli) gönderilemez
            kullanilan = ["zemin", "kenar_renk"] + [f"h{i}_malzeme" for i in range(1, veri["halka_sayisi"] + 1)]
            kullanilan += {"serit": ["serit_malzeme"], "panel": ["panel_malzeme"]}.get(veri["orta"], [])
            kullanilan += ["madalyon_malzeme"] if veri["orta"] == "duz" and veri["madalyon"] != "yok" else []
            for alan in kullanilan:
                if alan in veri and not parcali.izinli_mi(veri.get("katalog"), alan, veri[alan]):
                    form.add_error(None, f"{parcali.MALZEME_AD.get(veri[alan], parcali.KENAR_AD.get(veri[alan], veri[alan]))}"
                                         " bu modelde kullanılamaz; kartelasından bir renk seçin.")
                    break
        if form.is_valid():
            tasarim = tasarim_gonder(bayi=bayi, kullanici=request.user, veri=veri, ek=ek, **form.cleaned_data)
            messages.success(request, f"Tasarımınız gönderildi ({tasarim.siparis.siparis_no}). "
                                      "Onaylanınca üretime alınacak; durumunu bu sayfadan izleyebilirsiniz.")
            return redirect("bayi_ana")
    else:
        kaynak = Tasarim.objects.filter(pk=request.GET.get("kaynak") or 0, musteri=bayi).first()
        veri = _temizle(kaynak.veri if kaynak else parcali.hazir_degerler(request.GET.get("hazir") or "IPS-449"))
    yalniz_secili = bayi is not None and not getattr(settings, "STUDYO_BAYIYE_ACIK", False)
    veri = _temizle(parcali.eskiden_cevir(veri))  # ekran yalnız halkalı yapıyı düzenler
    desenler = LazerDeseni.objects.filter(kod__in=_desen_kodlari() - parcali.GIZLI_DESENLER)
    pasifler = set(KatalogModeli.objects.filter(aktif=False).values_list("kod", flat=True))
    bayiye = set(parcali.SECILI_MODELLER) & set(parcali.BAYI_VITRINI)
    hazirlar = [{"kod": k, "deger": _temizle(parcali.hazir_degerler(k))} for k, _, _ in parcali.HAZIRLAR
                if k not in pasifler and (not yalniz_secili or k in bayiye)]
    seriler = []
    for on, ad in parcali.KATALOG_SERILERI + parcali.EK_SERILER:
        # pasif (fotoğrafı kötü) modeller stüdyoda da görünmez (2026-11-23)
        modeller = KatalogModeli.objects.filter(kod__startswith=on + "-", aktif=True).exclude(resim="").order_by("kod")
        if yalniz_secili:  # bayi yalnız vitrindeki, gerçekçi çizimi hazır modelleri görür
            modeller = modeller.filter(kod__in=bayiye)
        # "bu modelden başla" yönetici dahil herkese yalnız fotoğrafa göre kurulmuş (seçili) modellerde (2026-11-16:
        # öteki modellerde çizim katalog fotoğrafına benzemiyor, madalyon logosu kayboluyordu)
        seriler.append({"on": on, "ad": ad, "modeller": [{"kod": m.kod, "resim": m.resim.url,
                                                          "duzenlenir": m.kod in parcali.SECILI_MODELLER} for m in modeller]})
    seriler = [sr for sr in seriler if sr["modeller"]]
    motifler = [{"kod": k, "ad": a, "olcu": f"{e:g}×{b:g}"} for k, a, e, b, _ in parcali.NAKIS_MOTIFLERI]
    halkalar = [{"no": i, "tur": veri[f"h{i}_tur"], "gen": veri[f"h{i}_gen"], "malzeme": veri[f"h{i}_malzeme"],
                 "desen": veri[f"h{i}_desen"], "nakis": veri[f"h{i}_nakis"], "ara": veri.get(f"a{i}_gen", 0),
                 "ad_malzeme": f"h{i}_malzeme", "ad_desen": f"h{i}_desen", "ad_nakis": f"h{i}_nakis"} for i in range(1, parcali.EN_COK_HALKA + 1)]
    return render(request, "uretim/tasarim_parcali.html", {
        "form": form, "v": veri, "h": bayi_hesap(veri), "halkalar": halkalar,
        "ek_satirlar": list(zip(request.POST.getlist("ek_en"), request.POST.getlist("ek_boy"), request.POST.getlist("ek_adet")))
        if request.method == "POST" else [], "malzemeler": _gruplu_malzemeler(),
        "ara_secenek": parcali.ARA_SECENEK,
        "sekiller": parcali.SEKILLER, "halka_turleri": parcali.HALKA_TURLERI, "orta_turleri": parcali.ORTA_TURLERI,
        "serit_turleri": parcali.SERIT_TURLERI, "serit_yonleri": parcali.SERIT_YONLERI, "nakis_motifleri": motifler,
        "iplikler": parcali.IPLIKLER,
        "kenarlar": parcali.KENARLAR, "kenar_renkleri": [(k, ad, _grup(k)) for k, ad in parcali.kenar_secenekleri()], "desenler": desenler,
        "seriler": seriler, "madalyonlar": parcali.MADALYONLAR, "hazir_json": {h["kod"]: h["deger"] for h in hazirlar}, "kendi_zemin": {k: d["zemin"] for k, d in parcali.FOTO_RENK.items()}, "en_cok_halka": parcali.EN_COK_HALKA,
        "aile_malzemeleri": parcali.AILE_MALZEMELERI,
    })


@login_required
def onizleme(request):
    v = _temizle(request.GET)
    if v["duzen"] == "halkali":
        return JsonResponse({"v": v, **bayi_hesap(v)})
    return JsonResponse({"v": v, **hesap(v)})


def _kisa_ad(k):
    """'Rono RN06 Koyu kahve' → 'RN06', 'Krem peluş' → 'Krem peluş', 'Altın' → 'Altın'."""
    ad = (parcali.MALZEME_AD.get(k) or parcali.KENAR_AD.get(k) or k).split(" (")[0]
    parca = ad.split(" ")
    return parca[1] if len(parca) > 2 and parca[0] in ("Rono", "Bienca") else ad


@login_required
def fikir(request):
    """'Bana fikir ver': kurallara uygun 6 farklı öneri (bayi ölçüsü korunur)."""
    try:
        olcu = (float(request.GET["en"]), float(request.GET["boy"]))
    except (KeyError, ValueError):
        olcu = None
    sonuc = []
    for v in parcali.fikirler(6, None, _desen_kodlari() - parcali.GIZLI_DESENLER, olcu,
                              katalog=str(request.GET.get("katalog", "")).upper(), seri=request.GET.get("seri", ""),
                              sekil=request.GET.get("sekil")):
        baslik = f"{v['katalog']} · zemin {_kisa_ad(v['zemin'])} · kenar {_kisa_ad(v['kenar_renk'])}"
        sonuc.append({"v": {k: ("" if d is None else d) for k, d in v.items()}, "baslik": baslik})
    return JsonResponse(sonuc, safe=False)


@login_required
def onizleme_resmi(request):
    return _jpeg(_temizle(request.GET), _boyut(request))


@login_required
def motif_ornegi(request, kod):
    if kod not in parcali.MOTIF:
        raise Http404
    yanit = HttpResponse(parcali_gorsel.nakis_ornegi(kod), content_type="image/png")
    yanit["Cache-Control"] = "private, max-age=604800"
    return yanit


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
