"""Güvenlik (CSRF) hatasında korkutucu 403 yerine anlaşılır bir sayfa.

En sık sebep: sayfa uzun süre açık kaldı ya da aynı tarayıcıda başka sekmede giriş/çıkış yapıldı;
formun içindeki güvenlik anahtarı eskidi. Sayfayı yeniden açıp tekrar denemek yeter.
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def csrf_hatasi(request, reason=""):
    giris = reverse("login")
    if request.path == giris:
        # Giriş formu eskimiş: formu yenileyip kullanıcıdan bir kez daha girmesini iste.
        messages.info(request, "Sayfa yenilendi, lütfen kullanıcı adı ve şifrenizi tekrar girin.")
        return redirect(giris)
    geri = request.path if url_has_allowed_host_and_scheme(request.path, {request.get_host()}) else "/"
    return render(request, "uretim/csrf_hatasi.html", {"geri": geri}, status=403)
