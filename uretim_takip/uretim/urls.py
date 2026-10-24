from django.urls import path

from . import views

urlpatterns = [
    path("", views.pano, name="pano"),
    path("islem/baslat/", views.islem_baslat, name="islem_baslat"),
    path("islem/<int:pk>/bitir/", views.islem_bitir, name="islem_bitir"),
    path("lotlar/", views.lot_listesi, name="lot_listesi"),
    path("lotlar/<int:pk>/", views.lot_detay, name="lot_detay"),
    path("rapor/", views.rapor, name="rapor"),
    path("rapor/excel/", views.rapor_excel, name="rapor_excel"),
]
