from django.urls import path

from . import aktarim_views, pwa, qr, siparis_views, stok_views, views, yedek

urlpatterns = [
    path("", views.pano, name="pano"),
    path("islem/", stok_views.islem_merkezi, name="islem_merkezi"),
    path("islem/yeni/", stok_views.yeni_is, name="yeni_is"),
    path("islem/baslat/", views.islem_baslat, name="islem_baslat"),
    path("islem/<int:pk>/bitir/", views.islem_bitir, name="islem_bitir"),
    path("isler/", views.lot_listesi, name="lot_listesi"),
    path("isler/<int:pk>/", views.lot_detay, name="lot_detay"),
    path("stok/", stok_views.stok_listesi, name="stok_listesi"),
    path("stok/yeni/", stok_views.stok_yeni, name="stok_yeni"),
    path("stok/<int:pk>/", stok_views.stok_detay, name="stok_detay"),
    path("stok/bilgi/<str:lot_no>/", stok_views.stok_bilgi, name="stok_bilgi"),
    path("siparisler/", siparis_views.siparis_listesi, name="siparis_listesi"),
    path("siparisler/yeni/", siparis_views.siparis_yeni, name="siparis_yeni"),
    path("siparisler/<int:pk>/", siparis_views.siparis_detay, name="siparis_detay"),
    path("siparisler/<int:pk>/durum/", siparis_views.siparis_durum, name="siparis_durum"),
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
