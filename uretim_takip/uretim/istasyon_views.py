"""İstasyon ekranları: her istasyonun tabletinde açık durur, yeni iş gelince uyarır."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.core.exceptions import ValidationError

from . import fotograf, oturum, servisler, uyarilar
from .forms import IstasyonTamirForm, KayitsizHaliForm, PinliForm
from .models import Asama, KatalogModeli, Siparis, UretimLotu, hesap_personeli


@login_required
def istasyon_secimi(request):
    gelen = uyarilar.gelenler()
    calisilan = uyarilar.calisilanlar()
    satirlar = []
    for asama in Asama.objects.filter(aktif=True):
        g = [k for k in gelen if k.asama.pk == asama.pk]
        c = [k for k in calisilan if k.asama.pk == asama.pk]
        satirlar.append({"asama": asama, "gelen": len(g), "calisilan": len(c),
                         "geciken": sum(1 for k in g + c if k.gecikti)})
    return render(request, "uretim/istasyon_secimi.html", {"satirlar": satirlar})


def _baglam(asama, sekme=None, kullanici=None):
    gelen = uyarilar.gelenler(asama)
    calisilan = uyarilar.calisilanlar(asama)
    # ⚡ Öncelikli: öne alınan ya da acil siparişlerin bu istasyondaki işleri (bekleyen + devam eden), sırasıyla
    oncelikli = sorted([k for k in calisilan + gelen if uyarilar.oncelikli_mi(k.siparis)], key=uyarilar.oncelik)
    ekran = reverse("istasyon_ekrani", args=[asama.pk])
    if sekme not in ("calisilan", "gelen", "oncelikli"):  # ilk açılış: devam eden iş varsa o liste, yoksa bekleyenler
        sekme = "calisilan" if calisilan else "gelen"
    return {"asama": asama, "gelen": gelen, "calisilan": calisilan, "oncelikli": oncelikli,
            "oncelikli_geciken": sum(1 for k in oncelikli if k.gecikti),
            "oncelik_yetkisi": kullanici is not None and servisler.oncelik_yetkisi(kullanici),
            "tamir_istasyonu": servisler.tamir_istasyonu_mu(asama),
            "geciken": sum(1 for k in gelen + calisilan if k.gecikti),
            "gelen_geciken": sum(1 for k in gelen if k.gecikti),
            "calisilan_geciken": sum(1 for k in calisilan if k.gecikti),
            "sekme": sekme, "ekran_adresi": ekran,
            # işi başlatınca ekrana "Devam eden" listesiyle dönülür
            "ekran_devam_adresi": f"{ekran}?sekme=calisilan"}


@login_required
def istasyon_ekrani(request, pk):
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    oturum.kaydet(request, "istasyon", asama=asama)
    return render(request, "uretim/istasyon_ekrani.html", _baglam(asama, request.GET.get("sekme"), request.user))


CSRF_YERI = "__CSRF_ANAHTARI__"


@login_required
def istasyon_parca(request, pk):
    """Ekranın kendini yenilemesi için yalnızca liste kısmı (20 sn'de bir).

    Hız (2026-11-24): anahtar = istasyon + hesabın düğme yetkileri + değişiklik sayacı + dakika. Tablet son aldığı
    anahtarı gönderir: aynıysa hiçbir şey hesaplanmaz (204). Değiştiyse liste bir kez hazırlanır ve aynı istasyona
    bakan öteki tabletler de onu kullanır (önbellek); liste gerçekten aynıysa yine 204 (sürüm). Süreler dakikada bir
    güncellenir.
    """
    import hashlib
    import re

    from django.core.cache import cache
    from django.middleware.csrf import get_token
    from django.template.loader import render_to_string
    from django.utils import timezone

    from . import degisiklik

    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    kullanici = request.user
    yetki = servisler.oncelik_yetkisi(kullanici)
    anahtar = (f"ist{asama.pk}-{int(kullanici.is_staff)}{int(kullanici.is_superuser)}{int(yetki)}-"
               f"{degisiklik.numara()}-{timezone.now():%Y%m%d%H%M}")
    if request.headers.get("X-Son-Anahtar") == anahtar:
        yanit = HttpResponse(status=204)
        yanit["X-Anahtar"] = anahtar
        return yanit
    kayit = cache.get(anahtar)
    if kayit is None:
        html = render_to_string("uretim/_istasyon_parca.html", _baglam(asama, kullanici=kullanici), request=request)
        # formlardaki güvenlik anahtarı her tablette başka: önbellekte yer tutucu, gönderirken tabletin kendi anahtarı
        icerik = re.sub(r'(name="csrfmiddlewaretoken" value=")[^"]*"', r'\1' + CSRF_YERI + '"', html)
        kayit = (icerik, hashlib.sha1(icerik.encode()).hexdigest()[:16])
        cache.set(anahtar, kayit, 120)
    icerik, surum = kayit
    if request.headers.get("X-Son-Surum") == surum:
        yanit = HttpResponse(status=204)
    else:
        yanit = HttpResponse(icerik.replace(CSRF_YERI, get_token(request)))
    yanit["X-Surum"] = surum
    yanit["X-Anahtar"] = anahtar
    return yanit


@login_required
@require_POST
def oncelik_degistir(request, pk):
    """⚡ Öne al / ↑ / ↓ / ✕: ofis, yönetici ve lazer ustası."""
    if not servisler.oncelik_yetkisi(request.user):
        raise PermissionDenied
    siparis = get_object_or_404(Siparis, pk=pk)
    islem = request.POST.get("islem")
    if islem in ("ekle", "cikar", "yukari", "asagi"):
        servisler.oncelik_degistir(siparis=siparis, islem=islem)
        if islem == "ekle":
            messages.success(request, f"{siparis.siparis_no} öncelikli işlere eklendi.")
    geri = request.POST.get("geri", "")
    if not url_has_allowed_host_and_scheme(geri, allowed_hosts={request.get_host()}):
        geri = reverse("siparis_detay", args=[siparis.pk])
    return redirect(geri)


@login_required
def istasyon_tamir(request, pk):
    """🔧 Tamir (Zig-zag, Biye, Lanfel, Kenar dikişi): müşteriden dönen ya da üretimde fark edilen halının tamiri yalnız
    bu istasyonda yapılır; kişisel hesapta iş hemen başlar. Ofis Tamirler sayfasında görür."""
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    if not servisler.tamir_istasyonu_mu(asama):
        raise PermissionDenied
    personel = hesap_personeli(request.user)
    kayitsiz = request.GET.get("kayitsiz") == "1" or request.POST.get("kayitsiz") == "1"
    form = IstasyonTamirForm(request.POST or None, request.FILES or None, personel_belli=personel is not None,
                             kayitsiz=kayitsiz, initial={"siparis_no": request.GET.get("siparis", "")})
    hali = KayitsizHaliForm(request.POST or None, prefix="h") if kayitsiz else None
    if request.method == "POST" and form.is_valid() and (hali is None or hali.is_valid()):
        v = form.cleaned_data
        try:
            foto = fotograf.kucult(v["foto"]) if v.get("foto") else None
            with transaction.atomic():
                if hali is not None:  # sisteme girilmemiş halı: kayıt da açılır (bayide görünmez)
                    h = hali.cleaned_data
                    siparis = servisler.kayitsiz_siparis(
                        musteri=h.get("musteri"), yeni_musteri=h.get("yeni_musteri", ""),
                        katalog_modeli=h["katalog_modeli"], urun=h.get("urun", ""), en=h.get("en"), boy=h.get("boy"),
                        kullanici=request.user)
                else:
                    siparis = form.siparis
                kayit = servisler.istasyon_tamiri(siparis=siparis, asama=asama, neden=v["neden"],
                                                  aciklama=v["aciklama"], foto=foto,
                                                  personel=personel or v.get("personel"), kullanici=request.user)
        except (fotograf.FotografHatasi, ValidationError) as e:
            form.add_error(None, str(e) if isinstance(e, fotograf.FotografHatasi) else " ".join(e.messages))
        else:
            kayit.lot.refresh_from_db()
            basladi = kayit.lot.durum == "islemde"
            messages.success(request, f"{kayit.no} açıldı ({siparis.siparis_no}); tamir işi "
                                      + ("başladı, bitince ■ Bitir'e basın." if basladi else "Bekleyen listesinde."))
            return redirect(f"{reverse('istasyon_ekrani', args=[asama.pk])}?sekme={'calisilan' if basladi else 'gelen'}")
    adaylar = (Siparis.objects.filter(durum__in=("uretimde", "tamamlandi", "sevk", "tamirde"))
               .select_related("musteri").order_by("-pk")[:200])
    modeller = KatalogModeli.objects.filter(aktif=True).order_by("kod") if kayitsiz else []
    return render(request, "uretim/istasyon_tamir.html", {"form": form, "asama": asama, "adaylar": adaylar,
                                                          "hali": hali, "kayitsiz": kayitsiz, "modeller": modeller})


@login_required
@require_POST
def hizli_bitir(request, pk):
    """✓ Bitti (bilgi istemeyen istasyonlar: Zig-zag, Biye, Lanfel, Kenar dikişi…): bekleyen işi tek dokunuşla başlatıp
    bitirir, iş sıradaki istasyona geçer. Kişisel hesapta hemen; ortak tablette ad + PIN sorulur."""
    if request.user.is_staff and not request.user.is_superuser:
        raise PermissionDenied  # ofis kalan istasyonları iş sayfasından topluca işaretler
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    lot = get_object_or_404(UretimLotu.objects.select_related("siparis", "son_asama"), pk=request.POST.get("lot") or 0)
    ekran = reverse("istasyon_ekrani", args=[asama.pk])
    if not servisler.hizli_bitirilir_mi(lot, asama):
        messages.error(request, f"{lot.lot_no} şu an {asama.ad} istasyonunu beklemiyor (başka ekranda başlatılmış "
                                "ya da bitmiş olabilir).")
        return redirect(f"{ekran}?sekme=gelen")
    personel = hesap_personeli(request.user)
    form = PinliForm(request.POST if "pin" in request.POST else None, personel=personel)
    if personel is not None or form.is_valid():
        kisi = personel or form.cleaned_data["personel"]
        try:
            islem = servisler.hizli_bitir(lot=lot, asama=asama, personel=kisi)
        except ValidationError as hata:
            messages.error(request, " ".join(hata.messages))
        else:
            islem.lot.refresh_from_db()
            sonraki = ", ".join(a.ad for a in islem.lot.siradaki_asamalar)
            messages.success(request, f"✓ {lot.lot_no} {asama.ad} bitti ({kisi})"
                                      + (f" → {sonraki}." if sonraki else " · iş tamamlandı."))
        return redirect(f"{ekran}?sekme=gelen")
    return render(request, "uretim/hizli_bitir.html", {"form": form, "lot": lot, "asama": asama, "ekran": ekran})
