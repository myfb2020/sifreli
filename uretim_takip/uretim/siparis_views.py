from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SiparisForm
from .models import Siparis, UretimLotu

SEKMELER = [
    ("aktif", "Devam eden"),
    ("tamamlandi", "Tamamlanan"),
    ("sevk", "Sevk edilen"),
    ("iptal", "İptal"),
    ("hepsi", "Hepsi"),
]


def _lotlu(qs):
    return qs.select_related("musteri", "deri_turu", "hali_turu").prefetch_related(
        Prefetch("lotlar", queryset=UretimLotu.objects.select_related("son_asama"))
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
    })


@login_required
@permission_required("uretim.view_siparis", raise_exception=True)
def siparis_detay(request, pk):
    siparis = get_object_or_404(_lotlu(Siparis.objects.all()), pk=pk)
    lotlar = siparis.lotlar.select_related("son_asama").prefetch_related("kaynaklar__ham_deri__deri_turu").order_by("lot_no")
    return render(request, "uretim/siparis_detay.html", {
        "siparis": siparis, "ilerleme": siparis.ilerleme(), "lotlar": lotlar,
    })


@login_required
@permission_required("uretim.add_siparis", raise_exception=True)
def siparis_yeni(request):
    form = SiparisForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        siparis = form.save()
        messages.success(request, f"{siparis.siparis_no} numaralı sipariş kaydedildi.")
        return redirect("siparis_detay", pk=siparis.pk)
    return render(request, "uretim/siparis_yeni.html", {"form": form})


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
