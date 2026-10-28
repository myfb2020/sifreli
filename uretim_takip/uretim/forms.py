from django import forms
from django.core.exceptions import ValidationError

from .models import (
    NEDENLER, Asama, DeriTuru, HaliTuru, HamDeriGirisi, KatalogModeli, LazerDeseni, Makine, Malzeme, Musteri, Personel, Siparis, Tedarikci, UretimLotu,
    m2_hesapla, pin_dogrulayici,
)


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


class MakineSecimi(forms.Select):
    """Seçeneklere istasyon bilgisini ekler; sayfa yalnızca seçilen istasyonun makinelerini gösterir."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        secenek = super().create_option(name, value, label, selected, index, subindex, attrs)
        makine = getattr(value, "instance", None)
        if makine is not None:
            secenek["attrs"]["data-asama"] = makine.asama_id
        return secenek


def makine_alani():
    return forms.ModelChoiceField(
        queryset=Makine.objects.filter(aktif=True).select_related("asama"), label="Makine", required=False,
        empty_label="— Makine seçin —", widget=MakineSecimi,
    )


def makine_kontrol(form, veri):
    """Seçilen istasyonun makinesi varsa makine seçimi zorunlu, makine o istasyona ait olmalı."""
    asama, makine = veri.get("asama"), veri.get("makine")
    if asama is None:
        return
    if makine is not None and makine.asama_id != asama.pk:
        form.add_error("makine", f"{makine} makinesi “{asama.ad}” istasyonunda değil.")
    elif makine is None and asama.makineler.filter(aktif=True).exists():
        form.add_error("makine", "Hangi makinede çalıştığınızı seçin.")


class HaliTuruAlani(forms.ModelChoiceField):
    def label_from_instance(self, tur):
        rota = tur.rota_metni()
        return f"{tur.ad} ({rota})" if rota else tur.ad


class IsSecimAlani(forms.ModelChoiceField):
    def label_from_instance(self, lot):
        parcalar = [lot.lot_no]
        if lot.siparis:
            parcalar.append(f"{lot.siparis.siparis_no} {lot.siparis.musteri}")
        parcalar.append(f"son: {lot.son_asama.ad}" if lot.son_asama else "başlamadı")
        return " – ".join(parcalar)


class SiparisSecimi(forms.Select):
    """Seçeneklere siparişin ilk istasyon(lar)ını ekler; makine listesi buna göre süzülür."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        secenek = super().create_option(name, value, label, selected, index, subindex, attrs)
        siparis = getattr(value, "instance", None)
        if siparis is not None:
            secenek["attrs"]["data-ilk"] = ",".join(str(a.pk) for a in siparis.ilk_asamalar())
        return secenek


class SiparisSecimAlani(forms.ModelChoiceField):
    widget = SiparisSecimi

    def label_from_instance(self, s):
        tur = f" [{s.hali_turu}]" if s.hali_turu_id else ""
        return f"{s.siparis_no} – {s.musteri} – {s.urun}{tur} (teslim {s.teslim_tarihi:%d.%m})"


class IslemBaslatForm(PinliForm):
    lot = IsSecimAlani(
        queryset=UretimLotu.objects.filter(durum="bekliyor").select_related("siparis__musteri", "son_asama"),
        label="İş", empty_label="— İş seçin —",
    )
    asama = forms.ModelChoiceField(
        queryset=Asama.objects.filter(aktif=True), label="Aşama", empty_label="— Aşama seçin —"
    )
    makine = makine_alani()
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    field_order = ["personel", "pin", "lot", "asama", "makine", "aciklama"]

    def clean(self):
        veri = super().clean()
        makine_kontrol(self, veri)
        return veri


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
    hali_turu = HaliTuruAlani(
        queryset=HaliTuru.objects.filter(aktif=True), label="Halı türü", empty_label="— Halı türü seçin —",
        help_text="İş bu türün istasyonlarından sırayla geçer.",
    )
    yeni_musteri = forms.CharField(
        label="veya yeni müşteri adı", required=False, max_length=120,
        help_text="Müşteri listede yoksa buraya yazın, otomatik eklenir.",
    )
    model_kodu = forms.CharField(
        label="Katalog modeli (isteğe bağlı)", required=False, max_length=20,
        widget=forms.TextInput(attrs={"list": "model-kodlari", "autocomplete": "off", "autocapitalize": "characters",
                                      "placeholder": "Ör. TOS-034"}),
        help_text="Katalogdaki model kodu. Seçince resmi siparişte ve istasyon ekranlarında görünür.",
    )
    lazer_deseni = forms.ModelChoiceField(
        queryset=LazerDeseni.objects.filter(aktif=True), label="Lazer deseni (isteğe bağlı)", required=False,
        empty_label="— Desen yok —",
    )

    class Meta:
        model = Siparis
        fields = ["hali_turu", "urun", "deri_turu", "adet", "toplam_m2", "teslim_tarihi", "notlar", "lazer_deseni"]
        widgets = {
            "teslim_tarihi": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notlar": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"notlar": "Not (isteğe bağlı)"}

    field_order = ["musteri", "yeni_musteri", "model_kodu", "lazer_deseni", "hali_turu", "urun", "deri_turu", "adet",
                   "toplam_m2", "teslim_tarihi", "notlar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deri_turu"].empty_label = "— (isteğe bağlı) —"
        # Halı türü kaydederken denetlenir: katalog serisinden de gelebilir.
        self.fields["hali_turu"].required = False
        self.fields["urun"].required = False
        self.fields["urun"].help_text = "Ölçü, renk vb. Örn: 200x300 krem. Model seçildiyse boş bırakılabilir."

    def clean_model_kodu(self):
        kod = (self.cleaned_data.get("model_kodu") or "").strip().upper().replace(".", "")
        if not kod:
            return None
        model = KatalogModeli.objects.filter(kod__iexact=kod).select_related("seri__hali_turu").first()
        if model is None:
            raise forms.ValidationError(f"“{kod}” kodlu katalog modeli yok. Katalog sayfasından bakabilirsiniz.")
        return model

    def clean(self):
        veri = super().clean()
        if not (veri.get("yeni_musteri") or "").strip() and not veri.get("musteri"):
            self.add_error("musteri", "Bir müşteri seçin ya da yeni müşteri adı yazın.")
        model = veri.get("model_kodu")
        if not veri.get("hali_turu") and model and model.seri.hali_turu and model.seri.hali_turu.aktif:
            veri["hali_turu"] = self.instance.hali_turu = model.seri.hali_turu
        if not veri.get("hali_turu") and HaliTuru.objects.filter(aktif=True).exists() and "hali_turu" not in self.errors:
            self.add_error("hali_turu", "Halı türünü seçin.")
        if not (veri.get("urun") or "").strip():
            if model:
                veri["urun"] = self.instance.urun = f"{model.kod} {model.seri}"
            elif "urun" not in self.errors:
                self.add_error("urun", "Ürünü yazın ya da katalog modeli seçin.")
        return veri

    def save(self, commit=True):
        yeni = self.cleaned_data["yeni_musteri"].strip()
        if yeni:
            musteri = Musteri.objects.filter(ad__iexact=yeni).first() or Musteri.objects.create(ad=yeni)
        else:
            musteri = self.cleaned_data["musteri"]
        self.instance.musteri = musteri
        self.instance.katalog_modeli = self.cleaned_data.get("model_kodu")
        return super().save(commit)


class YeniIsForm(PinliForm):
    siparis = SiparisSecimAlani(
        queryset=Siparis.objects.filter(durum__in=["acik", "uretimde"]).select_related("musteri", "hali_turu").order_by("teslim_tarihi"),
        label="Sipariş", empty_label="— Hangi sipariş için? —",
    )
    asama = forms.ModelChoiceField(
        queryset=Asama.objects.filter(aktif=True), label="Başlanacak istasyon", required=False,
        empty_label="— Halı türüne göre ilk istasyon —",
    )
    makine = makine_alani()
    eski_tur = forms.ModelChoiceField(
        queryset=DeriTuru.objects.all(), label="Eski stoktan (etiketsiz) – malzeme türü", required=False,
        empty_label="— Eski stok kullanılmadı —",
        help_text="Geçiş dönemi: etiketi olmayan eski malzemeden aldıysanız türünü seçip miktarı yazın.",
    )
    eski_m2 = ondalik_alan("Eski stoktan alınan m²", required=False)
    eski_kg = ondalik_alan("Eski stoktan alınan kg (isteğe bağlı)", required=False)
    aciklama = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    field_order = ["personel", "pin", "siparis", "asama", "makine", "eski_tur", "eski_m2", "eski_kg", "aciklama"]

    def __init__(self, *args, gecis_modu=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not gecis_modu:
            for alan in ("eski_tur", "eski_m2", "eski_kg"):
                del self.fields[alan]

    def eski_stok(self):
        v = self.cleaned_data
        if not v.get("eski_tur"):
            return None
        return v["eski_tur"], v.get("eski_kg"), v.get("eski_m2")

    def clean(self):
        veri = super().clean()
        if veri.get("eski_tur") and not veri.get("eski_m2") and not veri.get("eski_kg"):
            self.add_error("eski_m2", "Eski stoktan aldığınız miktarı girin.")
        siparis = veri.get("siparis")
        if siparis and not veri.get("asama"):
            ilkler = siparis.ilk_asamalar()
            makine = veri.get("makine")
            if len(ilkler) == 1:
                veri["asama"] = ilkler[0]
            elif makine is not None and makine.asama in ilkler:
                # İlk adım alternatifliyse (Lazer kesim 1 / 2) seçilen makine istasyonu belirler.
                veri["asama"] = makine.asama
            elif ilkler:
                self.add_error("makine", "Bu halı türü " + " ya da ".join(a.ad for a in ilkler)
                               + " ile başlıyor; hangi makinede çalıştığınızı seçin.")
            else:
                self.add_error("asama", "Başlanacak istasyonu seçin.")
        makine_kontrol(self, veri)
        return veri


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
            malzeme = Malzeme.objects.filter(kod=no).first()
            if malzeme is not None:
                self.add_error("stok_no", f"{no} bir malzeme etiketi ({malzeme.ad}), işin ana malzemesi değil. "
                                          "Malzemeler işi bitirirken “Kullanılan malzemeler” bölümüne girilir.")
            else:
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
    giris_birimi = forms.ChoiceField(label="Geliş birimi", choices=HamDeriGirisi.GIRIS_BIRIMLERI, initial="m2")
    giris_miktari = ondalik_alan("Gelen miktar")
    en_cm = ondalik_alan("Rulo eni (cm)", required=False)
    kg = ondalik_alan("Kg (isteğe bağlı)", required=False)

    class Meta:
        model = HamDeriGirisi
        fields = ["tarih", "deri_turu", "renk", "model", "kalite", "adet", "giris_birimi", "giris_miktari", "en_cm", "kg",
                  "notlar"]
        widgets = {
            "tarih": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notlar": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"notlar": "Not (isteğe bağlı)", "adet": "Adet / rulo (isteğe bağlı)", "renk": "Renk",
                  "model": "Model / desen", "deri_turu": "Malzeme türü"}

    field_order = ["tedarikci", "yeni_tedarikci", "tarih", "deri_turu", "renk", "model", "kalite", "adet",
                   "giris_birimi", "giris_miktari", "en_cm", "kg", "notlar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Daha önce yazılan renk ve modeller öneri olarak çıkar (aynı adın farklı yazımı azalır).
        self.fields["renk"].widget.attrs.update({"list": "renk-onerileri", "autocomplete": "off"})
        self.fields["model"].widget.attrs.update({"list": "model-onerileri", "autocomplete": "off"})
        self.fields["deri_turu"].help_text = ("Fasonda birleştirilen malzemeler (lamine, taban) normalde Stok → Fason'dan "
                                              "teslim alınırken kendiliğinden oluşur; buradan yalnızca hazır alınanları girin.")

    def clean(self):
        veri = super().clean()
        if not (veri.get("yeni_tedarikci") or "").strip() and not veri.get("tedarikci"):
            self.add_error("tedarikci", "Bir tedarikçi seçin ya da yeni tedarikçi adı yazın.")
        birim, miktar = veri.get("giris_birimi"), veri.get("giris_miktari")
        if birim == "mtul" and not veri.get("en_cm"):
            self.add_error("en_cm", "Metretül girişinde rulonun enini (cm) yazın; m² buna göre hesaplanır.")
        if birim != "mtul":
            veri["en_cm"] = None
        if veri.get("kg") is None:
            veri["kg"] = 0
        # Stok her zaman m² tutulur; işe malzeme alırken de m² girilir.
        self.instance.m2 = m2_hesapla(birim, miktar, veri.get("en_cm")) or 0
        return veri

    def save(self, commit=True):
        yeni = self.cleaned_data["yeni_tedarikci"].strip()
        if yeni:
            self.instance.tedarikci = Tedarikci.objects.filter(ad__iexact=yeni).first() or Tedarikci.objects.create(ad=yeni)
        else:
            self.instance.tedarikci = self.cleaned_data["tedarikci"]
        return super().save(commit)


# --- Fason ---------------------------------------------------------------------


class FasonGonderForm(forms.Form):
    fasoncu = forms.ModelChoiceField(queryset=Tedarikci.objects.all(), label="Fasoncu", required=False,
                                     empty_label="— Fasoncu seçin —")
    yeni_fasoncu = forms.CharField(label="veya yeni fasoncu adı", required=False, max_length=120)
    hedef_tur = forms.ModelChoiceField(queryset=DeriTuru.objects.filter(bilesik=True), label="Ne yapılacak",
                                       empty_label="— Seçin (ör. 3'lü lamine) —")
    notlar = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        veri = super().clean()
        if not (veri.get("yeni_fasoncu") or "").strip() and not veri.get("fasoncu"):
            self.add_error("fasoncu", "Bir fasoncu seçin ya da yeni fasoncu adı yazın.")
        return veri

    def fasoncu_bul(self):
        yeni = self.cleaned_data["yeni_fasoncu"].strip()
        if yeni:
            return Tedarikci.objects.filter(ad__iexact=yeni).first() or Tedarikci.objects.create(ad=yeni)
        return self.cleaned_data["fasoncu"]


class FasonTeslimForm(forms.Form):
    m2 = ondalik_alan("Gelen m²")
    kg = ondalik_alan("Gelen kg (isteğe bağlı)", required=False)
    adet = forms.IntegerField(label="Adet / rulo (isteğe bağlı)", required=False, min_value=0)
    renk = forms.CharField(label="Renk", required=False, max_length=60,
                           help_text="Üst katmandan (rona / suni deri) geldi; farklıysa düzeltin.")
    model = forms.CharField(label="Model / desen", required=False, max_length=60)
    notlar = forms.CharField(label="Not (isteğe bağlı)", required=False, widget=forms.Textarea(attrs={"rows": 2}))


# --- Malzemeler ve stok düzeltme ----------------------------------------------


class MalzemeKullanimForm(forms.Form):
    malzeme = forms.ModelChoiceField(queryset=Malzeme.objects.filter(aktif=True), required=False,
                                     label="Malzeme", empty_label="— Malzeme —")
    miktar = ondalik_alan("Miktar", required=False)

    def clean(self):
        veri = super().clean()
        if veri.get("malzeme") and not veri.get("miktar"):
            self.add_error("miktar", "Kullanılan miktarı girin.")
        if veri.get("miktar") and not veri.get("malzeme"):
            self.add_error("malzeme", "Malzemeyi seçin.")
        return veri


MalzemeKullanimFormSet = forms.formset_factory(MalzemeKullanimForm, extra=3, max_num=10)


class MalzemeForm(forms.ModelForm):
    min_stok = ondalik_alan("En az stok (uyarı sınırı)", required=False)

    class Meta:
        model = Malzeme
        fields = ["ad", "kategori", "birim", "min_stok"]


class MalzemeGirisForm(forms.Form):
    malzeme = forms.ModelChoiceField(queryset=Malzeme.objects.filter(aktif=True), label="Malzeme",
                                     empty_label="— Malzeme seçin —")
    miktar = ondalik_alan("Gelen miktar")
    tedarikci = forms.ModelChoiceField(queryset=Tedarikci.objects.all(), required=False, label="Tedarikçi (isteğe bağlı)")
    aciklama = forms.CharField(label="Açıklama (isteğe bağlı)", required=False, max_length=200,
                               help_text="Örn. fatura no")


class MalzemeDuzeltmeForm(forms.Form):
    neden = forms.ChoiceField(choices=NEDENLER, label="Neden")
    miktar = ondalik_alan("Miktar", help_text="Sayım farkı: sayılan gerçek miktar. Diğerleri: stoktan düşülecek miktar.")
    aciklama = forms.CharField(label="Açıklama (isteğe bağlı)", required=False, max_length=200)


class DeriDuzeltmeForm(forms.Form):
    neden = forms.ChoiceField(choices=NEDENLER, label="Neden")
    kg = ondalik_alan("kg", required=False)
    m2 = ondalik_alan("m²", required=False)
    aciklama = forms.CharField(label="Açıklama (isteğe bağlı)", required=False, max_length=200)
