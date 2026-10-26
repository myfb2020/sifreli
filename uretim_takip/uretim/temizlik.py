"""Canlı kullanıma geçmeden önce deneme kayıtlarını silme (yalnızca yönetici).

Tanımlar (istasyonlar, makineler, halı türleri, deri türleri, kullanıcı hesapları) silinmez.
Silmeden önce veritabanının yedeği yedekler/ klasörüne alınır.
"""

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import (
    DeriDuzeltme, HamDeriGirisi, IslemKaydi, LotKaynagi, Malzeme, MalzemeHareketi, Musteri, OturumKaydi, Personel,
    Siparis, Tedarikci, UretimLotu,
)
from .yedek import sadece_yonetici, yedek_al

# Her zaman silinenler: (etiket, model) — silme sırası yabancı anahtarlara göre.
KAYITLAR = [
    ("Malzeme hareketleri", MalzemeHareketi),
    ("İşlem kayıtları", IslemKaydi),
    ("Stoktan işe çıkışlar", LotKaynagi),
    ("İşler", UretimLotu),
    ("Stok düzeltmeleri", DeriDuzeltme),
    ("Stok lotları", HamDeriGirisi),
    ("Siparişler", Siparis),
    ("Tablet giriş kayıtları", OturumKaydi),
]
# İsteğe bağlı silinenler: (form alanı, etiket, model)
SECMELI = [
    ("musteri", "Müşteriler", Musteri),
    ("tedarikci", "Tedarikçiler", Tedarikci),
    ("malzeme", "Malzeme tanımları", Malzeme),
    ("personel", "Personel (çalışanlar ve PIN'leri)", Personel),
]
ONAY_KELIMESI = "SİL"


def _yedek_yolu():
    klasor = Path(settings.BASE_DIR) / "yedekler"
    klasor.mkdir(exist_ok=True)
    return klasor / f"temizlik_oncesi_{timezone.localtime():%Y-%m-%d_%H%M%S}.sqlite3"


@sadece_yonetici
def test_verilerini_sil(request):
    if request.method == "POST":
        onay = request.POST.get("onay", "").strip().upper().replace("I", "İ")
        if onay != ONAY_KELIMESI:
            messages.error(request, f"Silmek için kutuya büyük harflerle {ONAY_KELIMESI} yazın.")
            return redirect("test_verilerini_sil")
        yedek = yedek_al(_yedek_yolu())
        secilenler = [(etiket, model) for alan, etiket, model in SECMELI if request.POST.get(alan)]
        with transaction.atomic():
            silinen = [(etiket, model.objects.all().delete()[0]) for etiket, model in KAYITLAR + secilenler]
        ozet = ", ".join(f"{etiket}: {sayi}" for etiket, sayi in silinen if sayi)
        messages.success(request, f"Deneme kayıtları silindi ({ozet or 'silinecek kayıt yoktu'}). "
                                  f"Silmeden önceki yedek: yedekler/{yedek.name}")
        return redirect("pano")

    return render(request, "uretim/test_verilerini_sil.html", {
        "kayitlar": [(etiket, model.objects.count()) for etiket, model in KAYITLAR],
        "secmeli": [(alan, etiket, model.objects.count()) for alan, etiket, model in SECMELI],
        "onay_kelimesi": ONAY_KELIMESI,
    })
