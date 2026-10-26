from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from uretim import servisler
from uretim.models import Asama, DeriTuru, HaliTuru, HamDeriGirisi, Malzeme, Musteri, Personel, Siparis, Tedarikci, UretimLotu


class Command(BaseCommand):
    help = "Denemek için örnek personel, ham deri, sipariş ve lot oluşturur. Canlı veritabanında çalıştırmayın."

    def handle(self, *args, **opts):
        if UretimLotu.objects.exists():
            self.stdout.write(self.style.WARNING("Veritabanında zaten lot var, örnek veri eklenmedi."))
            return

        User = get_user_model()
        if not User.objects.filter(username="yonetici").exists():
            User.objects.create_superuser("yonetici", password="yonetici123")
        if not User.objects.filter(username="tablet").exists():
            User.objects.create_user("tablet", password="tablet123")

        personel = []
        for ad, gorev in [("Ahmet Yılmaz", "Tabakhane"), ("Ayşe Demir", "Kesim"), ("Mehmet Kaya", "Dikim"),
                          ("Fatma Çelik", "Kalite kontrol"), ("Ali Şahin", "Genel")]:
            p = Personel(ad_soyad=ad, gorev=gorev)
            p.pin_ayarla("1234")
            p.save()
            personel.append(p)

        ted = Tedarikci.objects.create(ad="Anadolu Deri Ltd.")
        mus = Musteri.objects.create(ad="Örnek Mobilya A.Ş.")
        kuzu = DeriTuru.objects.get(ad="Kuzu")
        koyun = DeriTuru.objects.get(ad="Koyun")

        hd1 = HamDeriGirisi.objects.create(tedarikci=ted, deri_turu=kuzu, kalite="A", adet=200,
                                           kg=Decimal("640"), m2=Decimal("110"))
        hd2 = HamDeriGirisi.objects.create(tedarikci=ted, deri_turu=koyun, kalite="B", adet=120,
                                           kg=Decimal("520"), m2=Decimal("95"))

        nakisli, lazerli = HaliTuru.objects.get(ad="Nakışlı halı"), HaliTuru.objects.get(ad="Lazerli halı")
        sp = Siparis.objects.create(musteri=mus, hali_turu=nakisli, urun="200x300 krem nakışlı halı", deri_turu=kuzu,
                                    adet=4, toplam_m2=Decimal("24"),
                                    teslim_tarihi=timezone.localdate() + timedelta(days=5))
        Siparis.objects.create(musteri=mus, hali_turu=lazerli, urun="160x230 gri lazerli halı", deri_turu=koyun, adet=2,
                               toplam_m2=Decimal("7.4"), teslim_tarihi=timezone.localdate() - timedelta(days=2))

        D = Decimal

        def makine(asama):
            return asama.makineler.first()

        # 1. iş: tek stok lotundan; Nakış ve Lazer kesim bitti, Zig-zag devam ediyor
        nakis, lazer, zigzag = (Asama.objects.get(ad=ad) for ad in ("Nakış", "Lazer kesim", "Zig-zag"))
        islem = servisler.yeni_is_baslat(personel=personel[0], siparis=sp, kaynaklar=[(hd1, D("320"), D("55"))],
                                         asama=nakis, makine=makine(nakis))
        l1 = islem.lot
        kg, m2 = D("320"), D("55")
        for i, asama in enumerate([nakis, lazer]):
            if i:
                islem = servisler.islem_baslat(lot=l1, asama=asama, personel=personel[i % 2], makine=makine(asama))
            kg, m2 = kg - D("12"), m2 - D("1.5")
            servisler.islem_bitir(islem=islem, personel=personel[i % 2], cikis_kg=kg, cikis_m2=m2)
        servisler.islem_baslat(lot=l1, asama=zigzag, personel=personel[0], makine=makine(zigzag))
        # 2. iş: iki stok lotundan malzeme; Nakış bitti, Lazer kesimi bekliyor
        islem = servisler.yeni_is_baslat(personel=personel[3], siparis=sp,
                                         kaynaklar=[(hd1, D("200"), D("35")), (hd2, D("100"), D("18"))],
                                         asama=nakis, makine=makine(nakis))
        servisler.islem_bitir(islem=islem, personel=personel[3], cikis_kg=D("290"), cikis_m2=D("51.5"))

        # İstasyon süre sınırları (yönetim panelinden değiştirilebilir) ve stok uyarı sınırları
        sinirlar = {"Nakış": (4, 8), "Lazer kesim": (4, 3), "Zig-zag": (8, 6), "Biye": (8, 4), "Lanfel": (8, 4)}
        for asama in Asama.objects.filter(aktif=True):
            if asama.ad in sinirlar:
                asama.azami_bekleme_saat, asama.azami_sure_saat = map(D, sinirlar[asama.ad])
                asama.save()
        DeriTuru.objects.filter(ad="Kuzu").update(min_kg=D("150"))
        DeriTuru.objects.filter(ad="Koyun").update(min_kg=D("100"))
        for ad, kategori, birim, giris, sinir in [
            ("Nakış ipliği (altın)", "iplik", "makara", "60", "20"), ("Zig-zag ipliği", "iplik", "makara", "8", "10"),
            ("Biye şeridi", "diger", "m", "400", "100"), ("Taban keçesi", "astar", "m2", "120", "30"),
        ]:
            m = Malzeme.objects.create(ad=ad, kategori=kategori, birim=birim, min_stok=D(sinir))
            servisler.malzeme_giris(malzeme=m, miktar=D(giris))
        servisler.malzeme_duzelt(malzeme=Malzeme.objects.get(ad="Biye şeridi"), neden="fire", miktar=D("12"),
                                 aciklama="Hatalı kesim")

        self.stdout.write(self.style.SUCCESS(
            "Örnek veri yüklendi.\n"
            "  Yönetici girişi: yonetici / yonetici123\n"
            "  Tablet girişi:   tablet / tablet123\n"
            "  Tüm personelin PIN'i: 1234"
        ))
