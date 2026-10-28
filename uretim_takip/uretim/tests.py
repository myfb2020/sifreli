from datetime import timedelta
from pathlib import Path
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import raporlar, servisler, uyarilar
from .models import (
    Asama, DeriTuru, HaliTuru, HamDeriGirisi, IslemKaydi, LotKaynagi, Makine, Musteri, Personel, Siparis, Tedarikci, UretimLotu,
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
        self.assertIn((self.asamalar[2].ad, 1), i["dagilim"])
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
        self.assertContains(self.stok_gir(giris_birimi="mtul", giris_miktari="50"), "rulonun enini")
        self.stok_gir(giris_birimi="mtul", giris_miktari="50", en_cm="140")
        h = HamDeriGirisi.objects.latest("pk")
        self.assertEqual((h.m2, h.giris_metni), (Decimal("70.00"), "50 metretül × 140 cm"))

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
        # İstasyon listesi açık kalır, üstte kendi istasyonunun kısayolu
        self.assertContains(self.client.get(reverse("istasyon_secimi")), "Lazer kesim 2 ekranını aç")


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

        tur = {ad: DeriTuru.objects.get(ad=ad) for ad in ("Keçe", "Süet", "Rona")}
        lamine = DeriTuru.objects.get(ad="3'lü lamine (Keçe+Süet+Rona)")
        fasoncu = Tedarikci.objects.create(ad="Presçi")
        lotlar = {ad: HamDeriGirisi.objects.create(tedarikci=self.ham.tedarikci, deri_turu=t, kg=0, m2=Decimal("50"),
                                                   renk="Bej" if ad == "Rona" else "Gri",
                                                   model="Mermer" if ad == "Rona" else "")
                  for ad, t in tur.items()}
        ofis = get_user_model().objects.create_user("ofis", password="x", is_staff=True)
        ofis.groups.add(ofis_grubu())
        self.client.force_login(ofis)

        v = {"fasoncu": fasoncu.pk, "hedef_tur": lamine.pk, "kaynak-TOTAL_FORMS": 3, "kaynak-INITIAL_FORMS": 0}
        for i, ad in enumerate(("Keçe", "Süet", "Rona")):
            v[f"kaynak-{i}-stok_no"] = lotlar[ad].lot_no
            v[f"kaynak-{i}-m2"] = "10" if ad != "Rona" else "12"
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

        # Teslim al: renk/model rona katmanından gelir
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
        self.assertContains(detay, lotlar["Rona"].lot_no)
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
