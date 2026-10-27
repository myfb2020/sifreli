"""Hesapları (giriş yapan cihaz/kişi) karmaşık yetki listesi olmadan yönetmek: yalnızca hesap türü seçilir.

- İstasyon tableti: üretim ekranları (personel durumu yok, yetki yok)
- Ofis: siparişler, stok girişi, raporlar ("Ofis" grubu üzerinden yetkiler)
- Yönetici: her şey (süper kullanıcı)
"""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import Group, Permission
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Asama, HesapAyari, hesap_istasyonu
from .yedek import sadece_yonetici

OFIS_GRUBU = "Ofis"
# Ofis hesabının yapabildikleri: (model, işlemler)
OFIS_YETKILERI = {
    "siparis": "add change view",
    "musteri": "add change view",
    "hamderigirisi": "add change view",
    "tedarikci": "add change view",
    "deriduzeltme": "add view",
    "malzeme": "add change view",
    "malzemehareketi": "add view",
    "uretimlotu": "view",
    "islemkaydi": "view",
    "derituru": "view",
    "halituru": "view",
}
TURLER = [("tablet", "İstasyon tableti"), ("ofis", "Ofis"), ("yonetici", "Yönetici")]
TUR_ACIKLAMA = {
    "tablet": "İstasyon ekranı, QR okutma, işlem başlatma/bitirme. Sipariş ve rapor göremez.",
    "ofis": "Sipariş girme, stok/malzeme girişi, raporlar. Hesap ve yedek işlerine giremez.",
    "yonetici": "Her şey: hesaplar, yedek, deneme kayıtlarını silme, ayarlar.",
}


def ofis_grubu():
    """'Ofis' grubunu oluşturur ve yetkilerini günceller (her çağrıda eksik yetki tamamlanır)."""
    grup, _ = Group.objects.get_or_create(name=OFIS_GRUBU)
    kodlar = [f"{islem}_{model}" for model, islemler in OFIS_YETKILERI.items() for islem in islemler.split()]
    grup.permissions.set(Permission.objects.filter(content_type__app_label="uretim", codename__in=kodlar))
    return grup


def hesap_turu(kullanici):
    if kullanici.is_superuser:
        return "yonetici"
    return "ofis" if kullanici.is_staff else "tablet"


class HesapFormu(forms.Form):
    kullanici_adi = forms.RegexField(
        label="Kullanıcı adı", max_length=150, regex=r"^[\w.@+-]+$",
        error_messages={"invalid": "Yalnızca harf, rakam ve - _ . kullanın (boşluk olmaz)."},
        widget=forms.TextInput(attrs={"autocapitalize": "none", "autocomplete": "off"}),
        help_text="Örn: lazer1-tablet, ofis-ayse",
    )
    tur = forms.ChoiceField(label="Hesap türü", choices=TURLER, widget=forms.RadioSelect, initial="tablet")
    sifre = forms.CharField(label="Şifre", required=False, min_length=6,
                            widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    sifre_tekrar = forms.CharField(label="Şifre (tekrar)", required=False,
                                   widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    istasyon = forms.ModelChoiceField(
        queryset=Asama.objects.filter(aktif=True), label="Bu tablet hangi istasyonda?", required=False,
        empty_label="— Seçilmedi (tablet istediği istasyonu açar) —",
        help_text="Seçilirse tablet açılınca doğrudan bu istasyonun ekranı gelir.",
    )
    aktif = forms.BooleanField(label="Hesap açık (kapatılırsa giriş yapamaz)", required=False, initial=True)

    def __init__(self, *args, kullanici=None, **kwargs):
        self.kullanici = kullanici
        super().__init__(*args, **kwargs)
        if kullanici is None:
            self.fields["sifre"].required = True
            self.fields["sifre_tekrar"].required = True
        else:
            self.fields["sifre"].help_text = "Değiştirmek istemiyorsanız boş bırakın."

    def clean_kullanici_adi(self):
        ad = self.cleaned_data["kullanici_adi"]
        varolan = get_user_model().objects.filter(username__iexact=ad)
        if self.kullanici is not None:
            varolan = varolan.exclude(pk=self.kullanici.pk)
        if varolan.exists():
            raise forms.ValidationError("Bu kullanıcı adı zaten var.")
        return ad

    def clean(self):
        veri = super().clean()
        if veri.get("sifre") != veri.get("sifre_tekrar"):
            self.add_error("sifre_tekrar", "İki şifre aynı değil.")
        return veri

    def kaydet(self, istekte_bulunan):
        v = self.cleaned_data
        kullanici = self.kullanici or get_user_model()(username=v["kullanici_adi"])
        kullanici.username = v["kullanici_adi"]
        kendisi = kullanici.pk == istekte_bulunan.pk
        # Yönetici kendi hesabını kapatamaz ya da yetkisini düşüremez (kilitlenmesin).
        tur = "yonetici" if kendisi else v["tur"]
        kullanici.is_active = True if kendisi else v["aktif"]
        kullanici.is_superuser = tur == "yonetici"
        kullanici.is_staff = tur in ("ofis", "yonetici")
        if v.get("sifre"):
            kullanici.set_password(v["sifre"])
        kullanici.save()
        kullanici.user_permissions.clear()
        kullanici.groups.set([ofis_grubu()] if tur == "ofis" else [])
        HesapAyari.objects.update_or_create(
            kullanici=kullanici, defaults={"istasyon": v.get("istasyon") if tur == "tablet" else None}
        )
        return kullanici


@sadece_yonetici
def hesap_listesi(request):
    hesaplar = get_user_model().objects.order_by("-is_superuser", "-is_staff", "username")
    satirlar = [{"k": k, "tur": dict(TURLER)[hesap_turu(k)], "istasyon": hesap_istasyonu(k)} for k in hesaplar]
    return render(request, "uretim/hesap_listesi.html", {"satirlar": satirlar})


@sadece_yonetici
def hesap_formu(request, pk=None):
    kullanici = get_object_or_404(get_user_model(), pk=pk) if pk else None
    baslangic = {"tur": "tablet", "aktif": True}
    if kullanici:
        baslangic = {"kullanici_adi": kullanici.username, "tur": hesap_turu(kullanici), "aktif": kullanici.is_active,
                     "istasyon": hesap_istasyonu(kullanici)}
    form = HesapFormu(request.POST or None, kullanici=kullanici, initial=baslangic)
    if request.method == "POST" and form.is_valid():
        k = form.kaydet(request.user)
        messages.success(request, f"“{k.username}” hesabı kaydedildi ({dict(TURLER)[hesap_turu(k)]}).")
        return redirect("hesap_listesi")
    return render(request, "uretim/hesap_formu.html", {
        "form": form, "kullanici": kullanici, "aciklamalar": TUR_ACIKLAMA,
    })


class GirisView(LoginView):
    """İstasyonu belirlenmiş tablet giriş yapınca doğrudan o istasyonun ekranına gider."""

    def get_default_redirect_url(self):
        istasyon = hesap_istasyonu(self.request.user)
        if istasyon is not None:
            return reverse("istasyon_ekrani", args=[istasyon.pk])
        return super().get_default_redirect_url()
