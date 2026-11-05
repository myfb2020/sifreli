"""Bayi tarafı (Siparişlerim, basit sipariş, davet) ve ofisin Bayiler sayfası; ofise yeni sipariş bildirimi."""

import json
import re
import secrets
import unicodedata
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import bildirim, servisler
from .forms import olcu_formseti
from .models import (
    BayiDavet, BildirimAboneligi, HesapAyari, KatalogModeli, KatalogSerisi, Musteri, Renk, Siparis, UretimLotu,
)
from .views import sadece_ofis

DAVET_GUN = 7


def _bayi(request):
    if getattr(request, "bayi", None) is None:
        raise PermissionDenied("Bu sayfa bayi hesapları içindir.")
    return request.bayi


# --- Bayi: Siparişlerim ------------------------------------------------------------


@login_required
def bayi_ana(request):
    bayi = _bayi(request)
    siparisler = (
        Siparis.objects.filter(musteri=bayi)
        .select_related("katalog_modeli", "renk", "tasarim")
        .prefetch_related(Prefetch("lotlar", queryset=UretimLotu.objects.select_related("son_asama", "kalem")),
                          "kalemler", "tamirler")
        .order_by("-tarih", "-pk")
    )
    satirlar = []
    for s in siparisler[:150]:
        tasarim = getattr(s, "tasarim", None)
        if s.durum == "iptal" and not (tasarim and tasarim.durum == "reddedildi"):
            continue
        satirlar.append({"s": s, "t": tasarim, "d": s.bayi_durumu()})
    return render(request, "uretim/bayi_ana.html", {"satirlar": satirlar, "studyo": bayi.studyo_acik})


# --- Bayi: katalogdan basit sipariş -------------------------------------------------


class BayiSiparisForm(forms.Form):
    model = forms.CharField(widget=forms.HiddenInput)
    renk = forms.CharField(required=False, widget=forms.HiddenInput)
    renk_notu = forms.CharField(label="Renk", required=False, max_length=100,
                                widget=forms.TextInput(attrs={"placeholder": "Ör. krem zemin, altın biye"}))
    teslim = forms.DateField(label="İstediğiniz teslim tarihi (isteğe bağlı)", required=False,
                             widget=forms.DateInput(attrs={"type": "date"}))
    notlar = forms.CharField(label="Notunuz (isteğe bağlı)", required=False, max_length=1000,
                             widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        veri = super().clean()
        model = KatalogModeli.objects.filter(kod=veri.get("model", ""), aktif=True).select_related("seri__hali_turu").first()
        if model is None:
            raise ValidationError("Katalogdan bir model seçin.")
        veri["model"] = model
        renk = None
        if model.seri.kartela:
            renk = Renk.objects.filter(kod=veri.get("renk", ""), grup=model.seri.kartela, aktif=True).first()
            if renk is None:
                raise ValidationError("Kartelanın renklerinden birini seçin.")
        elif not (veri.get("renk_notu") or "").strip():
            self.add_error("renk_notu", "Rengi yazın.")
        veri["renk"] = renk
        return veri


@login_required
def bayi_siparis(request):
    bayi = _bayi(request)
    form = BayiSiparisForm(request.POST or None, initial={"model": request.GET.get("model", "")})
    olculer = olcu_formseti(request.POST or None)
    if request.method == "POST" and form.is_valid() and olculer.is_valid():
        satirlar = olculer.satirlar()
        if not satirlar:
            form.add_error(None, "En az bir ölçü (en × boy) yazın.")
        else:
            v = form.cleaned_data
            model, renk = v["model"], v["renk"]
            with transaction.atomic():
                siparis = Siparis.objects.create(
                    musteri=bayi, durum="onay", katalog_modeli=model, hali_turu=model.seri.hali_turu,
                    renk=renk, renk_notu="" if renk else v["renk_notu"].strip(),
                    urun=f"{model.kod} · {renk or v['renk_notu'].strip()}"[:200],
                    teslim_tarihi=v["teslim"] or timezone.localdate() + timedelta(days=21),
                    notlar=v["notlar"] + ("" if v["teslim"] else "\n(Bayi teslim tarihi istemedi; tarih ofisçe belirlenecek.)"),
                )
                servisler.kalemleri_kaydet(siparis, satirlar)
            bildirim.yeni_bayi_siparisi(siparis)
            messages.success(request, f"Siparişiniz gönderildi ({siparis.siparis_no}). Onaylanınca üretime alınacak.")
            return redirect("bayi_ana")
    seriler = []
    for seri in KatalogSerisi.objects.order_by("sira", "ad"):
        modeller = [m for m in seri.modeller.filter(aktif=True).order_by("kod") if m.resim]
        if modeller:
            seriler.append({"seri": seri, "modeller": modeller})
    kartelalar = {g: list(Renk.objects.filter(grup=g, aktif=True)) for g, _ in Renk.GRUPLAR}
    from . import parcali
    return render(request, "uretim/bayi_siparis.html", {"form": form, "olculer": olculer, "seriler": seriler,
                                                        "kartelalar": kartelalar, "studyo": bayi.studyo_acik,
                                                        "duzenlenir": set(parcali.HAZIR)})


# --- Davet bağlantısı -------------------------------------------------------------------


def davet_ac(request, anahtar):
    davet = BayiDavet.objects.filter(anahtar=anahtar).select_related("kullanici").first()
    if davet is None or not davet.gecerli or not davet.kullanici.is_active:
        return render(request, "uretim/davet.html", {"gecersiz": True}, status=410)
    form = SetPasswordForm(davet.kullanici, request.POST or None)
    form.fields["new_password1"].label = "Şifreniz"
    form.fields["new_password2"].label = "Şifreniz (tekrar)"
    if request.method == "POST" and form.is_valid():
        kullanici = form.save()
        davet.kullanildi = timezone.now()
        davet.save(update_fields=["kullanildi"])
        login(request, kullanici, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Hoş geldiniz! Şifreniz kaydedildi; bu telefon sizi hatırlayacak.")
        return redirect("bayi_ana")
    return render(request, "uretim/davet.html", {"form": form, "davet": davet})


def _kullanici_adi(ad):
    taban = unicodedata.normalize("NFKD", ad.lower().replace("ı", "i")).encode("ascii", "ignore").decode()
    taban = re.sub(r"[^a-z0-9]+", "-", taban).strip("-")[:30] or "bayi"
    aday, i = taban, 1
    while get_user_model().objects.filter(username=aday).exists():
        i += 1
        aday = f"{taban}-{i}"
    return aday


def davet_olustur(kullanici, olusturan):
    BayiDavet.objects.filter(kullanici=kullanici, kullanildi__isnull=True).delete()  # eski bağlantı geçersiz olur
    return BayiDavet.objects.create(kullanici=kullanici, anahtar=secrets.token_urlsafe(24), olusturan=olusturan,
                                    son_gecerlilik=timezone.now() + timedelta(days=DAVET_GUN))


# --- Ofis: Bayiler ------------------------------------------------------------------------


class YeniBayiForm(forms.Form):
    musteri = forms.ModelChoiceField(queryset=Musteri.objects.filter(bayi_hesaplari__isnull=True), required=False,
                                     label="Var olan müşteri", empty_label="— Listeden seçin —")
    ad = forms.CharField(label="veya yeni bayi adı", required=False, max_length=120)
    telefon = forms.CharField(label="Telefon (WhatsApp)", required=False, max_length=30,
                              widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "05xx xxx xx xx"}))
    studyo_acik = forms.BooleanField(label="Tasarım stüdyosu açık (kapalıysa yalnız katalogdan sipariş verir)",
                                     required=False, initial=False)

    def clean(self):
        veri = super().clean()
        ad = (veri.get("ad") or "").strip()
        if not veri.get("musteri") and not ad:
            raise ValidationError("Müşteri seçin ya da yeni bayi adı yazın.")
        if ad and not veri.get("musteri"):
            var = Musteri.objects.filter(ad__iexact=ad).first()
            if var is not None and var.bayi_hesaplari.exists():
                raise ValidationError(f"“{var}” için zaten bayi hesabı var.")
            veri["musteri"] = var
        return veri


def _bayi_hesabi(musteri):
    ayar = HesapAyari.objects.filter(musteri=musteri).select_related("kullanici").first()
    return ayar.kullanici if ayar else None


@sadece_ofis
def bayi_listesi(request):
    form = YeniBayiForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        v = form.cleaned_data
        with transaction.atomic():
            musteri = v["musteri"] or Musteri.objects.create(ad=v["ad"].strip())
            if v.get("telefon"):
                musteri.telefon = v["telefon"].strip()
            musteri.studyo_acik = v["studyo_acik"]
            musteri.save()
            kullanici = get_user_model().objects.create_user(_kullanici_adi(musteri.ad))
            kullanici.set_unusable_password()
            kullanici.save()
            HesapAyari.objects.create(kullanici=kullanici, musteri=musteri)
            davet = davet_olustur(kullanici, request.user)
        messages.success(request, f"{musteri} için bayi hesabı açıldı. Davet bağlantısını WhatsApp'tan gönderin.")
        return redirect(f"{reverse('bayi_listesi')}?davet={davet.pk}")
    musteriler = (Musteri.objects.filter(bayi_hesaplari__isnull=False).distinct()
                  .annotate(bekleyen=Count("siparis", filter=Q(siparis__durum="onay"), distinct=True),
                            aktif=Count("siparis", filter=Q(siparis__durum__in=["acik", "uretimde"]), distinct=True)))
    satirlar = []
    for m in musteriler:
        k = _bayi_hesabi(m)
        satirlar.append({"m": m, "k": k, "davet": BayiDavet.objects.filter(kullanici=k).order_by("-olusturma").first()})
    davet = None
    if request.GET.get("davet"):
        davet = BayiDavet.objects.filter(pk=request.GET["davet"]).select_related("kullanici").first()
    baglam = {"form": form, "satirlar": satirlar}
    if davet is not None and davet.gecerli:
        adres = request.build_absolute_uri(reverse("davet_ac", args=[davet.anahtar]))
        musteri = davet.kullanici.hesap_ayari.musteri
        mesaj = (f"Merhaba, Bienna Fur sipariş ekranınız hazır: {adres}\n"
                 f"Bağlantıyı açıp kendi şifrenizi belirleyin. Bağlantı {DAVET_GUN} gün geçerlidir, bir kez kullanılır.")
        telefon = re.sub(r"\D", "", musteri.telefon or "")
        if telefon.startswith("0"):
            telefon = "9" + telefon
        elif len(telefon) == 10:
            telefon = "90" + telefon
        from urllib.parse import quote
        baglam["davet"] = {"musteri": musteri, "adres": adres, "mesaj": mesaj,
                           "whatsapp": f"https://wa.me/{telefon}?text={quote(mesaj)}" if telefon
                           else f"https://wa.me/?text={quote(mesaj)}"}
    return render(request, "uretim/bayi_listesi.html", baglam)


@require_POST
@sadece_ofis
def bayi_davet(request, pk):
    musteri = get_object_or_404(Musteri, pk=pk)
    kullanici = _bayi_hesabi(musteri)
    if kullanici is None:
        raise Http404
    if not kullanici.is_active:
        messages.error(request, "Hesap kapalı; önce yönetici açmalı.")
        return redirect("bayi_listesi")
    davet = davet_olustur(kullanici, request.user)
    return redirect(f"{reverse('bayi_listesi')}?davet={davet.pk}")


@require_POST
@sadece_ofis
def bayi_studyo(request, pk):
    musteri = get_object_or_404(Musteri, pk=pk)
    musteri.studyo_acik = not musteri.studyo_acik
    musteri.save(update_fields=["studyo_acik"])
    messages.success(request, f"{musteri}: tasarım stüdyosu {'açıldı' if musteri.studyo_acik else 'kapatıldı'}.")
    return redirect("bayi_listesi")


@require_POST
@sadece_ofis
def bayi_hesap(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied("Hesabı yalnız yönetici kapatıp açabilir.")
    kullanici = _bayi_hesabi(get_object_or_404(Musteri, pk=pk))
    if kullanici is None:
        raise Http404
    kullanici.is_active = not kullanici.is_active
    kullanici.save(update_fields=["is_active"])
    messages.success(request, f"{kullanici.username} hesabı {'açıldı' if kullanici.is_active else 'kapatıldı'}.")
    return redirect("bayi_listesi")


# --- Ofis bildirimleri --------------------------------------------------------------------


@sadece_ofis
def bildirim_durum(request):
    """Ofis ekranı her dakika sorar: onay bekleyen bayi siparişi sayısı ve en yenisi."""
    bekleyen = Siparis.objects.filter(durum="onay").select_related("musteri").order_by("-pk")
    son = bekleyen.first()
    return JsonResponse({"sayi": bekleyen.count(), "son": son.pk if son else 0,
                         "metin": f"{son.musteri} – {son.urun}" if son else "",
                         "adres": reverse("siparis_detay", args=[son.pk]) if son else ""})


@require_POST
@sadece_ofis
def bildirim_abone(request):
    try:
        veri = json.loads(request.body or b"{}")
        endpoint, anahtar = veri["endpoint"], veri["keys"]
        p256dh, auth = anahtar["p256dh"], anahtar["auth"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"tamam": False}, status=400)
    if not str(endpoint).startswith("https://"):
        return JsonResponse({"tamam": False}, status=400)
    BildirimAboneligi.objects.update_or_create(endpoint=endpoint, defaults={
        "kullanici": request.user, "p256dh": p256dh, "auth": auth})
    return JsonResponse({"tamam": True})
