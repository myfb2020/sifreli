"""Nöbetçi (UptimeRobot vb.) için sağlık sayfası: veritabanı okunuyor ve diske yazılabiliyorsa "TAMAM"."""

import tempfile

from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache


@never_cache
def saglik(request):
    sorunlar = []
    try:
        with connection.cursor() as imlec:
            imlec.execute("SELECT COUNT(*) FROM uretim_siparis")
            imlec.fetchone()
    except Exception as hata:  # noqa: BLE001 - nöbetçiye sebebi kısaca söyle
        sorunlar.append(f"veritabani: {type(hata).__name__}")
    try:  # disk doluysa (kota aşıldıysa) yazma başarısız olur
        with tempfile.NamedTemporaryFile(dir=settings.BASE_DIR, prefix=".saglik-") as dosya:
            dosya.write(b"x" * 1024)
            dosya.flush()
    except OSError as hata:
        sorunlar.append(f"disk: {hata.strerror or type(hata).__name__}")
    if sorunlar:
        return HttpResponse("SORUN: " + "; ".join(sorunlar), status=503, content_type="text/plain; charset=utf-8")
    return HttpResponse("TAMAM", content_type="text/plain; charset=utf-8")
