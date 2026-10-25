"""İstasyon ekranları: her istasyonun tabletinde açık durur, yeni iş gelince uyarır."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import uyarilar
from .models import Asama


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


def _baglam(asama):
    gelen = uyarilar.gelenler(asama)
    calisilan = uyarilar.calisilanlar(asama)
    return {"asama": asama, "gelen": gelen, "calisilan": calisilan,
            "geciken": sum(1 for k in gelen + calisilan if k.gecikti),
            "ekran_adresi": reverse("istasyon_ekrani", args=[asama.pk])}


@login_required
def istasyon_ekrani(request, pk):
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    return render(request, "uretim/istasyon_ekrani.html", _baglam(asama))


@login_required
def istasyon_parca(request, pk):
    """Ekranın kendini yenilemesi için yalnızca liste kısmı."""
    asama = get_object_or_404(Asama, pk=pk, aktif=True)
    return render(request, "uretim/_istasyon_parca.html", _baglam(asama))
