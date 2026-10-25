from django import forms
from django.core.exceptions import ValidationError

from .models import Asama, Musteri, Personel, Siparis, UretimLotu, pin_dogrulayici


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


class IslemBaslatForm(PinliForm):
    lot = forms.ModelChoiceField(
        queryset=UretimLotu.objects.filter(durum="bekliyor"), label="Lot", empty_label="— Lot seçin —"
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
