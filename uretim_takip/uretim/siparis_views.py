from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import fotograf, servisler
from .forms import FotografForm, SiparisForm, TamirForm, olcu_formseti
from .katalog_views import secim_verisi
from .models import IsNotu, Siparis, SiparisFotografi, UretimLotu

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
        Prefetch("lotlar", queryset=UretimLotu.objects.select_related("son_asama", "kalem")), "fotograflar", "kalemler"
    )


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def siparis_listesi(request):
    sekme = request.GET.get("durum", "aktif")
    siparisler = _lotlu(Siparis.objects.all())
    if sekme == "aktif":
        siparisler = siparisler.filter(durum__in=["acik", "uretimde", "tamirde"]).order_by("-acil", "teslim_tarihi")
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
    lotlar = siparis.lotlar.select_related("son_asama", "kalem").prefetch_related("kaynaklar__ham_deri__deri_turu").order_by("lot_no")
    from .tasarim_views import onay_formu

    return render(request, "uretim/siparis_detay.html", {
        "siparis": siparis, "ilerleme": siparis.ilerleme(), "lotlar": lotlar,
        "onay_formu": onay_formu(siparis) if siparis.durum == "onay" and request.user.has_perm("uretim.change_siparis")
        else None,
        "foto_formu": FotografForm() if request.user.has_perm("uretim.change_siparis") else None,
        "foto_yer": SiparisFotografi.EN_COK - len(siparis.fotograflar.all()),
        "notlar": IsNotu.objects.filter(lot__siparis=siparis).select_related("lot", "asama", "personel", "kullanici"),
        "duzenlenir": siparis.durum not in ("sevk", "iptal"),
    })


def _siparis_kaydet(request, form, olculer, siparis=None):
    """Formu, ölçü satırlarını ve fotoğrafları birlikte kaydeder; hata olursa form hatası olarak döner."""
    try:
        icerikler = [fotograf.kucult(d) for d in form.cleaned_data["fotograflar"]]
    except fotograf.FotografHatasi as e:
        form.add_error("fotograflar", str(e))
        return None
    try:
        with transaction.atomic():
            siparis = form.save()
            if olculer.gonderildi:
                servisler.kalemleri_kaydet(siparis, olculer.satirlar(siparis))
            if siparis is not None:
                silinecek = siparis.fotograflar.filter(pk__in=request.POST.getlist("foto_sil"))
                for f in silinecek:
                    f.resim.delete(save=False)
                silinecek.delete()
    except ValidationError as e:
        form.add_error(None, " ".join(e.messages))
        return None
    for icerik in icerikler:
        fotograf.kaydet(siparis, icerik)
    return siparis, len(icerikler)


@login_required
@permission_required("uretim.add_siparis", raise_exception=True)
def siparis_yeni(request):
    form = SiparisForm(request.POST or None, request.FILES or None, initial={"model_kodu": request.GET.get("model", "")})
    olculer = olcu_formseti(request.POST or None)
    if request.method == "POST" and form.is_valid() and olculer.is_valid():
        sonuc = _siparis_kaydet(request, form, olculer)
        if sonuc:
            siparis, n = sonuc
            messages.success(request, f"{siparis.siparis_no} numaralı sipariş kaydedildi"
                                      + (f" ({n} fotoğraf)." if n else "."))
            return redirect("siparis_detay", pk=siparis.pk)
    return render(request, "uretim/siparis_yeni.html", {"form": form, "olculer": olculer, **secim_verisi()})


@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_duzenle(request, pk):
    siparis = get_object_or_404(Siparis.objects.prefetch_related("fotograflar", "kalemler"), pk=pk)
    if siparis.durum in ("sevk", "iptal"):
        messages.error(request, f"{siparis.siparis_no} {siparis.get_durum_display().lower()}; düzenlenemez.")
        return redirect("siparis_detay", pk=pk)
    silinecek = set(request.POST.getlist("foto_sil"))
    kalan = sum(1 for f in siparis.fotograflar.all() if str(f.pk) not in silinecek)
    form = SiparisForm(request.POST or None, request.FILES or None, instance=siparis, foto_sayisi=kalan)
    olculer = olcu_formseti(request.POST or None, siparis)
    if request.method == "POST" and form.is_valid() and olculer.is_valid():
        if _siparis_kaydet(request, form, olculer, siparis):
            messages.success(request, f"{siparis.siparis_no} güncellendi.")
            return redirect("siparis_detay", pk=siparis.pk)
    return render(request, "uretim/siparis_yeni.html", {"form": form, "olculer": olculer, "siparis": siparis,
                                                         **secim_verisi()})


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
        siparis.sevk_tarihi = timezone.localdate() if yeni == "sevk" else None
        siparis.save(update_fields=["durum", "sevk_tarihi"])
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


@require_POST
@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def siparis_acil(request, pk):
    siparis = get_object_or_404(Siparis, pk=pk)
    siparis.acil = not siparis.acil
    siparis.save(update_fields=["acil"])
    messages.success(request, f"{siparis.siparis_no} " + ("⚡ acil olarak işaretlendi; istasyonlarda en üstte görünür."
                                                           if siparis.acil else "artık acil değil."))
    return redirect("siparis_detay", pk=siparis.pk)


@login_required
@permission_required("uretim.change_siparis", raise_exception=True)
def tamir_ac(request, pk):
    """İade / tamir / düzeltme kaydı ve tamir işi (yalnız ofis; bayi görmez; stoğa giriş yok)."""
    siparis = get_object_or_404(Siparis, pk=pk)
    if siparis.durum not in ("tamamlandi", "sevk", "tamirde"):
        messages.error(request, "Tamir / iade yalnız biten ya da sevk edilen siparişe açılır.")
        return redirect("siparis_detay", pk=pk)
    form = TamirForm(request.POST or None, request.FILES or None, siparis=siparis)
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            foto = fotograf.kucult(v["foto"]) if v.get("foto") else None
            kayit = servisler.tamir_ac(siparis=siparis, istasyonlar=v["istasyonlar"], neden=v["neden"],
                                       kaynak_lot=v.get("kaynak_lot"), aciklama=v.get("aciklama", ""), foto=foto,
                                       hata_asama=v.get("hata_asama"), hata_personel=v.get("hata_personel"),
                                       kullanici=request.user)
        except (fotograf.FotografHatasi, ValidationError) as e:
            form.add_error(None, str(e) if isinstance(e, fotograf.FotografHatasi) else " ".join(e.messages))
        else:
            messages.success(request, f"{kayit.no} açıldı; tamir işi {kayit.istasyonlar.order_by('sira').first().ad} "
                                      "ekranına düştü. Bayi bunu görmez.")
            return redirect("siparis_detay", pk=pk)
    return render(request, "uretim/tamir_ac.html", {"form": form, "siparis": siparis})
