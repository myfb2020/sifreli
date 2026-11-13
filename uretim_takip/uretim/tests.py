from datetime import timedelta
from pathlib import Path
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import raporlar, servisler, tasarim_cizim, uyarilar
from .models import (
    Asama, DeriTuru, HaliTuru, HamDeriGirisi, IslemKaydi, LotKaynagi, Makine, Musteri, Personel, Siparis, Tedarikci, UretimLotu,
    hesap_bayisi,
)


class TemelVeri(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ahmet = Personel(ad_soyad="Ahmet")
        cls.ahmet.pin_ayarla("1234")
        cls.ahmet.save()
        cls.ayse = Personel(ad_soyad="Ayşe")
        cls.ayse.pin_ayarla("5678")
        cls.ayse.save()
        cls.ham = HamDeriGirisi.objects.create(
            tedarikci=Tedarikci.objects.create(ad="T"), deri_turu=DeriTuru.objects.get(ad="Kuzu"),
            kg=Decimal("100"), m2=Decimal("20"),
        )
        cls.siparis = Siparis.objects.create(
            musteri=Musteri.objects.create(ad="M"), urun="Halı", teslim_tarihi=timezone.localdate() + timedelta(days=3)
        )
        cls.asamalar = list(Asama.objects.filter(aktif=True))

    @staticmethod
    def makine(asama):
        m = asama.makineler.first()
        return m.pk if m else ""

    def yeni_lot(self, ham_deri=None, **kw):
        """Doğrudan iş kaydı (testlerin çoğu için yeterli); malzeme tek stok lotundan alınmış sayılır."""
        kw.setdefault("baslangic_kg", Decimal("50"))
        kw.setdefault("baslangic_m2", Decimal("10"))
        lot = UretimLotu.objects.create(**kw)
        LotKaynagi.objects.create(uretim_lotu=lot, ham_deri=ham_deri or self.ham, kg=lot.baslangic_kg, m2=lot.baslangic_m2)
        return lot


class NumaralamaTesti(TemelVeri):
    def test_numaralar_sirali_uretilir(self):
        yil = timezone.localdate().year
        self.assertEqual(self.ham.lot_no, f"HD-{yil}-0001")
        a, b = self.yeni_lot(), self.yeni_lot()
        self.assertEqual(a.lot_no, f"IS-{yil}-0001")
        self.assertEqual(b.lot_no, f"IS-{yil}-0002")
        self.assertEqual(self.siparis.siparis_no, f"SP-{yil}-0001")

    def test_ham_deri_kalan_miktar(self):
        self.yeni_lot(baslangic_kg=Decimal("30"), baslangic_m2=Decimal("6"))
        self.assertEqual(self.ham.kalan_kg, Decimal("70"))
        self.assertEqual(self.ham.kalan_m2, Decimal("14"))


class PinTesti(TemelVeri):
    def test_pin_sifrelenir_ve_dogrulanir(self):
        self.assertNotEqual(self.ahmet.pin, "1234")
        self.assertTrue(self.ahmet.pin_dogru_mu("1234"))
        self.assertFalse(self.ahmet.pin_dogru_mu("0000"))

    def test_duz_pin_kaydedilirken_sifrelenir(self):
        p = Personel.objects.create(ad_soyad="Ali", pin="4321")
        self.assertTrue(p.pin.startswith("pbkdf2_"))
        self.assertTrue(p.pin_dogru_mu("4321"))


class IslemAkisiTesti(TemelVeri):
    def test_baslat_ve_bitir_lotu_gunceller(self):
        lot = self.yeni_lot(siparis=self.siparis)
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        lot.refresh_from_db()
        self.assertEqual(lot.durum, "islemde")
        self.assertEqual(lot.son_asama, self.asamalar[0])
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "uretimde")

        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("47"), cikis_m2=Decimal("9.5"))
        lot.refresh_from_db()
        islem.refresh_from_db()
        self.assertEqual(lot.durum, "bekliyor")
        self.assertEqual((lot.mevcut_kg, lot.mevcut_m2), (Decimal("47"), Decimal("9.5")))
        self.assertEqual(islem.fire_m2, Decimal("0.5"))
        self.assertEqual(islem.fire_yuzde_m2, Decimal("5.0"))
        self.assertEqual(lot.siradaki_asama, self.asamalar[1])

    def test_sonraki_islem_onceki_ciktiyla_baslar(self):
        lot = self.yeni_lot()
        i1 = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        servisler.islem_bitir(islem=i1, personel=self.ahmet, cikis_kg=Decimal("45"), cikis_m2=Decimal("9"))
        i2 = servisler.islem_baslat(lot=lot, asama=self.asamalar[1], personel=self.ayse)
        self.assertEqual((i2.giris_kg, i2.giris_m2), (Decimal("45"), Decimal("9")))

    def test_ayni_lotta_iki_acik_islem_olamaz(self):
        lot = self.yeni_lot()
        servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        with self.assertRaises(ValidationError):
            servisler.islem_baslat(lot=lot, asama=self.asamalar[1], personel=self.ayse)

    def test_bitmis_islem_tekrar_bitirilemez(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))
        with self.assertRaises(ValidationError):
            servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))

    def test_son_asama_lotu_ve_siparisi_tamamlar(self):
        lot = self.yeni_lot(siparis=self.siparis)
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[-1], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("40"), cikis_m2=Decimal("9"))
        lot.refresh_from_db()
        self.siparis.refresh_from_db()
        self.assertEqual(lot.durum, "tamamlandi")
        self.assertEqual(self.siparis.durum, "tamamlandi")
        with self.assertRaises(ValidationError):
            servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)

    def test_siparis_tum_lotlar_bitmeden_tamamlanmaz(self):
        lot = self.yeni_lot(siparis=self.siparis)
        self.yeni_lot(siparis=self.siparis)
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[-1], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("40"), cikis_m2=Decimal("9"))
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "uretimde")


class RaporTesti(TemelVeri):
    def test_personel_ozeti(self):
        for personel, cikis in [(self.ahmet, "9"), (self.ahmet, "8"), (self.ayse, "10")]:
            lot = self.yeni_lot()
            islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=personel)
            servisler.islem_bitir(islem=islem, personel=personel, cikis_kg=Decimal("50"), cikis_m2=Decimal(cikis))
        bugun = timezone.localdate()
        ozet = {s["personel__ad_soyad"]: s for s in raporlar.personel_ozeti(bugun, bugun)}
        self.assertEqual(ozet["Ahmet"]["islem_sayisi"], 2)
        self.assertEqual(ozet["Ahmet"]["fire_m2"], Decimal("3"))
        self.assertEqual(ozet["Ayşe"]["fire_m2"], Decimal("0"))

    def test_acik_islemler_rapora_girmez(self):
        servisler.islem_baslat(lot=self.yeni_lot(), asama=self.asamalar[0], personel=self.ahmet)
        bugun = timezone.localdate()
        self.assertEqual(raporlar.personel_ozeti(bugun, bugun), [])


class EkranTesti(TemelVeri):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tablet", password="x")
        self.client.force_login(self.user)

    def test_giris_yapmadan_yonlendirir(self):
        self.client.logout()
        yanit = self.client.get(reverse("pano"))
        self.assertEqual(yanit.status_code, 302)

    def test_sayfalar_acilir(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        for url in [reverse("pano"), reverse("islem_merkezi"), reverse("yeni_is"), reverse("islem_baslat"),
                    reverse("lot_listesi"), reverse("lot_detay", args=[lot.pk]), reverse("islem_bitir", args=[islem.pk]),
                    reverse("stok_listesi"), reverse("stok_detay", args=[self.ham.pk]), reverse("qr_tara")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        # Tablet hesabı ofis ekranlarına giremez
        for url in [reverse("rapor"), reverse("rapor_excel"), reverse("siparis_listesi"), reverse("stok_yeni")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_yanlis_pin_ile_islem_baslamaz(self):
        lot = self.yeni_lot()
        yanit = self.client.post(reverse("islem_baslat"), {
            "personel": self.ahmet.pk, "pin": "0000", "lot": lot.pk, "asama": self.asamalar[0].pk,
            "makine": self.makine(self.asamalar[0]),
        })
        self.assertContains(yanit, "PIN hatalı")
        self.assertFalse(IslemKaydi.objects.exists())

    def test_ekrandan_baslat_ve_bitir(self):
        lot = self.yeni_lot()
        yanit = self.client.post(reverse("islem_baslat"), {
            "personel": self.ahmet.pk, "pin": "1234", "lot": lot.pk, "asama": self.asamalar[0].pk,
            "makine": self.makine(self.asamalar[0]),
        })
        self.assertRedirects(yanit, reverse("pano"))
        islem = IslemKaydi.objects.get()
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]), {
            "personel": self.ayse.pk, "pin": "5678", "cikis_kg": "48", "cikis_m2": "9.8",
        })
        self.assertRedirects(yanit, reverse("pano"))
        islem.refresh_from_db()
        self.assertEqual(islem.personel, self.ahmet)
        self.assertEqual(islem.bitiren, self.ayse)

    def test_excel_indirilir(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("49"), cikis_m2=Decimal("9.9"))
        self.client.force_login(get_user_model().objects.create_user("ofis", password="x", is_staff=True))
        yanit = self.client.get(reverse("rapor_excel"))
        self.assertEqual(yanit.status_code, 200)
        self.assertIn("spreadsheetml", yanit["Content-Type"])
        self.assertTrue(yanit.content.startswith(b"PK"))


class QrVePwaTesti(TemelVeri):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))

    def test_bekleyen_lot_qr_ile_baslat_ekranina_gider(self):
        lot = self.yeni_lot()
        yanit = self.client.get(reverse("qr_yonlendir", args=[lot.lot_no]))
        self.assertRedirects(yanit, f"{reverse('islem_baslat')}?lot={lot.pk}")

    def test_acik_islemli_lot_qr_ile_bitir_ekranina_gider(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        yanit = self.client.get(reverse("qr_yonlendir", args=[lot.lot_no.lower()]))
        self.assertRedirects(yanit, reverse("islem_bitir", args=[islem.pk]))

    def test_tamamlanan_lot_qr_ile_gecmise_gider(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[-1], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))
        yanit = self.client.get(reverse("qr_yonlendir", args=[lot.lot_no]))
        self.assertRedirects(yanit, reverse("lot_detay", args=[lot.pk]))

    def test_bilinmeyen_lot_404(self):
        self.assertEqual(self.client.get(reverse("qr_yonlendir", args=["UL-1999-9999"])).status_code, 404)

    def test_elle_lot_no_girisi(self):
        lot = self.yeni_lot()
        yanit = self.client.get(reverse("qr_tara"), {"lot_no": lot.lot_no.lower()})
        self.assertRedirects(yanit, reverse("qr_yonlendir", args=[lot.lot_no]), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("qr_tara"), {"lot_no": "UL-1999-9999"}), "bulunamadı")

    def test_etiketler_stok_lotlarina_basilir(self):
        yanit = self.client.get(reverse("etiketler"), {"stok": self.ham.pk})
        self.assertContains(yanit, self.ham.lot_no)
        self.assertContains(yanit, "<svg")
        # Parametresiz: stokta malı kalan lotlar; tamamen kullanılan lot listelenmez
        self.yeni_lot(baslangic_kg=Decimal("100"), baslangic_m2=Decimal("20"))
        self.assertNotContains(self.client.get(reverse("etiketler")), self.ham.lot_no)

    def test_stok_etiketi_okutulunca_stok_sayfasi_acilir(self):
        yanit = self.client.get(reverse("qr_yonlendir", args=[self.ham.lot_no.lower()]))
        self.assertRedirects(yanit, reverse("stok_detay", args=[self.ham.pk]))
        yanit = self.client.get(reverse("qr_tara"), {"lot_no": self.ham.lot_no})
        self.assertRedirects(yanit, reverse("qr_yonlendir", args=[self.ham.lot_no]), fetch_redirect_response=False)

    def test_manifest_ve_service_worker(self):
        self.client.logout()
        manifest = self.client.get(reverse("manifest")).json()
        self.assertEqual(manifest["display"], "standalone")
        self.assertTrue(any(i["sizes"] == "512x512" for i in manifest["icons"]))
        sw = self.client.get(reverse("service_worker"))
        self.assertEqual(sw["Content-Type"], "application/javascript")
        self.assertIn(reverse("cevrimdisi").encode(), sw.content)
        self.assertNotIn(b"&quot;", sw.content)


class YedekTesti(TestCase):
    def test_yedek_sadece_yoneticiye_acik(self):
        User = get_user_model()
        self.client.force_login(User.objects.create_user("tablet", password="x"))
        self.assertEqual(self.client.get(reverse("yedek_indir")).status_code, 302)

    def test_yedek_komutu_eski_yedekleri_temizler(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from unittest import mock

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as klasor:
            kaynak = Path(klasor) / "kaynak.sqlite3"
            baglanti = sqlite3.connect(kaynak)
            baglanti.execute("create table t (x)")
            baglanti.execute("insert into t values (42)")
            baglanti.commit()
            baglanti.close()
            hedef = Path(klasor) / "yedekler"
            hedef.mkdir()
            for i in range(3):
                (hedef / f"uretim_yedek_2020-01-0{i + 1}_0000.sqlite3").write_bytes(b"")
            with mock.patch("uretim.yedek.veritabani_yolu", return_value=kaynak):
                call_command("yedekle", klasor=str(hedef), tut=2, stdout=open(Path(klasor) / "log", "w"))
            yedekler = sorted(hedef.glob("uretim_yedek_*.sqlite3"))
            self.assertEqual(len(yedekler), 2)
            self.assertEqual(sqlite3.connect(yedekler[-1]).execute("select x from t").fetchone(), (42,))


class ExcelAktarimTesti(TestCase):
    def doldur(self, sayfalar):
        """Şablonu oluşturur, verilen sayfalara satır ekler ve dosya nesnesi döner."""
        import io

        from .excel_aktar import sablon_olustur

        kitap = sablon_olustur()
        for ad, satirlar in sayfalar.items():
            for satir in satirlar:
                kitap[ad].append(satir)
        tampon = io.BytesIO()
        kitap.save(tampon)
        tampon.seek(0)
        return tampon

    def tam_dosya(self):
        return self.doldur({
            "Personel": [["Ahmet Yılmaz", "1234", "Kesim", "Evet"], ["Ayşe Demir", "0789", "", ""]],
            "Tedarikçiler": [["Anadolu Deri", "0532 111", ""]],
            "Stok Lotları": [["HD-ESKI-1", "01.10.2026", "Anadolu Deri", "Kuzu", "A", 200, "640", "110,5", ""],
                         ["", "2026-10-02", "Yeni Tedarikçi", "Merinos", "Karışık", "", "1.250,75", 90, ""]],
            "Siparişler": [["SP-ESKI-7", "Örnek Mobilya", "05.10.2026", "200x300 halı", "Kuzu", 4, 24,
                            "30.10.2026", "Üretimde", ""]],
            "Devam Eden İşler": [["L-15", "hd-eski-1", "SP-ESKI-7", 320, 55, 284, "50,5", "Tabaklama", "", ""],
                               ["", "HD-ESKI-1", "", 100, 20, "", "", "", "", ""]],
        })

    def test_onizleme_hicbir_sey_kaydetmez(self):
        from .excel_aktar import ice_aktar

        rapor = ice_aktar(self.tam_dosya(), kaydet=False)
        self.assertEqual(rapor.hatalar, [])
        self.assertEqual(rapor.toplam, 8)
        self.assertFalse(rapor.kaydedildi)
        self.assertFalse(Personel.objects.exists())
        self.assertFalse(UretimLotu.objects.exists())
        self.assertIn("Tedarikçi: Yeni Tedarikçi", rapor.yeni_tanimlar)
        self.assertIn("Deri türü: Merinos", rapor.yeni_tanimlar)

    def test_kaydet_ve_tekrar_yukleme_cogaltmaz(self):
        from .excel_aktar import ice_aktar

        rapor = ice_aktar(self.tam_dosya(), kaydet=True)
        self.assertTrue(rapor.kaydedildi, rapor.hatalar)
        self.assertTrue(Personel.objects.get(ad_soyad="Ayşe Demir").pin_dogru_mu("0789"))
        hd = HamDeriGirisi.objects.get(lot_no="HD-ESKI-1")
        self.assertEqual((hd.kg, hd.m2), (Decimal("640.00"), Decimal("110.50")))
        otomatik = HamDeriGirisi.objects.exclude(lot_no="HD-ESKI-1").get()
        self.assertEqual(otomatik.kg, Decimal("1250.75"))
        self.assertTrue(otomatik.lot_no.startswith("HD-"))
        lot = UretimLotu.objects.get(lot_no="L-15")
        self.assertEqual(lot.son_asama.ad, "Tabaklama")
        self.assertEqual(lot.durum, "bekliyor")
        self.assertEqual(lot.mevcut_m2, Decimal("50.50"))
        self.assertEqual(lot.siparis.siparis_no, "SP-ESKI-7")
        self.assertEqual(Siparis.objects.get().durum, "uretimde")
        # Mevcut kayıtlar güncellenir; numarasız satırlar (otomatik numara) yeniden eklenir.
        ikinci = ice_aktar(self.tam_dosya(), kaydet=True)
        self.assertTrue(ikinci.kaydedildi, ikinci.hatalar)
        self.assertEqual(Personel.objects.count(), 2)
        self.assertEqual(ikinci.guncellenen["Personel"], 2)
        self.assertEqual(UretimLotu.objects.filter(lot_no="L-15").count(), 1)

    def test_hatali_satir_varsa_hicbiri_kaydedilmez(self):
        from .excel_aktar import ice_aktar

        dosya = self.doldur({
            "Personel": [["Ali", "12", "", ""], ["Veli", "5678", "", ""], ["Can", "", "", ""]],
            "Stok Lotları": [["", "", "T", "Kuzu", "", "", "abc", "5", ""],
                         ["", "32.13.2026", "T", "Kuzu", "", "", "5", "5", ""],
                         ["", "", "T", "Kuzu", "Z", "", "5", "5", ""],
                         ["", "", "T", "Kuzu", "", "", "5", "-5", ""]],
            "Devam Eden İşler": [["", "YOK-1", "", 1, 1, "", "", "Uçurma", "", ""]],
        })
        rapor = ice_aktar(dosya, kaydet=True)
        self.assertFalse(rapor.kaydedildi)
        self.assertFalse(Personel.objects.filter(ad_soyad="Veli").exists())
        mesajlar = " | ".join(h[2] for h in rapor.hatalar)
        self.assertIn("PIN 4-6 haneli", mesajlar)
        self.assertIn("Yeni personel için PIN zorunlu", mesajlar)
        self.assertIn("“Kg” sayı olmalı", mesajlar)
        self.assertIn("“Tarih” tarih olmalı", mesajlar)
        self.assertIn("“Kalite” şunlardan biri olmalı", mesajlar)
        self.assertIn("“m²” negatif olamaz", mesajlar)
        self.assertIn("YOK-1", mesajlar)
        satirlar = {(h[0], h[1]) for h in rapor.hatalar}
        self.assertIn(("Personel", 2), satirlar)
        self.assertIn(("Personel", 4), satirlar)

    def test_pin_bastaki_sifir_ipucu(self):
        from .excel_aktar import ice_aktar

        rapor = ice_aktar(self.doldur({"Personel": [["Ali", 123, "", ""]]}))
        self.assertIn("baştaki sıfırı", rapor.hatalar[0][2])

    def test_farkli_baslik_yazimi_ve_sayfa_adi(self):
        import io

        from openpyxl import Workbook

        from .excel_aktar import ice_aktar

        kitap = Workbook()
        ws = kitap.active
        ws.title = "TEDARIKCI"
        ws.append(["Tedarikçi Listesi"])  # başlıktan önce açıklama satırı
        ws.append(["AD", "telefon", "Fazladan Sütun"])
        ws.append(["Deri A.Ş.", 5321112233, "x"])
        tampon = io.BytesIO()
        kitap.save(tampon)
        tampon.seek(0)
        rapor = ice_aktar(tampon, kaydet=True)
        self.assertTrue(rapor.kaydedildi, rapor.hatalar)
        self.assertEqual(Tedarikci.objects.get().telefon, "5321112233")
        self.assertTrue(any("Fazladan Sütun" in u for u in rapor.uyarilar))

    def test_bozuk_dosya(self):
        import io

        from .excel_aktar import ice_aktar

        rapor = ice_aktar(io.BytesIO(b"bu bir excel degil"))
        self.assertIn("okunamadı", rapor.hatalar[0][2])

    def test_ekran_onizle_ve_onayla(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        yonetici = get_user_model().objects.create_superuser("y", password="x")
        self.client.force_login(yonetici)
        self.assertEqual(self.client.get(reverse("sablon_indir")).status_code, 200)
        dosya = SimpleUploadedFile("veri.xlsx", self.tam_dosya().read())
        yanit = self.client.post(reverse("excel_aktar"), {"dosya": dosya})
        self.assertContains(yanit, "Önizleme")
        self.assertContains(yanit, "8 kaydı kaydet")
        self.assertFalse(Personel.objects.exists())
        yanit = self.client.post(reverse("excel_aktar"), {"onayla": "1"})
        self.assertContains(yanit, "Kaydedildi")
        self.assertEqual(Personel.objects.count(), 2)
        # Aynı onay ikinci kez gönderilirse dosya artık yoktur
        yanit = self.client.post(reverse("excel_aktar"), {"onayla": "1"}, follow=True)
        self.assertContains(yanit, "tekrar yükleyin")

    def test_xls_reddedilir_ve_tablet_erisemez(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        self.assertEqual(self.client.get(reverse("excel_aktar")).status_code, 302)
        self.client.force_login(get_user_model().objects.create_superuser("y", password="x"))
        yanit = self.client.post(reverse("excel_aktar"), {"dosya": SimpleUploadedFile("eski.xls", b"x")})
        self.assertContains(yanit, "Farklı Kaydet")


class SiparisEkraniTesti(TemelVeri):
    def setUp(self):
        self.yonetici = get_user_model().objects.create_superuser("y", password="x")
        self.tablet = get_user_model().objects.create_user("tablet", password="x")

    def bitir(self, lot, m2):
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[-1], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("10"), cikis_m2=Decimal(m2))

    def test_ilerleme_m2_ve_lot_sayisina_gore(self):
        self.siparis.toplam_m2 = Decimal("20")
        self.siparis.save()
        l1, l2 = self.yeni_lot(siparis=self.siparis), self.yeni_lot(siparis=self.siparis)
        self.yeni_lot(siparis=self.siparis, durum="iptal")
        servisler.islem_baslat(lot=l2, asama=self.asamalar[2], personel=self.ayse)
        self.bitir(l1, "9")
        i = self.siparis.ilerleme()
        self.assertEqual((i["yuzde"], i["lot_sayisi"], i["biten_lot"]), (45, 2, 1))
        self.assertIn(("Bitti", 1), i["dagilim"])
        self.assertIn((self.asamalar[2].ad + " – çalışılıyor", 1), i["dagilim"])
        self.siparis.toplam_m2 = None
        self.assertEqual(self.siparis.ilerleme()["yuzde"], 50)

    def test_siparis_ekranlari_tablete_kapali(self):
        self.yeni_lot(siparis=self.siparis)
        self.client.force_login(self.tablet)
        self.assertEqual(self.client.get(reverse("siparis_listesi")).status_code, 403)
        self.assertEqual(self.client.get(reverse("siparis_detay", args=[self.siparis.pk])).status_code, 403)
        pano = self.client.get(reverse("pano"))
        self.assertNotContains(pano, reverse("siparis_listesi"))
        self.assertContains(pano, "İşlem Başlat")
        self.client.force_login(self.yonetici)
        self.assertContains(self.client.get(reverse("siparis_detay", args=[self.siparis.pk])), "İşler (1)")
        self.client.force_login(self.tablet)
        self.assertEqual(self.client.get(reverse("siparis_yeni")).status_code, 403)
        self.assertEqual(self.client.post(reverse("siparis_durum", args=[self.siparis.pk]), {"durum": "sevk"}).status_code, 403)

    def test_geciken_siparis_uyarisi_ve_sekmeler(self):
        self.siparis.teslim_tarihi = timezone.localdate() - timedelta(days=3)
        self.siparis.save()
        self.client.force_login(self.yonetici)
        yanit = self.client.get(reverse("siparis_listesi"))
        self.assertContains(yanit, "3 gün gecikti")
        self.assertContains(yanit, "1 sipariş teslim tarihini geçti")
        self.assertNotContains(self.client.get(reverse("siparis_listesi"), {"durum": "sevk"}), self.siparis.siparis_no)
        self.assertContains(self.client.get(reverse("siparis_listesi"), {"ara": "M"}), self.siparis.siparis_no)

    def test_yeni_siparis_yeni_musteriyle(self):
        self.client.force_login(self.yonetici)
        veri = {"musteri": "", "yeni_musteri": "Yıldız Otel", "hali_turu": HaliTuru.objects.get(ad="Lazerli halı").pk,
                "urun": "Lobi halısı", "adet": 1,
                "toplam_m2": "12,5", "teslim_tarihi": "2026-12-01"}
        yanit = self.client.post(reverse("siparis_yeni"), veri)
        yeni = Siparis.objects.get(urun="Lobi halısı")
        self.assertRedirects(yanit, reverse("siparis_detay", args=[yeni.pk]))
        self.assertEqual(yeni.musteri.ad, "Yıldız Otel")
        # Aynı müşteri adı ikinci kez yazılırsa yeni müşteri açılmaz
        self.client.post(reverse("siparis_yeni"), {**veri, "yeni_musteri": "yıldız otel", "urun": "İkinci"})
        self.assertEqual(Musteri.objects.filter(ad__iexact="Yıldız Otel").count(), 1)

    def test_musterisiz_siparis_reddedilir_ve_kayit_olusmaz(self):
        self.client.force_login(self.yonetici)
        yanit = self.client.post(reverse("siparis_yeni"), {"urun": "X", "adet": 1, "teslim_tarihi": ""})
        self.assertContains(yanit, "Bir müşteri seçin")
        self.assertFalse(Siparis.objects.filter(urun="X").exists())
        # Diğer alanlar hatalıysa yazılan yeni müşteri de oluşturulmaz
        self.client.post(reverse("siparis_yeni"), {"yeni_musteri": "Hayalet", "urun": "", "adet": 1})
        self.assertFalse(Musteri.objects.filter(ad="Hayalet").exists())

    def test_sevk_ve_geri_alma(self):
        self.client.force_login(self.yonetici)
        url = reverse("siparis_durum", args=[self.siparis.pk])
        self.client.post(url, {"durum": "sevk"})
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "sevk")
        self.client.post(url, {"durum": "iptal"})  # sevk edilmiş sipariş iptal edilemez
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "sevk")
        self.client.post(url, {"durum": "uretimde"})
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "uretimde")
        self.assertEqual(self.client.get(url).status_code, 405)


class OndalikGirisTesti(TemelVeri):
    def test_lazerde_cikis_olcusu_virgul_ve_nokta_kabul_edilir(self):
        from .forms import IslemBitirForm

        for en, beklenen in [("120,5", (Decimal("120.5"), Decimal("200"))), ("120.5", (Decimal("120.5"), Decimal("200")))]:
            f = IslemBitirForm({"personel": self.ahmet.pk, "pin": "1234", "cikis_en": en, "cikis_boy": "200"}, lazer=True)
            self.assertTrue(f.is_valid(), f.errors)
            self.assertEqual(f.cleaned_data["cikis_olcu"], beklenen)
        self.assertFalse(IslemBitirForm({"personel": self.ahmet.pk, "pin": "1234", "cikis_en": "-1", "cikis_boy": "1"},
                                        lazer=True).is_valid())
        self.assertFalse(IslemBitirForm({"personel": self.ahmet.pk, "pin": "1234", "cikis_en": "100"}, lazer=True).is_valid())

    def test_lazer_disinda_olcu_ve_kg_sorulmaz(self):
        zigzag = Asama.objects.get(ad="Zig-zag")
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        lot = self.yeni_lot(baslangic_kg=Decimal("47.50"))
        islem = servisler.islem_baslat(lot=lot, asama=zigzag, personel=self.ahmet)
        sayfa = self.client.get(reverse("islem_bitir", args=[islem.pk]))
        self.assertNotContains(sayfa, 'name="cikis_kg"')
        self.assertNotContains(sayfa, 'name="fire_m2"')
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]), {"personel": self.ahmet.pk, "pin": "1234"})
        self.assertRedirects(yanit, reverse("pano"))
        islem.refresh_from_db()
        self.assertEqual((islem.cikis_kg, islem.cikis_m2), (Decimal("47.50"), Decimal("10.00")))


class SiparisDurumuTesti(TemelVeri):
    def test_tamamlanan_siparise_yeni_lot_eklenince_uretime_doner(self):
        l1 = self.yeni_lot(siparis=self.siparis)
        islem = servisler.islem_baslat(lot=l1, asama=self.asamalar[-1], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "tamamlandi")
        self.yeni_lot(siparis=self.siparis)
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "uretimde")

    def test_sevk_edilmis_siparis_lot_eklenince_degismez(self):
        self.siparis.durum = "sevk"
        self.siparis.save()
        self.yeni_lot(siparis=self.siparis)
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "sevk")


class OfisHesabiTesti(TestCase):
    def test_personel_durumlu_ofis_hesabi_yedek_ve_aktarima_giremez(self):
        from django.contrib.auth.models import Permission

        ofis = get_user_model().objects.create_user("ofis", password="x", is_staff=True)
        ofis.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="uretim", codename__in=["add_siparis", "change_siparis", "view_siparis"]))
        self.client.force_login(ofis)
        for ad in ("yedek_indir", "excel_aktar", "sablon_indir"):
            with self.subTest(ad=ad):
                self.assertEqual(self.client.get(reverse(ad)).status_code, 302)
        self.assertEqual(self.client.get(reverse("siparis_yeni")).status_code, 200)
        pano = self.client.get(reverse("pano"))
        self.assertContains(pano, "Yönetim")
        self.assertNotContains(pano, "💾 Yedek")

    def test_yonetici_yedek_indirir(self):
        self.client.force_login(get_user_model().objects.create_superuser("y", password="x"))
        yanit = self.client.get(reverse("sablon_indir"))
        self.assertEqual(yanit.status_code, 200)


class YeniIsAkisiTesti(TemelVeri):
    """Çalışan siparişi seçer, stok lotlarını okutur, iş kendiliğinden açılır."""

    def setUp(self):
        self.ham2 = HamDeriGirisi.objects.create(
            tedarikci=self.ham.tedarikci, deri_turu=self.ham.deri_turu, kg=Decimal("40"), m2=Decimal("8"),
        )

    def test_iki_stok_lotundan_is_acilir_ve_ilk_asama_baslar(self):
        islem = servisler.yeni_is_baslat(
            personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
            kaynaklar=[(self.ham, Decimal("30"), Decimal("6")), (self.ham2, Decimal("10"), Decimal("2.5"))],
        )
        lot = islem.lot
        self.assertEqual((lot.baslangic_kg, lot.baslangic_m2), (Decimal("40"), Decimal("8.5")))
        self.assertEqual(lot.durum, "islemde")
        self.assertEqual(lot.siparis, self.siparis)
        self.assertEqual(sorted(lot.kaynak_listesi.split(", ")), sorted([self.ham.lot_no, self.ham2.lot_no]))
        self.assertEqual((self.ham.kalan_kg, self.ham2.kalan_m2), (Decimal("70"), Decimal("5.5")))
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "uretimde")
        self.assertEqual([i.lot_no for i in self.ham2.aktif_isler()], [lot.lot_no])

    def test_ayni_lot_iki_kez_okutulursa_toplanir(self):
        islem = servisler.yeni_is_baslat(
            personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
            kaynaklar=[(self.ham, Decimal("5"), Decimal("1")), (self.ham, Decimal("5"), Decimal("1"))],
        )
        kaynak = islem.lot.kaynaklar.get()
        self.assertEqual((kaynak.kg, kaynak.m2), (Decimal("10"), Decimal("2")))

    def test_stoktan_fazla_alinamaz_ve_hicbir_sey_kaydedilmez(self):
        with self.assertRaises(ValidationError) as hata:
            servisler.yeni_is_baslat(
                personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
                kaynaklar=[(self.ham, Decimal("5"), Decimal("1")), (self.ham2, Decimal("41"), Decimal("1"))],
            )
        self.assertIn("stokta 40.00 kg", " ".join(hata.exception.messages))
        self.assertFalse(UretimLotu.objects.exists())
        self.assertFalse(LotKaynagi.objects.exists())

    def test_sevk_edilmis_siparise_is_acilamaz(self):
        self.siparis.durum = "sevk"
        self.siparis.save()
        with self.assertRaises(ValidationError):
            servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
                                     kaynaklar=[(self.ham, Decimal("1"), Decimal("1"))])

    def veri(self, **kw):
        v = {"personel": self.ahmet.pk, "pin": "1234", "siparis": self.siparis.pk, "asama": self.asamalar[0].pk,
             "makine": self.makine(self.asamalar[0]),
             "kaynak-TOTAL_FORMS": "4", "kaynak-INITIAL_FORMS": "0", "kaynak-MIN_NUM_FORMS": "0",
             "kaynak-MAX_NUM_FORMS": "10"}
        v.update(kw)
        return v

    def test_ekrandan_yeni_is(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        sayfa = self.client.get(reverse("yeni_is"), {"stok": self.ham.lot_no.lower()})
        self.assertContains(sayfa, f'value="{self.ham.lot_no}"')
        yanit = self.client.post(reverse("yeni_is"), self.veri(**{
            "kaynak-0-stok_no": self.ham.lot_no, "kaynak-0-kg": "20,5", "kaynak-0-m2": "4",
            "kaynak-1-stok_no": self.ham2.lot_no.lower(), "kaynak-1-m2": "2",
        }))
        self.assertRedirects(yanit, reverse("pano"))
        lot = UretimLotu.objects.get()
        self.assertEqual(lot.kaynaklar.count(), 2)
        self.assertEqual(lot.baslangic_m2, Decimal("6"))
        self.assertEqual(lot.islemler.get().personel, self.ahmet)

    def test_ekranda_hatalar(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        from .models import SistemAyari
        SistemAyari.yukle()
        SistemAyari.objects.update(stok_zorunlu=True)
        bos = self.client.post(reverse("yeni_is"), self.veri())
        self.assertContains(bos, "En az bir stok lotundan malzeme girin")
        yok = self.client.post(reverse("yeni_is"), self.veri(**{"kaynak-0-stok_no": "HD-1999-0001", "kaynak-0-m2": "1"}))
        self.assertContains(yok, "stok lotu bulunamadı")
        miktarsiz = self.client.post(reverse("yeni_is"), self.veri(**{"kaynak-0-stok_no": self.ham.lot_no}))
        self.assertContains(miktarsiz, "Alınan miktarı girin")
        fazla = self.client.post(reverse("yeni_is"), self.veri(**{"kaynak-0-stok_no": self.ham.lot_no, "kaynak-0-m2": "999"}))
        self.assertContains(fazla, "stokta")
        pin = self.client.post(reverse("yeni_is"), self.veri(pin="0000", **{"kaynak-0-stok_no": self.ham.lot_no, "kaynak-0-m2": "1"}))
        self.assertContains(pin, "PIN hatalı")
        self.assertFalse(UretimLotu.objects.exists())

    def test_stok_bilgi_ve_stok_sayfasi(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        bilgi = self.client.get(reverse("stok_bilgi", args=[self.ham2.lot_no])).json()
        self.assertEqual((bilgi["kalan_kg"], bilgi["kalan_m2"]), ("40.00", "8.00"))
        self.assertEqual(self.client.get(reverse("stok_bilgi", args=["YOK"])).status_code, 404)
        islem = servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
                                         kaynaklar=[(self.ham2, Decimal("10"), Decimal("2"))])
        sayfa = self.client.get(reverse("stok_detay", args=[self.ham2.pk]))
        self.assertContains(sayfa, islem.lot.lot_no)
        self.assertContains(sayfa, reverse("islem_bitir", args=[islem.pk]))
        self.assertContains(sayfa, "Bu lottan yeni iş başlat")
        self.assertContains(self.client.get(reverse("stok_listesi")), self.ham2.lot_no)

    def test_stok_girisi_formu_yeni_tedarikciyle(self):
        self.client.force_login(get_user_model().objects.create_superuser("y", password="x"))
        yanit = self.client.post(reverse("stok_yeni"), {
            "yeni_tedarikci": "Ege Deri", "tarih": "2026-10-20", "deri_turu": self.ham.deri_turu.pk, "kalite": "A",
            "kg": "480,5", "giris_birimi": "m2", "giris_miktari": "82",
        })
        stok = HamDeriGirisi.objects.get(tedarikci__ad="Ege Deri")
        self.assertRedirects(yanit, reverse("stok_detay", args=[stok.pk]))
        self.assertEqual((stok.kg, stok.m2), (Decimal("480.50"), Decimal("82.00")))
        self.assertTrue(stok.lot_no.startswith("HD-"))


class RolMenuTesti(TestCase):
    def test_ofis_ve_tablet_menuleri_ayrik(self):
        from django.contrib.auth.models import Permission

        User = get_user_model()
        tablet = User.objects.create_user("tablet", password="x")
        ofis = User.objects.create_user("ofis", password="x", is_staff=True)
        ofis.user_permissions.add(*Permission.objects.filter(content_type__app_label="uretim",
                                                              codename__in=["view_siparis", "add_siparis"]))
        self.client.force_login(tablet)
        pano = self.client.get(reverse("pano")).content.decode()
        self.assertIn(reverse("islem_merkezi"), pano)
        self.assertNotIn(reverse("siparis_listesi"), pano)
        self.assertNotIn(reverse("rapor"), pano)
        self.client.force_login(ofis)
        pano = self.client.get(reverse("pano")).content.decode()
        self.assertNotIn(reverse("islem_merkezi"), pano)
        self.assertNotIn(reverse("qr_tara"), pano)
        self.assertIn(reverse("siparis_listesi"), pano)
        self.assertIn(reverse("siparis_yeni"), pano)
        self.assertIn(reverse("rapor"), pano)


class EskiExcelSablonuTesti(TestCase):
    def test_eski_sayfa_ve_sutun_adlari_okunur(self):
        import io

        from openpyxl import Workbook

        from .excel_aktar import ice_aktar

        kitap = Workbook()
        ham = kitap.active
        ham.title = "Ham Deri"
        ham.append(["Lot No", "Tedarikçi", "Deri Türü", "Kg", "m²"])
        ham.append(["ESKI-1", "T", "Kuzu", 100, 20])
        lotlar = kitap.create_sheet("Üretim Lotları")
        lotlar.append(["Lot No", "Ham Deri Lot No", "Başlangıç kg", "Başlangıç m²"])
        lotlar.append(["UL-ESKI-9", "ESKI-1", 40, 8])
        tampon = io.BytesIO()
        kitap.save(tampon)
        tampon.seek(0)
        rapor = ice_aktar(tampon, kaydet=True)
        self.assertTrue(rapor.kaydedildi, rapor.hatalar)
        lot = UretimLotu.objects.get(lot_no="UL-ESKI-9")
        self.assertEqual(lot.kaynak_listesi, "ESKI-1")
        self.assertEqual(HamDeriGirisi.objects.get(lot_no="ESKI-1").kalan_m2, Decimal("12.00"))


class StokDuzeltmeVeMalzemeTesti(TemelVeri):
    def setUp(self):
        from .models import Malzeme

        self.krom = Malzeme.objects.create(ad="Krom tuzu", kategori="kimyasal", birim="kg", min_stok=Decimal("20"))

    def test_deri_fire_ve_sayim(self):
        servisler.deri_duzelt(ham_deri=self.ham, neden="fire", kg=Decimal("10"), m2=Decimal("2"))
        self.assertEqual((self.ham.kalan_kg, self.ham.kalan_m2), (Decimal("90"), Decimal("18")))
        servisler.deri_duzelt(ham_deri=self.ham, neden="sayim", kg=Decimal("85"), m2=Decimal("18"))
        self.assertEqual(self.ham.kalan_kg, Decimal("85"))
        with self.assertRaises(ValidationError):
            servisler.deri_duzelt(ham_deri=self.ham, neden="fire", kg=Decimal("86"), m2=Decimal("0"))
        with self.assertRaises(ValidationError):
            servisler.deri_duzelt(ham_deri=self.ham, neden="sayim", kg=Decimal("85"), m2=Decimal("18"))
        # Yeni iş, düzeltilmiş stoğu aşamaz
        with self.assertRaises(ValidationError):
            servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.asamalar[0],
                                     kaynaklar=[(self.ham, Decimal("86"), Decimal("1"))])

    def test_malzeme_giris_kullanim_duzeltme_ve_uyari(self):
        servisler.malzeme_giris(malzeme=self.krom, miktar=Decimal("50"))
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[2], personel=self.ahmet)
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("50"), cikis_m2=Decimal("10"),
                              malzemeler=[(self.krom, Decimal("32.5"))])
        self.assertEqual(self.krom.stok, Decimal("17.5"))
        self.assertTrue(self.krom.azaldi_mi)
        kullanim = self.krom.hareketler.get(tur="kullanim")
        self.assertEqual((kullanim.islem, kullanim.personel), (islem, self.ahmet))
        servisler.malzeme_duzelt(malzeme=self.krom, neden="sayim", miktar=Decimal("15"))
        self.assertEqual(self.krom.stok, Decimal("15"))
        servisler.malzeme_duzelt(malzeme=self.krom, neden="fire", miktar=Decimal("5"))
        self.assertEqual(self.krom.stok, Decimal("10"))
        from . import uyarilar
        self.assertIn("Krom tuzu", [u.ad for u in uyarilar.azalan_stoklar()])

    def test_deri_turu_toplam_ozeti_ve_azalma(self):
        from . import uyarilar
        tur = self.ham.deri_turu
        tur.min_kg = Decimal("80")
        tur.save()
        self.assertNotIn("Kuzu", [u.ad for u in uyarilar.azalan_stoklar()])
        self.yeni_lot(baslangic_kg=Decimal("30"), baslangic_m2=Decimal("5"))
        ozet = uyarilar.deri_ozeti()[tur.pk]
        self.assertEqual((ozet["kalan_kg"], ozet["kalan_m2"]), (Decimal("70"), Decimal("15")))
        self.assertIn("Kuzu", [u.ad for u in uyarilar.azalan_stoklar()])

    def test_bitir_ekraninda_malzeme(self):
        servisler.malzeme_giris(malzeme=self.krom, miktar=Decimal("50"))
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        veri = {"personel": self.ahmet.pk, "pin": "1234", "cikis_kg": "49", "cikis_m2": "9,5",
                "malzeme-TOTAL_FORMS": "3", "malzeme-INITIAL_FORMS": "0",
                "malzeme-0-malzeme": self.krom.pk, "malzeme-0-miktar": "2,5"}
        eksik = self.client.post(reverse("islem_bitir", args=[islem.pk]), {**veri, "malzeme-0-miktar": ""})
        self.assertContains(eksik, "Kullanılan miktarı girin")
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]) + "?geri=/istasyon/1/", veri)
        self.assertRedirects(yanit, "/istasyon/1/", fetch_redirect_response=False)
        self.assertEqual(self.krom.stok, Decimal("47.5"))

    def test_disari_geri_adresi_yok_sayilir(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]) + "?geri=https://kotu.example/",
                                 {"personel": self.ahmet.pk, "pin": "1234", "cikis_kg": "1", "cikis_m2": "1"})
        self.assertRedirects(yanit, reverse("pano"))

    def test_malzeme_ekranlari(self):
        self.client.force_login(get_user_model().objects.create_superuser("y", password="x"))
        yanit = self.client.post(reverse("malzeme_yeni"), {"ad": "Naylon iplik", "kategori": "iplik", "birim": "makara",
                                                           "min_stok": "10"})
        from .models import Malzeme
        iplik = Malzeme.objects.get(ad="Naylon iplik")
        self.assertRedirects(yanit, f"{reverse('malzeme_giris')}?malzeme={iplik.pk}")
        self.client.post(reverse("malzeme_giris"), {"malzeme": iplik.pk, "miktar": "24"})
        self.assertEqual(iplik.stok, Decimal("24"))
        self.client.post(reverse("malzeme_duzelt", args=[iplik.pk]), {"neden": "sayim", "miktar": "20"})
        self.assertEqual(iplik.stok, Decimal("20"))
        self.assertContains(self.client.get(reverse("malzeme_listesi")), "Naylon iplik")
        self.assertContains(self.client.get(reverse("malzeme_detay", args=[iplik.pk])), "Sayım farkı")
        yanit = self.client.post(reverse("deri_duzelt", args=[self.ham.pk]), {"neden": "fire", "kg": "5", "m2": "1"})
        self.assertRedirects(yanit, reverse("stok_detay", args=[self.ham.pk]))
        self.assertContains(self.client.get(reverse("stok_detay", args=[self.ham.pk])), "Fire / bozulma")
        # Tablet stok düzeltemez
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        self.assertEqual(self.client.get(reverse("deri_duzelt", args=[self.ham.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("malzeme_giris")).status_code, 403)


class IstasyonUyariTesti(TemelVeri):
    def test_yeni_siparis_ilk_istasyona_duser(self):
        from . import uyarilar
        ilk, ikinci = self.asamalar[0], self.asamalar[1]
        self.assertEqual([k.siparis for k in uyarilar.gelenler(ilk) if k.tur == "siparis"], [self.siparis])
        self.assertEqual(uyarilar.gelenler(ikinci), [])
        # İş açılınca sipariş ilk istasyonun listesinden kalkar
        servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=ilk,
                                 kaynaklar=[(self.ham, Decimal("5"), Decimal("1"))])
        self.assertEqual(uyarilar.gelenler(ilk), [])

    def test_asama_bitince_siradaki_istasyona_duser(self):
        from . import uyarilar
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        self.assertEqual([k.lot for k in uyarilar.calisilanlar(self.asamalar[0])], [lot])
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))
        self.assertEqual([k.lot for k in uyarilar.gelenler(self.asamalar[1])], [lot])
        self.assertEqual(uyarilar.calisilanlar(self.asamalar[0]), [])

    def test_calisma_ve_bekleme_sure_asimi(self):
        from . import uyarilar
        ilk, ikinci = self.asamalar[0], self.asamalar[1]
        ilk.azami_sure_saat = Decimal("2")
        ilk.save()
        ikinci.azami_bekleme_saat = Decimal("4")
        ikinci.save()
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=ilk, personel=self.ahmet)
        IslemKaydi.objects.filter(pk=islem.pk).update(baslangic=timezone.now() - timedelta(hours=3))
        kalem = uyarilar.calisilanlar(ilk)[0]
        self.assertTrue(kalem.gecikti)
        self.assertEqual(kalem.asim_metni, "1 sa 0 dk")
        islem.refresh_from_db()
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=Decimal("1"), cikis_m2=Decimal("1"))
        self.assertFalse(uyarilar.gelenler(ikinci)[0].gecikti)
        IslemKaydi.objects.filter(pk=islem.pk).update(bitis=timezone.now() - timedelta(hours=5))
        self.assertTrue(uyarilar.gelenler(ikinci)[0].gecikti)
        self.assertEqual(len(uyarilar.gecikmeler()), 1)

    def test_istasyon_ekranlari(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        ilk = self.asamalar[0]
        secim = self.client.get(reverse("istasyon_secimi"))
        self.assertContains(secim, ilk.ad)
        self.assertContains(secim, "1</b> iş bekliyor")
        ekran = self.client.get(reverse("istasyon_ekrani", args=[ilk.pk]))
        self.assertContains(ekran, "Yeni sipariş")
        self.assertContains(ekran, f"?siparis={self.siparis.pk}&amp;geri=/istasyon/{ilk.pk}/")
        parca = self.client.get(reverse("istasyon_parca", args=[ilk.pk]))
        self.assertContains(parca, f's{self.siparis.pk}')
        self.assertNotContains(parca, "<html")
        self.assertEqual(self.client.get(reverse("istasyon_ekrani", args=[9999])).status_code, 404)

    def test_panoda_gecikme_karti(self):
        ilk = self.asamalar[0]
        ilk.azami_bekleme_saat = Decimal("1")
        ilk.save()
        Siparis.objects.filter(pk=self.siparis.pk).update(olusturma=timezone.now() - timedelta(hours=2))
        self.client.force_login(get_user_model().objects.create_superuser("y", password="x"))
        pano = self.client.get(reverse("pano"))
        self.assertContains(pano, "Süre sınırını aşan işler (1)")
        self.assertContains(pano, "bekleme 1 sa 0 dk aştı")


class MalzemeEtiketiTesti(TemelVeri):
    def setUp(self):
        from .models import Malzeme

        self.krom = Malzeme.objects.create(ad="Krom tuzu", kategori="kimyasal", birim="kg")
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))

    def test_malzemeye_otomatik_kod_ve_etiket(self):
        from .models import Malzeme

        self.assertEqual(self.krom.kod, "MZ-0001")
        self.assertEqual(Malzeme.objects.create(ad="İplik").kod, "MZ-0002")
        yanit = self.client.get(reverse("etiketler"), {"malzeme": self.krom.pk, "kopya": "3"})
        self.assertContains(yanit, "MZ-0001", count=3)
        self.assertContains(yanit, "Krom tuzu", count=3)
        from django.test import RequestFactory

        from .qr import lot_adresi
        self.assertEqual(lot_adresi(RequestFactory().get("/"), self.krom), "http://testserver/q/MZ-0001/")
        # Malzeme etiketi istenince deri lotları basılmaz
        self.assertNotContains(yanit, self.ham.lot_no)
        self.assertEqual(self.client.get(reverse("etiketler"), {"malzeme": self.krom.pk, "kopya": "999"})
                         .content.decode().count('class="etiket-no"'), 50)

    def test_malzeme_etiketi_okutulunca_malzeme_sayfasi(self):
        self.assertRedirects(self.client.get(reverse("qr_yonlendir", args=["mz-0001"])),
                             reverse("malzeme_detay", args=[self.krom.pk]))
        self.assertRedirects(self.client.get(reverse("qr_tara"), {"lot_no": "MZ-0001"}),
                             reverse("qr_yonlendir", args=["MZ-0001"]), fetch_redirect_response=False)

    def test_bitir_ekraninda_malzeme_kodlari(self):
        lot = self.yeni_lot()
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        sayfa = self.client.get(reverse("islem_bitir", args=[islem.pk]))
        self.assertContains(sayfa, f'"MZ-0001": {self.krom.pk}')
        self.assertContains(sayfa, "malzeme-tara")


class HaliTuruRotaTesti(TemelVeri):
    """Halı türüne göre istasyon sırası, alternatif istasyonlar (Biye / Lanfel) ve makine seçimi."""

    def ist(self, ad):
        return Asama.objects.get(ad=ad)

    def siparis_ac(self, tur_adi):
        return Siparis.objects.create(
            musteri=self.siparis.musteri, urun="Halı", hali_turu=HaliTuru.objects.get(ad=tur_adi),
            teslim_tarihi=timezone.localdate() + timedelta(days=5),
        )

    def asamayi_yap(self, lot, asama):
        islem = servisler.islem_baslat(lot=lot, asama=asama, personel=self.ahmet,
                                       makine=asama.makineler.first())
        servisler.islem_bitir(islem=islem, personel=self.ahmet, cikis_kg=lot.mevcut_kg, cikis_m2=lot.mevcut_m2)
        lot.refresh_from_db()
        return islem

    def test_istasyonlar_ve_makineler_yuklendi(self):
        self.assertEqual([a.ad for a in Asama.objects.filter(aktif=True)],
                         ["Lazer kesim 1", "Lazer kesim 2", "Nakış", "Kaplama", "Zig-zag", "Biye", "Lanfel", "Kenar dikişi"])
        self.assertEqual(self.ist("Zig-zag").makineler.count(), 2)
        self.assertEqual([m.ad for m in self.ist("Lazer kesim 1").makineler.all()], ["Lazer 1"])
        self.assertEqual([m.ad for m in self.ist("Lazer kesim 2").makineler.all()], ["Lazer 2"])
        self.assertEqual(HaliTuru.objects.get(ad="Nakışlı halı").rota_metni(),
                         "Nakış → Lazer kesim 1 / Lazer kesim 2 → Zig-zag → Biye / Lanfel")

    def test_lazerli_hali_biye_ya_da_lanfel_ile_biter(self):
        sp = self.siparis_ac("Lazerli halı")
        self.assertEqual(sp.ilk_asamalar(), [self.ist("Lazer kesim 1"), self.ist("Lazer kesim 2")])
        lot = self.yeni_lot(siparis=sp)
        self.asamayi_yap(lot, self.ist("Lazer kesim 1"))
        self.assertEqual(lot.siradaki_asamalar, [self.ist("Zig-zag")])
        self.asamayi_yap(lot, self.ist("Zig-zag"))
        self.assertEqual(lot.durum, "bekliyor")
        self.assertEqual(lot.siradaki_metni, "Biye / Lanfel")
        # İş iki istasyonun ekranına da düşer
        self.assertEqual([k.lot for k in uyarilar.gelenler(self.ist("Biye"))], [lot])
        self.assertEqual([k.lot for k in uyarilar.gelenler(self.ist("Lanfel"))], [lot])
        self.asamayi_yap(lot, self.ist("Lanfel"))
        self.assertEqual(lot.durum, "tamamlandi")
        self.assertEqual(uyarilar.gelenler(self.ist("Biye")), [])

    def test_nakisli_hali_nakistan_baslar(self):
        sp = self.siparis_ac("Nakışlı halı")
        self.assertIn(sp, [k.siparis for k in uyarilar.gelenler(self.ist("Nakış")) if k.tur == "siparis"])
        self.assertNotIn(sp, [k.siparis for k in uyarilar.gelenler(self.ist("Lazer kesim 1"))])
        lot = self.yeni_lot(siparis=sp)
        self.asamayi_yap(lot, self.ist("Nakış"))
        self.assertEqual(lot.siradaki_asamalar, [self.ist("Lazer kesim 1"), self.ist("Lazer kesim 2")])

    def test_pelus_hali_biye_ya_da_kenar_dikisiyle_biter(self):
        sp = self.siparis_ac("Peluş halı")
        self.assertEqual(sp.ilk_asamalar(), [self.ist("Kaplama")])
        lot = self.yeni_lot(siparis=sp)
        self.asamayi_yap(lot, self.ist("Kaplama"))
        self.assertEqual(lot.siradaki_asamalar, [self.ist("Lazer kesim 1"), self.ist("Lazer kesim 2")])
        self.asamayi_yap(lot, self.ist("Lazer kesim 1"))
        self.asamayi_yap(lot, self.ist("Zig-zag"))
        self.assertEqual(lot.siradaki_metni, "Biye / Kenar dikişi")
        self.asamayi_yap(lot, self.ist("Kenar dikişi"))
        self.assertEqual(lot.durum, "tamamlandi")

    def test_suni_deri_hali_lazerden_baslar(self):
        sp = self.siparis_ac("Suni deri halı")
        self.assertEqual(sp.ilk_asamalar(), [self.ist("Lazer kesim 1"), self.ist("Lazer kesim 2")])
        lot = self.yeni_lot(siparis=sp)
        self.asamayi_yap(lot, self.ist("Lazer kesim 2"))
        self.assertEqual(lot.siradaki_metni, "Zig-zag")
        self.asamayi_yap(lot, self.ist("Zig-zag"))
        self.assertEqual(lot.siradaki_metni, "Biye / Kenar dikişi")
        self.asamayi_yap(lot, self.ist("Biye"))
        self.assertEqual(lot.durum, "tamamlandi")

    def test_makine_baska_istasyonun_olamaz(self):
        lot = self.yeni_lot(siparis=self.siparis_ac("Peluş halı"))
        lazer = self.ist("Lazer kesim 1")
        with self.assertRaises(ValidationError):
            servisler.islem_baslat(lot=lot, asama=lazer, personel=self.ahmet,
                                   makine=self.ist("Zig-zag").makineler.first())

    def test_ekranda_makine_zorunlu_ve_ilk_istasyon_otomatik(self):
        sp = self.siparis_ac("Lazerli halı")
        self.client.force_login(get_user_model().objects.create_user("tablet2", password="x"))
        v = {"personel": self.ahmet.pk, "pin": "1234", "siparis": sp.pk, "asama": "",
             "kaynak-TOTAL_FORMS": 1, "kaynak-INITIAL_FORMS": 0,
             "kaynak-0-stok_no": self.ham.lot_no, "kaynak-0-kg": "10", "kaynak-0-m2": "2"}
        self.assertContains(self.client.post(reverse("yeni_is"), v), "hangi makinede çalıştığınızı seçin")
        lazer2 = Makine.objects.get(ad="Lazer 2")
        self.assertRedirects(self.client.post(reverse("yeni_is"), {**v, "makine": lazer2.pk}), reverse("pano"))
        islem = IslemKaydi.objects.get(lot__siparis=sp)
        self.assertEqual((islem.asama.ad, islem.makine), ("Lazer kesim 2", lazer2))

    def test_makine_raporu(self):
        lot = self.yeni_lot(siparis=self.siparis_ac("Peluş halı"))
        self.asamayi_yap(lot, self.ist("Lazer kesim 1"))
        bugun = timezone.localdate()
        satirlar = raporlar.makine_ozeti(bugun, bugun)
        self.assertEqual([(s["makine__ad"], s["islem_sayisi"]) for s in satirlar], [("Lazer 1", 1)])


class StokBirimiVeBeklemeTesti(TemelVeri):
    def stok_gir(self, **alanlar):
        kullanici, _ = get_user_model().objects.get_or_create(username="ofis9", is_staff=True, is_superuser=True)
        self.client.force_login(kullanici)
        veri = {"tedarikci": Tedarikci.objects.first().pk, "tarih": "2026-10-26",
                "deri_turu": DeriTuru.objects.get(ad="Kuzu").pk, "kalite": "A", **alanlar}
        return self.client.post(reverse("stok_yeni"), veri)

    def test_ayak_girisi_m2ye_cevrilir(self):
        self.stok_gir(giris_birimi="ayak", giris_miktari="1000")
        h = HamDeriGirisi.objects.latest("pk")
        self.assertEqual((h.m2, h.kg, h.giris_metni), (Decimal("92.90"), Decimal("0"), "1000 ayak (ft²)"))

    def test_metretul_girisi_en_ile_m2ye_cevrilir(self):
        self.assertContains(self.stok_gir(giris_birimi="mtul", giris_miktari="50"), "Enini (cm) yazın")
        self.stok_gir(giris_birimi="mtul", giris_miktari="50", en_cm="140")
        h = HamDeriGirisi.objects.latest("pk")
        self.assertEqual((h.m2, h.giris_metni), (Decimal("70.00"), "140 cm × 50 m"))
        # Plaka: en × boy cm × adet
        self.stok_gir(giris_birimi="plaka", giris_miktari="150", en_cm="100", adet="3")
        h = HamDeriGirisi.objects.latest("pk")
        self.assertEqual(h.m2, Decimal("4.50"))

    def test_istasyonlar_arasi_bekleme_ve_personel_istasyon(self):
        lazer, zigzag = Asama.objects.get(ad="Lazer kesim 1"), Asama.objects.get(ad="Zig-zag")
        lot = self.yeni_lot()
        i1 = servisler.islem_baslat(lot=lot, asama=lazer, personel=self.ahmet, makine=lazer.makineler.first())
        servisler.islem_bitir(islem=i1, personel=self.ahmet, cikis_kg=lot.baslangic_kg, cikis_m2=lot.baslangic_m2)
        i2 = servisler.islem_baslat(lot=lot, asama=zigzag, personel=self.ayse, makine=zigzag.makineler.first())
        # Lazer 1 saat önce bitmiş, Zig-zag şimdi başlamış gibi
        IslemKaydi.objects.filter(pk=i1.pk).update(bitis=i2.baslangic - timedelta(hours=1, minutes=30))
        bugun = timezone.localdate()
        satir = raporlar.bekleme_ozeti(bugun, bugun)[0]
        self.assertEqual((satir["gecis"], satir["sayi"]), ("Lazer kesim 1 → Zig-zag", 1))
        self.assertEqual(round(satir["ortalama"].total_seconds() / 60), 90)
        self.assertEqual([(s["personel__ad_soyad"], s["asama__ad"]) for s in raporlar.personel_istasyon_ozeti(bugun, bugun)],
                         [("Ahmet", "Lazer kesim 1")])
        self.client.force_login(get_user_model().objects.create_superuser("ofis8", password="x"))
        self.assertContains(self.client.get(reverse("lot_detay", args=[lot.pk])), "1 sa 30 dk")
        self.assertContains(self.client.get(reverse("rapor")), "Lazer kesim 1 → Zig-zag")

    def test_excelden_ayak_girisi(self):
        from io import BytesIO

        from .excel_aktar import ice_aktar, sablon_olustur

        kitap = sablon_olustur()
        ws = kitap["Stok Lotları"]
        basliklar = [h.value for h in ws[1]]
        satir = {"Tedarikçi": "T", "Deri Türü": "Kuzu", "Giriş Birimi": "Ayak", "Giriş Miktarı": 500}
        ws.append([satir.get(b) for b in basliklar])
        dosya = BytesIO()
        kitap.save(dosya)
        dosya.seek(0)
        rapor = ice_aktar(dosya, kaydet=True)
        self.assertEqual(rapor.hatalar, [])
        h = HamDeriGirisi.objects.latest("pk")
        self.assertEqual((h.giris_birimi, h.m2), ("ayak", Decimal("46.45")))


class TabletGirisTesti(TestCase):
    def test_giris_istasyon_ve_cikis_kaydedilir(self):
        from .models import OturumKaydi

        User = get_user_model()
        User.objects.create_user("lazer-tablet", password="gizli12345")
        ofis = User.objects.create_superuser("patron", password="x")
        android = {"HTTP_USER_AGENT": "Mozilla/5.0 (Linux; Android 13) Chrome/120 Mobile"}
        self.client.post(reverse("login"), {"username": "lazer-tablet", "password": "gizli12345"}, **android)
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.client.get(reverse("istasyon_ekrani", args=[lazer.pk]), **android)
        self.client.get(reverse("istasyon_ekrani", args=[lazer.pk]), **android)  # yenileme: tekrar yazılmaz
        self.client.get(reverse("istasyon_parca", args=[lazer.pk]), **android)
        self.client.post(reverse("logout"), **android)
        self.assertEqual(list(OturumKaydi.objects.order_by("zaman", "pk").values_list("tur", "asama__ad", "cihaz")),
                         [("giris", None, "Android · Chrome"), ("istasyon", "Lazer kesim 1", "Android · Chrome"),
                          ("cikis", None, "Android · Chrome")])
        self.client.force_login(ofis)
        sayfa = self.client.get(reverse("tablet_girisleri"))
        self.assertContains(sayfa, "lazer-tablet")
        self.assertContains(sayfa, "İstasyon ekranını açtı")
        # Tablet hesabı bu sayfayı göremez
        self.client.force_login(User.objects.get(username="lazer-tablet"))
        self.assertEqual(self.client.get(reverse("tablet_girisleri")).status_code, 403)


class DenemeKayitlariTemizlikTesti(TemelVeri):
    def test_kayitlar_silinir_tanimlar_kalir(self):
        import shutil
        import tempfile
        from unittest import mock

        lot = self.yeni_lot(siparis=self.siparis)
        servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        klasor = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, klasor)
        yonetici = get_user_model().objects.create_superuser("yon", password="x")
        self.client.force_login(yonetici)
        self.assertContains(self.client.get(reverse("test_verilerini_sil")), "Kalıcı olarak sil")
        with mock.patch("uretim.temizlik.yedek_al") as yedek, mock.patch("uretim.temizlik._yedek_yolu",
                                                                       return_value=klasor / "y.sqlite3"):
            yedek.return_value = klasor / "y.sqlite3"
            # Onay yazılmazsa hiçbir şey silinmez
            self.client.post(reverse("test_verilerini_sil"), {"onay": "evet"})
            self.assertTrue(UretimLotu.objects.exists())
            self.client.post(reverse("test_verilerini_sil"), {"onay": "sil", "musteri": "on"})
            yedek.assert_called_once()
        self.assertFalse(UretimLotu.objects.exists() or IslemKaydi.objects.exists() or Siparis.objects.exists()
                         or HamDeriGirisi.objects.exists() or Musteri.objects.exists())
        self.assertTrue(Personel.objects.exists() and Tedarikci.objects.exists() and Asama.objects.exists())
        # Tablet hesabı sayfaya giremez
        self.client.force_login(get_user_model().objects.create_user("tab", password="x"))
        self.assertNotEqual(self.client.get(reverse("test_verilerini_sil")).status_code, 200)


class MarkaVeIstasyonSayfasiTesti(TestCase):
    def test_istasyon_listesi_lazerle_baslar_ve_logo_alani(self):
        self.client.force_login(get_user_model().objects.create_user("t", password="x"))
        sayfa = self.client.get(reverse("istasyon_secimi"))
        self.assertEqual(Asama.objects.filter(aktif=True).first().ad, "Lazer kesim 1")
        self.assertNotContains(sayfa, "location.replace")
        self.assertContains(sayfa, "BIENNA FUR")


class CsrfHatasiTesti(TestCase):
    def test_eski_giris_formu_yeniden_sorulur(self):
        from django.test import Client

        istemci = Client(enforce_csrf_checks=True)
        get_user_model().objects.create_user("lazer-tablet", password="gizli12345")
        yanit = istemci.post(reverse("login"), {"username": "lazer-tablet", "password": "gizli12345"}, follow=True)
        self.assertContains(yanit, "tekrar girin")
        # Yenilenen formla giriş çalışır
        yanit = istemci.post(reverse("login"), {"username": "lazer-tablet", "password": "gizli12345",
                                                "csrfmiddlewaretoken": yanit.context["csrf_token"]})
        self.assertEqual(yanit.status_code, 302)

    def test_diger_sayfalarda_anlasilir_mesaj(self):
        from django.test import Client

        istemci = Client(enforce_csrf_checks=True)
        istemci.force_login(get_user_model().objects.create_user("t", password="x"))
        yanit = istemci.post(reverse("islem_baslat"), {})
        self.assertEqual(yanit.status_code, 403)
        self.assertContains(yanit, "Sayfa eskimiş", status_code=403)


class HesapYonetimiTesti(TestCase):
    def test_hesap_turu_secilerek_acilir(self):
        User = get_user_model()
        yonetici = User.objects.create_superuser("patron2", password="x")
        self.client.force_login(yonetici)
        self.client.post(reverse("hesap_yeni"), {"kullanici_adi": "lazer1-tablet", "tur": "tablet",
                                                 "sifre": "gizli123", "sifre_tekrar": "gizli123", "aktif": "on"})
        self.client.post(reverse("hesap_yeni"), {"kullanici_adi": "ofis-ayse", "tur": "ofis",
                                                 "sifre": "gizli123", "sifre_tekrar": "gizli123", "aktif": "on"})
        tablet, ofis = User.objects.get(username="lazer1-tablet"), User.objects.get(username="ofis-ayse")
        self.assertFalse(tablet.is_staff or tablet.is_superuser)
        self.assertTrue(ofis.is_staff and not ofis.is_superuser)
        self.assertTrue(ofis.has_perm("uretim.add_siparis") and ofis.has_perm("uretim.add_hamderigirisi"))
        self.assertFalse(tablet.has_perm("uretim.add_siparis"))
        self.assertContains(self.client.get(reverse("hesap_listesi")), "ofis-ayse")
        # Şifre boş bırakılarak tür değiştirilebilir; şifre değişmez
        self.client.post(reverse("hesap_duzenle", args=[ofis.pk]), {"kullanici_adi": "ofis-ayse", "tur": "tablet",
                                                                    "aktif": "on"})
        ofis = User.objects.get(pk=ofis.pk)  # yetki önbelleği tazelensin
        self.assertFalse(ofis.is_staff or ofis.has_perm("uretim.add_siparis"))
        self.assertTrue(ofis.check_password("gizli123"))
        # Yönetici kendini kilitleyemez
        self.client.post(reverse("hesap_duzenle", args=[yonetici.pk]), {"kullanici_adi": "patron2", "tur": "tablet"})
        yonetici.refresh_from_db()
        self.assertTrue(yonetici.is_superuser and yonetici.is_active)
        # Ofis hesabı bu sayfaya giremez
        self.client.force_login(User.objects.create_user("o2", password="x", is_staff=True))
        self.assertNotEqual(self.client.get(reverse("hesap_listesi")).status_code, 200)


class HesapIstasyonuTesti(TestCase):
    def test_tablet_hesabi_istasyonuna_gider(self):
        User = get_user_model()
        self.client.force_login(User.objects.create_superuser("patron3", password="x"))
        lazer2 = Asama.objects.get(ad="Lazer kesim 2")
        self.client.post(reverse("hesap_yeni"), {"kullanici_adi": "lazer2-tablet", "tur": "tablet",
                                                 "istasyon": lazer2.pk, "sifre": "gizli123",
                                                 "sifre_tekrar": "gizli123", "aktif": "on"})
        self.assertContains(self.client.get(reverse("hesap_listesi")), "Lazer kesim 2")
        self.client.logout()
        yanit = self.client.post(reverse("login"), {"username": "lazer2-tablet", "password": "gizli123"})
        self.assertRedirects(yanit, reverse("istasyon_ekrani", args=[lazer2.pk]))
        pano = self.client.get(reverse("pano"))
        self.assertContains(pano, "Lazer kesim 2 ekranı")
        # İstasyon listesi açık kalır (bir kişi birden çok istasyonda çalışabilir), üstte kendi istasyonunun kısayolu
        self.assertContains(self.client.get(reverse("istasyon_secimi")), "Lazer kesim 2 ekranını aç")
        lazer1 = Asama.objects.get(ad="Lazer kesim 1")
        self.assertEqual(self.client.get(reverse("istasyon_ekrani", args=[lazer1.pk])).status_code, 200)


class MalzemeEtiketiYanlisYerdeTesti(TemelVeri):
    def test_malzeme_etiketi_stok_lotu_yerine_okutulursa_aciklama(self):
        from .models import Malzeme

        m = Malzeme.objects.create(ad="Halı taban", birim="m2")
        self.client.force_login(get_user_model().objects.create_user("tb", password="x"))
        yanit = self.client.get(reverse("stok_bilgi", args=[m.kod]))
        self.assertEqual(yanit.json()["malzeme"], "Halı taban")
        v = {"personel": self.ahmet.pk, "pin": "1234", "siparis": self.siparis.pk, "asama": self.asamalar[0].pk,
             "makine": self.makine(self.asamalar[0]), "kaynak-TOTAL_FORMS": 1, "kaynak-INITIAL_FORMS": 0,
             "kaynak-0-stok_no": m.kod, "kaynak-0-m2": "5"}
        self.assertContains(self.client.post(reverse("yeni_is"), v), "bir malzeme etiketi (Halı taban)")


class PanoIstasyonSayilariTesti(TemelVeri):
    def test_panoda_istasyona_gelen_isler_gorunur(self):
        lazerli = HaliTuru.objects.get(ad="Lazerli halı")
        Siparis.objects.create(musteri=self.siparis.musteri, urun="X", hali_turu=lazerli,
                               teslim_tarihi=timezone.localdate() + timedelta(days=3))
        self.client.force_login(get_user_model().objects.create_user("pt", password="x"))
        sayfa = self.client.get(reverse("pano"))
        satir = next(a for a in sayfa.context["asamalar"] if a["asama"].ad == "Lazer kesim 1")
        # Temel verideki türsüz sipariş de genel sırada ilk istasyona (Lazer kesim 1) düşer
        self.assertEqual(satir["bekleyen"], 2)
        self.assertContains(sayfa, "2 bekliyor")


class GecisDonemiTesti(TemelVeri):
    def test_eski_stoktan_is_yalnizca_gecis_doneminde(self):
        from .models import SistemAyari

        kece = DeriTuru.objects.get_or_create(ad="Keçe")[0]
        yonetici = get_user_model().objects.create_superuser("gy", password="x")
        self.client.force_login(yonetici)
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        v = {"personel": self.ahmet.pk, "pin": "1234", "siparis": self.siparis.pk, "asama": lazer.pk,
             "makine": self.makine(lazer), "eski_tur": kece.pk, "eski_m2": "12,5",
             "kaynak-TOTAL_FORMS": 1, "kaynak-INITIAL_FORMS": 0}
        # Kapalıyken eski stok alanı yok, iş açılmaz
        self.assertNotContains(self.client.get(reverse("yeni_is")), "Eski stoktan")
        SistemAyari.objects.update(stok_zorunlu=True)
        self.assertContains(self.client.post(reverse("yeni_is"), v), "En az bir stok lotundan")
        # Aç
        self.client.post(reverse("gecis_modu_degistir"))
        self.assertTrue(SistemAyari.yukle().gecis_modu)
        self.assertContains(self.client.get(reverse("pano")), "AÇIK")
        self.assertRedirects(self.client.post(reverse("yeni_is"), v), reverse("pano"))
        lot = UretimLotu.objects.latest("pk")
        self.assertEqual((lot.baslangic_m2, lot.kaynak_listesi), (Decimal("12.50"), "Eski stok (Keçe)"))
        self.assertEqual(self.ham.kalan_m2, Decimal("20"))  # etiketli stoktan düşülmedi
        # Kapat: servis de reddeder
        self.client.post(reverse("gecis_modu_degistir"))
        with self.assertRaises(ValidationError):
            servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, kaynaklar=[], asama=lazer,
                                     eski_stok=(kece, None, Decimal("5")))


class FasonTesti(TemelVeri):
    def test_fasona_gonder_teslim_al_fire_ve_iz(self):
        from .hesaplar import ofis_grubu
        from .models import FasonIsi

        tur = {ad: DeriTuru.objects.get(ad=ad) for ad in ("Keçe", "Süet", "Rono")}
        lamine = DeriTuru.objects.get(ad="3'lü lamine (Keçe+Süet+Rono)")
        fasoncu = Tedarikci.objects.create(ad="Presçi")
        lotlar = {ad: HamDeriGirisi.objects.create(tedarikci=self.ham.tedarikci, deri_turu=t, kg=0, m2=Decimal("50"),
                                                   renk="Bej" if ad == "Rono" else "Gri",
                                                   model="Mermer" if ad == "Rono" else "")
                  for ad, t in tur.items()}
        ofis = get_user_model().objects.create_user("ofis", password="x", is_staff=True)
        ofis.groups.add(ofis_grubu())
        self.client.force_login(ofis)

        v = {"fasoncu": fasoncu.pk, "hedef_tur": lamine.pk, "kaynak-TOTAL_FORMS": 3, "kaynak-INITIAL_FORMS": 0}
        for i, ad in enumerate(("Keçe", "Süet", "Rono")):
            v[f"kaynak-{i}-stok_no"] = lotlar[ad].lot_no
            v[f"kaynak-{i}-m2"] = "10" if ad != "Rono" else "12"
        # Stokta olandan fazlası gönderilemez
        fazla = dict(v, **{"kaynak-0-m2": "60"})
        self.assertContains(self.client.post(reverse("fason_gonder"), fazla), "stokta")
        yanit = self.client.post(reverse("fason_gonder"), v)
        fason = FasonIsi.objects.get()
        self.assertRedirects(yanit, reverse("fason_detay", args=[fason.pk]))
        lotlar["Keçe"].refresh_from_db()
        self.assertEqual(lotlar["Keçe"].kalan_m2, Decimal("40"))
        self.assertEqual(fason.katman_m2, Decimal("10.67"))
        self.assertContains(self.client.get(reverse("fason_listesi")), fason.no)

        # Teslim al: renk/model rono katmanından gelir
        sayfa = self.client.get(reverse("fason_detay", args=[fason.pk]))
        self.assertContains(sayfa, 'value="Bej"')
        yanit = self.client.post(reverse("fason_detay", args=[fason.pk]), {"m2": "10", "renk": "Bej", "model": "Mermer"})
        fason.refresh_from_db()
        yeni = fason.gelen_lot
        self.assertRedirects(yanit, reverse("stok_detay", args=[yeni.pk]))
        self.assertEqual((yeni.deri_turu, yeni.tedarikci, yeni.m2, yeni.renk, yeni.model, fason.durum),
                         (lamine, fasoncu, Decimal("10"), "Bej", "Mermer", "teslim"))
        self.assertEqual(fason.fire_m2, Decimal("0.67"))
        detay = self.client.get(reverse("stok_detay", args=[yeni.pk]))
        self.assertContains(detay, fason.no)
        self.assertContains(detay, lotlar["Rono"].lot_no)
        # İkinci kez teslim alınamaz
        with self.assertRaises(ValidationError):
            servisler.fason_teslim_al(fason=fason, m2=Decimal("1"))

    def test_iptal_stogu_geri_verir(self):
        lamine = DeriTuru.objects.get(ad="Halı tabanı (Keçe+Süet)")
        fason = servisler.fasona_gonder(fasoncu=self.ham.tedarikci, hedef_tur=lamine,
                                        kaynaklar=[(self.ham, None, Decimal("5"))])
        self.assertEqual(self.ham.kalan_m2, Decimal("15"))
        servisler.fason_iptal(fason=fason)
        self.assertEqual(self.ham.kalan_m2, Decimal("20"))
        with self.assertRaises(ValidationError):
            servisler.fasona_gonder(fasoncu=self.ham.tedarikci, hedef_tur=self.ham.deri_turu,
                                    kaynaklar=[(self.ham, None, Decimal("5"))])


class KatalogTesti(TemelVeri):
    def test_katalog_ve_modelli_siparis(self):
        from .hesaplar import ofis_grubu
        from .models import KatalogModeli, LazerDeseni

        self.assertEqual(KatalogModeli.objects.count(), 202)  # 192 katalog + 10 fotoğraflı model
        self.assertEqual(LazerDeseni.objects.count(), 23)
        model = KatalogModeli.objects.get(kod="LTS-003")
        # Resimler yalnızca giriş yapanlara
        self.assertEqual(self.client.get(model.resim.url).status_code, 302)
        ofis = get_user_model().objects.create_user("ofis", password="x", is_staff=True)
        ofis.groups.add(ofis_grubu())
        self.client.force_login(ofis)
        self.assertEqual(self.client.get(model.resim.url).status_code, 200)
        self.assertContains(self.client.get(reverse("katalog"), {"ara": "lts-003"}), "LTS-003")
        self.assertContains(self.client.get(reverse("desenler")), "DB014")
        self.assertEqual(self.client.get(reverse("tasarim_desen_onizleme", args=["DB014"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tasarim_desen_onizleme", args=["YOK"])).status_code, 404)

        # Model kodu küçük harf / noktalı yazılabilir; halı türü seriden, ürün koddan gelir
        desen = LazerDeseni.objects.get(kod="DB003")
        yanit = self.client.post(reverse("siparis_yeni"), {
            "yeni_musteri": "Bayi", "model_kodu": "lts.-003", "lazer_deseni": desen.pk, "adet": 1,
            "teslim_tarihi": (timezone.localdate() + timedelta(days=5)).isoformat(),
        })
        sp = Siparis.objects.latest("pk")
        self.assertRedirects(yanit, reverse("siparis_detay", args=[sp.pk]))
        self.assertEqual((sp.katalog_modeli, sp.lazer_deseni, sp.hali_turu.ad, sp.urun),
                         (model, desen, "Lazerli halı", "LTS-003 Lazerli Toskana"))
        self.assertContains(self.client.get(reverse("siparis_detay", args=[sp.pk])), model.resim.url)
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.assertContains(self.client.get(reverse("istasyon_ekrani", args=[lazer.pk])), model.resim.url)
        # Olmayan kod
        yanit = self.client.post(reverse("siparis_yeni"), {"yeni_musteri": "Bayi", "model_kodu": "XX-1", "adet": 1,
                                                          "teslim_tarihi": timezone.localdate().isoformat()})
        self.assertContains(yanit, "katalog modeli yok")


@override_settings(STUDYO_BAYIYE_ACIK=True)  # stüdyo artık yalnız yöneticide; bu testler eski bayi akışıyla çalışır
class TasarimStudyosuTesti(TemelVeri):
    def setUp(self):
        from .hesaplar import HesapFormu, ofis_grubu

        self.yonetici = get_user_model().objects.create_superuser("yon", password="x")
        form = HesapFormu({"kullanici_adi": "bayi-ankara", "tur": "bayi", "sifre": "gizli123", "sifre_tekrar": "gizli123",
                           "yeni_bayi": "Ankara Bayi", "aktif": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        self.bayi_hesap = form.kaydet(self.yonetici)
        self.ofis = get_user_model().objects.create_user("ofis", password="x", is_staff=True)
        self.ofis.groups.add(ofis_grubu())

    def test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder(self):
        from .models import Tasarim

        self.client.force_login(self.bayi_hesap)
        # Bayi üretim ekranlarına giremez
        self.assertRedirects(self.client.get(reverse("pano")), reverse("bayi_ana"))
        self.assertRedirects(self.client.get(reverse("stok_listesi")), reverse("bayi_ana"))
        sayfa = self.client.get(reverse("tasarim_studyo"), {"katalog": "TOS-036"})
        self.assertContains(sayfa, "Halınızı tasarlayın")
        self.assertContains(sayfa, "LTS-006")  # katalog kombinasyonları
        veri = self.client.get(reverse("tasarim_onizleme"), {"en": "200", "boy": "300", "dis_bant": "999",
                                                              "dis_desen": "DB002", "sekil": "dikdortgen"}).json()
        self.assertEqual((veri["v"]["dis_bant"], veri["v"]["dis_desen"]), (40.0, "DB002"))  # 40 cm ile sınırlı
        resim = self.client.get(reverse("tasarim_onizleme_resmi"), {"dis_desen": "DB007", "b": "300"})
        self.assertEqual((resim.status_code, resim["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(self.client.get(reverse("tasarim_doku", args=["vizon_kurk"])).status_code, 200)

        yanit = self.client.post(reverse("tasarim_studyo"), {
            "katalog": "TOS-034", "sekil": "dikdortgen", "en": "200", "boy": "300", "dis_bant": "16",
            "dis_malzeme": "altin", "dis_desen": "DB005", "halka": "20", "halka_zemin": "siyah_kurk", "ic_bant": "7",
            "ic_malzeme": "gumus", "ic_desen": "", "zemin": "vizon_kurk", "desen_alti": "siyah", "madalyon": "40",
            "madalyon_malzeme": "beyaz_deri", "adet": "2", "notlar": "Acil",
        })
        self.assertRedirects(yanit, reverse("bayi_ana"))
        t = Tasarim.objects.get()
        sp = t.siparis
        self.assertEqual((sp.durum, sp.musteri.ad, sp.adet, sp.lazer_deseni.kod, sp.katalog_modeli.kod),
                         ("onay", "Ankara Bayi", 2, "DB005", "TOS-034"))
        self.assertEqual(sp.toplam_m2, Decimal("12.00"))
        self.assertContains(self.client.get(reverse("bayi_ana")), "Onay bekliyor")
        self.assertEqual(self.client.get(reverse("tasarim_lazer", args=[t.pk, "dxf"])).status_code, 403)
        # Onaylanmadan istasyonlara düşmez
        self.assertNotIn(sp, [k.siparis for k in uyarilar.gelenler()])

        # Ofis: siparişlerde onay bekleyen sekmesi, sipariş sayfasında tasarım + lazer dosyası + onay
        self.client.force_login(self.ofis)
        self.assertContains(self.client.get(reverse("siparis_listesi"), {"durum": "onay"}), sp.siparis_no)
        detay = self.client.get(reverse("siparis_detay", args=[sp.pk]))
        self.assertContains(detay, "Onayla, üretime al")
        self.assertContains(detay, reverse("tasarim_resim", args=[t.pk]))
        dxf = self.client.get(reverse("tasarim_lazer", args=[t.pk, "dxf"]))
        self.assertIn(b"POLYLINE", dxf.content)
        self.assertIn(b"DB005", dxf.content)
        self.assertIn(b'width="2000mm"', self.client.get(reverse("tasarim_lazer", args=[t.pk, "svg"])).content)
        lazerli = HaliTuru.objects.get(ad="Lazerli halı")
        yanit = self.client.post(reverse("siparis_onay", args=[sp.pk]), {
            "islem": "onayla", "onay-hali_turu": lazerli.pk,
            "onay-teslim_tarihi": (timezone.localdate() + timedelta(days=10)).isoformat(), "onay-ofis_notu": "Teşekkürler",
        })
        self.assertRedirects(yanit, reverse("siparis_detay", args=[sp.pk]))
        sp.refresh_from_db()
        t.refresh_from_db()
        self.assertEqual((sp.durum, sp.hali_turu, t.durum), ("acik", lazerli, "onaylandi"))
        # İstasyon ekranında tasarım resmi
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        self.assertContains(self.client.get(reverse("istasyon_ekrani", args=[lazer.pk])),
                            reverse("tasarim_resim", args=[t.pk]))

        # Bayi siparişin durumunu görür; başka bayinin tasarımını göremez
        self.client.force_login(self.bayi_hesap)
        sayfa = self.client.get(reverse("bayi_ana"))
        self.assertContains(sayfa, sp.siparis_no)
        self.assertContains(sayfa, "Teşekkürler")
        baska = Tasarim.objects.create(musteri=Musteri.objects.create(ad="Başka"), veri={})
        self.assertEqual(self.client.get(reverse("tasarim_resim", args=[baska.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("tasarim_resim", args=[t.pk])).status_code, 200)

    def test_ret(self):
        from .tasarim_views import tasarim_gonder

        t = tasarim_gonder(bayi=hesap_bayisi(self.bayi_hesap), kullanici=self.bayi_hesap, adet=1,
                           veri=tasarim_cizim.temizle(tasarim_cizim.hazir_degerler("LTS-005"), {"DB001"}))
        self.client.force_login(self.ofis)
        self.client.post(reverse("siparis_onay", args=[t.siparis.pk]), {"islem": "reddet", "onay-ofis_notu": "Ölçü yok"})
        t.refresh_from_db()
        self.assertEqual((t.siparis.durum, t.durum, t.ofis_notu), ("iptal", "reddedildi", "Ölçü yok"))


class SuniDeriTasarimTesti(TasarimStudyosuTesti):
    def test_suni_deri_tasarim_ve_onayda_hali_turu(self):
        from .tasarim_views import onay_formu, tasarim_gonder

        self.client.force_login(self.bayi_hesap)
        sayfa = self.client.get(reverse("tasarim_studyo"), {"katalog": "SD-2"})
        self.assertContains(sayfa, "Suni deri halı")
        self.assertContains(sayfa, reverse("tasarim_hazir_resmi", args=["SD-1"]))
        self.assertEqual(self.client.get(reverse("tasarim_hazir_resmi", args=["SD-1"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("tasarim_doku", args=["varak_altin"])).status_code, 200)
        v = self.client.get(reverse("tasarim_onizleme"), {"model": "suni", "zemin": "siyah_kurk", "biye": "altin",
                                                           "desen_alti": "altin_sim"}).json()["v"]
        self.assertEqual((v["zemin"], v["biye"], v["desen_alti"]), ("varak_altin", "altin", "altin_sim"))  # kürk seçilemez
        self.assertEqual(self.client.get(reverse("tasarim_onizleme_resmi"), {"model": "suni", "biye": "gumus",
                                                                           "b": "300"}).status_code, 200)
        t = tasarim_gonder(bayi=hesap_bayisi(self.bayi_hesap), kullanici=self.bayi_hesap, adet=1,
                           veri=tasarim_cizim.temizle(tasarim_cizim.hazir_degerler("SD-1"), {"DB010"}))
        self.assertIn("Suni deri", t.ozet)
        self.assertEqual(onay_formu(t.siparis).initial["hali_turu"], HaliTuru.objects.get(ad="Suni deri halı").pk)

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None


class HaliGorselTesti(TestCase):
    def test_tum_katalog_kombinasyonlari_ve_desenler_cizilir(self):
        from . import hali_gorsel

        desenler = set(hali_gorsel.desen_bilgisi())
        self.assertEqual(len(desenler), 23)  # DB001–015 + atölye DXF LZ01–08
        for kod, _, _ in tasarim_cizim.HAZIRLAR:
            resim = hali_gorsel.ciz(tasarim_cizim.temizle(tasarim_cizim.hazir_degerler(kod), desenler), 300)
            self.assertGreater(resim.width, 100)
        for desen in sorted(desenler):
            v = tasarim_cizim.temizle({"dis_desen": desen, "ic_desen": desen, "sekil": "dikdortgen"}, desenler)
            hali_gorsel.ciz(v, 250)
        hali_gorsel.ciz(tasarim_cizim.temizle({"sekil": "oval", "dis_desen": "DB001"}, desenler), 250)


class SaglikVeYedekTesti(TestCase):
    def test_saglik_sayfasi_girissiz_tamam_der(self):
        yanit = self.client.get(reverse("saglik"))
        self.assertEqual((yanit.status_code, yanit.content), (200, b"TAMAM"))

    def test_saglik_sayfasi_veritabani_sorununda_503(self):
        from unittest import mock

        with mock.patch("uretim.saglik.connection.cursor", side_effect=RuntimeError("bozuk")):
            yanit = self.client.get(reverse("saglik"))
        self.assertEqual(yanit.status_code, 503)
        self.assertIn(b"veritabani", yanit.content)

    def test_yedekle_komutu_onekle_ve_eskileri_siler(self):
        import tempfile
        from io import StringIO

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as klasor:
            for i in range(3):
                Path(klasor, f"gunluk_2020-01-0{i + 1}_000000.sqlite3").write_bytes(b"")
            call_command("yedekle", klasor=klasor, onek="gunluk", tut=2, stdout=StringIO())
            kalan = sorted(p.name for p in Path(klasor).iterdir())
            self.assertEqual(len(kalan), 2)
            self.assertNotIn("gunluk_2020-01-01_000000.sqlite3", kalan)
            call_command("yedekle", klasor=klasor, stdout=StringIO())  # eski kullanım: uretim_yedek_…
            self.assertTrue(any(p.name.startswith("uretim_yedek_") for p in Path(klasor).iterdir()))


class ParcaliTasarimTesti(TasarimStudyosuTesti):
    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def test_parca_kurallari(self):
        from . import parcali

        k = {"DB003"}
        # 250×350 çerçeve: tüm parçalar 140×300 tablaya sığar (dikiş payıyla)
        v = parcali.temizle({"duzen": "cerceve", "en": 250, "boy": 350, "dis_bant": 10, "ara": 0, "ic_bant": 0, "pay": 2}, k)
        for p in parcali.parcalar(v):
            self.assertTrue(parcali.sigar(p["en"], p["boy"], v["pay"]), p["ad"])
        self.assertTrue(any("1/2" in p["ad"] for p in parcali.parcalar(v)))
        # yuvarlak halka en az 4 yay parçası, hepsi tablaya sığar
        v = parcali.temizle({"duzen": "yuvarlak", "cap": 300, "dis_halka": 30, "desen_halka": 25, "desen": "DB003"}, k)
        yaylar = [p for p in parcali.parcalar(v) if p["tur"] == "yay"]
        self.assertGreaterEqual(len(yaylar), 8)
        self.assertTrue(all(parcali.sigar(p["en"], p["boy"], v["pay"]) for p in yaylar))
        self.assertTrue(all(p["desen"] == "DB003" for p in yaylar if p["ad"].startswith("Desenli")))
        # nakış: motif 40 cm ile sınırlı, 7 kafa önerisi
        v = parcali.temizle({"duzen": "oval_serit", "en": 130, "boy": 260, "serit": 50, "motif": 99, "aralik": 2}, k)
        self.assertEqual(v["motif"], 40)
        bilgi = parcali.nakis_bilgisi(v)
        self.assertEqual(bilgi["tur"], -(-bilgi["adet"] // 7))
        # rulo: her malzeme 140 cm enden metre verir
        rulo = parcali.rulo_yerlesimi(parcali.parcalar(v), v["pay"])
        self.assertTrue(all(b["metre"] > 0 for b in rulo.values()))

    def test_bayi_parcali_tasarim_gonderir_ofis_kesim_listesi(self):
        from .models import Tasarim

        self.client.force_login(self.bayi_hesap)
        sayfa = self.client.get(reverse("parcali_studyo"), {"hazir": "IPS-484"})
        self.assertContains(sayfa, "Suni deri halı tasarla")
        self.assertContains(sayfa, 'data-kod="PCH-010"')
        j = self.client.get(reverse("parcali_onizleme"), {"duzen": "oval_serit", "en": "130", "boy": "190",
                                                           "nakis": "grek_kare"}).json()
        self.assertEqual(len(j["parcalar"]), 3)
        self.assertEqual(j["nakis"]["adet"] % 1, 0)
        self.assertEqual(self.client.get(reverse("parcali_onizleme_resmi"), {"duzen": "yuvarlak", "b": "300"})["Content-Type"],
                         "image/jpeg")
        self.assertEqual(self.client.get(reverse("parcali_malzeme", args=["varak_gumus"])).status_code, 200)
        yanit = self.client.post(reverse("parcali_studyo"), {
            "duzen": "cerceve", "en": "100", "boy": "160", "dis_bant": "6", "dis_malzeme": "antrasit_keten", "ara": "12",
            "ara_malzeme": "beyaz_keten", "ic_bant": "11", "ic_malzeme": "antrasit_keten", "ic_desen": "DB003",
            "zemin": "beyaz_keten", "desen_alti": "krem", "kenar": "biye", "kenar_renk": "siyah", "pay": "1", "adet": "2",
        })
        self.assertRedirects(yanit, reverse("bayi_ana"))
        t = Tasarim.objects.get()
        self.assertEqual((t.veri["tip"], t.siparis.durum, t.siparis.lazer_deseni.kod), ("parcali", "onay", "DB003"))
        self.assertEqual(t.siparis.toplam_m2, Decimal("3.20"))
        self.assertIn("Suni deri", t.ozet)
        self.assertEqual(self.client.get(reverse("tasarim_resim", args=[t.pk]))["Content-Type"], "image/jpeg")
        self.assertEqual(self.client.get(reverse("parcali_kesim", args=[t.pk])).status_code, 403)
        self.assertRedirects(self.client.get(reverse("tasarim_studyo"), {"kaynak": t.pk}),
                             f"{reverse('parcali_studyo')}?kaynak={t.pk}", fetch_redirect_response=False)

        self.client.force_login(self.ofis)
        detay = self.client.get(reverse("siparis_detay", args=[t.siparis.pk]))
        self.assertContains(detay, reverse("parcali_kesim", args=[t.pk]))
        kesim = self.client.get(reverse("parcali_kesim", args=[t.pk]))
        self.assertContains(kesim, "Ara şerit (sol)")
        self.assertContains(kesim, "Montaj sırası")
        self.assertEqual(self.client.get(reverse("parcali_plan", args=[t.pk]))["Content-Type"], "image/png")
        dxf = self.client.get(reverse("tasarim_lazer", args=[t.pk, "dxf"]), {"malzeme": "beyaz_keten"})
        self.assertIn(b"KESIM", dxf.content)
        self.assertIn(b"Orta zemin", dxf.content)
        self.assertNotIn(b"Dis bant", dxf.content)  # antrasit parçalar bu dosyada yok
        self.assertNotIn("Dış bant".encode(), dxf.content)
        self.assertEqual(self.client.get(reverse("tasarim_lazer", args=[t.pk, "svg"])).status_code, 404)
        from .tasarim_views import onay_formu
        self.assertEqual(onay_formu(t.siparis).initial["hali_turu"], HaliTuru.objects.get(ad="Suni deri halı").pk)


class ParcaliGorselTumSecenekTesti(TestCase):
    """Her düzen × kenar × kenar rengi × farklı ölçü/boyutta çizim hata vermemeli (Lanfel hatası tekrar etmesin)."""

    def test_tum_kombinasyonlar_cizilir(self):
        from . import parcali, parcali_gorsel

        desenler = {"DB001", "DB003", "DB007"}
        olculer = [(60, 60), (90, 160), (123, 187), (130, 190), (250, 350)]
        for kod, _, _ in parcali.HAZIRLAR:
            for kenar, _ in parcali.KENARLAR:
                # her kenar rengi bir kez, her ölçü ve görsel boyutu (tek/çift piksel) bir kez
                durumlar = [(renk, olculer[1], 240) for renk, _ in parcali.KENAR_RENKLERI]
                durumlar += [("altin", o, u) for o in olculer for u in (161, 240, 333)]
                for renk, (en, boy), uzun in durumlar:
                    v = parcali.temizle({**parcali.hazir_degerler(kod), "kenar": kenar, "kenar_renk": renk,
                                         "en": en, "boy": boy, "cap": en}, desenler)
                    with self.subTest(kod=kod, kenar=kenar, renk=renk, olcu=(en, boy), uzun=uzun):
                        parcali_gorsel.ciz(v, uzun)


class ParcaliYeniDuzenTesti(TasarimStudyosuTesti):
    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def test_izgara_elmas_serit_yarim_ve_fikir(self):
        from . import parcali

        k = {"DB007"}
        # ızgara: hücre sayısı ve dış bant; tüm parçalar tablaya sığar
        v = parcali.temizle({"duzen": "izgara", "en": 160, "boy": 240, "hucre": 40, "dis_bant": 10,
                             "dis_desen": "DB007", "aile": "siyah_altin", "dizilim": "dama"}, k)
        ps = parcali.parcalar(v)
        self.assertEqual(len([p for p in ps if p["tur"] == "panel"]), 4 * 6)
        self.assertEqual(len([p for p in ps if p["desen"] == "DB007"]), 4)
        self.assertTrue(all(parcali.sigar(p["en"], p["boy"], v["pay"]) for p in ps))
        self.assertGreater(len({p["malzeme"] for p in ps if p["tur"] == "panel"}), 1)
        # elmas: parçaların toplam alanı iç alanı doldurur
        v = parcali.temizle({"duzen": "elmas", "en": 200, "boy": 290, "hucre": 36, "dis_bant": 0}, k)
        toplam = sum(parcali.alan(p["poli"]) for p in parcali.parcalar(v))
        self.assertAlmostEqual(toplam, 200 * 290, delta=5)
        # geçiş: merkez ile köşe farklı renk
        ps = parcali.parcalar(v)
        merkez = min(ps, key=lambda p: (sum(x for x, _ in p["poli"]) / len(p["poli"]) - 100) ** 2
                     + (sum(y for _, y in p["poli"]) / len(p["poli"]) - 145) ** 2)
        self.assertEqual(merkez["malzeme"], parcali.AILE[v["aile"]][0])
        # şerit: serbest genişlik, toplam en korunur
        v = parcali.temizle({"duzen": "seritler", "en": 150, "boy": 220, "serit_sayisi": 6, "serbest": "on", "dis_bant": 0,
                             "tohum": 5}, k)
        seritler = [p for p in parcali.parcalar(v) if p["ad"].startswith("Şerit")]
        self.assertEqual(len(seritler), 6)
        self.assertAlmostEqual(sum(p["en"] for p in seritler), 150, delta=1)
        self.assertGreater(len({p["en"] for p in seritler}), 1)
        # iki parçalı: iki bölge (tablaya sığmayan bölünür), toplam alan halı alanı
        v = parcali.temizle({"duzen": "yarim", "en": 160, "boy": 230, "bolme": "capraz"}, k)
        self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in parcali.parcalar(v)), 160 * 230, delta=5)
        # fikirler: halkalı yapıda, birbirinden farklı
        fikirler = parcali.fikirler(7, 1, k)
        self.assertEqual({f["duzen"] for f in fikirler}, {"halkali"})
        self.assertEqual(len({parcali.ozet(f) for f in fikirler}), 7)

        self.client.force_login(self.bayi_hesap)
        liste = self.client.get(reverse("parcali_fikir"), {"en": "160", "boy": "230"}).json()
        self.assertEqual(len(liste), 6)
        for f in liste:
            self.assertEqual((f["v"]["en"], f["v"]["boy"]), (160.0, 230.0))
        sayfa = self.client.get(reverse("parcali_studyo"), {"hazir": "P-7"})
        self.assertContains(sayfa, "Bana fikir ver")
        self.assertContains(sayfa, "2. Bordürler")
        self.assertNotContains(sayfa, "Elmas (45°)")


P1 = {"duzen": "halkali", "sekil": "dikdortgen", "en": 80, "boy": 150, "halka_sayisi": 2, "h1_tur": "duz", "h1_gen": 11, "h1_malzeme": "beyaz_keten", "h2_tur": "desenli", "h2_gen": 12, "h2_malzeme": "antrasit_keten", "h2_desen": "DB003", "zemin": "beyaz_keten", "orta": "duz", "kenar": "biye", "kenar_renk": "siyah"}


class ParcaliHalkaliTesti(TasarimStudyosuTesti):
    """Atölyenin asıl yapısı: iç içe halkalar + orta (düz / nakış paneli / şerit)."""

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def test_halka_parcalari(self):
        from . import parcali

        k = {"DB003", "DB007"}
        # dikdörtgen: her halka 4 parça, uzun yanlar boydan boya, kısalar arada; alan tam dolu
        v = parcali.temizle({"duzen": "halkali", "sekil": "dikdortgen", "en": 80, "boy": 150, "halka_sayisi": 2,
                             "h1_tur": "duz", "h1_gen": 11, "h2_tur": "desenli", "h2_gen": 12, "h2_desen": "DB003"}, k)
        ps = parcali.parcalar(v)
        self.assertEqual(len([p for p in ps if p.get("halka") == 1]), 4)
        sol = next(p for p in ps if p["ad"] == "1. bordür (sol)")
        ust = next(p for p in ps if p["ad"] == "1. bordür (üst)")
        self.assertEqual((sol["en"], sol["boy"], ust["en"], ust["boy"]), (11, 150, 58, 11))
        self.assertTrue(all(p["desen"] == "DB003" for p in ps if p.get("halka") == 2))
        self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in ps), 80 * 150, delta=1)
        self.assertEqual(parcali.ana_desen(v), "DB003")
        self.assertEqual(v["desen_alti"], "yok")
        # yatay halıda uzun yanlar üst/alt olur
        v2 = parcali.temizle({**v, "en": 150, "boy": 80}, k)
        self.assertEqual(next(p for p in parcali.parcalar(v2) if p["ad"] == "1. bordür (üst)")["en"], 150)
        # en çok 4 halka; ortada en az 30 cm kalır
        v = parcali.temizle({"duzen": "halkali", "en": 100, "boy": 100, "halka_sayisi": 9,
                             **{f"h{i}_gen": 40 for i in range(1, 5)}}, k)
        self.assertEqual(v["halka_sayisi"], 4)
        self.assertLessEqual(parcali.halka_toplami(v), 35)
        # oval: yay parçaları tablaya sığar, toplam alan oval alanı
        v = parcali.temizle({"duzen": "halkali", "sekil": "oval", "en": 250, "boy": 380, "halka_sayisi": 2,
                             "h1_tur": "nakisli", "h1_gen": 24, "h2_tur": "duz", "h2_gen": 14, "pay": 2}, k)
        ps = parcali.parcalar(v)
        self.assertTrue(all(parcali.sigar(p["en"], p["boy"], v["pay"]) for p in ps))
        self.assertGreaterEqual(len([p for p in ps if p.get("yay") and p.get("halka") == 1]), 4)
        self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in ps), parcali.alan(parcali.dis_hat(v)), delta=60)
        n = parcali.nakis_bilgisi(v)
        self.assertGreater(n["adet"], 10)
        # iki bordür arası ara bant: orta malzemesinden, 5–30 cm ve 5'in katı; eski kayıtta yoksa bitişik kalır
        y = parcali.temizle({"duzen": "halkali", "en": 200, "boy": 300, "halka_sayisi": 2, "zemin": "pelus_krem",
                             "h1_gen": 10, "h2_gen": 10, "a1_gen": "12"}, k)
        self.assertEqual(y["a1_gen"], 10)
        ara = [h for h in parcali.halkalar(y) if h.get("ara")]
        self.assertEqual([(h["malzeme"], h["gen"]) for h in ara], [("pelus_krem", 10)])
        self.assertTrue(any(p["ad"] == "1. ara bant (sol)" for p in parcali.parcalar(y)))
        self.assertEqual(parcali.temizle({"duzen": "halkali", "halka_sayisi": 2}, k)["a1_gen"], 0)
        h455 = parcali.hazir_degerler("IPS-455")  # katalogdaki orta renkli düz bant ara banda çevrilir
        self.assertEqual((h455["halka_sayisi"], h455["a1_gen"]), (2, 15))
        # atölye kuralı: lazer desenli çerçeveli halıda nakış olmaz (nakışlı halka düz olur, panel/nakışlı şerit kalkar)
        y = parcali.temizle({"duzen": "halkali", "en": 160, "boy": 230, "halka_sayisi": 2, "h1_tur": "desenli",
                             "h1_desen": "DB003", "h2_tur": "nakisli", "orta": "panel"}, k)
        self.assertEqual((y["h2_tur"], y["orta"]), ("duz", "duz"))
        y = parcali.temizle({"duzen": "halkali", "en": 160, "boy": 230, "halka_sayisi": 1, "h1_tur": "duz",
                             "orta": "serit", "serit_tur": "nakisli"}, k)
        self.assertEqual(y["serit_tur"], "nakisli")  # düz bantlı halıda nakışlı şerit kalır
        self.assertEqual(n["tur"], -(-n["adet"] // 7))
        self.assertTrue(all(m[2] <= 40 and m[3] <= 65 for p in ps for m in p.get("motifler", [])))

    def test_orta_panel_ve_serit(self):
        from . import parcali

        k = {"DB003"}
        # panel: motifin nakış dosyasındaki ölçüsü + 4 cm pay; 3 motif alt alta
        v = parcali.temizle({"duzen": "halkali", "en": 120, "boy": 180, "halka_sayisi": 1, "h1_gen": 12, "orta": "panel",
                             "nakis": "61.01", "motif_adet": 3}, k)
        ps = parcali.parcalar(v)
        panel = next(p for p in ps if p["ad"] == "Nakış paneli")
        self.assertEqual((panel["en"], panel["boy"], panel["tur"]), (19.5, 50.5, "nakis"))
        self.assertEqual(len(panel["motifler"]), 3)
        self.assertEqual(parcali.nakis_bilgisi(v)["satirlar"][0]["olcu"], "11.5×11.5")
        # eski motif adı yeni kataloğa çevrilir; büyük motif sığmazsa uyarı
        self.assertEqual(parcali.temizle({"duzen": "halkali", "nakis": "grek_kare_gumus"}, k)["iplik"], "gumus")
        v = parcali.temizle({"duzen": "halkali", "en": 60, "boy": 60, "halka_sayisi": 0, "orta": "panel", "nakis": "57.01"}, k)
        self.assertTrue(any("sığmıyor" in u for u in parcali.uyarilar(v)))
        self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in ps), 120 * 180, delta=1)
        # iki enine desenli şerit: 3 zemin + 2 şerit
        v = parcali.temizle({"duzen": "halkali", "en": 160, "boy": 230, "halka_sayisi": 1, "h1_gen": 14, "orta": "serit",
                             "serit_tur": "desenli", "serit_yon": "enine", "serit_adet": 2, "serit": 16, "serit_desen": "DB003"}, k)
        ps = parcali.parcalar(v)
        seritler = [p for p in ps if p["ad"].startswith("Desenli şerit")]
        self.assertEqual([(p["en"], p["boy"]) for p in seritler], [(132, 16), (132, 16)])
        self.assertEqual(len([p for p in ps if p["ad"].startswith("Zemin")]), 3)
        self.assertIn("2 enine desenli şerit", parcali.ozet(v))
        # oval + boyuna nakışlı şerit: motifler ovalin içinde kalır
        v = parcali.temizle({"duzen": "halkali", "sekil": "oval", "en": 130, "boy": 190, "halka_sayisi": 0, "orta": "serit",
                             "serit_tur": "nakisli", "serit_yon": "boyuna", "serit": 16, "nakis": "61.01"}, k)
        serit = next(p for p in parcali.parcalar(v) if p["ad"].startswith("Nakışlı şerit"))
        orta = parcali.dis_hat(v)
        self.assertTrue(serit["motifler"])
        self.assertTrue(all(parcali.icinde(orta, m[:2]) for m in serit["motifler"]))

    def test_eski_tasarim_cevrilir_ve_bayi_gonderir(self):
        from . import parcali
        from .models import Tasarim

        k = {"DB003"}
        eski = parcali.temizle({"duzen": "cerceve", "en": 100, "boy": 160, "dis_bant": 6, "ara": 12, "ic_bant": 11,
                                "ic_desen": "DB003"}, k)
        yeni = parcali.temizle(parcali.eskiden_cevir(eski), k)
        self.assertEqual((yeni["duzen"], yeni["halka_sayisi"], yeni["h3_tur"], yeni["h3_desen"]),
                         ("halkali", 3, "desenli", "DB003"))
        yuv = parcali.temizle(parcali.eskiden_cevir(parcali.temizle({"duzen": "yuvarlak", "cap": 200, "dis_halka": 20,
                                                                      "desen_halka": 20, "desen": "DB003"}, k)), k)
        self.assertEqual((yuv["sekil"], yuv["en"], yuv["boy"], yuv["halka_sayisi"]), ("oval", 200, 200, 2))

        self.client.force_login(self.bayi_hesap)
        yanit = self.client.post(reverse("parcali_studyo"), {
            **{a: str(d) for a, d in P1.items()}, "orta": "serit",
            "serit_tur": "desenli", "serit_adet": "2", "serit_desen": "DB003", "adet": "1"})
        self.assertRedirects(yanit, reverse("bayi_ana"))
        t = Tasarim.objects.get()
        self.assertEqual((t.veri["duzen"], t.siparis.lazer_deseni.kod), ("halkali", "DB003"))
        self.assertEqual(self.client.get(reverse("parcali_studyo"), {"kaynak": t.pk}).status_code, 200)
        self.client.force_login(self.ofis)
        kesim = self.client.get(reverse("parcali_kesim", args=[t.pk]))
        self.assertContains(kesim, "1. bordür (sol)")
        self.assertContains(kesim, "Desenli şerit 2")

    def test_bayi_uyarilari_yerinde_ve_teknik_olmadan(self):
        from . import parcali

        self.client.force_login(self.bayi_hesap)
        q = {**{a: str(d) for a, d in P1.items()}, "halka_sayisi": "3", "h3_tur": "nakisli"}
        j = self.client.get(reverse("parcali_onizleme"), q).json()
        self.assertEqual(j["kalan_yer"], 0)
        self.assertEqual([(u["adim"], u["halka"]) for u in j["uyarilar"]], [(2, 3)])
        self.assertNotIn("parcalar", j)  # parça tablosu bayiye gitmez
        v = parcali.temizle(q, {"DB003"})
        self.assertTrue(any("4 cm" in u for u in parcali.uyarilar(v)))  # teknik uyarı ofiste görünür
        sayfa = self.client.get(reverse("parcali_studyo"), {"hazir": "IPS-449"})
        self.assertContains(sayfa, "✓ Üretilebilir")
        # nakış kataloğu motifleri ve gerçek ürün fotoğrafları
        self.assertContains(sayfa, reverse("parcali_motif", args=["61.01"]))
        self.assertContains(sayfa, 'data-kod="RNO-005"')  # katalog serileri
        self.assertNotContains(sayfa, 'value="DB007"')  # gizlenen lazer deseni
        self.assertEqual(self.client.get(reverse("parcali_motif", args=["61.01"]))["Content-Type"], "image/png")
        self.assertEqual(self.client.get(reverse("parcali_motif", args=["64.01"])).status_code, 404)  # marka logosu yok
        self.assertEqual(self.client.get(reverse("parcali_motif", args=["59.02"])).status_code, 404)  # marka logosu (Medusa) yok
        # kürk / deri sayfasında suni deri hazırları görünmez
        self.assertNotContains(self.client.get(reverse("tasarim_studyo")), "SD-1")

    def test_katalog_modeli_aynen_ve_madalyon(self):
        from . import parcali
        from .models import Tasarim

        k = {"DB015", "DB006"}
        # madalyonlu orta: parçalar halıyı tam doldurur, madalyon çerçevesi + nakış
        v = parcali.temizle({**parcali.hazir_degerler("IPS-449"), "madalyon": "nakisli", "madalyon_motif": "61.01",
                             "madalyon_cerceve": "altin"}, k)
        ps = parcali.parcalar(v)
        self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in ps), 160 * 230, delta=10)
        md = next(p for p in ps if p["ad"] == "Madalyon")
        self.assertEqual((md["tur"], len(md["motifler"])), ("nakis", 1))
        self.assertEqual(len([p for p in ps if p["ad"].startswith("Madalyon çerçevesi")]), 2)
        self.assertEqual((v["h2_desen"], v["a2_gen"]), ("DB015", 15))  # fotoğraftan: krem dış bant + Grek + ara bant
        # her katalog hazırı geçerli ve çizilebilir yapıda
        for kod in parcali.HAZIR:
            v = parcali.temizle(parcali.hazir_degerler(kod), k)
            self.assertAlmostEqual(sum(parcali.alan(p["poli"]) for p in parcali.parcalar(v)),
                                   parcali.alan(parcali.dis_hat(v)), delta=15, msg=kod)
        # olduğu gibi sipariş: katalog kodu siparişe yazılır, resim katalog fotoğrafı
        self.client.force_login(self.bayi_hesap)
        yanit = self.client.post(reverse("parcali_studyo"), {**{a: str(d) for a, d in P1.items()}, "katalog": "BNA-022",
                                                              "aynen": "on", "en": "120", "boy": "180", "adet": "1"})
        self.assertRedirects(yanit, reverse("bayi_ana"))
        t = Tasarim.objects.get()
        self.assertEqual((t.veri["aynen"], t.siparis.katalog_modeli.kod), ("on", "BNA-022"))
        self.assertIn("BNA-022", t.siparis.urun)
        self.assertEqual(self.client.get(reverse("tasarim_resim", args=[t.pk])).status_code, 200)


class SiparisFotografiTesti(TasarimStudyosuTesti):
    """Ofis WhatsApp'tan gelen fotoğrafı siparişe ekler; istasyonda görünür, modele dönüştürülür, bayi görür."""

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def setUp(self):
        import tempfile

        from django.test import override_settings

        super().setUp()
        self.medya = tempfile.TemporaryDirectory()
        self.ayar = override_settings(MEDIA_ROOT=self.medya.name)
        self.ayar.enable()

    def tearDown(self):
        self.ayar.disable()
        self.medya.cleanup()

    def _foto(self, ad="foto.jpg", boyut=(3000, 2000)):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        t = io.BytesIO()
        Image.new("RGB", boyut, (200, 180, 150)).save(t, "JPEG")
        return SimpleUploadedFile(ad, t.getvalue(), content_type="image/jpeg")

    def test_fotograf_yukle_goster_modele_ekle(self):
        from PIL import Image

        from .models import KatalogModeli, Musteri, Siparis

        tur = HaliTuru.objects.filter(aktif=True).first()
        self.client.force_login(self.ofis)
        yanit = self.client.post(reverse("siparis_yeni"), {
            "yeni_musteri": "WhatsApp Müşteri", "hali_turu": tur.pk, "adet": "1",
            "teslim_tarihi": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "fotograflar": [self._foto("a.jpg"), self._foto("b.jpg", (800, 1200))]})
        s = Siparis.objects.get(musteri=Musteri.objects.get(ad="WhatsApp Müşteri"))
        self.assertRedirects(yanit, reverse("siparis_detay", args=[s.pk]))
        self.assertEqual(s.urun, "Müşteri fotoğrafındaki ürün")
        fotolar = list(s.fotograflar.all())
        self.assertEqual(len(fotolar), 2)
        with fotolar[0].resim.open("rb") as f:
            self.assertEqual(max(Image.open(f).size), 1600)  # küçültüldü
        # liste ve detayda görünür; büyütme bağlantısı var
        self.assertContains(self.client.get(reverse("siparis_listesi")), fotolar[0].resim.url)
        detay = self.client.get(reverse("siparis_detay", args=[s.pk]))
        self.assertContains(detay, 'class="buyut"')
        self.assertContains(detay, "Fotoğraf ekle (2 yer)")
        # istasyon ekranlarında kullanılan parça fotoğrafı gösterir
        from django.template.loader import render_to_string
        self.assertIn(fotolar[1].resim.url, render_to_string("uretim/_siparis_resim.html", {"s": s}))
        # en çok 3: 2 fotoğraf daha eklenemez
        self.client.post(reverse("siparis_foto_ekle", args=[s.pk]), {"fotograflar": [self._foto(), self._foto(), self._foto()]})
        self.assertEqual(s.fotograflar.count(), 2)
        self.client.post(reverse("siparis_foto_ekle", args=[s.pk]), {"fotograflar": [self._foto()]})
        self.assertEqual(s.fotograflar.count(), 3)
        # resim olmayan dosya reddedilir
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.post(reverse("siparis_foto_sil", args=[s.fotograflar.last().pk]))
        self.client.post(reverse("siparis_foto_ekle", args=[s.pk]),
                         {"fotograflar": [SimpleUploadedFile("x.jpg", b"resim degil", content_type="image/jpeg")]})
        self.assertEqual(s.fotograflar.count(), 2)
        # modellere ekle: MM-001, sipariş modele bağlanır
        self.client.post(reverse("siparis_foto_model", args=[fotolar[0].pk]))
        model = KatalogModeli.objects.get(kod="MM-001")
        self.assertEqual(model.seri.ad, "Müşteri modelleri")
        s.refresh_from_db()
        self.assertEqual(s.katalog_modeli, model)
        self.client.post(reverse("siparis_foto_model", args=[fotolar[1].pk]))
        self.assertTrue(KatalogModeli.objects.filter(kod="MM-002").exists())
        # bayi: Suni deri sayfasında Müşteri modelleri sekmesi; olduğu gibi sipariş edebilir; sipariş fotoğrafını göremez
        self.client.force_login(self.bayi_hesap)
        sayfa = self.client.get(reverse("parcali_studyo"))
        self.assertContains(sayfa, "Müşteri modelleri")
        self.assertContains(sayfa, 'data-kod="MM-001"')
        self.assertEqual(self.client.get(fotolar[0].resim.url).status_code, 404)
        self.assertEqual(self.client.get(model.resim.url).status_code, 200)
        self.client.post(reverse("parcali_studyo"), {"duzen": "halkali", "katalog": "MM-002", "aynen": "on",
                                                      "en": "120", "boy": "180", "adet": "1"})
        self.assertEqual(Siparis.objects.get(durum="onay").katalog_modeli.kod, "MM-002")

    def test_android_paylas(self):
        manifest = self.client.get(reverse("manifest")).json()
        self.assertEqual(manifest["share_target"]["action"], reverse("paylas"))
        self.assertEqual(manifest["share_target"]["params"]["files"][0]["name"], "fotograflar")
        sw = self.client.get(reverse("service_worker")).content.decode()
        self.assertIn('const PAYLAS_ADRESI = "/paylas/"', sw)
        self.client.force_login(self.ofis)
        self.assertContains(self.client.get(reverse("paylas")), "Yeni sipariş aç")
        # uygulama kurulu değilse POST doğrudan gelir: bir şey kaydedilmez, yol gösterilir
        self.assertContains(self.client.post(reverse("paylas"), {"fotograflar": [self._foto()]}), "Fotoğraf alınamadı")
        self.client.force_login(self.bayi_hesap)
        self.assertNotEqual(self.client.get(reverse("paylas")).status_code, 200)


class DenemeDuzeltmeleriTesti(TemelVeri):
    """Atölye denemesinden gelen düzeltmeler: en×boy, PIN'siz kişisel hesap, isteğe bağlı stok, lazerde malzeme, acil."""

    def setUp(self):
        from .models import HesapAyari
        self.lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.zigzag = Asama.objects.get(ad="Zig-zag")
        self.telefon = get_user_model().objects.create_user("ahmet_tel", password="x")
        HesapAyari.objects.create(kullanici=self.telefon, personel=self.ahmet, istasyon=self.lazer)
        # Aynı çeşitten iki rulo: eski olan önce kullanılır
        self.rulo1 = HamDeriGirisi.objects.create(tedarikci=self.ham.tedarikci, deri_turu=self.ham.deri_turu,
                                                  tarih=timezone.localdate() - timedelta(days=5), kg=0, m2=Decimal("3"))
        self.rulo2 = HamDeriGirisi.objects.create(tedarikci=self.ham.tedarikci, deri_turu=self.ham.deri_turu,
                                                  kg=0, m2=Decimal("40"))

    def test_siparis_en_boy_m2(self):
        s = Siparis.objects.create(musteri=self.siparis.musteri, urun="Halı", en_cm=Decimal("160"), boy_cm=Decimal("230"),
                                   adet=2, teslim_tarihi=timezone.localdate())
        self.assertEqual((s.toplam_m2, s.olcu_metni, s.teslim_metni), (Decimal("7.36"), "160 × 230 cm", "bugün teslim"))
        ofis = get_user_model().objects.create_superuser("ofis_eb", password="x")
        self.client.force_login(ofis)
        self.client.post(reverse("siparis_yeni"), {
            "musteri": s.musteri.pk, "urun": "Peluş", "en_cm": "200", "adet": "1",
            "teslim_tarihi": "2026-12-01"})
        self.assertFalse(Siparis.objects.filter(urun="Peluş").exists())  # boy eksik

    def test_olcu_eski_siparis_metninden_okunur(self):
        import importlib
        g = importlib.import_module("uretim.migrations.0027_deneme_duzeltmeleri")
        self.assertEqual(g.OLCU.search("Toskana 160X230 krem").groups(), ("160", "230"))
        self.assertEqual(g.OLCU.search("120 x 180,5").groups(), ("120", "180,5"))

    def test_kisisel_hesap_pin_sormaz(self):
        self.client.force_login(self.telefon)
        v = {"siparis": self.siparis.pk, "asama": self.lazer.pk, "makine": self.makine(self.lazer),
             "kaynak-TOTAL_FORMS": "1", "kaynak-INITIAL_FORMS": "0"}
        sayfa = self.client.get(reverse("yeni_is"))
        self.assertNotContains(sayfa, 'name="pin"')
        self.assertContains(sayfa, "isteğe bağlı")
        # stok okutmadan iş açılır, Ahmet'e yazılır
        self.assertRedirects(self.client.post(reverse("yeni_is"), v), reverse("pano"))
        islem = IslemKaydi.objects.latest("pk")
        self.assertEqual(islem.personel, self.ahmet)
        # bitirirken PIN yok; lazerde malzeme bloğu var
        sayfa = self.client.get(reverse("islem_bitir", args=[islem.pk]))
        self.assertNotContains(sayfa, 'name="pin"')
        self.assertContains(sayfa, 'name="kesim_en"')
        self.assertRedirects(self.client.post(reverse("islem_bitir", args=[islem.pk]), {}), reverse("pano"))
        # ortak tablet hesabı hâlâ PIN sorar
        self.client.force_login(get_user_model().objects.create_user("ortak", password="x"))
        self.assertContains(self.client.get(reverse("yeni_is")), 'name="pin"')

    def test_lazerde_kullanilan_malzeme_fifo_dusulur_fire_hesaplanir(self):
        s = Siparis.objects.create(musteri=self.siparis.musteri, urun="Halı", en_cm=Decimal("100"), boy_cm=Decimal("200"),
                                   teslim_tarihi=timezone.localdate())
        islem = servisler.yeni_is_baslat(personel=self.ahmet, siparis=s, asama=self.lazer, kaynaklar=[])
        self.assertTrue(servisler.ilk_adim_mi(islem))
        self.client.force_login(self.telefon)
        cesit = servisler.cesit_anahtari(self.rulo1)
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]),
                                 {"cesit": cesit, "kesim_en": "140", "kesim_boy": "160"})
        self.assertRedirects(yanit, reverse("pano"))
        lot = islem.lot
        lot.refresh_from_db()
        # 2,24 m²: önce eski ruloda kalan, sonra yenisi
        kaynaklar = {k.ham_deri_id: k.m2 for k in lot.kaynaklar.all()}
        self.assertEqual(sum(kaynaklar.values()), Decimal("2.24"))
        self.assertIn(self.rulo1.pk, kaynaklar)
        islem.refresh_from_db()
        self.assertEqual((islem.giris_m2, islem.cikis_m2), (Decimal("2.24"), Decimal("2.00")))
        # sonraki istasyonda malzeme sorulmaz
        i2 = servisler.islem_baslat(lot=lot, asama=self.zigzag, personel=self.ahmet)
        self.assertFalse(servisler.ilk_adim_mi(i2))
        self.assertNotContains(self.client.get(reverse("islem_bitir", args=[i2.pk])), 'name="kesim_en"')
        lot.refresh_from_db()
        self.assertIn("Zig-zag – çalışılıyor", lot.konum_metni)

    def test_rulo_okutulunca_ondan_dusulur_yetmezse_hata(self):
        islem = servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.lazer, kaynaklar=[])
        self.client.force_login(self.telefon)
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]),
                                 {"rulo_no": self.rulo2.lot_no, "kesim_en": "100", "kesim_boy": "100"})
        self.assertRedirects(yanit, reverse("pano"))
        self.assertEqual(self.rulo2.kalan_m2, Decimal("39"))
        islem2 = servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.lazer, kaynaklar=[])
        yanit = self.client.post(reverse("islem_bitir", args=[islem2.pk]),
                                 {"rulo_no": self.rulo1.lot_no, "kesim_en": "200", "kesim_boy": "200"})
        self.assertEqual(yanit.status_code, 200)
        islem2.refresh_from_db()
        self.assertIsNone(islem2.bitis)

    def test_stok_zorunlu_dugmesi(self):
        from .models import SistemAyari
        yonetici = get_user_model().objects.create_superuser("y_sz", password="x")
        self.client.force_login(yonetici)
        self.client.post(reverse("stok_zorunlu_degistir"))
        self.assertTrue(SistemAyari.yukle().stok_zorunlu)
        islem = servisler.islem_baslat(lot=self.yeni_lot(), asama=self.lazer, personel=self.ahmet)
        with self.assertRaises(ValidationError):
            servisler.yeni_is_baslat(personel=self.ahmet, siparis=self.siparis, asama=self.lazer, kaynaklar=[])
        # stoktan okutulmuş iş bitirilebilir
        servisler.islem_bitir(islem=islem, personel=self.ahmet)
        self.client.post(reverse("stok_zorunlu_degistir"))
        self.assertFalse(SistemAyari.yukle().stok_zorunlu)

    def test_acil_ve_teslim_sirasi(self):
        bugun = timezone.localdate()
        gec = Siparis.objects.create(musteri=self.siparis.musteri, urun="Geç", teslim_tarihi=bugun + timedelta(days=10),
                                     notlar="Kenarı altın biye")
        yakin = Siparis.objects.create(musteri=self.siparis.musteri, urun="Yakın", teslim_tarihi=bugun + timedelta(days=1))
        for s in (gec, yakin):
            servisler.yeni_is_baslat(personel=self.ahmet, siparis=s, asama=self.lazer, kaynaklar=[])
        ofis = get_user_model().objects.create_superuser("ofis_ac", password="x")
        self.client.force_login(ofis)
        sira = lambda: [k.lot.siparis.urun for k in uyarilar.calisilanlar(self.lazer)]
        self.assertEqual(sira(), ["Yakın", "Geç"])
        self.client.post(reverse("siparis_acil", args=[gec.pk]))
        gec.refresh_from_db()
        self.assertTrue(gec.acil)
        self.assertEqual(sira(), ["Geç", "Yakın"])
        ekran = self.client.get(reverse("istasyon_parca", args=[self.lazer.pk]))
        self.assertContains(ekran, "ACİL")
        self.assertContains(ekran, "Kenarı altın biye")
        self.assertContains(ekran, "1 gün kaldı")


class BirinciGuncellemeTesti(TemelVeri):
    """Ölçü satırları + otomatik iş, sipariş düzenleme, istasyon notu, pano özeti, arşiv fotoğraf küçültme."""

    def setUp(self):
        import tempfile

        from django.test import override_settings

        from .models import HesapAyari
        self.medya = tempfile.TemporaryDirectory()
        self.ayar = override_settings(MEDIA_ROOT=self.medya.name)
        self.ayar.enable()
        self.lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.ofis = get_user_model().objects.create_superuser("ofis_g1", password="x")
        self.telefon = get_user_model().objects.create_user("ayse_tel", password="x")
        HesapAyari.objects.create(kullanici=self.telefon, personel=self.ayse, istasyon=self.lazer)

    def tearDown(self):
        self.ayar.disable()
        self.medya.cleanup()

    def _foto(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        t = io.BytesIO()
        Image.new("RGB", (2400, 1600), (200, 180, 150)).save(t, "JPEG")
        return SimpleUploadedFile("f.jpg", t.getvalue(), content_type="image/jpeg")

    def _olculer(self, *satirlar, **ek):
        v = {"olcu-TOTAL_FORMS": str(len(satirlar)), "olcu-INITIAL_FORMS": "0"}
        for i, (kalem, en, boy, adet) in enumerate(satirlar):
            v.update({f"olcu-{i}-kalem": kalem or "", f"olcu-{i}-en_cm": en, f"olcu-{i}-boy_cm": boy,
                      f"olcu-{i}-adet": adet})
        v.update(ek)
        return v

    def _yeni(self, *satirlar, **ek):
        self.client.force_login(self.ofis)
        veri = self._olculer(*satirlar, musteri=self.siparis.musteri.pk, urun="Peluş", teslim_tarihi="2026-12-20",
                             hali_turu=HaliTuru.objects.get(ad="Suni deri halı").pk, **ek)
        return self.client.post(reverse("siparis_yeni"), veri)

    def test_cok_olculu_siparis_her_olcuye_is(self):
        yanit = self._yeni((None, "160", "230", "2"), (None, "200", "300", ""), (None, "", "", ""))
        sp = Siparis.objects.get(urun="Peluş")
        self.assertRedirects(yanit, reverse("siparis_detay", args=[sp.pk]))
        self.assertEqual([k.olcu_metni() for k in sp.kalemler.all()], ["160 × 230 cm ×2", "200 × 300 cm"])
        self.assertEqual((sp.adet, sp.toplam_m2), (3, Decimal("13.36")))
        self.assertEqual(sp.olcu_metni, "160 × 230 ×2 · 200 × 300 cm")
        lotlar = list(sp.lotlar.order_by("kalem__sira"))
        self.assertEqual([l.baslangic_m2 for l in lotlar], [Decimal("7.36"), Decimal("6.00")])
        # iki iş de lazerin gelen işlerinde, kendi ölçüsüyle; "yeni sipariş" satırı yok
        gelen = [k for k in uyarilar.gelenler(self.lazer) if k.siparis == sp]
        self.assertEqual(sorted(k.tur for k in gelen), ["gelen", "gelen"])
        self.client.force_login(self.telefon)
        ekran = self.client.get(reverse("istasyon_parca", args=[self.lazer.pk]))
        self.assertContains(ekran, "160 × 230 cm ×2")
        # lazer bitirirken net m² o işin ölçüsünden
        islem = servisler.islem_baslat(lot=lotlar[1], asama=self.lazer, personel=self.ayse)
        servisler.islem_bitir(islem=islem, personel=self.ayse, kesim={"m2": Decimal("7"), "rulo": self.ham})
        islem.refresh_from_db()
        self.assertEqual((islem.giris_m2, islem.cikis_m2), (Decimal("7.00"), Decimal("6.00")))
        # "Yeni iş" ekranından aynı sipariş seçilirse yeni iş açılmaz, bekleyen iş başlar
        islem2 = servisler.yeni_is_baslat(personel=self.ayse, siparis=sp, asama=self.lazer, kaynaklar=[])
        self.assertEqual(islem2.lot, lotlar[0])
        self.assertEqual(sp.lotlar.count(), 2)

    def test_yonetici_islem_geri_al(self):
        self._yeni((None, "100", "150", "1"))
        sp = Siparis.objects.get(urun="Peluş")
        lot = sp.lotlar.get()
        kalan = self.ham.kalan_m2
        # yanlışlıkla başlatıldı → yönetici başlatmayı siler
        islem = servisler.islem_baslat(lot=lot, asama=self.lazer, personel=self.ayse)
        normal = get_user_model().objects.create_user("normal_ofis", password="x", is_staff=True)
        self.client.force_login(normal)
        self.assertEqual(self.client.post(reverse("islem_geri_al", args=[islem.pk])).status_code, 403)
        self.client.force_login(self.ofis)
        self.assertContains(self.client.get(reverse("lot_detay", args=[lot.pk])), "Başlatmayı geri al")
        self.client.post(reverse("islem_geri_al", args=[islem.pk]))
        lot.refresh_from_db()
        sp.refresh_from_db()
        self.assertEqual((lot.islemler.count(), lot.durum, sp.durum), (0, "bekliyor", "acik"))
        # yanlışlıkla bitirildi (stoktan 2 m² düştü) → bitirme geri alınır, malzeme stoğa döner
        islem = servisler.islem_baslat(lot=lot, asama=self.lazer, personel=self.ayse)
        servisler.islem_bitir(islem=islem, personel=self.ayse, kesim={"m2": Decimal("2"), "rulo": self.ham})
        self.ham.refresh_from_db()
        self.assertEqual(self.ham.kalan_m2, kalan - 2)
        self.assertContains(self.client.get(reverse("lot_detay", args=[lot.pk])), "Bitirmeyi geri al")
        self.client.post(reverse("islem_geri_al", args=[islem.pk]))
        islem.refresh_from_db()
        lot.refresh_from_db()
        self.ham.refresh_from_db()
        self.assertEqual((islem.bitis, lot.durum, lot.son_asama), (None, "islemde", self.lazer))
        self.assertEqual(self.ham.kalan_m2, kalan)
        self.assertTrue(lot.is_notlari.filter(metin__startswith="↩ Yönetici geri aldı").exists())
        # yeniden bitirilebilir; yalnız son işlem geri alınır
        servisler.islem_bitir(islem=islem, personel=self.ayse)
        sonraki = servisler.islem_baslat(lot=lot, asama=lot.siradaki_asama, personel=self.ayse)
        self.assertFalse(servisler.geri_alinabilir(islem))
        self.assertTrue(servisler.geri_alinabilir(sonraki))

    def test_siparis_duzenle_olcu_ve_fotograf(self):
        self._yeni((None, "100", "150", "1"), (None, "80", "120", "2"), fotograflar=[self._foto(), self._foto()])
        sp = Siparis.objects.get(urun="Peluş")
        k1, k2 = sp.kalemler.all()
        f1 = sp.fotograflar.first()
        self.assertContains(self.client.get(reverse("siparis_detay", args=[sp.pk])), reverse("siparis_duzenle", args=[sp.pk]))
        sayfa = self.client.get(reverse("siparis_duzenle", args=[sp.pk]))
        self.assertContains(sayfa, 'value="100"')
        veri = self._olculer((k1.pk, "120", "180", "1"), (k2.pk, "", "", ""), (None, "50", "50", "4"),
                             musteri=sp.musteri.pk, urun="Peluş krem", teslim_tarihi="2026-12-20", foto_sil=[f1.pk],
                             hali_turu=sp.hali_turu_id,
                             fotograflar=[self._foto(), self._foto()])
        y = self.client.post(reverse("siparis_duzenle", args=[sp.pk]), veri)
        self.assertRedirects(y, reverse("siparis_detay", args=[sp.pk]))
        sp.refresh_from_db()
        self.assertEqual(sp.urun, "Peluş krem")
        self.assertEqual([k.olcu_metni() for k in sp.kalemler.all()], ["120 × 180 cm", "50 × 50 cm ×4"])
        self.assertEqual(sorted(l.baslangic_m2 for l in sp.lotlar.all()), [Decimal("1.00"), Decimal("2.16")])
        self.assertEqual(sp.fotograflar.count(), 3)
        self.assertFalse(sp.fotograflar.filter(pk=f1.pk).exists())
        # başlamış işin satırı silinemez
        k1 = sp.kalemler.first()
        servisler.islem_baslat(lot=k1.lotlar.first(), asama=self.lazer, personel=self.ahmet)
        k3 = sp.kalemler.last()
        veri = self._olculer((k1.pk, "", "", ""), (k3.pk, "50", "50", "4"), musteri=sp.musteri.pk, urun="X",
                             teslim_tarihi="2026-12-20", hali_turu=sp.hali_turu_id)
        self.assertContains(self.client.post(reverse("siparis_duzenle", args=[sp.pk]), veri), "silinemez")
        self.assertEqual(sp.kalemler.count(), 2)

    def test_istasyon_notu(self):
        lot = self.yeni_lot(siparis=self.siparis)
        islem = servisler.islem_baslat(lot=lot, asama=self.lazer, personel=self.ayse)
        self.client.force_login(self.telefon)
        ekran = self.client.get(reverse("istasyon_parca", args=[self.lazer.pk]))
        self.assertContains(ekran, reverse("is_notu", args=[lot.pk]))
        sayfa = self.client.get(reverse("is_notu", args=[lot.pk]))
        self.assertNotContains(sayfa, 'name="pin"')
        self.client.post(reverse("is_notu", args=[lot.pk]) + f"?asama={self.lazer.pk}", {"metin": "Kenarda leke vardı"})
        n = lot.is_notlari.get()
        self.assertEqual((n.personel, n.asama, n.metin), (self.ayse, self.lazer, "Kenarda leke vardı"))
        self.assertContains(self.client.get(reverse("istasyon_parca", args=[self.lazer.pk])), "Kenarda leke vardı")
        # bitirirken yazılan açıklama da not olur; ofis sipariş sayfasında görür
        servisler.islem_bitir(islem=islem, personel=self.ayse, aciklama="Biye rengi farklı")
        self.client.force_login(self.ofis)
        detay = self.client.get(reverse("siparis_detay", args=[self.siparis.pk]))
        self.assertContains(detay, "Kenarda leke vardı")
        self.assertContains(detay, "Biye rengi farklı")
        # ortak tablet PIN ister
        self.client.force_login(get_user_model().objects.create_user("ortak_t", password="x"))
        self.assertContains(self.client.post(reverse("is_notu", args=[lot.pk]), {"metin": "x", "personel": self.ahmet.pk,
                                                                                "pin": "0000"}), "PIN hatalı")

    def test_pano_kim_ne_yapti(self):
        zigzag = Asama.objects.get(ad="Zig-zag")
        sp = Siparis.objects.create(musteri=self.siparis.musteri, urun="Halı", teslim_tarihi=timezone.localdate(),
                                    hali_turu=HaliTuru.objects.get(ad__icontains="Suni"), en_cm=Decimal("200"),
                                    boy_cm=Decimal("200"))
        lot = UretimLotu.objects.create(siparis=sp, baslangic_kg=0, baslangic_m2=Decimal("4"))
        rota = [a for a in sp.ilk_asamalar()]
        i = servisler.islem_baslat(lot=lot, asama=rota[0], personel=self.ahmet)
        servisler.islem_bitir(islem=i, personel=self.ayse, kesim={"m2": Decimal("5"), "rulo": self.ham})
        lot.refresh_from_db()
        while lot.durum != "tamamlandi":
            sonraki = lot.siradaki_asama
            i = servisler.islem_baslat(lot=lot, asama=sonraki, personel=self.ahmet)
            servisler.islem_bitir(islem=i, personel=self.ahmet)
            lot.refresh_from_db()
        ozet = {s["personel__ad_soyad"]: s for s in raporlar.bugun_kim_ne_yapti(timezone.localdate())}
        self.assertEqual(ozet["Ayşe"]["islem_sayisi"], 1)  # başlatan Ahmet ama bitiren Ayşe
        self.assertEqual(ozet["Ayşe"]["fire_m2"], Decimal("1"))  # 5 kullanıldı, ölçü 4
        self.assertEqual((ozet["Ahmet"]["biten_hali"], ozet["Ahmet"]["biten_m2"]), (1, Decimal("4")))
        self.assertEqual(ozet["Ahmet"]["fire_m2"], 0)
        self.client.force_login(self.ofis)
        self.assertContains(self.client.get(reverse("pano")), "Biten halı m²")
        self.assertIsNotNone(zigzag)

    def test_eski_sevk_fotograflari_kucultulur(self):
        from datetime import date

        from . import fotograf
        from .models import SiparisFotografi
        self._yeni((None, "100", "100", "1"), fotograflar=[self._foto()])
        sp = Siparis.objects.get(urun="Peluş")
        foto = sp.fotograflar.get()
        eski = foto.resim.size
        Siparis.objects.filter(pk=sp.pk).update(durum="sevk", sevk_tarihi=timezone.localdate() - timedelta(days=100))
        self.assertEqual(fotograf.arsiv_kucult()[0], 0)  # henüz 6 ay olmadı
        Siparis.objects.filter(pk=sp.pk).update(sevk_tarihi=timezone.localdate() - timedelta(days=200))
        adet, kazanc = fotograf.arsiv_kucult()
        foto.refresh_from_db()
        self.assertEqual(adet, 1)
        self.assertTrue(foto.kucultuldu)
        self.assertLess(foto.resim.size, eski)
        from PIL import Image
        with foto.resim.open("rb") as f:
            self.assertEqual(max(Image.open(f).size), fotograf.ARSIV_KENAR)
        self.assertEqual(fotograf.arsiv_kucult()[0], 0)
        # pano günde bir kez çalıştırır
        self.assertIsNotNone(fotograf.gunluk_arsiv_kucult())
        self.assertIsNone(fotograf.gunluk_arsiv_kucult())
        self.assertTrue(SiparisFotografi.objects.filter(pk=foto.pk).exists())
        self.assertIsInstance(date.today(), date)

    def test_sevk_tarihi_yazilir(self):
        self.client.force_login(self.ofis)
        self.client.post(reverse("siparis_durum", args=[self.siparis.pk]), {"durum": "sevk"})
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.sevk_tarihi, timezone.localdate())


class OlcuGocuTesti(TemelVeri):
    def test_eski_siparis_ve_isi_satira_baglanir(self):
        import importlib

        from django.apps import apps as gercek
        g = importlib.import_module("uretim.migrations.0028_olcu_satirlari_is_notu")
        eski = Siparis.objects.create(musteri=self.siparis.musteri, urun="Eski", teslim_tarihi=timezone.localdate(),
                                      en_cm=Decimal("200"), boy_cm=Decimal("300"), durum="uretimde")
        lot = self.yeni_lot(siparis=eski)
        acik = Siparis.objects.create(musteri=self.siparis.musteri, urun="Açık", teslim_tarihi=timezone.localdate(),
                                      en_cm=Decimal("100"), boy_cm=Decimal("100"), adet=2)
        g.olculeri_satira_cevir(gercek, None)
        lot.refresh_from_db()
        self.assertEqual(lot.kalem, eski.kalemler.get())
        self.assertEqual(acik.lotlar.get().baslangic_m2, Decimal("2.00"))
        # eski sipariş düzenlenince ikinci iş açılmaz
        servisler.siparis_islerini_ac(eski)
        self.assertEqual(eski.lotlar.count(), 1)



class IstasyonKendiIsiTesti(TemelVeri):
    """İstasyon hesabı yalnız kendi istasyonunu görür; lazerde giren/çıkan ölçü ve fire isteğe bağlı."""

    def setUp(self):
        from .models import HesapAyari
        self.lazer = Asama.objects.get(ad="Lazer kesim 1")
        self.zigzag = Asama.objects.get(ad="Zig-zag")
        self.tel = get_user_model().objects.create_user("ali_tel", password="x")
        HesapAyari.objects.create(kullanici=self.tel, personel=self.ahmet, istasyon=self.lazer)
        self.l1, self.l2 = self.yeni_lot(siparis=self.siparis), self.yeni_lot(siparis=self.siparis)
        servisler.islem_baslat(lot=self.l1, asama=self.lazer, personel=self.ahmet)
        servisler.islem_baslat(lot=self.l2, asama=self.zigzag, personel=self.ayse)

    def test_pano_ve_isler_yalniz_kendi_istasyonu(self):
        self.client.force_login(self.tel)
        pano = self.client.get(reverse("pano"))
        self.assertContains(pano, self.l1.lot_no)
        self.assertNotContains(pano, self.l2.lot_no)
        self.assertNotContains(pano, reverse("istasyon_ekrani", args=[self.zigzag.pk]))
        isler = self.client.get(reverse("lot_listesi"))
        self.assertContains(isler, self.l1.lot_no)
        self.assertNotContains(isler, self.l2.lot_no)
        # yönetici her şeyi görür
        self.client.force_login(get_user_model().objects.create_superuser("y_ki", password="x"))
        pano = self.client.get(reverse("pano"))
        self.assertContains(pano, self.l1.lot_no)
        self.assertContains(pano, self.l2.lot_no)
        self.assertContains(self.client.get(reverse("lot_listesi")), self.l2.lot_no)

    def test_lazerde_giren_cikan_olcu_ve_fire(self):
        lot = self.yeni_lot(siparis=self.siparis)
        self.client.force_login(self.tel)
        yanit = self.client.post(reverse("islem_baslat"), {"lot": lot.pk, "asama": self.lazer.pk,
                                                           "makine": self.makine(self.lazer),
                                                           "giris_en": "140", "giris_boy": "250"})
        self.assertRedirects(yanit, reverse("pano"))
        islem = IslemKaydi.objects.get(lot=lot)
        self.assertEqual((islem.giris_m2, islem.giris_en_cm), (Decimal("3.50"), Decimal("140")))
        sayfa = self.client.get(reverse("islem_bitir", args=[islem.pk]))
        self.assertContains(sayfa, 'name="fire_m2"')
        self.assertContains(sayfa, "140 × 250 cm")
        self.client.post(reverse("islem_bitir", args=[islem.pk]), {"cikis_en": "120", "cikis_boy": "250"})
        islem.refresh_from_db()
        self.assertEqual((islem.cikis_m2, islem.fire_m2), (Decimal("3.00"), Decimal("0.50")))
        # yalnız fire yazılırsa çıkış = giriş − fire
        lot2 = self.yeni_lot(siparis=self.siparis)
        i2 = servisler.islem_baslat(lot=lot2, asama=self.lazer, personel=self.ahmet)
        self.client.post(reverse("islem_bitir", args=[i2.pk]), {"fire_m2": "1,5"})
        i2.refresh_from_db()
        self.assertEqual((i2.giris_m2, i2.cikis_m2), (Decimal("10.00"), Decimal("8.50")))
        # hiçbir şey yazılmazsa giriş aynen geçer; lazer dışı istasyonda ölçü alanı yok
        self.assertNotContains(self.client.get(reverse("islem_baslat") + f"?lot={lot2.pk}"), "Lazer çıkışı")


class IkinciGuncellemeTesti(TasarimStudyosuTesti):
    """Kartela, basit sipariş, bayi görünümü, Bayiler + davet, bildirim, tamir, Nakışlı etiketi."""

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def _olcu(self, *satirlar, **ek):
        v = {"olcu-TOTAL_FORMS": str(len(satirlar)), "olcu-INITIAL_FORMS": "0"}
        for i, (en, boy, adet) in enumerate(satirlar):
            v.update({f"olcu-{i}-en_cm": en, f"olcu-{i}-boy_cm": boy, f"olcu-{i}-adet": adet})
        v.update(ek)
        return v

    def test_kartela_ve_rono_adi(self):
        from .models import KatalogSerisi, Renk
        self.assertEqual(Renk.objects.filter(grup="rono").count(), 7)
        self.assertEqual(Renk.objects.filter(grup="bienca", aktif=True).count(), 5)
        self.assertEqual(KatalogSerisi.objects.get(ad="Rono").kartela, "rono")
        self.assertTrue(DeriTuru.objects.filter(ad="Rono").exists())
        self.assertFalse(DeriTuru.objects.filter(ad="Rona").exists())
        from . import parcali
        self.assertEqual(parcali.MALZEME_AD["kahve_keten"], "Rono RN06 Koyu kahve")
        self.assertEqual(parcali._sec("siyah_keten", parcali.MALZEMELER, "x"), "antrasit_keten")

    def test_bayi_basit_siparis_ve_gorunum(self):
        from .models import Musteri, Renk
        bayi = Musteri.objects.get(ad="Ankara Bayi")
        bayi.studyo_acik = False
        bayi.save()
        self.client.force_login(self.bayi_hesap)
        self.assertRedirects(self.client.get(reverse("parcali_studyo")), reverse("bayi_siparis"))
        sayfa = self.client.get(reverse("bayi_siparis") + "?tur=suni")
        self.assertContains(sayfa, 'data-kod="RNO-001"')
        self.assertContains(sayfa, "RN06")
        self.assertNotContains(self.client.get(reverse("bayi_ana")), reverse("parcali_studyo"))
        # Rono: fotoğraflı model, renkler bölge bölge (kartela)
        yanit = self.client.post(reverse("bayi_siparis"), self._olcu(("160", "230", "2"), ("80", "150", ""),
                                                                     model="RNO-001", bolgeler='{"orta": "RN06"}',
                                                                     notlar="Acele"))
        self.assertRedirects(yanit, reverse("bayi_ana"))
        sp = Siparis.objects.get(musteri=bayi, katalog_modeli__kod="RNO-001")
        self.assertEqual((sp.durum, sp.renk, sp.kalemler.count(), sp.lotlar.count()), ("onay", None, 2, 0))
        self.assertIn("Orta: RN06", sp.renk_notu)
        self.assertContains(self.client.get(reverse("bayi_ana")), "Onay bekliyor")
        # Peluş: renk yazılır
        self.assertContains(self.client.post(reverse("bayi_siparis"), self._olcu(("100", "100", "1"), model="IPS-449")),
                            "Rengi yazın")
        self.client.post(reverse("bayi_siparis"), self._olcu(("100", "100", "1"), model="IPS-449", renk_notu="Krem"))
        self.assertTrue(Siparis.objects.filter(musteri=bayi, renk_notu="Krem").exists())
        # ofis onaylar → her ölçüye iş; bayi istasyonu "Üretimde" olarak görür, "bekliyor" görmez
        self.client.force_login(self.yonetici)
        self.client.post(reverse("siparis_onay", args=[sp.pk]), {"islem": "onayla", "onay-hali_turu": HaliTuru.objects.get(ad="Suni deri halı").pk,
                                                                 "onay-teslim_tarihi": "2026-12-20"})
        sp.refresh_from_db()
        self.assertEqual(sp.lotlar.count(), 2)
        lot = sp.lotlar.first()
        servisler.islem_baslat(lot=lot, asama=lot.siradaki_asama, personel=self.ahmet)
        # ofisin girdiği sipariş de bayide görünür
        Siparis.objects.create(musteri=bayi, urun="WhatsApp siparişi", teslim_tarihi=timezone.localdate())
        self.client.force_login(self.bayi_hesap)
        ana = self.client.get(reverse("bayi_ana")).content.decode()
        self.assertIn("Üretimde · Lazer kesim", ana)
        self.assertIn("WhatsApp siparişi", ana)
        self.assertNotIn("bekliyor</span>", ana.replace("Onay bekliyor</span>", ""))
        self.assertNotIn("çalışılıyor", ana)
        self.assertNotIn(str(self.ahmet), ana)

    def test_bayiler_sayfasi_ve_davet(self):
        from .models import BayiDavet, Musteri
        self.client.force_login(self.ofis)
        yanit = self.client.post(reverse("bayi_listesi"), {"ad": "İzmir Bayi", "telefon": "0532 111 22 33"})
        davet = BayiDavet.objects.latest("pk")
        self.assertRedirects(yanit, f"{reverse('bayi_listesi')}?davet={davet.pk}")
        sayfa = self.client.get(yanit.url)
        self.assertContains(sayfa, "wa.me/905321112233")
        self.assertContains(sayfa, reverse("davet_ac", args=[davet.anahtar]))
        k = davet.kullanici
        self.assertEqual((k.username, k.has_usable_password()), ("izmir-bayi", False))
        # ofis hesabı kapatamaz
        m = Musteri.objects.get(ad="İzmir Bayi")
        self.assertEqual(self.client.post(reverse("bayi_hesap", args=[m.pk])).status_code, 403)
        # bayi bağlantıyı açar, şifresini koyar, girer
        self.client.logout()
        adres = reverse("davet_ac", args=[davet.anahtar])
        self.assertContains(self.client.get(adres), "izmir-bayi")
        yanit = self.client.post(adres, {"new_password1": "Hali-2026x", "new_password2": "Hali-2026x"})
        self.assertRedirects(yanit, reverse("bayi_ana"))
        k.refresh_from_db()
        self.assertTrue(k.check_password("Hali-2026x"))
        self.client.logout()
        self.assertEqual(self.client.get(adres).status_code, 410)  # tek kullanımlık
        # süresi dolan bağlantı
        self.client.force_login(self.ofis)
        self.client.post(reverse("bayi_davet", args=[m.pk]))
        eski = BayiDavet.objects.latest("pk")
        BayiDavet.objects.filter(pk=eski.pk).update(son_gecerlilik=timezone.now() - timedelta(minutes=1))
        self.client.logout()
        self.assertEqual(self.client.get(reverse("davet_ac", args=[eski.anahtar])).status_code, 410)

    def test_bildirim_sifreleme_ve_gonderim(self):
        import base64
        from unittest import mock

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        from . import bildirim
        from .models import BildirimAboneligi
        # tarayıcı tarafı anahtarları
        ua = ec.generate_private_key(ec.SECP256R1())
        ua_acik = ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        auth = b"0123456789abcdef"
        b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
        govde = bildirim.sifrele(b'{"x":1}', b64(ua_acik), b64(auth))
        tuz, idlen = govde[:16], govde[20]
        sunucu_acik = govde[21:21 + idlen]
        ortak = ua.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sunucu_acik))
        h = lambda s, k, i, n: HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=i).derive(k)
        ikm = h(auth, ortak, b"WebPush: info\x00" + ua_acik + sunucu_acik, 32)
        acik = AESGCM(h(tuz, ikm, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(
            h(tuz, ikm, b"Content-Encoding: nonce\x00", 12), govde[21 + idlen:], None)
        self.assertEqual(acik, b'{"x":1}\x02')
        # abonelik kaydı + yeni bayi siparişinde gönderim
        self.client.force_login(self.ofis)
        self.client.post(reverse("bildirim_abone"), data={"endpoint": "https://fcm.googleapis.com/fcm/send/abc",
                                                          "keys": {"p256dh": b64(ua_acik), "auth": b64(auth)}},
                         content_type="application/json")
        self.assertEqual(BildirimAboneligi.objects.count(), 1)
        self.assertContains(self.client.get(reverse("pano")), "bildirim_durum".replace("_", "/")[:0] + "/bildirim/durum/")
        with mock.patch("urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = None
            self.client.force_login(self.bayi_hesap)
            self.client.post(reverse("bayi_siparis"), self._olcu(("100", "100", "1"), model="RNO-002", renk="RN01"))
        istek = urlopen.call_args[0][0]
        self.assertEqual(istek.full_url, "https://fcm.googleapis.com/fcm/send/abc")
        self.assertTrue(istek.headers["Authorization"].startswith("vapid t="))
        self.client.force_login(self.ofis)
        durum = self.client.get(reverse("bildirim_durum")).json()
        self.assertEqual(durum["sayi"], Siparis.objects.filter(durum="onay").count())
        self.assertIn("RNO-002", durum["metin"])

    def test_tamir_iade(self):
        biye = Asama.objects.get(ad="Biye")
        lot = self.yeni_lot(siparis=self.siparis)
        UretimLotu.objects.filter(pk=lot.pk).update(durum="tamamlandi")
        Siparis.objects.filter(pk=self.siparis.pk).update(durum="sevk", musteri=self.bayi_hesap.hesap_ayari.musteri)
        self.client.force_login(self.ofis)
        self.assertContains(self.client.get(reverse("siparis_detay", args=[self.siparis.pk])), reverse("tamir_ac", args=[self.siparis.pk]))
        yanit = self.client.post(reverse("tamir_ac", args=[self.siparis.pk]), {
            "neden": "tamir", "kaynak_lot": lot.pk, "aciklama": "Biye söküldü", "istasyonlar": [biye.pk],
            "hata_asama": biye.pk, "hata_personel": self.ayse.pk})
        self.assertRedirects(yanit, reverse("siparis_detay", args=[self.siparis.pk]))
        self.siparis.refresh_from_db()
        self.assertEqual(self.siparis.durum, "tamirde")
        tamir = self.siparis.tamirler.get()
        # Biye ekranına TAMİR olarak düşer
        gelen = [k for k in uyarilar.gelenler(biye) if k.lot == tamir.lot]
        self.assertEqual(len(gelen), 1)
        self.client.force_login(self.yonetici)
        self.assertContains(self.client.get(reverse("istasyon_parca", args=[biye.pk])), "TAMİR")
        # bayi görmez: hâlâ "Sevk edildi"
        self.client.force_login(self.bayi_hesap)
        ana = self.client.get(reverse("bayi_ana"))
        self.assertContains(ana, "Sevk edildi")
        self.assertNotContains(ana, "Tamir")
        # tamir bitince sipariş eski durumuna döner; stok değişmez
        kalan = self.ham.kalan_m2
        i = servisler.islem_baslat(lot=tamir.lot, asama=biye, personel=self.ahmet)
        servisler.islem_bitir(islem=i, personel=self.ahmet)
        self.siparis.refresh_from_db()
        tamir.refresh_from_db()
        self.assertEqual((self.siparis.durum, tamir.bitis is not None, self.ham.kalan_m2), ("sevk", True, kalan))
        ozet = raporlar.tamir_ozeti(timezone.localdate(), timezone.localdate())
        self.assertEqual((ozet["toplam"], ozet["istasyon"], ozet["personel"]), (1, [("Biye", 1)], [("Ayşe", 1)]))

    def test_nakisli_etiketi(self):
        nakisli = HaliTuru.objects.get(ad="Nakışlı halı")
        sp = Siparis.objects.create(musteri=self.siparis.musteri, urun="N", hali_turu=nakisli, teslim_tarihi=timezone.localdate())
        lot = self.yeni_lot(siparis=sp)
        nakis = Asama.objects.get(ad="Nakış")
        i = servisler.islem_baslat(lot=lot, asama=nakis, personel=self.ahmet)
        servisler.islem_bitir(islem=i, personel=self.ahmet)
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        k = [k for k in uyarilar.gelenler(lazer) if k.lot == lot][0]
        self.assertEqual(k.on_islem, "Nakışlı")
        self.client.force_login(self.yonetici)
        self.assertContains(self.client.get(reverse("istasyon_parca", args=[lazer.pk])), "(Nakışlı)")


class FotoModelTesti(TasarimStudyosuTesti):
    """Gerçek fotoğraflı modeller: bölge renkleri fotoğraf üzerinde boyanır, sipariş boyanmış fotoğrafla gider."""

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def setUp(self):
        import tempfile

        from django.test import override_settings

        super().setUp()
        self.medya = tempfile.TemporaryDirectory()
        self.ayar = override_settings(MEDIA_ROOT=self.medya.name)
        self.ayar.enable()

    def tearDown(self):
        self.ayar.disable()
        self.medya.cleanup()

    def test_bayi_secili_modeli_parcali_studyoda_tasarlar(self):
        from . import parcali
        with self.settings(STUDYO_BAYIYE_ACIK=False):
            self.client.force_login(self.bayi_hesap)
            sayfa = self.client.get(reverse("bayi_siparis") + "?tur=suni")
            self.assertContains(sayfa, 'data-tasarla="1"')
            self.assertNotContains(sayfa, "foto-model/RNO")
            kod = parcali.SECILI_MODELLER[0]
            studyo = self.client.get(reverse("parcali_studyo") + f"?hazir={kod}")
            self.assertEqual(studyo.status_code, 200)
            self.assertNotContains(studyo, 'data-kod="IPS-462"')  # yalnız seçili modeller
            self.assertRedirects(self.client.get(reverse("parcali_studyo") + "?hazir=IPS-462"), reverse("bayi_siparis"),
                                 fetch_redirect_response=False)
            v = parcali.temizle(parcali.hazir_degerler(kod))
            veri = {k: ("on" if x is True else x) for k, x in v.items() if x not in (None, False)}
            veri.update({"adet": "1"})
            self.assertRedirects(self.client.post(reverse("parcali_studyo"), veri), reverse("bayi_ana"))
            self.assertTrue(Siparis.objects.filter(durum="onay", tasarim__veri__katalog=kod).exists())
            self.client.force_login(self.ofis)
            self.assertContains(self.client.get(reverse("pano")), "Bugün kim ne yaptı")

    def test_yeni_bayi_duzeni_ve_stüdyo_yalniz_yonetici(self):
        with self.settings(STUDYO_BAYIYE_ACIK=False):
            self.client.force_login(self.bayi_hesap)
            for ad in ("parcali_studyo", "tasarim_studyo"):
                self.assertRedirects(self.client.get(reverse(ad)), reverse("bayi_siparis"), fetch_redirect_response=False)
            secim = self.client.get(reverse("bayi_siparis"))
            self.assertContains(secim, "Suni deri halı")
            self.assertContains(secim, "?tur=deri")
            self.assertNotContains(self.client.get(reverse("bayi_ana")), reverse("parcali_studyo"))
            suni = self.client.get(reverse("bayi_siparis") + "?tur=suni").content.decode()
            deri = self.client.get(reverse("bayi_siparis") + "?tur=deri").content.decode()
            self.assertIn('data-kod="RNO-010"', suni)
            self.assertNotIn('data-kod="TOS-034"', suni)
            self.assertIn('data-kod="TOS-034"', deri)
            self.assertNotIn('data-kod="RNO-010"', deri)
            self.client.force_login(self.ofis)
            self.assertRedirects(self.client.get(reverse("parcali_studyo")), reverse("pano"), fetch_redirect_response=False)
            self.client.force_login(self.yonetici)
            self.assertEqual(self.client.get(reverse("parcali_studyo")).status_code, 200)

    def test_boyama_ve_fikirler(self):
        from . import foto_model
        from .models import KatalogModeli
        self.assertEqual(set(KatalogModeli.objects.filter(kod__in=foto_model.MODELLER).values_list("kod", flat=True)),
                         set(foto_model.MODELLER))
        for kod in foto_model.MODELLER:
            asil = foto_model.secim_temizle(kod, {})
            fikirler = foto_model.fikirler(kod)
            self.assertGreaterEqual(len(fikirler), 6 if foto_model.MODELLER[kod].get("kaynak") != "katalog" else 2)
            self.assertNotIn(asil, fikirler)
            resim = foto_model.boya(kod, fikirler[0], 200)
            self.assertEqual(resim.width, 200)
        # geçersiz renk fotoğraftakine döner; metal yalnız desen bölgesinde, gümüş iplik yok
        secim = foto_model.secim_temizle("RNO-010", {"dis": "ALTIN", "bant": "BN04", "orta": "XX"})
        self.assertEqual(secim, {"dis": "RN06", "bant": "BN04", "orta": "RN06", "nakis_motif": "", "nakis_iplik": "bej"})
        self.assertIn("gumus", foto_model.secenekler(foto_model.IPLIK))
        self.assertTrue({"ALTIN", "GUMUS"} <= set(foto_model.secenekler(foto_model.DESEN)))
        self.assertEqual(foto_model.metin("RNO-006", foto_model.secim_temizle("RNO-006", {"iplik": "kahve"})),
                         "Zemin: RN03 · Nakış şeridi: RN07 · Nakış ipliği: Kahve")
        # renk değişince resim değişir; aynı seçim önbellekten gelir
        a = foto_model.jpeg("RNO-012", foto_model.secim_temizle("RNO-012", {}), 260)
        b = foto_model.jpeg("RNO-012", foto_model.secim_temizle("RNO-012", {"bant": "RN06"}), 260)
        self.assertNotEqual(a, b)
        self.assertEqual(b, foto_model.jpeg("RNO-012", foto_model.secim_temizle("RNO-012", {"bant": "RN06"}), 260))

    def test_katalog_fotograflari_desen_ve_motif(self):
        from . import foto_model
        katalog = [k for k, m in foto_model.MODELLER.items() if m.get("kaynak") == "katalog"]
        self.assertEqual(len(katalog), 31)
        for kod in ("BNA-004", "BNA-010", "RNO-002", "BNA-017"):
            self.assertEqual(foto_model.boya(kod, foto_model.fikirler(kod)[0], 120).width, 120)
        # lazer deseni ve nakış motifi değişir; geçersiz kod fotoğraftakine döner
        secim = foto_model.secim_temizle("BNA-003", {"desen_kodu": "DB015", "desen": "ALTIN"})
        self.assertEqual(secim["desen_kodu"], "DB015")
        self.assertEqual(foto_model.secim_temizle("BNA-003", {"desen_kodu": "DB002"})["desen_kodu"], "")  # gizli desen
        self.assertNotEqual(foto_model.jpeg("BNA-003", secim, 260),
                            foto_model.jpeg("BNA-003", foto_model.secim_temizle("BNA-003", {"desen": "ALTIN"}), 260))
        m = foto_model.secim_temizle("RNO-006", {"motif": "75.01", "iplik": "kahve"})
        self.assertIn("Nakış: 75.01", foto_model.metin("RNO-006", m))
        self.assertEqual(foto_model.secim_temizle("RNO-006", {"motif": "59.02"})["motif"], "")  # marka logosu yok
        self.assertEqual(foto_model.boya("RNO-006", m, 200).width, 200)

    def test_aile_kurallari_nakisli_bant_ve_yeni_modeller(self):
        from . import foto_model
        from .models import KatalogModeli, Renk
        self.assertTrue(Renk.objects.filter(kod="BN05", aktif=True).exists())  # Bienca 5 renk (2026-11-09 BN05 geri)
        self.assertTrue(KatalogModeli.objects.filter(kod__in=["BNA-027", "BNA-028", "RNO-013"]).count() == 3)
        # zemin kendi ailesinde: Rono zemine Bienca/metal olmaz, Rono halıdaki banda Bienca olur
        s = foto_model.secim_temizle("RNO-010", {"orta": "BN01", "bant": "BN04", "dis": "RN08"})
        self.assertEqual((s["orta"], s["bant"], s["dis"]), ("RN06", "BN04", "RN06"))
        self.assertEqual(foto_model.secim_temizle("BNA-005", {"orta": "RN03"})["orta"], "BN03")
        # nakışlı bant: bant Rono olur, lazer deseni kalkar, siparişe yazılır
        s = foto_model.secim_temizle("BNA-003", {"nakis_motif": "61.01", "nakis_iplik": "altin", "desen_kodu": "DB001",
                                                 "desen": "ALTIN"})
        self.assertTrue(s["desen"].startswith("RN"))
        self.assertEqual(s["desen_kodu"], "")
        self.assertIn("Nakışlı bant: 61.01", foto_model.metin("BNA-003", s))
        self.assertEqual(foto_model.boya("BNA-003", s, 200).width, 200)
        # nakışlı Rono yakın görünüm: motif ve iplik değişir
        s = foto_model.secim_temizle("RNO-013", {"motif": "75.01", "iplik": "altin", "zemin": "RN06"})
        self.assertNotEqual(foto_model.jpeg("RNO-013", s, 260), foto_model.jpeg("RNO-013", foto_model.secim_temizle("RNO-013", {}), 260))
        for kod in ("BNA-027", "BNA-028"):
            self.assertEqual(foto_model.boya(kod, foto_model.fikirler(kod)[0], 150).width, 150)

    def test_ayni_olcu_halilar_tek_tek_gecer(self):
        from .models import Musteri
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        sp = Siparis.objects.create(musteri=Musteri.objects.create(ad="Beşli"), urun="x", teslim_tarihi=timezone.localdate())
        servisler.kalemleri_kaydet(sp, [(None, Decimal("100"), Decimal("150"), 5)])
        servisler.siparis_islerini_ac(sp)
        lot = sp.lotlar.get()
        self.assertEqual(lot.adet, 5)
        islem = servisler.islem_baslat(lot=lot, asama=lazer, personel=self.ahmet)
        # ekranda "Kaç halı bitti?" sorulur; 2 tanesi biter → ayrı iş olarak sıradaki istasyona geçer
        self.client.force_login(self.ofis_kullanici if hasattr(self, "ofis_kullanici") else
                                get_user_model().objects.create_superuser("bes-yonetici", password="x"))
        self.assertContains(self.client.get(reverse("islem_bitir", args=[islem.pk])), "Kaç halı bitti?")
        servisler.islem_bitir(islem=islem, personel=self.ahmet, biten_adet=2)
        lot.refresh_from_db()
        yeni = lot.bolunenler.get()
        self.assertEqual((lot.adet, yeni.adet), (3, 2))
        self.assertEqual(yeni.lot_no, f"{lot.lot_no}/2")
        self.assertEqual(yeni.durum, "bekliyor")
        self.assertEqual(yeni.son_asama, lazer)
        self.assertTrue(lot.islemler.filter(bitis__isnull=True).exists())  # kalan 3 halı lazerde sürüyor
        self.assertEqual(lot.mevcut_m2 + yeni.mevcut_m2, Decimal("7.50"))
        self.assertIn("×2", yeni.olcu_metni)
        # kalanların hepsi bitince bölünme olmaz; yeni iş numarası da bozulmaz
        servisler.islem_bitir(islem=lot.islemler.get(bitis__isnull=True), personel=self.ahmet, biten_adet=3)
        self.assertEqual(lot.bolunenler.count(), 1)
        self.assertTrue(UretimLotu.objects.create(baslangic_kg=0, baslangic_m2=1).lot_no.endswith("2"))
        with self.assertRaises(ValidationError):
            servisler.islem_bitir(islem=servisler.islem_baslat(lot=yeni, asama=Asama.objects.get(ad="Zig-zag"),
                                                               personel=self.ahmet), personel=self.ahmet, biten_adet=9)

    def test_duzeltme_yetkisi_lazer_tableti(self):
        from .models import DuzeltmeKaydi, HesapAyari, Musteri
        lazer = Asama.objects.get(ad="Lazer kesim 1")
        zigzag = Asama.objects.get(ad="Zig-zag")
        tablet = get_user_model().objects.create_user("lazer-tablet-1", password="x")
        HesapAyari.objects.create(kullanici=tablet, istasyon=lazer, duzeltme_yetkisi=True)
        baska = get_user_model().objects.create_user("biye-tablet", password="x")
        HesapAyari.objects.create(kullanici=baska)
        sp = Siparis.objects.create(musteri=Musteri.objects.create(ad="Çift"), urun="x", teslim_tarihi=timezone.localdate())
        servisler.kalemleri_kaydet(sp, [(None, Decimal("100"), Decimal("150"), 1)])
        servisler.siparis_islerini_ac(sp)
        lot = sp.lotlar.get()
        islem = servisler.islem_baslat(lot=lot, asama=lazer, personel=self.ahmet)
        # yetkisiz tablet: düğme yok, istek reddedilir
        self.client.force_login(baska)
        self.assertNotContains(self.client.get(reverse("lot_detay", args=[lot.pk])), "Bu işi iptal et")
        self.assertEqual(self.client.post(reverse("is_iptal", args=[lot.pk]), {"neden": "x"}).status_code, 403)
        # yetkili lazer tableti: başlatmayı geri alır, işi iptal eder
        self.client.force_login(tablet)
        sayfa = self.client.get(reverse("lot_detay", args=[lot.pk]))
        self.assertContains(sayfa, "Başlatmayı geri al")
        self.assertContains(sayfa, "siparişini iptal et")
        self.client.post(reverse("islem_geri_al", args=[islem.pk]))
        self.assertEqual(lot.islemler.count(), 0)
        self.client.post(reverse("is_iptal", args=[lot.pk]), {"neden": "iki kez girildi"})
        lot.refresh_from_db()
        self.assertEqual(lot.durum, "iptal")
        kayit = DuzeltmeKaydi.objects.get(tur="is_iptal")
        self.assertEqual((kayit.kullanici, kayit.neden), (tablet, "iki kez girildi"))
        # yönetici geri açar
        self.client.force_login(self.yonetici)
        self.assertContains(self.client.get(reverse("duzeltmeler")), "iki kez girildi")
        self.client.post(reverse("duzeltmeler"), {"kayit": kayit.pk})
        lot.refresh_from_db()
        self.assertEqual(lot.durum, "bekliyor")
        # zig-zag'a geçmiş iş tabletten düzeltilemez; sipariş de iptal edilemez
        i1 = servisler.islem_baslat(lot=lot, asama=lazer, personel=self.ahmet)
        servisler.islem_bitir(islem=i1, personel=self.ahmet)
        servisler.islem_baslat(lot=lot, asama=zigzag, personel=self.ahmet)
        self.assertFalse(servisler.duzeltebilir(tablet, lot))
        self.assertFalse(servisler.siparis_iptal_edilebilir(tablet, sp))
        self.assertTrue(servisler.duzeltebilir(self.yonetici, lot))
        # çift sipariş: yalnız lazer/nakış/kaplamadaki işleriyle iptal
        sp2 = Siparis.objects.create(musteri=sp.musteri, urun="çift", teslim_tarihi=timezone.localdate())
        servisler.kalemleri_kaydet(sp2, [(None, Decimal("100"), Decimal("150"), 1), (None, Decimal("80"), Decimal("120"), 1)])
        servisler.siparis_islerini_ac(sp2)
        self.client.force_login(tablet)
        self.client.post(reverse("siparis_iptal_tablet", args=[sp2.lotlar.first().pk]), {"neden": "çift sipariş"})
        sp2.refresh_from_db()
        self.assertEqual(sp2.durum, "iptal")
        self.assertFalse(sp2.lotlar.exclude(durum="iptal").exists())

    def test_bayi_fotograf_ekler_ve_yalniz_kendininkini_gorur(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from .models import Musteri

        def foto():
            t = io.BytesIO()
            Image.new("RGB", (800, 600), (120, 100, 90)).save(t, "JPEG")
            return SimpleUploadedFile("oda.jpg", t.getvalue(), content_type="image/jpeg")

        self.client.force_login(self.bayi_hesap)
        v = {"olcu-TOTAL_FORMS": "1", "olcu-INITIAL_FORMS": "0", "olcu-0-en_cm": "160", "olcu-0-boy_cm": "230",
             "olcu-0-adet": "1", "model": "RNO-010", "bolgeler": "{}", "renk": "RN06"}
        self.assertContains(self.client.post(reverse("bayi_siparis"), {**v, "fotograflar": [foto() for _ in range(4)]}),
                            "En çok 3")
        self.assertRedirects(self.client.post(reverse("bayi_siparis"), {**v, "fotograflar": [foto(), foto()]}),
                             reverse("bayi_ana"))
        sp = Siparis.objects.get(musteri=Musteri.objects.get(ad="Ankara Bayi"), katalog_modeli__kod="RNO-010")
        self.assertEqual(sp.fotograflar.count(), 2)  # bayinin 2 fotoğrafı (boyama kapalı)
        url = sp.fotograflar.last().resim.url
        self.assertContains(self.client.get(reverse("bayi_ana")), url)
        self.assertEqual(self.client.get(url).status_code, 200)
        # başka müşterinin fotoğrafı bayiye kapalı
        baska = Siparis.objects.create(musteri=Musteri.objects.create(ad="Başka"), urun="x", teslim_tarihi=timezone.localdate())
        f = fotograf_kaydet = __import__("uretim.fotograf", fromlist=["kaydet"]).kaydet(baska, foto().read())
        self.assertEqual(self.client.get(f.resim.url).status_code, 404)

    def test_bayi_fotografli_siparis(self):
        from .models import Musteri
        self.client.force_login(self.bayi_hesap)
        sayfa = self.client.get(reverse("bayi_siparis") + "?tur=suni")
        self.assertContains(sayfa, 'data-kod="RNO-010"')
        self.assertContains(sayfa, "foto-modeller")
        resim = self.client.get(reverse("foto_model_resmi", args=["RNO-010"]) + "?bant=BN01&w=k")
        self.assertEqual((resim.status_code, resim["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(self.client.get(reverse("foto_model_resmi", args=["XYZ"])).status_code, 404)
        v = {"olcu-TOTAL_FORMS": "1", "olcu-INITIAL_FORMS": "0", "olcu-0-en_cm": "160", "olcu-0-boy_cm": "230",
             "olcu-0-adet": "1", "model": "RNO-010", "bolgeler": '{"dis": "RN03", "bant": "BN01", "orta": "RN03"}'}
        self.assertRedirects(self.client.post(reverse("bayi_siparis"), v), reverse("bayi_ana"))
        sp = Siparis.objects.get(musteri=Musteri.objects.get(ad="Ankara Bayi"), katalog_modeli__kod="RNO-010")
        self.assertEqual(sp.renk_notu, "Dış bant: RN03 · Eskitme bant: BN01 · Orta: RN03")
        self.assertIn("Renkler:", sp.notlar)
        self.assertEqual(sp.fotograflar.count(), 1)
        # ofis siparişte boyanmış fotoğrafı görür
        self.client.force_login(self.yonetici)
        self.assertContains(self.client.get(reverse("siparis_detay", args=[sp.pk])), sp.fotograflar.first().resim.url)


class KartelaStudyoTesti(TasarimStudyosuTesti):
    """Rono / Bienca modelleri yalnız kendi kartelasıyla (+ ince çizgi metalik) değiştirilir; fikir ver modeli korur."""

    test_bayi_tasarlar_ofis_siparisten_onaylar_bayi_takip_eder = None
    test_ret = None

    def test_hazir_modeller_kartelada(self):
        from . import parcali
        for kod in parcali.HAZIR:
            on = parcali.seri_kartelasi(kod)
            if not on:
                continue
            v = parcali.hazir_degerler(kod)
            izinli = set(parcali.kartela_secenekleri(on)) | {m for l in parcali.KARTELA_MALZEMELERI.values() for m in l}
            for alan in parcali.MALZEME_ALANLARI:
                # zemin serinin kartelasında; yalnız katalog fotoğrafında ortası başka malzeme olan model kendi ortasını korur
                kendi = [parcali.FOTO_RENK[kod]["zemin"]] if kod in parcali.FOTO_RENK else []
                self.assertIn(v[alan], parcali.KARTELA_MALZEMELERI[on] + kendi if alan == "zemin" else izinli, f"{kod} {alan}")
            self.assertIn(v["kenar_renk"], sorted(izinli) + parcali.METALIK, kod)
        # kartelalı modelde dışarıdan gelen yanlış malzeme düzeltilir; serbest tasarımda dokunulmaz
        v = parcali.temizle({"duzen": "halkali", "katalog": "BNA-005", "zemin": "pelus_taba", "halka_sayisi": 1,
                             "h1_malzeme": "gumus", "kenar_renk": "siyah"})
        self.assertEqual((v["zemin"], v["h1_malzeme"]), ("bienca_bn02", "gumus"))
        self.assertIn(v["kenar_renk"], parcali.KARTELA_MALZEMELERI["BNA"])
        v = parcali.temizle({"duzen": "halkali", "zemin": "pelus_taba", "kenar_renk": "siyah"})
        self.assertEqual((v["zemin"], v["kenar_renk"]), ("pelus_taba", "siyah"))

    def test_fikir_secili_modeli_korur(self):
        from . import parcali
        taban = parcali.hazir_degerler("RNO-004")
        self.client.force_login(self.bayi_hesap)
        liste = self.client.get(reverse("parcali_fikir"), {"en": "160", "boy": "230", "katalog": "RNO-004"}).json()
        self.assertEqual(len(liste), 6)
        renkler = set()
        for f in liste:
            v = f["v"]
            self.assertEqual((v["katalog"], v["halka_sayisi"], v["h1_tur"], v["h2_desen"]),
                             ("RNO-004", taban["halka_sayisi"], taban["h1_tur"], taban["h2_desen"]))
            self.assertIn(v["zemin"], parcali.KARTELA_MALZEMELERI["RNO"])
            self.assertIn(v["h1_malzeme"], parcali.kartela_secenekleri("RNO") + parcali.KARTELA_MALZEMELERI["BNA"])
            renkler.add(v["zemin"])
            self.assertTrue(f["baslik"].startswith("RNO-004"))
        self.assertGreater(len(renkler), 2)
        # model seçmeden Bienca sekmesindeyken: serbest ama Bienca kartelası
        liste = self.client.get(reverse("parcali_fikir"), {"seri": "BNA"}).json()
        self.assertTrue(all(f["v"]["zemin"] in parcali.KARTELA_MALZEMELERI["BNA"] for f in liste))
        # önizleme: Bienca dokusu ve kartela renginden kenar çizilir
        v = parcali.hazir_degerler("BNA-005")
        self.assertEqual(self.client.get(reverse("parcali_onizleme_resmi"), {**v, "b": 300}).status_code, 200)
        sayfa = self.client.get(reverse("parcali_studyo"), {"hazir": "RNO-004"})
        self.assertContains(sayfa, 'data-grup="RNO"')
        self.assertContains(sayfa, "Bienca BN01 Gümüş &amp; altın varak")
        self.assertNotContains(self.client.get(reverse("bayi_siparis") + "?tur=suni"), "Renklerini değiştir")
