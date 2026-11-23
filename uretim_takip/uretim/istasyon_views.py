"""İstasyon ekranları: her istasyonun tabletinde açık durur, yeni iş gelince uyarır."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.core.exceptions import ValidationError

from . import fotograf, oturum, servisler, uyarilar
from .forms import IstasyonTamirForm
from .models import Asama, Siparis, hesap_personeli


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


@login_required
def istasyon_parca(request, pk):
    """Ekranın kendini yenilemesi için yalnızca liste kısmı."""
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    return render(request, "uretim/_istasyon_parca.html", _baglam(asama, kullanici=request.user))


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
    form = IstasyonTamirForm(request.POST or None, request.FILES or None, personel_belli=personel is not None,
                             initial={"siparis_no": request.GET.get("siparis", "")})
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            foto = fotograf.kucult(v["foto"]) if v.get("foto") else None
            kayit = servisler.istasyon_tamiri(siparis=form.siparis, asama=asama, neden=v["neden"],
                                              aciklama=v["aciklama"], foto=foto, personel=personel or v.get("personel"),
                                              kullanici=request.user)
        except (fotograf.FotografHatasi, ValidationError) as e:
            form.add_error(None, str(e) if isinstance(e, fotograf.FotografHatasi) else " ".join(e.messages))
        else:
            kayit.lot.refresh_from_db()
            basladi = kayit.lot.durum == "islemde"
            messages.success(request, f"{kayit.no} açıldı ({form.siparis.siparis_no}); tamir işi "
                                      + ("başladı, bitince ■ Bitir'e basın." if basladi else "Bekleyen listesinde."))
            return redirect(f"{reverse('istasyon_ekrani', args=[asama.pk])}?sekme={'calisilan' if basladi else 'gelen'}")
    adaylar = (Siparis.objects.filter(durum__in=("uretimde", "tamamlandi", "sevk", "tamirde"))
               .select_related("musteri").order_by("-pk")[:200])
    return render(request, "uretim/istasyon_tamir.html", {"form": form, "asama": asama, "adaylar": adaylar})
