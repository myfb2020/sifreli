from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import FileExtensionValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

SIFIR = Decimal("0")
pozitif = [MinValueValidator(SIFIR)]


def sonraki_numara(model, alan, onek):
    """ONEK-YIL-0001 biçiminde sıradaki numarayı üretir."""
    yil = timezone.localdate().year
    bas = f"{onek}-{yil}-"
    son = (
        model.objects.filter(**{f"{alan}__startswith": bas})
        .order_by(f"-{alan}")
        .values_list(alan, flat=True)
        .first()
    )
    sira = int(son.rsplit("-", 1)[1]) + 1 if son else 1
    return f"{bas}{sira:04d}"


# --- Tanımlar -----------------------------------------------------------------


class Asama(models.Model):
    """Üretim aşaması; her aşama bir istasyondur."""

    ad = models.CharField("aşama adı", max_length=60, unique=True)
    sira = models.PositiveSmallIntegerField(
        "liste sırası", unique=True, help_text="İstasyonların listelerde hangi sırayla görüneceği (küçük olan önce).",
    )
    aktif = models.BooleanField(default=True)
    azami_sure_saat = models.DecimalField(
        "en fazla çalışma süresi (saat)", max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="İş bu istasyonda bu süreden uzun kalırsa uyarı verilir. Boş: sınır yok.",
    )
    azami_bekleme_saat = models.DecimalField(
        "en fazla bekleme süresi (saat)", max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="İş bu istasyona geldikten sonra bu süre içinde başlanmazsa uyarı verilir. Boş: sınır yok.",
    )

    class Meta:
        ordering = ["sira"]
        verbose_name = "aşama"
        verbose_name_plural = "aşamalar"

    def __str__(self):
        return self.ad

    def sonraki(self):
        return Asama.objects.filter(aktif=True, sira__gt=self.sira).first()

    @property
    def son_asama_mi(self):
        return self.sonraki() is None


class Makine(models.Model):
    """İstasyondaki bir makine (ör. Zig-zag 1). Çalışan işe başlarken hangi makinede çalıştığını seçer."""

    ad = models.CharField("makine adı", max_length=60, unique=True)
    asama = models.ForeignKey(Asama, on_delete=models.PROTECT, related_name="makineler", verbose_name="istasyon")
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["asama__sira", "ad"]
        verbose_name = "makine"
        verbose_name_plural = "makineler"

    def __str__(self):
        return self.ad


class HaliTuru(models.Model):
    """Halı türü (ör. Lazerli, Nakışlı, Peluş). Her türün istasyon sırası (rotası) vardır."""

    ad = models.CharField("halı türü", max_length=60, unique=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["ad"]
        verbose_name = "halı türü"
        verbose_name_plural = "halı türleri"

    def __str__(self):
        return self.ad

    def rota_metni(self):
        """Ör. 'Lazer kesim → Zig-zag → Biye / Lanfel'."""
        gruplar = {}
        for adim in self.adimlar.select_related("asama"):
            gruplar.setdefault(adim.sira, []).append(adim.asama.ad)
        return " → ".join(" / ".join(adlar) for _, adlar in sorted(gruplar.items()))


class RotaAdimi(models.Model):
    """Halı türünün geçtiği istasyonlardan biri. Aynı sıra numaralı adımlar alternatiftir (ya biri ya diğeri)."""

    hali_turu = models.ForeignKey(HaliTuru, on_delete=models.CASCADE, related_name="adimlar", verbose_name="halı türü")
    sira = models.PositiveSmallIntegerField("sıra", help_text="Aynı sıra numarası verilen istasyonlardan biri yapılır.")
    asama = models.ForeignKey(Asama, on_delete=models.PROTECT, verbose_name="istasyon")

    class Meta:
        ordering = ["sira", "asama__sira"]
        verbose_name = "rota adımı"
        verbose_name_plural = "rota adımları"
        constraints = [models.UniqueConstraint(fields=["hali_turu", "asama"], name="rotada_istasyon_tek")]

    def __str__(self):
        return f"{self.hali_turu}: {self.sira}. {self.asama.ad}"


def sonraki_asamalar(adimlar, son_asama):
    """Rotaya göre sıradaki istasyon(lar). adimlar: [(sira, asama), ...]; boşsa genel aşama sırası kullanılır.

    son_asama None ise ilk adım(lar) döner. Birden fazla dönerse alternatiftir. Boş liste: iş bitti.
    """
    if not adimlar:
        if son_asama is None:
            ilk = Asama.objects.filter(aktif=True).first()
            return [ilk] if ilk else []
        sonraki = son_asama.sonraki()
        return [sonraki] if sonraki else []
    if son_asama is None:
        esik = -1
    else:
        siralar = [s for s, a in adimlar if a.pk == son_asama.pk]
        if not siralar:  # rotada olmayan bir istasyonda çalışıldı
            return _rota_disi(adimlar, son_asama)
        esik = siralar[0]
    sonrakiler = [(s, a) for s, a in adimlar if s > esik]
    if not sonrakiler:
        return []
    ilk_sira = min(s for s, _ in sonrakiler)
    return [a for s, a in sonrakiler if s == ilk_sira]


def _rota_disi(adimlar, son_asama):
    """Rotada olmayan istasyondan sonra: genel sırada bu istasyondan sonra gelen ilk rota adımı."""
    sonrakiler = [(s, a) for s, a in adimlar if a.sira > son_asama.sira]
    if not sonrakiler:
        return []
    ilk_sira = min(s for s, _ in sonrakiler)
    return [a for s, a in sonrakiler if s == ilk_sira]


def rota_adimlari(hali_turu_id):
    if not hali_turu_id:
        return []
    return [(r.sira, r.asama) for r in RotaAdimi.objects.filter(hali_turu_id=hali_turu_id, asama__aktif=True)
            .select_related("asama")]


class Personel(models.Model):
    ad_soyad = models.CharField("ad soyad", max_length=100)
    pin = models.CharField(
        "PIN",
        max_length=128,
        help_text="4-6 haneli rakam. Kaydedilirken şifrelenir.",
    )
    gorev = models.CharField("görev", max_length=60, blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["ad_soyad"]
        verbose_name = "personel"
        verbose_name_plural = "personel"

    def __str__(self):
        return self.ad_soyad

    def pin_ayarla(self, ham_pin):
        self.pin = make_password(ham_pin)

    def pin_dogru_mu(self, ham_pin):
        return check_password(ham_pin, self.pin)

    def save(self, *args, **kwargs):
        # Admin'den düz PIN girildiyse şifrele.
        if self.pin and not self.pin.startswith(("pbkdf2_", "argon2", "bcrypt")):
            self.pin_ayarla(self.pin)
        super().save(*args, **kwargs)


pin_dogrulayici = RegexValidator(r"^\d{4,6}$", "PIN 4-6 haneli rakam olmalı.")


class Tedarikci(models.Model):
    ad = models.CharField(max_length=120, unique=True)
    telefon = models.CharField(max_length=30, blank=True)
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["ad"]
        verbose_name = "tedarikçi"
        verbose_name_plural = "tedarikçiler"

    def __str__(self):
        return self.ad


class Musteri(models.Model):
    ad = models.CharField(max_length=120, unique=True)
    telefon = models.CharField(max_length=30, blank=True)
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["ad"]
        verbose_name = "müşteri"
        verbose_name_plural = "müşteriler"

    def __str__(self):
        return self.ad


class DeriTuru(models.Model):
    """Ana malzeme türü: Deri çeşitleri, Keçe, Süet, Rona, Suni deri… ve fasonda birleştirilen malzemeler."""

    ad = models.CharField(max_length=60, unique=True)
    bilesik = models.BooleanField(
        "birleşik malzeme", default=False,
        help_text="Fasonda birkaç malzeme preslenerek yapılır (ör. 3'lü lamine, halı tabanı).",
    )
    min_kg = models.DecimalField(
        "en az stok (kg)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Bu türün toplam stoğu bunun altına düşünce uyarı verilir.",
    )
    min_m2 = models.DecimalField(
        "en az stok (m²)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Bu türün toplam m² stoğu bunun altına düşünce uyarı verilir.",
    )

    class Meta:
        ordering = ["bilesik", "ad"]
        verbose_name = "malzeme türü"
        verbose_name_plural = "malzeme türleri"

    def __str__(self):
        return self.ad


# --- Katalog -------------------------------------------------------------------

resim_dogrulayici = FileExtensionValidator(["jpg", "jpeg", "png", "webp"], "Yalnızca resim (jpg, png, webp) yükleyin.")


class KatalogSerisi(models.Model):
    ad = models.CharField("seri", max_length=60, unique=True)
    sira = models.PositiveIntegerField("liste sırası", default=0)
    hali_turu = models.ForeignKey(
        HaliTuru, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="halı türü",
        help_text="Bu seriden sipariş açılınca halı türü (istasyon sırası) kendiliğinden seçilir.",
    )

    class Meta:
        ordering = ["sira", "ad"]
        verbose_name = "katalog serisi"
        verbose_name_plural = "katalog serileri"

    def __str__(self):
        return self.ad


class KatalogModeli(models.Model):
    kod = models.CharField("model kodu", max_length=20, unique=True, help_text="Ör. TOS-034")
    seri = models.ForeignKey(KatalogSerisi, on_delete=models.PROTECT, related_name="modeller")
    resim = models.FileField(upload_to="katalog/model/", validators=[resim_dogrulayici], blank=True)
    aktif = models.BooleanField(default=True)
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["seri__sira", "kod"]
        verbose_name = "katalog modeli"
        verbose_name_plural = "katalog modelleri"

    def __str__(self):
        return f"{self.kod} ({self.seri})"


class LazerDeseni(models.Model):
    kod = models.CharField("desen kodu", max_length=20, unique=True, help_text="Ör. DB001")
    resim = models.FileField(upload_to="katalog/desen/", validators=[resim_dogrulayici], blank=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["kod"]
        verbose_name = "lazer deseni"
        verbose_name_plural = "lazer desenleri"

    def __str__(self):
        return self.kod


# --- Hammadde ve sipariş ------------------------------------------------------


AYAK_M2 = Decimal("0.09290304")  # 1 ayak kare (ft²) = 0,0929 m²


def sayi_metni(sayi):
    """12.50 → '12,5', 120.00 → '120'."""
    return format(sayi.normalize(), "f").replace(".", ",")


def m2_hesapla(birim, miktar, en_cm=None):
    """Gelen miktarı m²'ye çevirir: m² olduğu gibi, metretül × en, ayak × 0,0929."""
    if miktar is None:
        return None
    if birim == "mtul":
        if not en_cm:
            return None
        sonuc = miktar * en_cm / 100
    elif birim == "ayak":
        sonuc = miktar * AYAK_M2
    else:
        sonuc = miktar
    return sonuc.quantize(Decimal("0.01"))


class HamDeriGirisi(models.Model):
    KALITE = [("A", "A"), ("B", "B"), ("C", "C"), ("K", "Karışık")]
    GIRIS_BIRIMLERI = [("m2", "m²"), ("mtul", "metretül"), ("ayak", "ayak (ft²)")]

    lot_no = models.CharField("stok lot no", max_length=20, unique=True, blank=True)
    tarih = models.DateField(default=timezone.localdate)
    tedarikci = models.ForeignKey(Tedarikci, on_delete=models.PROTECT, verbose_name="tedarikçi")
    deri_turu = models.ForeignKey(DeriTuru, on_delete=models.PROTECT, verbose_name="malzeme türü")
    renk = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=60, blank=True, help_text="Desen / model adı ya da kodu")
    kalite = models.CharField(max_length=1, choices=KALITE, default="K")
    adet = models.PositiveIntegerField(null=True, blank=True)
    kg = models.DecimalField(max_digits=10, decimal_places=2, validators=pozitif)
    m2 = models.DecimalField("m²", max_digits=10, decimal_places=2, validators=pozitif)
    giris_birimi = models.CharField("giriş birimi", max_length=4, choices=GIRIS_BIRIMLERI, default="m2")
    giris_miktari = models.DecimalField("gelen miktar", max_digits=10, decimal_places=2, null=True, blank=True,
                                        validators=pozitif, help_text="Giriş biriminde gelen miktar.")
    en_cm = models.DecimalField("rulo eni (cm)", max_digits=7, decimal_places=1, null=True, blank=True,
                                validators=pozitif, help_text="Metretül girişinde m² hesabı için.")
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["-tarih", "-lot_no"]
        verbose_name = "stok lotu (ana malzeme)"
        verbose_name_plural = "stok lotları (ana malzeme)"

    def __str__(self):
        return f"{self.lot_no} – {self.tedarikci} ({self.deri_turu})"

    def save(self, *args, **kwargs):
        if not self.lot_no:
            self.lot_no = sonraki_numara(HamDeriGirisi, "lot_no", "HD")
        super().save(*args, **kwargs)

    @property
    def cesit_metni(self):
        """Ör. 'Süet · Bej · Mermer desen'."""
        return " · ".join(p for p in (str(self.deri_turu), self.renk, self.model) if p)

    @property
    def giris_metni(self):
        """Ör. '120 ayak' ya da '50 metretül × 140 cm'. m² girişinde boş."""
        if self.giris_birimi == "m2" or self.giris_miktari is None:
            return ""
        metin = f"{sayi_metni(self.giris_miktari)} {self.get_giris_birimi_display()}"
        if self.giris_birimi == "mtul" and self.en_cm:
            metin += f" × {sayi_metni(self.en_cm)} cm"
        return metin

    @property
    def kullanilan_kg(self):
        return self.cikislar.aggregate(t=models.Sum("kg"))["t"] or SIFIR

    @property
    def kullanilan_m2(self):
        return self.cikislar.aggregate(t=models.Sum("m2"))["t"] or SIFIR

    @property
    def duzeltme_kg(self):
        return self.duzeltmeler.aggregate(t=models.Sum("kg"))["t"] or SIFIR

    @property
    def duzeltme_m2(self):
        return self.duzeltmeler.aggregate(t=models.Sum("m2"))["t"] or SIFIR

    @property
    def kalan_kg(self):
        return self.kg - self.kullanilan_kg + self.duzeltme_kg

    @property
    def kalan_m2(self):
        return self.m2 - self.kullanilan_m2 + self.duzeltme_m2

    def aktif_isler(self):
        """Bu stok lotundan malzeme almış, bitmemiş işler."""
        return (
            UretimLotu.objects.filter(kaynaklar__ham_deri=self)
            .exclude(durum__in=["tamamlandi", "iptal"])
            .select_related("siparis__musteri", "son_asama")
            .distinct()
            .order_by("olusturma")
        )


class Siparis(models.Model):
    DURUM = [
        ("acik", "Açık"),
        ("uretimde", "Üretimde"),
        ("tamamlandi", "Tamamlandı"),
        ("sevk", "Sevk edildi"),
        ("iptal", "İptal"),
    ]

    siparis_no = models.CharField("sipariş no", max_length=20, unique=True, blank=True)
    musteri = models.ForeignKey(Musteri, on_delete=models.PROTECT, verbose_name="müşteri")
    tarih = models.DateField(default=timezone.localdate)
    olusturma = models.DateTimeField("kayıt zamanı", default=timezone.now, editable=False)
    hali_turu = models.ForeignKey(
        HaliTuru, on_delete=models.PROTECT, null=True, blank=True, verbose_name="halı türü",
        help_text="İşin hangi istasyonlardan geçeceğini belirler.",
    )
    katalog_modeli = models.ForeignKey(KatalogModeli, on_delete=models.PROTECT, null=True, blank=True,
                                       verbose_name="katalog modeli")
    lazer_deseni = models.ForeignKey(LazerDeseni, on_delete=models.PROTECT, null=True, blank=True,
                                     verbose_name="lazer deseni")
    urun = models.CharField("ürün açıklaması", max_length=200, help_text="Örn: 200x300 krem kuzu patchwork halı")
    deri_turu = models.ForeignKey(DeriTuru, on_delete=models.PROTECT, null=True, blank=True, verbose_name="deri türü")
    adet = models.PositiveIntegerField(default=1)
    toplam_m2 = models.DecimalField("toplam m²", max_digits=10, decimal_places=2, null=True, blank=True)
    teslim_tarihi = models.DateField("teslim tarihi")
    durum = models.CharField(max_length=12, choices=DURUM, default="acik")
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["teslim_tarihi"]
        verbose_name = "sipariş"
        verbose_name_plural = "siparişler"

    def __str__(self):
        return f"{self.siparis_no} – {self.musteri}"

    def save(self, *args, **kwargs):
        if not self.siparis_no:
            self.siparis_no = sonraki_numara(Siparis, "siparis_no", "SP")
        super().save(*args, **kwargs)

    def ilk_asamalar(self):
        return sonraki_asamalar(rota_adimlari(self.hali_turu_id), None)

    @property
    def gecikti_mi(self):
        return self.durum in ("acik", "uretimde") and self.teslim_tarihi < timezone.localdate()

    @property
    def kalan_gun(self):
        return (self.teslim_tarihi - timezone.localdate()).days

    @property
    def gecikme_gun(self):
        return max(0, -self.kalan_gun)

    def ilerleme(self):
        """Siparişin üretim durumu: tamamlanma yüzdesi ve lotların aşamalara dağılımı.

        Toplam m² girilmişse yüzde, biten lotların m²'sine göre; girilmemişse biten lot sayısına göre
        hesaplanır. İptal edilen lotlar sayılmaz.
        """
        lotlar = [lot for lot in self.lotlar.all() if lot.durum != "iptal"]
        biten = [lot for lot in lotlar if lot.durum == "tamamlandi"]
        uretilen_m2 = sum((lot.mevcut_m2 or SIFIR for lot in biten), SIFIR)
        if self.toplam_m2:
            yuzde = min(100, round(uretilen_m2 / self.toplam_m2 * 100))
        elif lotlar:
            yuzde = round(len(biten) / len(lotlar) * 100)
        else:
            yuzde = 0

        dagilim = {}
        for lot in lotlar:
            if lot.durum == "tamamlandi":
                etiket = "Bitti"
            elif lot.son_asama is None:
                etiket = "Başlamadı"
            elif lot.durum == "islemde":
                etiket = lot.son_asama.ad
            else:
                etiket = f"{lot.son_asama.ad} bitti"
            dagilim[etiket] = dagilim.get(etiket, 0) + 1
        return {
            "yuzde": yuzde,
            "lot_sayisi": len(lotlar),
            "biten_lot": len(biten),
            "uretilen_m2": uretilen_m2,
            "dagilim": sorted(dagilim.items(), key=lambda x: x[0] == "Bitti"),
        }


# --- Üretim -------------------------------------------------------------------


class UretimLotu(models.Model):
    DURUM = [
        ("bekliyor", "Sıradaki aşamayı bekliyor"),
        ("islemde", "İşlemde"),
        ("tamamlandi", "Tamamlandı"),
        ("iptal", "İptal"),
    ]

    lot_no = models.CharField("iş no", max_length=20, unique=True, blank=True)
    siparis = models.ForeignKey(
        Siparis, on_delete=models.SET_NULL, null=True, blank=True, related_name="lotlar", verbose_name="sipariş"
    )
    olusturma = models.DateTimeField("oluşturma", default=timezone.now)
    baslangic_kg = models.DecimalField("başlangıç kg", max_digits=10, decimal_places=2, validators=pozitif)
    baslangic_m2 = models.DecimalField("başlangıç m²", max_digits=10, decimal_places=2, validators=pozitif)
    mevcut_kg = models.DecimalField("mevcut kg", max_digits=10, decimal_places=2, blank=True, null=True)
    mevcut_m2 = models.DecimalField("mevcut m²", max_digits=10, decimal_places=2, blank=True, null=True)
    son_asama = models.ForeignKey(
        Asama, on_delete=models.PROTECT, null=True, blank=True, verbose_name="son aşama",
        help_text="Lotun en son işlem gördüğü aşama.",
    )
    durum = models.CharField(max_length=12, choices=DURUM, default="bekliyor")
    eski_stok_turu = models.ForeignKey(
        DeriTuru, on_delete=models.PROTECT, null=True, blank=True, verbose_name="etiketsiz eski stok türü",
        help_text="Geçiş döneminde stok etiketi olmadan, eski stoktan başlatılan işlerde.",
    )
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["-olusturma"]
        verbose_name = "iş"
        verbose_name_plural = "işler"

    def __str__(self):
        return self.lot_no

    def save(self, *args, **kwargs):
        if not self.lot_no:
            self.lot_no = sonraki_numara(UretimLotu, "lot_no", "IS")
        if self.mevcut_kg is None:
            self.mevcut_kg = self.baslangic_kg
        if self.mevcut_m2 is None:
            self.mevcut_m2 = self.baslangic_m2
        super().save(*args, **kwargs)
        # Tamamlanmış bir siparişe bitmemiş lot eklenirse sipariş yeniden üretime döner.
        if self.siparis_id and self.durum not in ("tamamlandi", "iptal"):
            Siparis.objects.filter(pk=self.siparis_id, durum="tamamlandi").update(durum="uretimde")

    @property
    def kaynak_listesi(self):
        """Malzemenin alındığı stok lotları, ör. 'HD-2026-0001, HD-2026-0004'; etiketsiz eski stok da yazılır."""
        parcalar = [k.ham_deri.lot_no for k in self.kaynaklar.all()]
        if self.eski_stok_turu_id:
            parcalar.append(f"Eski stok ({self.eski_stok_turu})")
        return ", ".join(parcalar)

    def asama_sonrasi(self, asama):
        """Bu iş için verilen istasyondan sonra gelecek istasyon(lar); boş liste: iş biter."""
        hali_turu_id = self.siparis.hali_turu_id if self.siparis_id else None
        return sonraki_asamalar(rota_adimlari(hali_turu_id), asama)

    @property
    def siradaki_asamalar(self):
        if self.durum in ("tamamlandi", "iptal"):
            return []
        return self.asama_sonrasi(self.son_asama)

    @property
    def siradaki_asama(self):
        sonrakiler = self.siradaki_asamalar
        return sonrakiler[0] if sonrakiler else None

    @property
    def siradaki_metni(self):
        return " / ".join(a.ad for a in self.siradaki_asamalar)

    @property
    def acik_islem(self):
        return self.islemler.filter(bitis__isnull=True).first()

    @property
    def toplam_fire_kg(self):
        return self.baslangic_kg - (self.mevcut_kg or SIFIR)

    @property
    def toplam_fire_m2(self):
        return self.baslangic_m2 - (self.mevcut_m2 or SIFIR)


class LotKaynagi(models.Model):
    """Bir işe hangi stok lotundan ne kadar malzeme alındığı."""

    uretim_lotu = models.ForeignKey(UretimLotu, on_delete=models.CASCADE, related_name="kaynaklar", verbose_name="iş")
    ham_deri = models.ForeignKey(
        HamDeriGirisi, on_delete=models.PROTECT, related_name="cikislar", verbose_name="stok lotu"
    )
    kg = models.DecimalField(max_digits=10, decimal_places=2, validators=pozitif)
    m2 = models.DecimalField("m²", max_digits=10, decimal_places=2, validators=pozitif)
    tarih = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["tarih"]
        verbose_name = "malzeme çıkışı"
        verbose_name_plural = "malzeme çıkışları"
        constraints = [models.UniqueConstraint(fields=["uretim_lotu", "ham_deri"], name="is_basina_stok_lotu_tek")]

    def __str__(self):
        return f"{self.ham_deri.lot_no} → {self.uretim_lotu.lot_no}"


class IslemKaydi(models.Model):
    lot = models.ForeignKey(UretimLotu, on_delete=models.CASCADE, related_name="islemler")
    asama = models.ForeignKey(Asama, on_delete=models.PROTECT, verbose_name="aşama")
    makine = models.ForeignKey(Makine, on_delete=models.PROTECT, null=True, blank=True, related_name="islemler")
    personel = models.ForeignKey(Personel, on_delete=models.PROTECT, related_name="islemler")
    bitiren = models.ForeignKey(
        Personel, on_delete=models.PROTECT, null=True, blank=True, related_name="bitirdigi_islemler",
        verbose_name="bitiren personel",
    )
    baslangic = models.DateTimeField("başlangıç", default=timezone.now)
    bitis = models.DateTimeField("bitiş", null=True, blank=True)
    giris_kg = models.DecimalField("giriş kg", max_digits=10, decimal_places=2, validators=pozitif)
    giris_m2 = models.DecimalField("giriş m²", max_digits=10, decimal_places=2, validators=pozitif)
    cikis_kg = models.DecimalField("çıkış kg", max_digits=10, decimal_places=2, null=True, blank=True, validators=pozitif)
    cikis_m2 = models.DecimalField("çıkış m²", max_digits=10, decimal_places=2, null=True, blank=True, validators=pozitif)
    aciklama = models.TextField("açıklama", blank=True)

    class Meta:
        ordering = ["-baslangic"]
        verbose_name = "işlem kaydı"
        verbose_name_plural = "işlem kayıtları"
        constraints = [
            models.UniqueConstraint(
                fields=["lot"], condition=models.Q(bitis__isnull=True), name="lot_basina_tek_acik_islem"
            )
        ]

    def __str__(self):
        return f"{self.lot} / {self.asama.ad} / {self.personel}"

    @property
    def tamamlandi(self):
        return self.bitis is not None

    @property
    def fire_kg(self):
        return None if self.cikis_kg is None else self.giris_kg - self.cikis_kg

    @property
    def fire_m2(self):
        return None if self.cikis_m2 is None else self.giris_m2 - self.cikis_m2

    @property
    def fire_yuzde_m2(self):
        if self.fire_m2 is None or not self.giris_m2:
            return None
        return round(self.fire_m2 / self.giris_m2 * 100, 1)

    @property
    def sure(self):
        return (self.bitis or timezone.now()) - self.baslangic


# --- Stok düzeltme ve malzemeler ----------------------------------------------


NEDENLER = [
    ("sayim", "Sayım farkı"),
    ("fire", "Fire / bozulma"),
    ("iade", "Tedarikçiye iade"),
    ("diger", "Diğer"),
]


class FasonIsi(models.Model):
    """Fasoncuya preslenmeye giden malzemeler (ör. Keçe + Süet + Rona → 3'lü lamine).

    Gönderilen miktarlar stoktan "fasona gönderildi" düzeltmesiyle düşer; teslim alınınca yeni bir stok lotu açılır.
    """

    DURUMLAR = [("fasonda", "Fasonda"), ("teslim", "Teslim alındı"), ("iptal", "İptal")]

    no = models.CharField("fason no", max_length=20, unique=True, blank=True)
    fasoncu = models.ForeignKey(Tedarikci, on_delete=models.PROTECT, related_name="fason_isleri")
    hedef_tur = models.ForeignKey(DeriTuru, on_delete=models.PROTECT, verbose_name="yapılacak malzeme",
                                  limit_choices_to={"bilesik": True})
    durum = models.CharField(max_length=8, choices=DURUMLAR, default="fasonda")
    gonderim = models.DateTimeField("gönderim", default=timezone.now)
    teslim = models.DateTimeField("teslim", null=True, blank=True)
    gelen_lot = models.OneToOneField(HamDeriGirisi, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="fason_kaynagi", verbose_name="gelen stok lotu")
    notlar = models.TextField(blank=True)
    kullanici = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="gönderen")

    class Meta:
        ordering = ["-gonderim"]
        verbose_name = "fason işi"
        verbose_name_plural = "fason işleri"

    def __str__(self):
        return f"{self.no} – {self.fasoncu} ({self.hedef_tur})"

    def save(self, *args, **kwargs):
        if not self.no:
            self.no = sonraki_numara(FasonIsi, "no", "FS")
        super().save(*args, **kwargs)

    def gidenler(self):
        """Gönderilen stok lotları ve miktarları (stoktan düşülen pozitif değerlerle)."""
        return [(d.ham_deri, -d.kg, -d.m2) for d in self.gonderimler.select_related("ham_deri__deri_turu")]

    @property
    def giden_kg(self):
        return -(self.gonderimler.aggregate(t=models.Sum("kg"))["t"] or SIFIR)

    @property
    def katman_m2(self):
        """Katman başına ortalama giden m²: üç katman 10'ar m² ise 10 m² lamine beklenir."""
        turler = {}
        for lot, _, m2 in self.gidenler():
            turler[lot.deri_turu_id] = turler.get(lot.deri_turu_id, SIFIR) + m2
        if not turler:
            return SIFIR
        return (sum(turler.values(), SIFIR) / len(turler)).quantize(Decimal("0.01"))

    @property
    def fire_m2(self):
        if self.gelen_lot is None:
            return None
        return self.katman_m2 - self.gelen_lot.m2

    @property
    def fire_yuzde(self):
        if self.fire_m2 is None or not self.katman_m2:
            return None
        return round(self.fire_m2 / self.katman_m2 * 100, 1)


class DeriDuzeltme(models.Model):
    """Stok lotunun kalan miktarına elle yapılan düzeltme. Eksi: stoktan düşer, artı: stoğa eklenir."""

    ham_deri = models.ForeignKey(HamDeriGirisi, on_delete=models.CASCADE, related_name="duzeltmeler",
                                 verbose_name="stok lotu")
    neden = models.CharField(max_length=10, choices=NEDENLER + [("fason", "Fasona gönderildi")])
    fason = models.ForeignKey(FasonIsi, on_delete=models.CASCADE, null=True, blank=True, related_name="gonderimler",
                              verbose_name="fason işi")
    kg = models.DecimalField(max_digits=10, decimal_places=2, default=SIFIR)
    m2 = models.DecimalField("m²", max_digits=10, decimal_places=2, default=SIFIR)
    aciklama = models.CharField("açıklama", max_length=200, blank=True)
    kullanici = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="giren")
    tarih = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-tarih"]
        verbose_name = "deri stok düzeltmesi"
        verbose_name_plural = "deri stok düzeltmeleri"

    def __str__(self):
        return f"{self.ham_deri.lot_no} {self.get_neden_display()} {self.kg} kg / {self.m2} m²"


class Malzeme(models.Model):
    """Deri dışındaki sarf malzemeleri: kimyasal, iplik, astar, yapıştırıcı…"""

    BIRIMLER = [("kg", "kg"), ("lt", "litre"), ("m", "metre"), ("m2", "m²"), ("adet", "adet"), ("makara", "makara")]
    KATEGORILER = [("kimyasal", "Kimyasal"), ("iplik", "İplik"), ("astar", "Astar / taban"),
                   ("yapistirici", "Yapıştırıcı"), ("ambalaj", "Ambalaj"), ("diger", "Diğer")]

    kod = models.CharField(max_length=20, unique=True, blank=True, help_text="Etiketteki kod; boşsa otomatik verilir.")
    ad = models.CharField(max_length=100, unique=True)
    kategori = models.CharField(max_length=12, choices=KATEGORILER, default="diger")
    birim = models.CharField(max_length=6, choices=BIRIMLER, default="kg")
    min_stok = models.DecimalField("en az stok", max_digits=10, decimal_places=2, null=True, blank=True,
                                   help_text="Stok bunun altına düşünce uyarı verilir.")
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["kategori", "ad"]
        verbose_name = "malzeme"
        verbose_name_plural = "malzemeler"

    def __str__(self):
        return f"{self.ad} ({self.get_birim_display()})"

    def save(self, *args, **kwargs):
        if not self.kod:
            self.kod = malzeme_kodu_uret()
        self.kod = self.kod.upper()
        super().save(*args, **kwargs)

    @property
    def lot_no(self):
        """Etiket ve QR adresi için (stok lotlarıyla aynı arayüz)."""
        return self.kod

    @property
    def stok(self):
        return self.hareketler.aggregate(t=models.Sum("miktar"))["t"] or SIFIR

    @property
    def azaldi_mi(self):
        return self.min_stok is not None and self.stok < self.min_stok


def malzeme_kodu_uret():
    son = Malzeme.objects.filter(kod__startswith="MZ-").order_by("-kod").values_list("kod", flat=True).first()
    sira = int(son.split("-")[1]) + 1 if son and son.split("-")[1].isdigit() else 1
    return f"MZ-{sira:04d}"


class MalzemeHareketi(models.Model):
    """Malzeme stoğundaki her değişiklik. Miktar işaretlidir: giriş artı, kullanım/fire eksi."""

    TURLER = [("giris", "Giriş"), ("kullanim", "Üretimde kullanım"), *NEDENLER]

    malzeme = models.ForeignKey(Malzeme, on_delete=models.PROTECT, related_name="hareketler")
    tur = models.CharField("tür", max_length=10, choices=TURLER)
    miktar = models.DecimalField(max_digits=10, decimal_places=2)
    islem = models.ForeignKey("IslemKaydi", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="malzeme_kullanimlari", verbose_name="işlem")
    personel = models.ForeignKey(Personel, on_delete=models.SET_NULL, null=True, blank=True)
    kullanici = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="giren")
    tedarikci = models.ForeignKey(Tedarikci, on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="tedarikçi")
    aciklama = models.CharField("açıklama", max_length=200, blank=True)
    tarih = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-tarih"]
        verbose_name = "malzeme hareketi"
        verbose_name_plural = "malzeme hareketleri"

    def __str__(self):
        return f"{self.malzeme.ad} {self.get_tur_display()} {self.miktar}"


# --- Tablet / oturum kayıtları ------------------------------------------------


class OturumKaydi(models.Model):
    """Hangi hesap ne zaman giriş yaptı, çıktı ya da hangi istasyon ekranını açtı."""

    TURLER = [("giris", "Giriş yaptı"), ("cikis", "Çıkış yaptı"), ("istasyon", "İstasyon ekranını açtı")]

    kullanici = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, verbose_name="hesap")
    kullanici_adi = models.CharField("hesap adı", max_length=150, blank=True)
    tur = models.CharField("olay", max_length=10, choices=TURLER)
    asama = models.ForeignKey(Asama, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="istasyon")
    cihaz = models.CharField(max_length=60, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    zaman = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-zaman"]
        verbose_name = "tablet / oturum kaydı"
        verbose_name_plural = "tablet / oturum kayıtları"

    def __str__(self):
        return f"{self.kullanici_adi} {self.get_tur_display()} {self.zaman:%d.%m.%Y %H:%M}"


class HesapAyari(models.Model):
    """Giriş hesabına bağlı ayar: istasyon tableti hangi istasyonun ekranını açar."""

    kullanici = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="hesap_ayari")
    istasyon = models.ForeignKey(Asama, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="istasyon")
    musteri = models.ForeignKey(Musteri, on_delete=models.PROTECT, null=True, blank=True, related_name="bayi_hesaplari",
                                verbose_name="bayi (müşteri)",
                                help_text="Bayi hesabı: yalnızca tasarım stüdyosu ve kendi siparişleri.")

    class Meta:
        verbose_name = "hesap ayarı"
        verbose_name_plural = "hesap ayarları"

    def __str__(self):
        return f"{self.kullanici} → {self.istasyon or '-'}"


def hesap_istasyonu(kullanici):
    """Hesaba bağlı (aktif) istasyon; yoksa None."""
    if not getattr(kullanici, "is_authenticated", False):
        return None
    ayar = HesapAyari.objects.filter(kullanici=kullanici, istasyon__aktif=True).select_related("istasyon").first()
    return ayar.istasyon if ayar else None


def hesap_bayisi(kullanici):
    """Bayi hesabının bağlı olduğu müşteri; bayi değilse None."""
    if not getattr(kullanici, "is_authenticated", False) or kullanici.is_staff:
        return None
    ayar = HesapAyari.objects.filter(kullanici=kullanici, musteri__isnull=False).select_related("musteri").first()
    return ayar.musteri if ayar else None


class Tasarim(models.Model):
    """Bayinin tasarım stüdyosunda hazırladığı halı. Ofis onaylayınca siparişe dönüşür."""

    DURUMLAR = [("gonderildi", "Onay bekliyor"), ("onaylandi", "Onaylandı"), ("reddedildi", "Reddedildi")]

    no = models.CharField("tasarım no", max_length=20, unique=True, blank=True)
    musteri = models.ForeignKey(Musteri, on_delete=models.PROTECT, related_name="tasarimlar", verbose_name="bayi")
    kullanici = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    olusturma = models.DateTimeField(default=timezone.now)
    durum = models.CharField(max_length=10, choices=DURUMLAR, default="gonderildi")
    veri = models.JSONField("tasarım", default=dict)
    adet = models.PositiveIntegerField(default=1)
    istenen_tarih = models.DateField("istenen teslim", null=True, blank=True)
    notlar = models.TextField("bayinin notu", blank=True)
    ofis_notu = models.TextField("ofisin notu", blank=True)
    siparis = models.OneToOneField(Siparis, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasarim")

    class Meta:
        ordering = ["-olusturma"]
        verbose_name = "tasarım"
        verbose_name_plural = "tasarımlar"

    def __str__(self):
        return f"{self.no} – {self.musteri}"

    def save(self, *args, **kwargs):
        if not self.no:
            self.no = sonraki_numara(Tasarim, "no", "TS")
        super().save(*args, **kwargs)

    @property
    def ozet(self):
        from .tasarim_cizim import ozet
        return ozet(self.veri)


class SistemAyari(models.Model):
    """Tek satırlık genel ayarlar (yönetici değiştirir)."""

    gecis_modu = models.BooleanField(
        "geçiş dönemi", default=False,
        help_text="Açıkken yeni iş, stok etiketi olmadan 'eski stoktan' başlatılabilir; stoktan düşülmez.",
    )

    class Meta:
        verbose_name = "sistem ayarı"
        verbose_name_plural = "sistem ayarları"

    def __str__(self):
        return "Sistem ayarları"

    @classmethod
    def yukle(cls):
        ayar, _ = cls.objects.get_or_create(pk=1)
        return ayar
