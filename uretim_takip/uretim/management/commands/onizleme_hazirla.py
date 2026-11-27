"""Bayi vitrinindeki modellerin 'Bana fikir ver' küçük resimlerini önceden çizer (kurulum.sh çağırır; 2026-11-24, hız).

Ekranın istediği adresle aynı anahtar oluşur: öneri değerleri tarayıcının yaptığı gibi yazıya çevrilir, görünüm gibi
temizlenir ve tasarim_views._jpeg ile medya/onizleme'ye yazılır. Ölçüler: modelin kendi ölçüsü ve 160×230.
"""
import time

from django.core.management.base import BaseCommand
from django.http import QueryDict

from uretim import parcali
from uretim.parcali_views import _temizle
from uretim.tasarim_views import _jpeg

FIKIR_BOYU = 240  # tasarim_parcali.html: fikir kartı resmi b=240


def _js_yazi(d):
    """JSON'dan gelen değer tarayıcıda URLSearchParams ile nasıl yazılıyorsa öyle (160.0 → '160', True → 'true')."""
    if d is None:
        return ""
    if isinstance(d, bool):
        return "true" if d else "false"
    if isinstance(d, float) and d.is_integer():
        return str(int(d))
    return str(d)


class Command(BaseCommand):
    help = "Fikir ver küçük resimlerini önceden hazırlar (medya/onizleme)."

    def handle(self, *args, **kw):
        from uretim.tasarim_views import _desen_kodlari

        desenler = _desen_kodlari() - parcali.GIZLI_DESENLER  # parcali_views.fikir ile aynı
        bas, sayi = time.time(), 0
        for kod in parcali.BAYI_VITRINI:
            kendi = parcali.hazir_degerler(kod)
            for olcu in {(float(kendi["en"]), float(kendi["boy"])), (160.0, 230.0)}:
                for renk in parcali.SECILI_FIKIRLER.get(kod, []):
                    v = parcali.hazir_degerler(kod)
                    v["en"], v["boy"] = olcu
                    v.update(renk)
                    v["katalog"], v["hazir"] = kod, ""
                    q = QueryDict(mutable=True)
                    for a, d in parcali.temizle(v, desenler).items():
                        q[a] = _js_yazi(d)
                    _jpeg(_temizle(q), FIKIR_BOYU)
                    sayi += 1
        self.stdout.write(f"{sayi} fikir resmi hazır ({time.time() - bas:.0f} sn)")
        # 🧊 3B görünüm: vitrin modellerinin kendi hâli (ilk açılış beklemesin; 2026-11-27)
        from uretim import ucboyut
        bas, sayi = time.time(), 0
        for kod in parcali.BAYI_VITRINI:
            v = parcali.hazir_degerler(kod)
            v["katalog"] = kod
            q = QueryDict(mutable=True)
            for a, d in parcali.temizle(v, desenler).items():
                q[a] = _js_yazi(d)
            q["hazir"] = kod  # ekran (Bu modelden başla) hazir=KOD gönderir, şerit desenini göndermez
            q.pop("serit_desen", None)
            try:
                ucboyut.onbellekli(_temizle(q), "yuzey")
                sayi += 1
            except Exception as hata:  # noqa: BLE001 — kurulum 3B yüzünden durmasın
                self.stderr.write(f"{kod} 3B: {hata}")
        self.stdout.write(f"{sayi} 3B görünüm hazır ({time.time() - bas:.0f} sn)")
