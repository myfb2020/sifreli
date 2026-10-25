from django import forms
from django.core.exceptions import ValidationError

from .models import Asama, HamDeriGirisi, Musteri, Personel, Siparis, Tedarikci, UretimLotu, pin_dogrulayici


def ondalik_alan(etiket, **kw):
    """Hem 12,5 hem 12.5 yazımını kabul eden, telefonda sayı klavyesi açan alan."""
    return forms.DecimalField(
        label=etiket, min_value=0, max_digits=10, decimal_places=2, localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}), **kw,
    )


class PinliForm(forms.Form):
    """Ortak tablette çalışanın kendini PIN ile doğrulaması."""

    personel = forms.ModelChoiceField(
        queryset=Personel.objects.filter(aktif=True), label="Adınız", empty_label="— Seçin —"
    )
    pin = forms.CharField(
        label="PIN",
        validators=[pin_dogrulayici],
        widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )

    def clean(self):
        veri = super().clean()
        personel, pin = veri.get("personel"), veri.get("pin")
        if personel and pin and not personel.pin_dogru_mu(pin):
            raise ValidationError("PIN hatalı.")
        return veri


class IsSecimAlani(forms.ModelChoiceField):
    def label_from_instance(self, lot):
        parcalar = [lot.lot_no]
        if lot.siparis:
            parcalar.append(f"{lot.siparis.siparis_no} {lot.siparis.musteri}")
        parcalar.append(f"son: {lot.son_asama.ad}" if lot.son_asama else "başlamadı")
        return " – ".join(parcalar)


class SiparisSecimAlani(forms.ModelChoiceField):
    def label_from_instance(self, s):
        return f"{s.siparis_no} – {s.musteri} – {s.urun} (teslim {s.teslim_tarihi:%d.%m})"


class IslemBaslatForm(PinliForm):
    lot = IsSecimAlani(
        queryset=UretimLotu.objects.filter(durum="bekliyor").select_related("siparis__musteri", "son_asama"),
        label="İş", empty_label="— İş seçin —",
    )
    asama = forms.ModelChoiceField(
        queryset=Asama.objects.filter(aktif=True), label="Aşama", empty_label="— Aşama seçin —"
    )
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    field_order = ["personel", "pin", "lot", "asama", "aciklama"]


class IslemBitirForm(PinliForm):
    cikis_kg = ondalik_alan("Çıkış kg")
    cikis_m2 = ondalik_alan("Çıkış m²")
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class TarihAraligiForm(forms.Form):
    baslangic = forms.DateField(label="Başlangıç", widget=forms.DateInput(attrs={"type": "date"}))
    bitis = forms.DateField(label="Bitiş", widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        veri = super().clean()
        if veri.get("baslangic") and veri.get("bitis") and veri["baslangic"] > veri["bitis"]:
            raise ValidationError("Başlangıç tarihi bitişten sonra olamaz.")
        return veri


class SiparisForm(forms.ModelForm):
    # Müşteri model doğrulamasına girmez: yeni müşteri ancak form geçerliyse save() içinde oluşturulur.
    musteri = forms.ModelChoiceField(
        queryset=Musteri.objects.all(), label="Müşteri", required=False, empty_label="— Müşteri seçin —"
    )
    toplam_m2 = ondalik_alan("Toplam m²", required=False)
    yeni_musteri = forms.CharField(
        label="veya yeni müşteri adı", required=False, max_length=120,
        help_text="Müşteri listede yoksa buraya yazın, otomatik eklenir.",
    )

    class Meta:
        model = Siparis
        fields = ["urun", "deri_turu", "adet", "toplam_m2", "teslim_tarihi", "notlar"]
        widgets = {
            "teslim_tarihi": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notlar": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"notlar": "Not (isteğe bağlı)"}

    field_order = ["musteri", "yeni_musteri", "urun", "deri_turu", "adet", "toplam_m2", "teslim_tarihi", "notlar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deri_turu"].empty_label = "— (isteğe bağlı) —"

    def clean(self):
        veri = super().clean()
        if not (veri.get("yeni_musteri") or "").strip() and not veri.get("musteri"):
            self.add_error("musteri", "Bir müşteri seçin ya da yeni müşteri adı yazın.")
        return veri

    def save(self, commit=True):
        yeni = self.cleaned_data["yeni_musteri"].strip()
        if yeni:
            musteri = Musteri.objects.filter(ad__iexact=yeni).first() or Musteri.objects.create(ad=yeni)
        else:
            musteri = self.cleaned_data["musteri"]
        self.instance.musteri = musteri
        return super().save(commit)


class YeniIsForm(PinliForm):
    siparis = SiparisSecimAlani(
        queryset=Siparis.objects.filter(durum__in=["acik", "uretimde"]).select_related("musteri").order_by("teslim_tarihi"),
        label="Sipariş", empty_label="— Hangi sipariş için? —",
    )
    asama = forms.ModelChoiceField(queryset=Asama.objects.filter(aktif=True), label="Başlanacak aşama")
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    field_order = ["personel", "pin", "siparis", "asama", "aciklama"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asama"].initial = Asama.objects.filter(aktif=True).first()


class KaynakSatirForm(forms.Form):
    """Yeni işe malzeme veren bir stok lotu: QR okutularak ya da elle yazılarak."""

    stok_no = forms.CharField(
        label="Stok lot no", required=False, max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "QR okutun ya da yazın", "autocapitalize": "characters",
                                      "class": "stok-no"}),
    )
    kg = ondalik_alan("Alınan kg", required=False)
    m2 = ondalik_alan("Alınan m²", required=False)

    def clean(self):
        veri = super().clean()
        no = (veri.get("stok_no") or "").strip().upper()
        if not no:
            if veri.get("kg") or veri.get("m2"):
                self.add_error("stok_no", "Stok lot numarasını girin.")
            return veri
        stok = HamDeriGirisi.objects.filter(lot_no=no).first()
        if stok is None:
            self.add_error("stok_no", f"“{no}” numaralı stok lotu bulunamadı.")
        elif not veri.get("kg") and not veri.get("m2"):
            self.add_error("m2", "Alınan miktarı girin.")
        veri["stok"] = stok
        return veri


KaynakFormSet = forms.formset_factory(KaynakSatirForm, extra=4, max_num=10)


class StokGirisForm(forms.ModelForm):
    # Tedarikçi model doğrulamasına girmez: yeni tedarikçi ancak form geçerliyse save() içinde oluşturulur.
    tedarikci = forms.ModelChoiceField(
        queryset=Tedarikci.objects.all(), label="Tedarikçi", required=False, empty_label="— Tedarikçi seçin —"
    )
    yeni_tedarikci = forms.CharField(label="veya yeni tedarikçi adı", required=False, max_length=120)
    kg = ondalik_alan("Kg")
    m2 = ondalik_alan("m²")

    class Meta:
        model = HamDeriGirisi
        fields = ["tarih", "deri_turu", "kalite", "adet", "kg", "m2", "notlar"]
        widgets = {
            "tarih": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notlar": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"notlar": "Not (isteğe bağlı)", "adet": "Adet (isteğe bağlı)"}

    field_order = ["tedarikci", "yeni_tedarikci", "tarih", "deri_turu", "kalite", "adet", "kg", "m2", "notlar"]

    def clean(self):
        veri = super().clean()
        if not (veri.get("yeni_tedarikci") or "").strip() and not veri.get("tedarikci"):
            self.add_error("tedarikci", "Bir tedarikçi seçin ya da yeni tedarikçi adı yazın.")
        return veri

    def save(self, commit=True):
        yeni = self.cleaned_data["yeni_tedarikci"].strip()
        if yeni:
            self.instance.tedarikci = Tedarikci.objects.filter(ad__iexact=yeni).first() or Tedarikci.objects.create(ad=yeni)
        else:
            self.instance.tedarikci = self.cleaned_data["tedarikci"]
        return super().save(commit)
