from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("yonetim/", admin.site.urls),
    path("giris/", auth_views.LoginView.as_view(), name="login"),
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("uretim.urls")),
]
