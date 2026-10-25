from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import raporlar, servisler
from .models import Asama, DeriTuru, HamDeriGirisi, IslemKaydi, Musteri, Personel, Siparis, Tedarikci, UretimLotu


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

    def yeni_lot(self, **kw):
        kw.setdefault("ham_deri", self.ham)
        kw.setdefault("baslangic_kg", Decimal("50"))
        kw.setdefault("baslangic_m2", Decimal("10"))
        return UretimLotu.objects.create(**kw)


class NumaralamaTesti(TemelVeri):
    def test_numaralar_sirali_uretilir(self):
        yil = timezone.localdate().year
        self.assertEqual(self.ham.lot_no, f"HD-{yil}-0001")
        a, b = self.yeni_lot(), self.yeni_lot()
        self.assertEqual(a.lot_no, f"UL-{yil}-0001")
        self.assertEqual(b.lot_no, f"UL-{yil}-0002")
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
        for url in [reverse("pano"), reverse("islem_baslat"), reverse("lot_listesi"),
                    reverse("lot_detay", args=[lot.pk]), reverse("islem_bitir", args=[islem.pk]), reverse("rapor")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_yanlis_pin_ile_islem_baslamaz(self):
        lot = self.yeni_lot()
        yanit = self.client.post(reverse("islem_baslat"), {
            "personel": self.ahmet.pk, "pin": "0000", "lot": lot.pk, "asama": self.asamalar[0].pk,
        })
        self.assertContains(yanit, "PIN hatalı")
        self.assertFalse(IslemKaydi.objects.exists())

    def test_ekrandan_baslat_ve_bitir(self):
        lot = self.yeni_lot()
        yanit = self.client.post(reverse("islem_baslat"), {
            "personel": self.ahmet.pk, "pin": "1234", "lot": lot.pk, "asama": self.asamalar[0].pk,
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

    def test_etiketlerde_lot_adresi_qr_olarak_bulunur(self):
        lot = self.yeni_lot()
        yanit = self.client.get(reverse("etiketler"), {"lot": lot.pk})
        self.assertContains(yanit, lot.lot_no)
        self.assertContains(yanit, "<svg")

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
            "Ham Deri": [["HD-ESKI-1", "01.10.2026", "Anadolu Deri", "Kuzu", "A", 200, "640", "110,5", ""],
                         ["", "2026-10-02", "Yeni Tedarikçi", "Merinos", "Karışık", "", "1.250,75", 90, ""]],
            "Siparişler": [["SP-ESKI-7", "Örnek Mobilya", "05.10.2026", "200x300 halı", "Kuzu", 4, 24,
                            "30.10.2026", "Üretimde", ""]],
            "Üretim Lotları": [["L-15", "hd-eski-1", "SP-ESKI-7", 320, 55, 284, "50,5", "Tabaklama", "", ""],
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
            "Ham Deri": [["", "", "T", "Kuzu", "", "", "abc", "5", ""],
                         ["", "32.13.2026", "T", "Kuzu", "", "", "5", "5", ""],
                         ["", "", "T", "Kuzu", "Z", "", "5", "5", ""],
                         ["", "", "T", "Kuzu", "", "", "5", "-5", ""]],
            "Üretim Lotları": [["", "YOK-1", "", 1, 1, "", "", "Uçurma", "", ""]],
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
        self.assertIn((self.asamalar[2].ad, 1), i["dagilim"])
        self.siparis.toplam_m2 = None
        self.assertEqual(self.siparis.ilerleme()["yuzde"], 50)

    def test_liste_ve_detay_tablete_acik_form_kapali(self):
        self.yeni_lot(siparis=self.siparis)
        self.client.force_login(self.tablet)
        yanit = self.client.get(reverse("siparis_listesi"))
        self.assertContains(yanit, self.siparis.siparis_no)
        self.assertNotContains(yanit, "+ Yeni sipariş")
        self.assertContains(self.client.get(reverse("siparis_detay", args=[self.siparis.pk])), "Lotlar (1)")
        self.assertEqual(self.client.get(reverse("siparis_yeni")).status_code, 403)
        self.assertEqual(self.client.post(reverse("siparis_durum", args=[self.siparis.pk]), {"durum": "sevk"}).status_code, 403)

    def test_geciken_siparis_uyarisi_ve_sekmeler(self):
        self.siparis.teslim_tarihi = timezone.localdate() - timedelta(days=3)
        self.siparis.save()
        self.client.force_login(self.tablet)
        yanit = self.client.get(reverse("siparis_listesi"))
        self.assertContains(yanit, "3 gün gecikti")
        self.assertContains(yanit, "1 sipariş teslim tarihini geçti")
        self.assertNotContains(self.client.get(reverse("siparis_listesi"), {"durum": "sevk"}), self.siparis.siparis_no)
        self.assertContains(self.client.get(reverse("siparis_listesi"), {"ara": "M"}), self.siparis.siparis_no)

    def test_yeni_siparis_yeni_musteriyle(self):
        self.client.force_login(self.yonetici)
        veri = {"musteri": "", "yeni_musteri": "Yıldız Otel", "urun": "Lobi halısı", "adet": 1,
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
    def test_islem_bitirken_virgul_ve_nokta_kabul_edilir(self):
        from .forms import IslemBitirForm

        for kg, m2, beklenen in [("47,5", "9,25", Decimal("9.25")), ("47.5", "9.25", Decimal("9.25"))]:
            f = IslemBitirForm({"personel": self.ahmet.pk, "pin": "1234", "cikis_kg": kg, "cikis_m2": m2})
            self.assertTrue(f.is_valid(), f.errors)
            self.assertEqual(f.cleaned_data["cikis_m2"], beklenen)
        self.assertFalse(IslemBitirForm({"personel": self.ahmet.pk, "pin": "1234", "cikis_kg": "-1", "cikis_m2": "1"}).is_valid())

    def test_bitir_ekrani_virgullu_baslangic_degerini_geri_alir(self):
        self.client.force_login(get_user_model().objects.create_user("tablet", password="x"))
        lot = self.yeni_lot(baslangic_kg=Decimal("47.50"))
        islem = servisler.islem_baslat(lot=lot, asama=self.asamalar[0], personel=self.ahmet)
        sayfa = self.client.get(reverse("islem_bitir", args=[islem.pk]))
        self.assertContains(sayfa, 'value="47,50"')
        yanit = self.client.post(reverse("islem_bitir", args=[islem.pk]),
                                 {"personel": self.ahmet.pk, "pin": "1234", "cikis_kg": "47,50", "cikis_m2": "9,8"})
        self.assertRedirects(yanit, reverse("pano"))
        islem.refresh_from_db()
        self.assertEqual(islem.cikis_m2, Decimal("9.80"))


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
