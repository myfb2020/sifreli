"""Yavaş istek ölçümü (2026-11-24): eşikten uzun süren her istek sunucu hata günlüğüne tek satır yazılır.

Satır: YAVAŞ <yöntem> <yol> <durum> toplam X sn | bağlantı Y sn | veritabanı Z sn / N sorgu | kalan W sn
'bağlantı' = veritabanı dosyasının açılması, 'kalan' = Python (şablon, çizim, oturum çerezi…). Veriye dokunmaz.
"""

import sys
import time

from django.conf import settings
from django.db import connection


class YavasIstek:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        esik = getattr(settings, "YAVAS_ISTEK_ESIGI", 0.3)
        t0 = time.perf_counter()
        baglanti = 0.0
        if connection.connection is None:
            try:
                connection.ensure_connection()
            except Exception:  # noqa: BLE001 - bağlantı hatası sayfanın kendi hatası olarak görünsün
                pass
            baglanti = time.perf_counter() - t0
        sayac = {"n": 0, "sure": 0.0}

        def sarici(execute, sql, params, many, context):
            t = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                sayac["n"] += 1
                sayac["sure"] += time.perf_counter() - t

        with connection.execute_wrapper(sarici):
            yanit = self.get_response(request)
        toplam = time.perf_counter() - t0
        if toplam >= esik:
            kalan = toplam - baglanti - sayac["sure"]
            print(f"YAVAŞ {request.method} {request.path} {yanit.status_code} toplam {toplam:.2f} sn | "
                  f"bağlantı {baglanti:.2f} sn | veritabanı {sayac['sure']:.2f} sn / {sayac['n']} sorgu | "
                  f"kalan {kalan:.2f} sn", file=sys.stderr, flush=True)
        return yanit
