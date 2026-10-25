from django.urls import path

from . import aktarim_views, pwa, qr, views, yedek

urlpatterns = [
    path("", views.pano, name="pano"),
    path("islem/baslat/", views.islem_baslat, name="islem_baslat"),
    path("islem/<int:pk>/bitir/", views.islem_bitir, name="islem_bitir"),
    path("lotlar/", views.lot_listesi, name="lot_listesi"),
    path("lotlar/<int:pk>/", views.lot_detay, name="lot_detay"),
    path("rapor/", views.rapor, name="rapor"),
    path("rapor/excel/", views.rapor_excel, name="rapor_excel"),
    path("qr/", qr.qr_tara, name="qr_tara"),
    path("q/<str:lot_no>/", qr.qr_yonlendir, name="qr_yonlendir"),
    path("etiketler/", qr.etiketler, name="etiketler"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("sw.js", pwa.service_worker, name="service_worker"),
    path("cevrimdisi/", pwa.cevrimdisi, name="cevrimdisi"),
    path("yedek/", yedek.yedek_indir, name="yedek_indir"),
    path("aktar/", aktarim_views.excel_aktar, name="excel_aktar"),
    path("aktar/sablon/", aktarim_views.sablon_indir, name="sablon_indir"),
]
