"""İstasyon ekranları ve pano için: bekleyen işler, süre aşımları ve azalan stok."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Sum
from django.utils import timezone

from .models import Asama, DeriTuru, IslemKaydi, Malzeme, Siparis, UretimLotu


def _saat(sure):
    return Decimal(sure.total_seconds()) / 3600


def sure_metni(sure):
    dakika = max(0, int(sure.total_seconds() // 60))
    gun, dakika = divmod(dakika, 24 * 60)
    saat, dakika = divmod(dakika, 60)
    if gun:
        return f"{gun} gün {saat} sa"
    if saat:
        return f"{saat} sa {dakika} dk"
    return f"{dakika} dk"


@dataclass
class Kalem:
    """İstasyon ekranındaki bir satır: çalışılan iş, gelen iş ya da yeni sipariş."""

    tur: str  # "calisilan" | "gelen" | "siparis"
    anahtar: str  # sayfanın "yeni geldi" takibi için
    asama: Asama
    sure: timedelta
    sinir_saat: Decimal | None
    lot: UretimLotu | None = None
    islem: IslemKaydi | None = None
    siparis: Siparis | None = None

    @property
    def gecikti(self):
        return self.sinir_saat is not None and _saat(self.sure) > self.sinir_saat

    @property
    def sure_metni(self):
        return sure_metni(self.sure)

    @property
    def asim_metni(self):
        if not self.gecikti:
            return ""
        return sure_metni(self.sure - timedelta(hours=float(self.sinir_saat)))


def _ilk_asama():
    return Asama.objects.filter(aktif=True).first()


def calisilanlar(asama=None):
    simdi = timezone.now()
    qs = IslemKaydi.objects.filter(bitis__isnull=True).select_related("asama", "personel", "lot__siparis__musteri")
    if asama:
        qs = qs.filter(asama=asama)
    return [
        Kalem("calisilan", f"i{i.pk}", i.asama, simdi - i.baslangic, i.asama.azami_sure_saat, lot=i.lot, islem=i,
              siparis=i.lot.siparis)
        for i in qs.order_by("baslangic")
    ]


def gelenler(asama=None):
    """Sıradaki aşamayı bekleyen işler ve (ilk istasyon için) henüz işi açılmamış yeni siparişler."""
    simdi = timezone.now()
    asamalar = list(Asama.objects.filter(aktif=True))
    sonraki = {a.pk: b for a, b in zip(asamalar, asamalar[1:])}
    ilk = asamalar[0] if asamalar else None
    sonuc = []

    lotlar = (
        UretimLotu.objects.filter(durum="bekliyor")
        .select_related("son_asama", "siparis__musteri")
        .annotate(son_bitis=Max("islemler__bitis"))
    )
    for lot in lotlar:
        hedef = sonraki.get(lot.son_asama_id) if lot.son_asama_id else ilk
        if hedef is None or (asama and hedef.pk != asama.pk):
            continue
        bekleme = simdi - (lot.son_bitis or lot.olusturma)
        sonuc.append(Kalem("gelen", f"l{lot.pk}-{lot.son_asama_id}", hedef, bekleme, hedef.azami_bekleme_saat,
                           lot=lot, siparis=lot.siparis))

    if ilk and (asama is None or asama.pk == ilk.pk):
        for sp in Siparis.objects.filter(durum="acik", lotlar__isnull=True).select_related("musteri"):
            sonuc.append(Kalem("siparis", f"s{sp.pk}", ilk, simdi - sp.olusturma, ilk.azami_bekleme_saat, siparis=sp))
    return sorted(sonuc, key=lambda k: (not k.gecikti, -k.sure))


def gecikmeler():
    """Tüm istasyonlarda süre sınırını aşan işler (ofis panosu için)."""
    return [k for k in calisilanlar() + gelenler() if k.gecikti]


@dataclass
class StokUyarisi:
    ad: str
    mevcut: Decimal
    sinir: Decimal
    birim: str
    adres: str


def azalan_stoklar():
    from django.urls import reverse

    uyarilar = []
    for tur in DeriTuru.objects.filter(min_kg__isnull=False):
        toplam = deri_ozeti().get(tur.pk, {}).get("kalan_kg", Decimal(0))
        if toplam < tur.min_kg:
            uyarilar.append(StokUyarisi(f"{tur.ad} derisi", toplam, tur.min_kg, "kg", reverse("stok_listesi")))
    for m in Malzeme.objects.filter(aktif=True, min_stok__isnull=False):
        stok = m.stok
        if stok < m.min_stok:
            uyarilar.append(StokUyarisi(m.ad, stok, m.min_stok, m.get_birim_display(), reverse("malzeme_detay", args=[m.pk])))
    return uyarilar


def deri_ozeti():
    """Deri türüne göre toplam giriş ve kalan: {tur_id: {"tur", "giris_kg", "kalan_kg", "kalan_m2", "lot"}}."""
    from .models import DeriDuzeltme, HamDeriGirisi, LotKaynagi

    ozet = {}
    for tur_id, kg, m2 in HamDeriGirisi.objects.values_list("deri_turu", "kg", "m2"):
        o = ozet.setdefault(tur_id, {"giris_kg": Decimal(0), "kalan_kg": Decimal(0), "kalan_m2": Decimal(0)})
        o["giris_kg"] += kg
        o["kalan_kg"] += kg
        o["kalan_m2"] += m2
    for model, alan in ((LotKaynagi, -1), (DeriDuzeltme, 1)):
        for satir in model.objects.values("ham_deri__deri_turu").annotate(kg=Sum("kg"), m2=Sum("m2")):
            o = ozet.get(satir["ham_deri__deri_turu"])
            if o:
                o["kalan_kg"] += alan * (satir["kg"] or 0)
                o["kalan_m2"] += alan * (satir["m2"] or 0)
    turler = DeriTuru.objects.in_bulk(ozet.keys())
    for tur_id, o in ozet.items():
        o["tur"] = turler[tur_id]
    return ozet
