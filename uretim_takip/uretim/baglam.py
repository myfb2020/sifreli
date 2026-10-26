"""Tüm sayfalarda kullanılan marka bilgisi."""

from functools import lru_cache

from django.contrib.staticfiles import finders
from django.templatetags.static import static

LOGO_ADAYLARI = ["uretim/marka/logo.svg", "uretim/marka/logo.png", "uretim/marka/logo.jpg", "uretim/marka/logo.webp"]


@lru_cache(maxsize=1)
def _logo_yolu():
    return next((yol for yol in LOGO_ADAYLARI if finders.find(yol)), None)


def marka(request):
    """Firma logosu `uretim/static/uretim/marka/logo.*` olarak konursa sol üst köşede gösterilir."""
    yol = _logo_yolu()
    return {"marka_logo": static(yol) if yol else None, "marka_adi": "BIENNA FUR"}
