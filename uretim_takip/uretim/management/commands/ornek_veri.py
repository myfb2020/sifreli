from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from uretim import servisler
from uretim.models import Asama, DeriTuru, HamDeriGirisi, Musteri, Personel, Siparis, Tedarikci, UretimLotu


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

        sp = Siparis.objects.create(musteri=mus, urun="200x300 krem kuzu patchwork halı", deri_turu=kuzu,
                                    adet=4, toplam_m2=Decimal("24"),
                                    teslim_tarihi=timezone.localdate() + timedelta(days=5))
        Siparis.objects.create(musteri=mus, urun="160x230 gri koyun halı", deri_turu=koyun, adet=2,
                               toplam_m2=Decimal("7.4"), teslim_tarihi=timezone.localdate() - timedelta(days=2))

        asamalar = list(Asama.objects.filter(aktif=True))
        D = Decimal
        # 1. iş: tek stok lotundan; ilk üç aşama bitti, dördüncüsü devam ediyor
        islem = servisler.yeni_is_baslat(personel=personel[0], siparis=sp, kaynaklar=[(hd1, D("320"), D("55"))],
                                         asama=asamalar[0])
        l1 = islem.lot
        kg, m2 = D("320"), D("55")
        for i, asama in enumerate(asamalar[:3]):
            if i:
                islem = servisler.islem_baslat(lot=l1, asama=asama, personel=personel[i % 2])
            kg, m2 = kg - D("12"), m2 - D("1.5")
            servisler.islem_bitir(islem=islem, personel=personel[i % 2], cikis_kg=kg, cikis_m2=m2)
        servisler.islem_baslat(lot=l1, asama=asamalar[3], personel=personel[0])
        # 2. iş: iki stok lotundan malzeme; tasnif bitti, sıradaki aşamayı bekliyor
        islem = servisler.yeni_is_baslat(personel=personel[3], siparis=sp,
                                         kaynaklar=[(hd1, D("200"), D("35")), (hd2, D("100"), D("18"))],
                                         asama=asamalar[0])
        servisler.islem_bitir(islem=islem, personel=personel[3], cikis_kg=D("290"), cikis_m2=D("51.5"))

        self.stdout.write(self.style.SUCCESS(
            "Örnek veri yüklendi.\n"
            "  Yönetici girişi: yonetici / yonetici123\n"
            "  Tablet girişi:   tablet / tablet123\n"
            "  Tüm personelin PIN'i: 1234"
        ))
