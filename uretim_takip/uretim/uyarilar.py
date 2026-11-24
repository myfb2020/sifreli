"""İstasyon ekranları ve pano için: bekleyen işler, süre aşımları ve azalan stok."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Max, Sum, prefetch_related_objects
from django.utils import timezone

from .models import Asama, DeriTuru, IslemKaydi, Malzeme, RotaAdimi, Siparis, UretimLotu, sonraki_asamalar


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


def oncelikli_mi(siparis):
    """⚡ Öncelikli sekmesinde mi: ofis / lazer ustası öne aldı ya da acil."""
    return siparis is not None and (siparis.acil or siparis.oncelik_sira is not None)


def oncelik(kalem):
    """İstasyon listelerinin sırası: önce ⚡ öncelikliler (elle verilen sırayla, sonra acil), sonra teslim tarihi en yakın,
    sonra en uzun bekleyen."""
    sp = kalem.siparis
    sira = sp.oncelik_sira if sp is not None and sp.oncelik_sira is not None else 10 ** 9
    return (not oncelikli_mi(sp), sira, not (sp and sp.acil), sp.teslim_tarihi if sp else date.max, -kalem.sure)


# Biye / Lanfel / Kenar dikişi gibi alternatif istasyonlarda iş yalnız siparişin kenar türüne uyan istasyona düşer
KENAR_ISTASYON = {"biye": ("biye",), "lanfel": ("lanfel", "lanfer"), "kenar_dikisi": ("kenar",)}


def kenara_gore(hedefler, siparis):
    if len(hedefler) < 2 or siparis is None:
        return hedefler
    tur = siparis.kenar_turu()
    if not tur:
        return hedefler
    uyan = [h for h in hedefler if any(s in h.ad.replace("İ", "i").replace("I", "ı").lower() for s in KENAR_ISTASYON[tur])]
    return uyan or hedefler


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
    def on_islem(self):
        """Lazer ve sonrasında: iş önce Nakış'tan geçtiyse 'Nakışlı', Kaplama'dan geçtiyse 'Kaplamalı'."""
        if self.lot is None or self.lot.tur == "tamir":
            return ""
        rota = self.lot.rota()
        mevcut = next((sira for sira, a in rota if a.pk == self.asama.pk), None)
        if mevcut is None:
            return ""
        for sira, a in rota:
            ad = a.ad.lower()
            if sira < mevcut and ad.startswith("nakış"):
                return "Nakışlı"
            if sira < mevcut and ad.startswith("kaplama"):
                return "Kaplamalı"
        return ""

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


def calisilanlar(asama=None):
    simdi = timezone.now()
    qs = IslemKaydi.objects.filter(bitis__isnull=True).select_related("asama", "makine", "personel", "lot__siparis__musteri",
                                                                  "lot__siparis__katalog_modeli", "lot__siparis__lazer_deseni",
                                                                  "lot__siparis__tasarim")
    if asama:
        qs = qs.filter(asama=asama)
    rotalar = _rota_haritasi()
    kalemler = [
        Kalem("calisilan", f"i{i.pk}", i.asama, simdi - i.baslangic, i.asama.azami_sure_saat, lot=i.lot, islem=i,
              siparis=i.lot.siparis)
        for i in qs.select_related("lot__kalem").prefetch_related("lot__siparis__fotograflar", "lot__siparis__kalemler", "lot__olculer__kalem",
                                                                  "lot__is_notlari__asama", "lot__is_notlari__personel")
    ]
    for k in kalemler:
        _rotayi_tak(k.lot, rotalar)
    return sorted(kalemler, key=oncelik)


def _rota_haritasi():
    """{halı türü: [(sıra, istasyon)]} tek sorguda; işlerin rotası buradan (her iş için ayrı sorgu yapılıyordu)."""
    rotalar = {}
    for adim in RotaAdimi.objects.filter(asama__aktif=True).select_related("asama"):
        rotalar.setdefault(adim.hali_turu_id, []).append((adim.sira, adim.asama))
    for adimlar in rotalar.values():
        adimlar.sort(key=lambda x: (x[0], x[1].sira))
    return rotalar


def _rotayi_tak(lot, rotalar):
    if lot is not None and lot.tur != "tamir":
        lot._rota = rotalar.get(lot.siparis.hali_turu_id if lot.siparis_id else None, [])


def gelenler(asama=None):
    """Sıradaki aşamayı bekleyen işler ve (ilk istasyon için) henüz işi açılmamış yeni siparişler."""
    simdi = timezone.now()
    rotalar = _rota_haritasi()

    def hedefler(hali_turu_id, son_asama, siparis=None):
        # Alternatif istasyonlar (ör. Biye / Lanfel): siparişte kenar türü yazıyorsa yalnız o istasyona, yoksa hepsinin
        # ekranına düşer; hangisi başlarsa o alır.
        sonuc = kenara_gore(sonraki_asamalar(rotalar.get(hali_turu_id, []), son_asama), siparis)
        return [h for h in sonuc if asama is None or h.pk == asama.pk]

    sonuc = []
    lotlar = (
        UretimLotu.objects.filter(durum="bekliyor")
        .select_related("son_asama", "kalem", "siparis__musteri", "siparis__katalog_modeli", "siparis__lazer_deseni",
                        "siparis__tasarim")
        .annotate(son_bitis=Max("islemler__bitis"))
    )
    # ayrıntılar (ölçüler, fotoğraflar, notlar) yalnız bu istasyona düşen işler için okunur (2026-11-24, hız)
    secilenler = []
    for lot in lotlar:
        _rotayi_tak(lot, rotalar)
        bekleme = simdi - (lot.son_bitis or lot.olusturma)
        if lot.tur == "tamir":  # tamir işi ofisin seçtiği istasyonlardan geçer
            tamir_hedefleri = [h for h in lot.asama_sonrasi(lot.son_asama) if asama is None or h.pk == asama.pk]
        for hedef in (tamir_hedefleri if lot.tur == "tamir" else
                      hedefler(lot.siparis.hali_turu_id if lot.siparis else None, lot.son_asama, lot.siparis)):
            sonuc.append(Kalem("gelen", f"l{lot.pk}-{lot.son_asama_id}", hedef, bekleme, hedef.azami_bekleme_saat,
                               lot=lot, siparis=lot.siparis))
            if not secilenler or secilenler[-1] is not lot:
                secilenler.append(lot)
    prefetch_related_objects(secilenler, "siparis__kalemler", "olculer__kalem", "siparis__fotograflar",
                             "is_notlari__asama", "is_notlari__personel")

    for sp in (Siparis.objects.filter(durum="acik", lotlar__isnull=True)
               .select_related("musteri", "katalog_modeli", "lazer_deseni", "tasarim")
               .prefetch_related("kalemler", "fotograflar")):
        for hedef in hedefler(sp.hali_turu_id, None, sp):
            sonuc.append(Kalem("siparis", f"s{sp.pk}", hedef, simdi - sp.olusturma, hedef.azami_bekleme_saat,
                               siparis=sp))
    return sorted(sonuc, key=oncelik)


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
    ozet = deri_ozeti()
    for tur in DeriTuru.objects.exclude(min_kg__isnull=True, min_m2__isnull=True):
        kalan = ozet.get(tur.pk, {})
        if tur.min_kg is not None and kalan.get("kalan_kg", Decimal(0)) < tur.min_kg:
            uyarilar.append(StokUyarisi(tur.ad, kalan.get("kalan_kg", Decimal(0)), tur.min_kg, "kg",
                                        reverse("stok_listesi")))
        if tur.min_m2 is not None and kalan.get("kalan_m2", Decimal(0)) < tur.min_m2:
            uyarilar.append(StokUyarisi(tur.ad, kalan.get("kalan_m2", Decimal(0)), tur.min_m2, "m²",
                                        reverse("stok_listesi")))
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
