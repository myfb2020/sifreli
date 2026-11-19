"""Toplu stok (2026-11-19, kullanıcı): rulo malzemelerde (Rono, Suni deri, Keçe, Süet, lamine, halı tabanı…) aynı
tür + renk + model + firmadan gelen mal eskisinin üstüne eklenir. Bu modül hem migration'da (geçmiş modellerle)
hem programda çalışır: modeller sözlükle verilir, `models` içe aktarılmaz."""

from decimal import Decimal

# Migration'da "eskisine eklensin" işareti kendiliğinden konan türler (birleşik malzemeler de: lamine, taban)
TOPLU_ADLAR = {"rono", "rona", "suni deri", "keçe", "süet", "bienca"}


def kucuk(metin):
    return (metin or "").strip().replace("İ", "i").replace("I", "ı").casefold()


def anahtar(tur_id, renk, model, tedarikci_id):
    """Aynı stok kaydı sayılanlar: tür + renk + model + firma (büyük/küçük harf ve boşluk farkı yok sayılır)."""
    return (tur_id, kucuk(renk), kucuk(model), tedarikci_id)


def toplu_ad_mi(ad, bilesik):
    return bilesik or kucuk(ad) in TOPLU_ADLAR


def ilk_gelis(M, h, kaynak="giris", fason=None, eski_lot_no=""):
    """Stok kaydının kendi gelişini 'Gelişler' listesine yazar."""
    return M["StokGelisi"].objects.create(
        ham_deri_id=h.pk, tarih=h.tarih, tedarikci_id=h.tedarikci_id, kg=h.kg or 0, m2=h.m2, adet=h.adet,
        giris_birimi=h.giris_birimi, giris_miktari=h.giris_miktari, en_cm=h.en_cm, kaynak=kaynak, fason=fason,
        eski_lot_no=eski_lot_no, notlar=h.notlar or "")


def gelisleri_tamamla(M, kayitlar):
    """Gelişi hiç yazılmamış toplu kayıtlara kendi gelişi eklenir (fasondan geldiyse 'fason')."""
    for h in kayitlar:
        if M["StokGelisi"].objects.filter(ham_deri_id=h.pk).exists():
            continue
        fason = M["FasonIsi"].objects.filter(gelen_lot_id=h.pk).first()
        ilk_gelis(M, h, kaynak="fason" if fason else "giris", fason=fason)


def ekle(M, ana, diger):
    """'diger' stok kaydı 'ana'ya eklenir: miktar, gelişler, işlere verilenler, düzeltmeler / satışlar, fason ve
    geri alma kayıtları anaya geçer; diger silinir, numarası (eski etiket) gelişte kalır."""
    ana.m2 = (ana.m2 or 0) + (diger.m2 or 0)
    ana.kg = (ana.kg or 0) + (diger.kg or 0)
    if ana.adet or diger.adet:
        ana.adet = (ana.adet or 0) + (diger.adet or 0)
    if diger.tarih and ana.tarih and diger.tarih < ana.tarih:
        ana.tarih = diger.tarih
    ana.save(update_fields=["m2", "kg", "adet", "tarih"])
    gelisler = M["StokGelisi"].objects.filter(ham_deri_id=diger.pk)
    if not gelisler.exists():
        ilk_gelis(M, diger)
    for g in M["StokGelisi"].objects.filter(ham_deri_id=diger.pk):
        g.ham_deri_id = ana.pk
        if not g.eski_lot_no:
            g.eski_lot_no = diger.lot_no
        g.save(update_fields=["ham_deri", "eski_lot_no"])
    for k in M["LotKaynagi"].objects.filter(ham_deri_id=diger.pk):
        var = M["LotKaynagi"].objects.filter(ham_deri_id=ana.pk, uretim_lotu_id=k.uretim_lotu_id).first()
        if var is None:
            k.ham_deri_id = ana.pk
            k.save(update_fields=["ham_deri"])
        else:
            var.kg += k.kg
            var.m2 += k.m2
            var.save(update_fields=["kg", "m2"])
            k.delete()
    M["DeriDuzeltme"].objects.filter(ham_deri_id=diger.pk).update(ham_deri_id=ana.pk)
    M["FasonIsi"].objects.filter(gelen_lot_id=diger.pk).update(gelen_lot_id=ana.pk)
    # yöneticinin "geri al"ı düşülen miktarı stok kaydının numarasıyla geri koyar: numara anaya çevrilir
    for islem in M["IslemKaydi"].objects.exclude(stok_dusumu=[]):
        degisti = False
        for kayit in islem.stok_dusumu or []:
            if kayit and kayit[0] == diger.pk:
                kayit[0] = ana.pk
                degisti = True
        if degisti:
            islem.save(update_fields=["stok_dusumu"])
    diger.delete()


def birlestir(M):
    """Toplu türlerde aynı anahtarlı kayıtları birleştirir (en eski kayıt kalır). Birleşen kayıt sayısını döner."""
    turler = set(M["DeriTuru"].objects.filter(toplu=True).values_list("pk", flat=True))
    kayitlar = list(M["HamDeriGirisi"].objects.filter(deri_turu_id__in=turler).order_by("tarih", "lot_no", "pk"))
    gelisleri_tamamla(M, kayitlar)
    gruplar = {}
    for h in kayitlar:
        gruplar.setdefault(anahtar(h.deri_turu_id, h.renk, h.model, h.tedarikci_id), []).append(h)
    sayi = 0
    for grup in gruplar.values():
        ana = grup[0]
        for diger in grup[1:]:
            ekle(M, ana, diger)
            sayi += 1
    return sayi


SIFIR = Decimal(0)
