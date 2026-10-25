import re
import secrets
import tempfile
from pathlib import Path

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .excel_aktar import SAYFALAR, ice_aktar, sablon_olustur
from .yedek import sadece_yonetici

AZAMI_BOYUT = 5 * 1024 * 1024
GECICI_KLASOR = Path(tempfile.gettempdir()) / "uretim_aktarim"
OTURUM_ANAHTARI = "excel_aktarim"


def _gecici_yol(anahtar):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,}", anahtar or ""):
        return None
    return GECICI_KLASOR / f"{anahtar}.xlsx"


@sadece_yonetici
def sablon_indir(request):
    yanit = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    yanit["Content-Disposition"] = 'attachment; filename="uretim_aktarim_sablonu.xlsx"'
    sablon_olustur().save(yanit)
    return yanit


@sadece_yonetici
def excel_aktar(request):
    baglam = {"sayfalar": SAYFALAR}

    if request.method == "POST" and "onayla" in request.POST:
        yol = _gecici_yol(request.session.get(OTURUM_ANAHTARI))
        if not yol or not yol.exists():
            messages.error(request, "Önizlemesi yapılan dosya bulunamadı, lütfen tekrar yükleyin.")
            return redirect("excel_aktar")
        rapor = ice_aktar(yol, kaydet=True)
        if rapor.kaydedildi:
            yol.unlink(missing_ok=True)
            request.session.pop(OTURUM_ANAHTARI, None)
            messages.success(request, f"Aktarım tamamlandı: {rapor.toplam} kayıt kaydedildi.")
        baglam.update(rapor=rapor, dosya_adi=request.session.get("excel_aktarim_ad", ""))
        return render(request, "uretim/excel_aktar.html", baglam)

    if request.method == "POST":
        dosya = request.FILES.get("dosya")
        if not dosya:
            messages.error(request, "Lütfen bir Excel dosyası seçin.")
        elif not dosya.name.lower().endswith((".xlsx", ".xlsm")):
            messages.error(request, "Yalnızca .xlsx dosyaları okunabilir. Eski .xls dosyasını Excel'de "
                                    "“Farklı Kaydet → Excel Çalışma Kitabı (.xlsx)” ile kaydedin.")
        elif dosya.size > AZAMI_BOYUT:
            messages.error(request, "Dosya 5 MB'tan büyük olamaz.")
        else:
            GECICI_KLASOR.mkdir(parents=True, exist_ok=True)
            eski = _gecici_yol(request.session.get(OTURUM_ANAHTARI))
            if eski:
                eski.unlink(missing_ok=True)
            anahtar = secrets.token_urlsafe(24)
            yol = _gecici_yol(anahtar)
            with open(yol, "wb") as hedef:
                for parca in dosya.chunks():
                    hedef.write(parca)
            request.session[OTURUM_ANAHTARI] = anahtar
            request.session["excel_aktarim_ad"] = dosya.name
            baglam.update(rapor=ice_aktar(yol, kaydet=False), dosya_adi=dosya.name, onizleme=True)
    return render(request, "uretim/excel_aktar.html", baglam)
