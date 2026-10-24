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
