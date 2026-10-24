from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MinValueValidator, RegexValidator
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
    ad = models.CharField("aşama adı", max_length=60, unique=True)
    sira = models.PositiveSmallIntegerField("sıra", unique=True)
    aktif = models.BooleanField(default=True)

    class Meta:
        ordering = ["sira"]
        verbose_name = "aşama"
        verbose_name_plural = "aşamalar"

    def __str__(self):
        return f"{self.sira}. {self.ad}"

    def sonraki(self):
        return Asama.objects.filter(aktif=True, sira__gt=self.sira).first()

    @property
    def son_asama_mi(self):
        return self.sonraki() is None


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
    ad = models.CharField(max_length=60, unique=True)

    class Meta:
        ordering = ["ad"]
        verbose_name = "deri türü"
        verbose_name_plural = "deri türleri"

    def __str__(self):
        return self.ad


# --- Hammadde ve sipariş ------------------------------------------------------


class HamDeriGirisi(models.Model):
    KALITE = [("A", "A"), ("B", "B"), ("C", "C"), ("K", "Karışık")]

    lot_no = models.CharField("ham deri lot no", max_length=20, unique=True, blank=True)
    tarih = models.DateField(default=timezone.localdate)
    tedarikci = models.ForeignKey(Tedarikci, on_delete=models.PROTECT, verbose_name="tedarikçi")
    deri_turu = models.ForeignKey(DeriTuru, on_delete=models.PROTECT, verbose_name="deri türü")
    kalite = models.CharField(max_length=1, choices=KALITE, default="K")
    adet = models.PositiveIntegerField(null=True, blank=True)
    kg = models.DecimalField(max_digits=10, decimal_places=2, validators=pozitif)
    m2 = models.DecimalField("m²", max_digits=10, decimal_places=2, validators=pozitif)
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["-tarih", "-lot_no"]
        verbose_name = "ham deri girişi"
        verbose_name_plural = "ham deri girişleri"

    def __str__(self):
        return f"{self.lot_no} – {self.tedarikci} ({self.deri_turu})"

    def save(self, *args, **kwargs):
        if not self.lot_no:
            self.lot_no = sonraki_numara(HamDeriGirisi, "lot_no", "HD")
        super().save(*args, **kwargs)

    @property
    def kullanilan_kg(self):
        return self.uretim_lotlari.aggregate(t=models.Sum("baslangic_kg"))["t"] or SIFIR

    @property
    def kullanilan_m2(self):
        return self.uretim_lotlari.aggregate(t=models.Sum("baslangic_m2"))["t"] or SIFIR

    @property
    def kalan_kg(self):
        return self.kg - self.kullanilan_kg

    @property
    def kalan_m2(self):
        return self.m2 - self.kullanilan_m2


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

    @property
    def gecikti_mi(self):
        return self.durum in ("acik", "uretimde") and self.teslim_tarihi < timezone.localdate()


# --- Üretim -------------------------------------------------------------------


class UretimLotu(models.Model):
    DURUM = [
        ("bekliyor", "Sıradaki aşamayı bekliyor"),
        ("islemde", "İşlemde"),
        ("tamamlandi", "Tamamlandı"),
        ("iptal", "İptal"),
    ]

    lot_no = models.CharField("lot no", max_length=20, unique=True, blank=True)
    ham_deri = models.ForeignKey(
        HamDeriGirisi, on_delete=models.PROTECT, related_name="uretim_lotlari", verbose_name="ham deri lotu"
    )
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
    notlar = models.TextField(blank=True)

    class Meta:
        ordering = ["-olusturma"]
        verbose_name = "üretim lotu"
        verbose_name_plural = "üretim lotları"

    def __str__(self):
        return self.lot_no

    def save(self, *args, **kwargs):
        if not self.lot_no:
            self.lot_no = sonraki_numara(UretimLotu, "lot_no", "UL")
        if self.mevcut_kg is None:
            self.mevcut_kg = self.baslangic_kg
        if self.mevcut_m2 is None:
            self.mevcut_m2 = self.baslangic_m2
        super().save(*args, **kwargs)

    @property
    def siradaki_asama(self):
        if self.durum in ("tamamlandi", "iptal"):
            return None
        if self.son_asama is None:
            return Asama.objects.filter(aktif=True).first()
        return self.son_asama.sonraki()

    @property
    def acik_islem(self):
        return self.islemler.filter(bitis__isnull=True).first()

    @property
    def toplam_fire_kg(self):
        return self.baslangic_kg - (self.mevcut_kg or SIFIR)

    @property
    def toplam_fire_m2(self):
        return self.baslangic_m2 - (self.mevcut_m2 or SIFIR)


class IslemKaydi(models.Model):
    lot = models.ForeignKey(UretimLotu, on_delete=models.CASCADE, related_name="islemler")
    asama = models.ForeignKey(Asama, on_delete=models.PROTECT, verbose_name="aşama")
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
