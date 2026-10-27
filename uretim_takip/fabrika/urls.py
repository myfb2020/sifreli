from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from uretim.hesaplar import GirisView

urlpatterns = [
    path("yonetim/", admin.site.urls),
    path("giris/", GirisView.as_view(), name="login"),
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("uretim.urls")),
]
