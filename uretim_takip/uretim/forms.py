from django import forms
from django.core.exceptions import ValidationError

from .models import Asama, Personel, UretimLotu, pin_dogrulayici


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
    cikis_kg = forms.DecimalField(label="Çıkış kg", min_value=0, max_digits=10, decimal_places=2)
    cikis_m2 = forms.DecimalField(label="Çıkış m²", min_value=0, max_digits=10, decimal_places=2)
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class TarihAraligiForm(forms.Form):
    baslangic = forms.DateField(label="Başlangıç", widget=forms.DateInput(attrs={"type": "date"}))
    bitis = forms.DateField(label="Bitiş", widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        veri = super().clean()
        if veri.get("baslangic") and veri.get("bitis") and veri["baslangic"] > veri["bitis"]:
            raise ValidationError("Başlangıç tarihi bitişten sonra olamaz.")
        return veri
