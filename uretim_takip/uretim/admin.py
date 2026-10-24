from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Asama, DeriTuru, HamDeriGirisi, IslemKaydi, Musteri, Personel, Siparis, Tedarikci, UretimLotu,
    pin_dogrulayici,
)

admin.site.site_header = "Üretim Takip – Yönetim"
admin.site.site_title = "Üretim Takip"
admin.site.index_title = "Tanımlar ve kayıtlar"


@admin.register(Asama)
class AsamaAdmin(admin.ModelAdmin):
    list_display = ["sira", "ad", "aktif"]
    list_editable = ["ad", "aktif"]
    list_display_links = ["sira"]


class PersonelForm(forms.ModelForm):
    yeni_pin = forms.CharField(
        label="Yeni PIN", required=False, validators=[pin_dogrulayici],
        help_text="4-6 haneli rakam. Değiştirmek istemiyorsanız boş bırakın.",
    )

    class Meta:
        model = Personel
        fields = ["ad_soyad", "gorev", "aktif"]

    def clean(self):
        veri = super().clean()
        if not self.instance.pk and not veri.get("yeni_pin"):
            self.add_error("yeni_pin", "Yeni personel için PIN zorunlu.")
        return veri

    def save(self, commit=True):
        personel = super().save(commit=False)
        if self.cleaned_data.get("yeni_pin"):
            personel.pin_ayarla(self.cleaned_data["yeni_pin"])
        if commit:
            personel.save()
        return personel


@admin.register(Personel)
class PersonelAdmin(admin.ModelAdmin):
    form = PersonelForm
    list_display = ["ad_soyad", "gorev", "aktif"]
    list_filter = ["aktif"]
    search_fields = ["ad_soyad"]


admin.site.register([Tedarikci, Musteri, DeriTuru], admin.ModelAdmin)


@admin.register(HamDeriGirisi)
class HamDeriGirisiAdmin(admin.ModelAdmin):
    list_display = ["lot_no", "tarih", "tedarikci", "deri_turu", "kalite", "adet", "kg", "m2", "kalan_kg", "kalan_m2"]
    list_filter = ["tedarikci", "deri_turu", "kalite"]
    search_fields = ["lot_no"]
    date_hierarchy = "tarih"
    readonly_fields = ["lot_no"]

    @admin.display(description="kalan kg")
    def kalan_kg(self, obj):
        return obj.kalan_kg

    @admin.display(description="kalan m²")
    def kalan_m2(self, obj):
        return obj.kalan_m2


class LotInline(admin.TabularInline):
    model = UretimLotu
    fields = ["lot_no", "ham_deri", "baslangic_kg", "baslangic_m2", "durum"]
    readonly_fields = ["lot_no", "durum"]
    extra = 0
    show_change_link = True


@admin.register(Siparis)
class SiparisAdmin(admin.ModelAdmin):
    list_display = ["siparis_no", "musteri", "urun", "adet", "toplam_m2", "teslim_tarihi", "durum", "gecikme"]
    list_filter = ["durum", "musteri"]
    search_fields = ["siparis_no", "urun", "musteri__ad"]
    readonly_fields = ["siparis_no"]
    inlines = [LotInline]

    @admin.display(description="gecikme")
    def gecikme(self, obj):
        return format_html('<b style="color:#c0392b">GECİKTİ</b>') if obj.gecikti_mi else ""


class IslemInline(admin.TabularInline):
    model = IslemKaydi
    fk_name = "lot"
    fields = ["asama", "personel", "baslangic", "bitis", "giris_kg", "cikis_kg", "giris_m2", "cikis_m2", "bitiren"]
    extra = 0
    can_delete = False


class UretimLotuForm(forms.ModelForm):
    class Meta:
        model = UretimLotu
        fields = "__all__"

    def clean(self):
        veri = super().clean()
        ham = veri.get("ham_deri")
        if ham and veri.get("baslangic_kg") is not None and veri.get("baslangic_m2") is not None:
            onceki_kg = onceki_m2 = 0
            if self.instance.pk and self.instance.ham_deri_id == ham.pk:
                onceki_kg, onceki_m2 = self.instance.baslangic_kg, self.instance.baslangic_m2
            if veri["baslangic_kg"] > ham.kalan_kg + onceki_kg:
                self.add_error("baslangic_kg", f"Ham deri lotunda kalan: {ham.kalan_kg + onceki_kg} kg")
            if veri["baslangic_m2"] > ham.kalan_m2 + onceki_m2:
                self.add_error("baslangic_m2", f"Ham deri lotunda kalan: {ham.kalan_m2 + onceki_m2} m²")
        return veri


@admin.register(UretimLotu)
class UretimLotuAdmin(admin.ModelAdmin):
    form = UretimLotuForm
    list_display = ["lot_no", "ham_deri", "siparis", "son_asama", "durum", "baslangic_m2", "mevcut_m2"]
    list_filter = ["durum", "son_asama"]
    search_fields = ["lot_no", "ham_deri__lot_no", "siparis__siparis_no"]
    readonly_fields = ["lot_no"]
    autocomplete_fields = ["ham_deri", "siparis"]
    inlines = [IslemInline]


@admin.register(IslemKaydi)
class IslemKaydiAdmin(admin.ModelAdmin):
    list_display = ["lot", "asama", "personel", "baslangic", "bitis", "giris_m2", "cikis_m2", "bitiren"]
    list_filter = ["asama", "personel"]
    search_fields = ["lot__lot_no", "personel__ad_soyad"]
    date_hierarchy = "baslangic"
