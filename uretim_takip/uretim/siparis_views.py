from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import fotograf
from .forms import FotografForm, SiparisForm
from .katalog_views import secim_verisi
from .models import Siparis, SiparisFotografi, UretimLotu

SEKMELER = [
    ("onay", "Onay bekleyen"),
    ("aktif", "Devam eden"),
    ("tamamlandi", "Tamamlanan"),
    ("sevk", "Sevk edilen"),
    ("iptal", "İptal"),
    ("hepsi", "Hepsi"),
]


def _lotlu(qs):
    return qs.select_related("musteri", "deri_turu", "hali_turu", "katalog_modeli__seri", "lazer_deseni", "tasarim").prefetch_related(
        Prefetch("lotlar", queryset=UretimLotu.objects.select_related("son_asama")), "fotograflar"
    )


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def siparis_listesi(request):
    sekme = request.GET.get("durum", "aktif")
    siparisler = _lotlu(Siparis.objects.all())
    if sekme == "aktif":
        siparisler = siparisler.filter(durum__in=["acik", "uretimde"]).order_by("teslim_tarihi")
    elif sekme in dict(Siparis.DURUM):
        siparisler = siparisler.filter(durum=sekme).order_by("-teslim_tarihi")
    else:
        siparisler = siparisler.order_by("-tarih", "-siparis_no")
    ara = request.GET.get("ara", "").strip()
    if ara:
        siparisler = siparisler.filter(
            Q(siparis_no__icontains=ara) | Q(musteri__ad__icontains=ara) | Q(urun__icontains=ara)
        )
    satirlar = [(s, s.ilerleme()) for s in siparisler[:200]]
    return render(request, "uretim/siparis_listesi.html", {
        "satirlar": satirlar, "sekme": sekme, "sekmeler": SEKMELER, "ara": ara,
        "geciken": sum(1 for s, _ in satirlar if s.gecikti_mi),
        "onay_sayisi": Siparis.objects.filter(durum="onay").count(),
    })


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def siparis_detay(request, pk):
    siparis = get_object_or_404(_lotlu(Siparis.objects.all()), pk=pk)
    lotlar = siparis.lotlar.select_related("son_asama").prefetch_related("kaynaklar__ham_deri__deri_turu").order_by("lot_no")
    from .tasarim_views import onay_formu

    return render(request, "uretim/siparis_detay.html", {
        "siparis": siparis, "ilerleme": siparis.ilerleme(), "lotlar": lotlar,
        "onay_formu": onay_formu(siparis) if siparis.durum == "onay" and request.user.has_perm("uretim.change_siparis")
        else None,
        "foto_formu": FotografForm() if request.user.has_perm("uretim.change_siparis") else None,
        "foto_yer": SiparisFotografi.EN_COK - len(siparis.fotograflar.all()),
    })


@login_required
@permission_required("uretim.add_siparis", raise_exception=True)
def siparis_yeni(request):
    form = SiparisForm(request.POST or None, request.FILES or None, initial={"model_kodu": request.GET.get("model", "")})
    if request.method == "POST" and form.is_valid():
        try:
            icerikler = [fotograf.kucult(d) for d in form.cleaned_data["fotograflar"]]
        except fotograf.FotografHatasi as e:
            form.add_error("fotograflar", str(e))
        else:
            siparis = form.save()
            for icerik in icerikler:
                fotograf.kaydet(siparis, icerik)
            messages.success(request, f"{siparis.siparis_no} numaralı sipariş kaydedildi"
                                      + (f" ({len(icerikler)} fotoğraf)." if icerikler else "."))
            return redirect("siparis_detay", pk=siparis.pk)
    return render(request, "uretim/siparis_yeni.html", {"form": form, **secim_verisi()})


@require_POST
@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_durum(request, pk):
    siparis = get_object_or_404(Siparis, pk=pk)
    yeni = request.POST.get("durum")
    izinli = {"sevk": ("tamamlandi", "uretimde", "acik"), "iptal": ("acik", "uretimde"), "uretimde": ("sevk",)}
    if yeni not in izinli or siparis.durum not in izinli[yeni]:
        messages.error(request, "Bu durum değişikliği yapılamaz.")
    else:
        siparis.durum = yeni
        siparis.save(update_fields=["durum"])
        messages.success(request, f"{siparis.siparis_no}: durum “{siparis.get_durum_display()}” olarak güncellendi.")
    return redirect("siparis_detay", pk=siparis.pk)


@require_POST
@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_foto_ekle(request, pk):
    siparis = get_object_or_404(Siparis, pk=pk)
    form = FotografForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Fotoğraf seçin.")
    else:
        try:
            n = fotograf.ekle(siparis, form.cleaned_data["fotograflar"])
            messages.success(request, f"{n} fotoğraf eklendi.")
        except fotograf.FotografHatasi as e:
            messages.error(request, str(e))
    return redirect("siparis_detay", pk=siparis.pk)


@require_POST
@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_foto_sil(request, pk):
    foto = get_object_or_404(SiparisFotografi, pk=pk)
    siparis = foto.siparis
    foto.resim.delete(save=False)
    foto.delete()
    messages.success(request, "Fotoğraf silindi.")
    return redirect("siparis_detay", pk=siparis.pk)


@require_POST
@login_required
@permission_required("uretim.add_katalogmodeli", raise_exception=True)
def siparis_foto_model(request, pk):
    foto = get_object_or_404(SiparisFotografi.objects.select_related("siparis__musteri"), pk=pk)
    model = fotograf.modele_ekle(foto)
    messages.success(request, f"Fotoğraf katalog modeli {model.kod} olarak eklendi (seri: {model.seri}). "
                              "Artık yeni siparişte bu kod seçilebilir; bayiler de Suni deri sayfasında görür.")
    return redirect("siparis_detay", pk=foto.siparis_id)
