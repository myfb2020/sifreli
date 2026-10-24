from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font

from . import raporlar, servisler
from .forms import IslemBaslatForm, IslemBitirForm, TarihAraligiForm
from .models import Asama, IslemKaydi, Siparis, UretimLotu


@login_required
def pano(request):
    bugun = timezone.localdate()
    aktif_lotlar = UretimLotu.objects.exclude(durum__in=["tamamlandi", "iptal"])
    asamalar = Asama.objects.filter(aktif=True).annotate(
        islemde=Count("uretimlotu", filter=Q(uretimlotu__durum="islemde")),
        bekleyen=Count("uretimlotu", filter=Q(uretimlotu__durum="bekliyor")),
    )
    baglam = {
        "asamalar": asamalar,
        "yeni_lot_sayisi": aktif_lotlar.filter(son_asama__isnull=True).count(),
        "acik_islemler": IslemKaydi.objects.filter(bitis__isnull=True).select_related("lot", "asama", "personel"),
        "bugun_personel": raporlar.personel_ozeti(bugun, bugun),
        "geciken_siparisler": Siparis.objects.filter(
            durum__in=["acik", "uretimde"], teslim_tarihi__lt=bugun
        ).select_related("musteri"),
        "yaklasan_siparisler": Siparis.objects.filter(
            durum__in=["acik", "uretimde"], teslim_tarihi__gte=bugun, teslim_tarihi__lte=bugun + timedelta(days=7)
        ).select_related("musteri"),
    }
    return render(request, "uretim/pano.html", baglam)


@login_required
def islem_baslat(request):
    baslangic = {}
    if "lot" in request.GET:
        lot = UretimLotu.objects.filter(pk=request.GET["lot"]).first()
        if lot:
            baslangic = {"lot": lot, "asama": lot.siradaki_asama}

    form = IslemBaslatForm(request.POST or None, initial=baslangic)
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            islem = servisler.islem_baslat(
                lot=v["lot"], asama=v["asama"], personel=v["personel"], aciklama=v["aciklama"]
            )
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(request, f"{islem.personel} – {islem.lot} lotunda “{islem.asama.ad}” başladı.")
            return redirect("pano")
    return render(request, "uretim/islem_baslat.html", {"form": form})


@login_required
def islem_bitir(request, pk):
    islem = get_object_or_404(IslemKaydi.objects.select_related("lot", "asama", "personel"), pk=pk)
    if islem.tamamlandi:
        messages.info(request, "Bu işlem zaten bitirilmiş.")
        return redirect("lot_detay", pk=islem.lot_id)

    form = IslemBitirForm(
        request.POST or None,
        initial={"personel": islem.personel, "cikis_kg": islem.giris_kg, "cikis_m2": islem.giris_m2},
    )
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        try:
            servisler.islem_bitir(
                islem=islem, personel=v["personel"], cikis_kg=v["cikis_kg"], cikis_m2=v["cikis_m2"],
                aciklama=v["aciklama"],
            )
        except ValidationError as hata:
            form.add_error(None, hata)
        else:
            messages.success(request, f"{islem.lot} – “{islem.asama.ad}” bitti.")
            return redirect("pano")
    return render(request, "uretim/islem_bitir.html", {"form": form, "islem": islem})


@login_required
def lot_listesi(request):
    durum = request.GET.get("durum", "aktif")
    lotlar = UretimLotu.objects.select_related("ham_deri__tedarikci", "ham_deri__deri_turu", "siparis", "son_asama")
    if durum == "aktif":
        lotlar = lotlar.exclude(durum__in=["tamamlandi", "iptal"])
    elif durum in dict(UretimLotu.DURUM):
        lotlar = lotlar.filter(durum=durum)
    ara = request.GET.get("ara", "").strip()
    if ara:
        lotlar = lotlar.filter(
            Q(lot_no__icontains=ara) | Q(ham_deri__lot_no__icontains=ara) | Q(siparis__siparis_no__icontains=ara)
        )
    return render(
        request, "uretim/lot_listesi.html",
        {"lotlar": lotlar[:300], "durum": durum, "ara": ara, "durumlar": UretimLotu.DURUM},
    )


@login_required
def lot_detay(request, pk):
    lot = get_object_or_404(
        UretimLotu.objects.select_related("ham_deri__tedarikci", "ham_deri__deri_turu", "siparis__musteri"), pk=pk
    )
    islemler = lot.islemler.select_related("asama", "personel", "bitiren").order_by("baslangic")
    return render(request, "uretim/lot_detay.html", {"lot": lot, "islemler": islemler})


def _tarih_araligi(request):
    bugun = timezone.localdate()
    form = TarihAraligiForm(request.GET or {"baslangic": bugun.replace(day=1), "bitis": bugun})
    if form.is_valid():
        return form, form.cleaned_data["baslangic"], form.cleaned_data["bitis"]
    return form, bugun.replace(day=1), bugun


@login_required
def rapor(request):
    form, bas, son = _tarih_araligi(request)
    personel = raporlar.personel_ozeti(bas, son)
    asama = raporlar.asama_ozeti(bas, son)
    for satir in personel + asama:
        satir["sure_metni"] = raporlar.sure_metni(satir["toplam_sure"])
    return render(
        request, "uretim/rapor.html",
        {"form": form, "personel": personel, "asama": asama, "bas": bas, "son": son},
    )


@login_required
def rapor_excel(request):
    _, bas, son = _tarih_araligi(request)
    kitap = Workbook()
    kalin = Font(bold=True)

    def sayfa_yaz(sayfa, basliklar, satirlar):
        sayfa.append(basliklar)
        for hucre in sayfa[1]:
            hucre.font = kalin
        for satir in satirlar:
            sayfa.append(satir)
        for sutun in sayfa.columns:
            sayfa.column_dimensions[sutun[0].column_letter].width = max(12, len(str(sutun[0].value)) + 4)

    ozet_baslik = ["İşlem", "Giriş kg", "Çıkış kg", "Fire kg", "Giriş m²", "Çıkış m²", "Fire m²", "Fire % (m²)", "Süre"]

    def ozet_satiri(s):
        return [
            s["islem_sayisi"], s["giris_kg"], s["cikis_kg"], s["fire_kg"], s["giris_m2"], s["cikis_m2"],
            s["fire_m2"], s["fire_yuzde_m2"], raporlar.sure_metni(s["toplam_sure"]),
        ]

    sayfa = kitap.active
    sayfa.title = "Personel"
    sayfa_yaz(sayfa, ["Personel"] + ozet_baslik,
              [[s["personel__ad_soyad"]] + ozet_satiri(s) for s in raporlar.personel_ozeti(bas, son)])

    sayfa_yaz(kitap.create_sheet("Aşamalar"), ["Aşama"] + ozet_baslik,
              [[s["asama__ad"]] + ozet_satiri(s) for s in raporlar.asama_ozeti(bas, son)])

    detay = raporlar.tamamlanan_islemler(bas, son).select_related("lot", "asama", "personel", "bitiren")
    yerel = timezone.localtime
    sayfa_yaz(
        kitap.create_sheet("İşlem detayı"),
        ["Lot", "Aşama", "Personel", "Bitiren", "Başlangıç", "Bitiş", "Giriş kg", "Çıkış kg", "Giriş m²", "Çıkış m²", "Not"],
        [
            [i.lot.lot_no, i.asama.ad, i.personel.ad_soyad, i.bitiren.ad_soyad if i.bitiren else "",
             yerel(i.baslangic).replace(tzinfo=None), yerel(i.bitis).replace(tzinfo=None),
             i.giris_kg, i.cikis_kg, i.giris_m2, i.cikis_m2, i.aciklama]
            for i in detay.order_by("bitis")
        ],
    )

    yanit = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    yanit["Content-Disposition"] = f'attachment; filename="uretim_raporu_{bas}_{son}.xlsx"'
    kitap.save(yanit)
    return yanit
