"""Tablet giriş/çıkış ve istasyon ekranı açılış kayıtları."""

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.utils import timezone

from .models import OturumKaydi

# Ekran yenilendikçe kayıt çoğalmasın: aynı hesap aynı istasyonu bu süre içinde yeniden açarsa yazılmaz.
TEKRAR_ARALIGI = timedelta(minutes=30)


def cihaz_adi(request):
    """Tarayıcı bilgisinden kısa cihaz adı, ör. 'Android · Chrome'."""
    ua = request.META.get("HTTP_USER_AGENT", "")
    sistem = next((ad for anahtar, ad in [("iPad", "iPad"), ("iPhone", "iPhone"), ("Android", "Android"),
                                          ("Windows", "Windows"), ("Mac OS", "Mac"), ("Linux", "Linux")]
                   if anahtar in ua), "Bilinmiyor")
    tarayici = next((ad for anahtar, ad in [("Edg/", "Edge"), ("SamsungBrowser", "Samsung"), ("Chrome", "Chrome"),
                                            ("Firefox", "Firefox"), ("Safari", "Safari")] if anahtar in ua), "")
    return f"{sistem} · {tarayici}" if tarayici else sistem


def _ip(request):
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
    return ip or None


def kaydet(request, tur, asama=None, kullanici=None):
    kullanici = kullanici or request.user
    if not kullanici or not kullanici.is_authenticated:
        return None
    if tur == "istasyon":
        yakin = OturumKaydi.objects.filter(kullanici=kullanici, tur="istasyon", asama=asama,
                                           zaman__gte=timezone.now() - TEKRAR_ARALIGI)
        if yakin.exists():
            return None
    return OturumKaydi.objects.create(kullanici=kullanici, kullanici_adi=kullanici.get_username(), tur=tur,
                                      asama=asama, cihaz=cihaz_adi(request), ip=_ip(request))


@receiver(user_logged_in)
def giris(sender, request, user, **kwargs):
    if request is not None:
        kaydet(request, "giris", kullanici=user)


@receiver(user_logged_out)
def cikis(sender, request, user, **kwargs):
    if request is not None and user is not None:
        kaydet(request, "cikis", kullanici=user)
