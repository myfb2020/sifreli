from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Asama, DeriDuzeltme, DeriTuru, HamDeriGirisi, IslemKaydi, LotKaynagi, Malzeme, MalzemeHareketi, Musteri, Personel,
    Siparis, Tedarikci, UretimLotu,
    pin_dogrulayici,
)

admin.site.site_header = "Üretim Takip – Yönetim"
admin.site.site_title = "Üretim Takip"
admin.site.index_title = "Tanımlar ve kayıtlar"


@admin.register(Asama)
class AsamaAdmin(admin.ModelAdmin):
    """Aşamalar = istasyonlar. Süre sınırları listede doğrudan değiştirilebilir."""

    list_display = ["sira", "ad", "azami_bekleme_saat", "azami_sure_saat", "aktif"]
    list_editable = ["ad", "azami_bekleme_saat", "azami_sure_saat", "aktif"]
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


admin.site.register([Tedarikci, Musteri], admin.ModelAdmin)


@admin.register(DeriTuru)
class DeriTuruAdmin(admin.ModelAdmin):
    list_display = ["ad", "min_kg"]
    list_editable = ["min_kg"]


class HareketInline(admin.TabularInline):
    model = MalzemeHareketi
    fields = ["tarih", "tur", "miktar", "islem", "personel", "kullanici", "aciklama"]
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ["-tarih"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Malzeme)
class MalzemeAdmin(admin.ModelAdmin):
    list_display = ["ad", "kategori", "birim", "stok_miktari", "min_stok", "aktif"]
    list_filter = ["kategori", "aktif"]
    list_editable = ["min_stok", "aktif"]
    search_fields = ["ad"]
    inlines = [HareketInline]

    @admin.display(description="stok")
    def stok_miktari(self, obj):
        return obj.stok


@admin.register(MalzemeHareketi)
class MalzemeHareketiAdmin(admin.ModelAdmin):
    list_display = ["tarih", "malzeme", "tur", "miktar", "islem", "personel", "kullanici"]
    list_filter = ["tur", "malzeme"]
    date_hierarchy = "tarih"


@admin.register(DeriDuzeltme)
class DeriDuzeltmeAdmin(admin.ModelAdmin):
    list_display = ["tarih", "ham_deri", "neden", "kg", "m2", "kullanici"]
    list_filter = ["neden"]
    date_hierarchy = "tarih"


class CikisInline(admin.TabularInline):
    """Stok lotunun hangi işlere ne kadar malzeme verdiği (salt okunur)."""

    model = LotKaynagi
    fk_name = "ham_deri"
    fields = ["uretim_lotu", "kg", "m2", "tarih"]
    readonly_fields = fields
    extra = 0
    can_delete = False
    verbose_name_plural = "bu lottan malzeme alan işler"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(HamDeriGirisi)
class HamDeriGirisiAdmin(admin.ModelAdmin):
    list_display = ["lot_no", "tarih", "tedarikci", "deri_turu", "kalite", "adet", "kg", "m2", "kalan_kg", "kalan_m2"]
    list_filter = ["tedarikci", "deri_turu", "kalite"]
    search_fields = ["lot_no"]
    date_hierarchy = "tarih"
    readonly_fields = ["lot_no"]
    inlines = [CikisInline]

    @admin.display(description="kalan kg")
    def kalan_kg(self, obj):
        return obj.kalan_kg

    @admin.display(description="kalan m²")
    def kalan_m2(self, obj):
        return obj.kalan_m2


class LotInline(admin.TabularInline):
    model = UretimLotu
    fields = ["lot_no", "kaynak_listesi", "baslangic_kg", "baslangic_m2", "durum"]
    readonly_fields = ["lot_no", "kaynak_listesi", "baslangic_kg", "baslangic_m2", "durum"]
    extra = 0
    show_change_link = True
    verbose_name_plural = "işler"

    @admin.display(description="stok lotları")
    def kaynak_listesi(self, obj):
        return obj.kaynak_listesi

    def has_add_permission(self, request, obj=None):
        return False


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


class KaynakInline(admin.TabularInline):
    model = LotKaynagi
    fk_name = "uretim_lotu"
    fields = ["ham_deri", "kg", "m2", "tarih"]
    autocomplete_fields = ["ham_deri"]
    extra = 0
    verbose_name_plural = "malzemenin alındığı stok lotları"


@admin.register(UretimLotu)
class UretimLotuAdmin(admin.ModelAdmin):
    """İşler çalışanların 'Yeni iş' ekranında oluşur; burası düzeltme içindir."""

    list_display = ["lot_no", "kaynaklar", "siparis", "son_asama", "durum", "baslangic_m2", "mevcut_m2"]
    list_filter = ["durum", "son_asama"]
    search_fields = ["lot_no", "kaynaklar__ham_deri__lot_no", "siparis__siparis_no"]
    readonly_fields = ["lot_no"]
    autocomplete_fields = ["siparis"]
    inlines = [KaynakInline, IslemInline]

    @admin.display(description="stok lotları")
    def kaynaklar(self, obj):
        return obj.kaynak_listesi

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("kaynaklar__ham_deri")


@admin.register(IslemKaydi)
class IslemKaydiAdmin(admin.ModelAdmin):
    list_display = ["lot", "asama", "personel", "baslangic", "bitis", "giris_m2", "cikis_m2", "bitiren"]
    list_filter = ["asama", "personel"]
    search_fields = ["lot__lot_no", "personel__ad_soyad"]
    date_hierarchy = "baslangic"
