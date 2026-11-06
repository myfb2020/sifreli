"""Üretim iş kuralları. Görünümler veritabanını doğrudan değiştirmez, buradan geçer."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    DuzeltmeKaydi, TamirKaydi, DeriDuzeltme, FasonIsi, HamDeriGirisi, IslemKaydi, IsNotu, LotKaynagi, MalzemeHareketi, SistemAyari, SiparisKalemi,
    UretimLotu, sayi_metni,
)


# --- Sipariş ölçü satırları ve otomatik işler -------------------------------------


@transaction.atomic
def kalemleri_kaydet(siparis, satirlar):
    """Siparişin ölçü satırlarını verilen listeye eşitler: [(kalem ya da None, en, boy, adet), ...].

    Başlamış işi olan satır silinemez (ValidationError); ölçüsü değişen, henüz başlamamış işin m²'si güncellenir.
    """
    eldekiler = {k.pk: k for k in siparis.kalemler.all()}
    tutulan = {k.pk for k, *_ in satirlar if k is not None}
    for pk, kalem in eldekiler.items():
        if pk in tutulan:
            continue
        if kalem.lotlar.filter(islemler__isnull=False).exists():
            raise ValidationError(f"{kalem.olcu_metni()} satırının işi başlamış; bu satır silinemez.")
        kalem.lotlar.all().delete()
        kalem.delete()
    for sira, (kalem, en, boy, adet) in enumerate(satirlar, 1):
        if kalem is None:
            kalem = SiparisKalemi(siparis=siparis)
        degisti = (kalem.en_cm, kalem.boy_cm, kalem.adet) != (en, boy, adet)
        kalem.sira, kalem.en_cm, kalem.boy_cm, kalem.adet = sira, en, boy, adet
        kalem.save()
        if degisti:
            kalem.lotlar.filter(islemler__isnull=True).update(baslangic_m2=kalem.m2, mevcut_m2=kalem.m2)
    siparis.kalemleri_yansit()
    siparis_islerini_ac(siparis)


def siparis_islerini_ac(siparis):
    """Açık / üretimdeki siparişin işi olmayan her ölçü satırı için iş açar (ilk istasyona 'gelen iş' düşer)."""
    if siparis.durum not in ("acik", "uretimde"):
        return []
    if not siparis.kalemler.exists() and siparis.en_cm and siparis.boy_cm and not siparis.lotlar.exists():
        # Tasarım stüdyosundan gelen, ölçüsü siparişte yazılı sipariş: tek satıra çevrilir.
        SiparisKalemi.objects.create(siparis=siparis, en_cm=siparis.en_cm, boy_cm=siparis.boy_cm, adet=siparis.adet or 1)
    acilan = []
    for kalem in siparis.kalemler.filter(lotlar__isnull=True):
        acilan.append(UretimLotu.objects.create(siparis=siparis, kalem=kalem, baslangic_kg=Decimal(0),
                                                baslangic_m2=kalem.m2))
    return acilan


def not_ekle(*, lot, metin, asama=None, personel=None, kullanici=None):
    metin = (metin or "").strip()
    if not metin:
        raise ValidationError("Notu yazın.")
    return IsNotu.objects.create(lot=lot, metin=metin[:1000], asama=asama, personel=personel, kullanici=kullanici)


@transaction.atomic
def islem_baslat(*, lot, asama, personel, aciklama="", makine=None, giris_olcu=None):
    """giris_olcu: (en, boy) cm — lazerde isteğe bağlı giren parça ölçüsü; girilirse işlemin giriş m²'si olur."""
    lot = UretimLotu.objects.select_for_update().get(pk=lot.pk)
    if lot.durum in ("tamamlandi", "iptal"):
        raise ValidationError(f"{lot} işi {lot.get_durum_display().lower()}, işlem başlatılamaz.")
    if lot.islemler.filter(bitis__isnull=True).exists():
        raise ValidationError(f"{lot} işinde zaten açık bir işlem var. Önce onu bitirin.")
    if makine is not None and makine.asama_id != asama.pk:
        raise ValidationError(f"{makine} makinesi “{asama.ad}” istasyonunda değil.")

    islem = IslemKaydi.objects.create(
        lot=lot,
        asama=asama,
        makine=makine,
        personel=personel,
        giris_kg=lot.mevcut_kg,
        giris_m2=(giris_olcu[0] * giris_olcu[1] / 10000).quantize(Decimal("0.01")) if giris_olcu else lot.mevcut_m2,
        giris_en_cm=giris_olcu[0] if giris_olcu else None,
        giris_boy_cm=giris_olcu[1] if giris_olcu else None,
        aciklama=aciklama,
    )
    lot.durum = "islemde"
    lot.son_asama = asama
    lot.save(update_fields=["durum", "son_asama"])
    if aciklama and aciklama.strip():
        not_ekle(lot=lot, metin=aciklama, asama=asama, personel=personel)

    if lot.siparis and lot.siparis.durum == "acik":
        lot.siparis.durum = "uretimde"
        lot.siparis.save(update_fields=["durum"])
    return islem


def ilk_adim_mi(islem):
    """İşin ilk istasyonu mu (ör. lazer)? Ana malzemenin kullanımı burada girilir."""
    return not islem.lot.islemler.exclude(pk=islem.pk).filter(baslangic__lte=islem.baslangic).exists()


def cesit_anahtari(stok):
    return f"{stok.deri_turu_id}|{stok.renk}|{stok.model}"


def stoktaki_cesitler():
    """Kalanı olan malzeme çeşitleri: [(anahtar, 'Suni deri · Beyaz · Rono – 42 m²'), ...] (FIFO seçimi için)."""
    toplam, ad = {}, {}
    for stok in HamDeriGirisi.objects.select_related("deri_turu").order_by("deri_turu__ad", "renk", "model"):
        kalan = stok.kalan_m2
        if kalan <= 0:
            continue
        k = cesit_anahtari(stok)
        toplam[k] = toplam.get(k, Decimal(0)) + kalan
        ad[k] = stok.cesit_metni
    return [(k, f"{ad[k]} – stokta {sayi_metni(toplam[k].quantize(Decimal('0.01')))} m²") for k in ad]


def malzeme_dus(*, lot, m2, rulo=None, cesit=None):
    """Kullanılan ana malzemeyi stoktan düşer: rulo okutulduysa ondan, yoksa çeşidin en eski lotlarından (FIFO).

    Düşülen miktarlar işin kaynaklarına (LotKaynagi) eklenir.
    """
    if m2 is None or m2 <= 0:
        raise ValidationError("Kullanılan ölçüyü girin.")
    if rulo is not None:
        adaylar = [HamDeriGirisi.objects.select_for_update().get(pk=rulo.pk)]
    elif cesit:
        tur_id, renk, model = cesit.split("|", 2)
        adaylar = list(HamDeriGirisi.objects.select_for_update()
                       .filter(deri_turu_id=tur_id, renk=renk, model=model).order_by("tarih", "lot_no"))
    else:
        raise ValidationError("Kullanılan malzemeyi seçin ya da rulonun etiketini okutun.")
    kalan_toplam = sum((s.kalan_m2 for s in adaylar), Decimal(0))
    if m2 > kalan_toplam:
        ad = adaylar[0].cesit_metni if adaylar else "Bu malzeme"
        raise ValidationError(f"{ad}: stokta yalnızca {kalan_toplam} m² var, {m2} m² düşülemez.")
    gerekli = m2
    dusulen = []
    for stok in adaylar:
        if gerekli <= 0:
            break
        al = min(gerekli, stok.kalan_m2)
        if al <= 0:
            continue
        kaynak, yeni = LotKaynagi.objects.get_or_create(uretim_lotu=lot, ham_deri=stok,
                                                        defaults={"kg": Decimal(0), "m2": al})
        if not yeni:
            kaynak.m2 += al
            kaynak.save(update_fields=["m2"])
        dusulen.append([stok.pk, str(al)])
        gerekli -= al
    return dusulen


@transaction.atomic
def islem_bitir(*, islem, personel, cikis_kg=None, cikis_m2=None, aciklama="", malzemeler=(), kesim=None, cikis_olcu=None,
                fire_m2=None):
    """Aşamayı bitirir. malzemeler: [(malzeme, miktar), ...] bu aşamada kullanılan sarf malzemeleri.

    kesim: ilk istasyonda kullanılan ana malzeme {"m2", "rulo" ya da "cesit"}; stoktan düşülür, işin başlangıç m²'si
    kullanılan miktar, çıkışı siparişin net m²'si olur (aradaki fark fire). Çıkış verilmezse giriş aynen geçer.
    """
    islem = IslemKaydi.objects.select_for_update().select_related("lot", "asama", "lot__siparis").get(pk=islem.pk)
    if islem.bitis is not None:
        raise ValidationError("Bu işlem zaten bitirilmiş.")
    if kesim is None and ilk_adim_mi(islem) and SistemAyari.yukle().stok_zorunlu and not islem.lot.kaynaklar.exists():
        raise ValidationError("Kullanılan malzemeyi ve ölçüsünü girin (stok okutma zorunlu).")
    if kesim is not None:
        islem.stok_dusumu = [*malzeme_dus(lot=islem.lot, m2=kesim["m2"], rulo=kesim.get("rulo"), cesit=kesim.get("cesit")),
                             ["baslangic", str(islem.lot.baslangic_m2)]]
        lot = islem.lot
        kullanilan = sum((k.m2 for k in lot.kaynaklar.all()), Decimal(0))
        if lot.kalem_id:
            net = lot.kalem.m2
        else:
            net = lot.siparis.tek_m2 if lot.siparis_id else None
            if net and lot.siparis.lotlar.count() == 1:
                net = net * (lot.siparis.adet or 1)
        lot.baslangic_m2 = kullanilan
        lot.save(update_fields=["baslangic_m2"])
        islem.giris_m2 = kullanilan
        if cikis_m2 is None:
            cikis_m2 = min(net, kullanilan) if net else kullanilan
    if cikis_olcu:  # lazerde çıkan ölçü (isteğe bağlı)
        islem.cikis_en_cm, islem.cikis_boy_cm = cikis_olcu
        cikis_m2 = (cikis_olcu[0] * cikis_olcu[1] / 10000).quantize(Decimal("0.01"))
    if fire_m2 is not None:  # lazerde elle yazılan fire (isteğe bağlı)
        if cikis_olcu:
            islem.giris_m2 = cikis_m2 + fire_m2
        else:
            cikis_m2 = max(islem.giris_m2 - fire_m2, Decimal(0))
    cikis_kg = islem.giris_kg if cikis_kg is None else cikis_kg
    cikis_m2 = islem.giris_m2 if cikis_m2 is None else cikis_m2
    if cikis_kg < 0 or cikis_m2 < 0:
        raise ValidationError("Çıkış değerleri negatif olamaz.")

    islem.bitis = timezone.now()
    islem.bitiren = personel
    islem.cikis_kg = cikis_kg
    islem.cikis_m2 = cikis_m2
    if aciklama:
        islem.aciklama = f"{islem.aciklama}\n{aciklama}".strip()
    islem.save()
    if aciklama and aciklama.strip():
        not_ekle(lot=islem.lot, metin=aciklama, asama=islem.asama, personel=personel)

    for malzeme, miktar in malzemeler:
        if miktar and miktar > 0:
            MalzemeHareketi.objects.create(malzeme=malzeme, tur="kullanim", miktar=-miktar, islem=islem,
                                           personel=personel)

    lot = islem.lot
    lot.mevcut_kg = cikis_kg
    lot.mevcut_m2 = cikis_m2
    lot.durum = "bekliyor" if lot.asama_sonrasi(islem.asama) else "tamamlandi"
    lot.save(update_fields=["mevcut_kg", "mevcut_m2", "durum"])

    siparis = lot.siparis
    if lot.tur == "tamir":
        if lot.durum == "tamamlandi":
            tamir_bitti(lot)
        return islem
    if siparis and lot.durum == "tamamlandi":
        if not siparis.lotlar.exclude(durum__in=["tamamlandi", "iptal"]).exists():
            siparis.durum = "tamamlandi"
            siparis.save(update_fields=["durum"])
    return islem


@transaction.atomic
def yeni_is_baslat(*, personel, siparis, kaynaklar, asama, aciklama="", makine=None, eski_stok=None):
    """Stoktan malzeme alarak yeni bir iş açar ve ilk aşamasını başlatır.

    kaynaklar: [(stok_lotu, kg, m2), ...]. Aynı stok lotu birden çok kez okutulduysa miktarlar toplanır.
    eski_stok: (malzeme_turu, kg, m2) — yalnızca geçiş döneminde, etiketsiz eski stoktan; stoktan düşülmez.
    """
    toplam = {}
    for stok, kg, m2 in kaynaklar:
        onceki = toplam.get(stok.pk, (stok, Decimal(0), Decimal(0)))
        toplam[stok.pk] = (stok, onceki[1] + (kg or 0), onceki[2] + (m2 or 0))
    eski_tur, eski_kg, eski_m2 = eski_stok or (None, Decimal(0), Decimal(0))
    eski_kg, eski_m2 = eski_kg or Decimal(0), eski_m2 or Decimal(0)
    if eski_tur is not None:
        if not SistemAyari.yukle().gecis_modu:
            raise ValidationError("Geçiş dönemi kapalı: iş yalnızca etiketli stok lotlarından başlatılabilir.")
        if eski_kg <= 0 and eski_m2 <= 0:
            raise ValidationError("Eski stoktan aldığınız m² (ya da kg) miktarını girin.")
    if not toplam and eski_tur is None and SistemAyari.yukle().stok_zorunlu:
        raise ValidationError("En az bir stok lotundan malzeme girin (stok okutma zorunlu).")
    if siparis is not None and siparis.durum in ("sevk", "iptal"):
        raise ValidationError(f"{siparis} {siparis.get_durum_display().lower()}, bu siparişe iş açılamaz.")

    kilitli = {h.pk: h for h in HamDeriGirisi.objects.select_for_update().filter(pk__in=toplam)}
    hatalar = []
    for pk, (_, kg, m2) in toplam.items():
        stok = kilitli[pk]
        if kg <= 0 and m2 <= 0:
            hatalar.append(f"{stok.lot_no}: alınan kg veya m² girin.")
        if kg > stok.kalan_kg or m2 > stok.kalan_m2:
            hatalar.append(f"{stok.lot_no}: stokta {stok.kalan_kg} kg / {stok.kalan_m2} m² kaldı.")
    if hatalar:
        raise ValidationError(hatalar)

    bekleyen = (siparis.lotlar.filter(durum="bekliyor", islemler__isnull=True).order_by("kalem__sira", "pk").first()
                if siparis is not None else None)
    if bekleyen is not None:
        # Siparişin ölçü satırı için iş zaten açılmış (henüz başlamamış): yeni iş açılmaz, o iş başlatılır.
        if toplam or eski_tur is not None:
            bekleyen.baslangic_kg = sum((kg for _, kg, _ in toplam.values()), Decimal(0)) + eski_kg
            bekleyen.baslangic_m2 = sum((m2 for _, _, m2 in toplam.values()), Decimal(0)) + eski_m2
            bekleyen.mevcut_kg, bekleyen.mevcut_m2 = bekleyen.baslangic_kg, bekleyen.baslangic_m2
            bekleyen.eski_stok_turu = eski_tur
            bekleyen.save()
            LotKaynagi.objects.bulk_create(
                LotKaynagi(uretim_lotu=bekleyen, ham_deri=kilitli[pk], kg=kg, m2=m2) for pk, (_, kg, m2) in toplam.items()
            )
        return islem_baslat(lot=bekleyen, asama=asama, personel=personel, aciklama=aciklama, makine=makine)

    baslangic_m2 = sum((m2 for _, _, m2 in toplam.values()), Decimal(0)) + eski_m2
    if not toplam and eski_tur is None and siparis is not None:
        # Stok okutulmadan açılan iş: siparişin net m²'si (siparişin ilk işiyse); kullanılan malzeme ilk istasyon
        # bitince girilir. Aynı siparişe ikinci iş açılırsa toplam yeniden yazılmaz (pano iki kez saymasın).
        baslangic_m2 = Decimal(0) if siparis.lotlar.exists() else (siparis.toplam_m2 or Decimal(0))
    lot = UretimLotu.objects.create(
        siparis=siparis,
        baslangic_kg=sum((kg for _, kg, _ in toplam.values()), Decimal(0)) + eski_kg,
        baslangic_m2=baslangic_m2,
        eski_stok_turu=eski_tur,
    )
    LotKaynagi.objects.bulk_create(
        LotKaynagi(uretim_lotu=lot, ham_deri=kilitli[pk], kg=kg, m2=m2) for pk, (_, kg, m2) in toplam.items()
    )
    return islem_baslat(lot=lot, asama=asama, personel=personel, aciklama=aciklama, makine=makine)


@transaction.atomic
def tamir_ac(*, siparis, istasyonlar, neden, kaynak_lot=None, aciklama="", foto=None, hata_asama=None, hata_personel=None,
             kullanici=None):
    """Biten / sevk edilen siparişe tamir işi açar: seçilen istasyonlardan geçer, bitince sipariş eski durumuna döner.
    Bayi görmez; stoğa giriş yapılmaz."""
    if siparis.durum not in ("tamamlandi", "sevk", "tamirde"):
        raise ValidationError("Tamir / iade yalnız biten ya da sevk edilen siparişe açılır.")
    istasyonlar = list(istasyonlar)
    if not istasyonlar:
        raise ValidationError("Tamirin geçeceği en az bir istasyon seçin.")
    m2 = (kaynak_lot.mevcut_m2 if kaynak_lot else None) or (siparis.tek_m2 or Decimal(0))
    lot = UretimLotu.objects.create(siparis=siparis, kalem=kaynak_lot.kalem if kaynak_lot else None, tur="tamir",
                                    baslangic_kg=Decimal(0), baslangic_m2=m2)
    kayit = TamirKaydi(siparis=siparis, kaynak_lot=kaynak_lot, lot=lot, neden=neden, aciklama=aciklama,
                       hata_asama=hata_asama, hata_personel=hata_personel, kullanici=kullanici,
                       onceki_durum=siparis.durum if siparis.durum != "tamirde" else
                       (siparis.tamirler.order_by("tarih").first().onceki_durum if siparis.tamirler.exists() else "sevk"))
    if foto is not None:
        from django.core.files.base import ContentFile
        kayit.foto.save(f"{siparis.siparis_no}-tamir.jpg", ContentFile(foto), save=False)
    kayit.save()
    kayit.istasyonlar.set(istasyonlar)
    if aciklama:
        not_ekle(lot=lot, metin=f"🔧 {kayit.get_neden_display()}: {aciklama}", kullanici=kullanici)
    siparis.durum = "tamirde"
    siparis.save(update_fields=["durum"])
    return kayit


def tamir_bitti(lot):
    kayit = TamirKaydi.objects.filter(lot=lot).select_related("siparis").first()
    if kayit is None:
        return
    kayit.bitis = timezone.now()
    kayit.save(update_fields=["bitis"])
    siparis = kayit.siparis
    acik = siparis.lotlar.filter(tur="tamir").exclude(durum__in=["tamamlandi", "iptal"]).exists()
    if not acik and siparis.durum == "tamirde":
        siparis.durum = kayit.onceki_durum or "sevk"
        siparis.save(update_fields=["durum"])


# --- Yönetici düzeltmesi: yanlışlıkla başlatılan / bitirilen işlem ---------------------------------


def geri_alinabilir(islem):
    """İşin en son işlemi mi (yalnız o geri alınır)? Sevk / iptal edilmiş siparişte geri alma yok."""
    lot = islem.lot
    if lot.siparis_id and lot.siparis.durum in ("sevk", "iptal") and lot.tur != "tamir":
        return False
    return not lot.islemler.filter(baslangic__gt=islem.baslangic).exclude(pk=islem.pk).exists() and \
        not lot.islemler.filter(baslangic=islem.baslangic, pk__gt=islem.pk).exists()


@transaction.atomic
def islem_geri_al(*, islem, kullanici):
    """Açık işlem → başlatma silinir (iş o istasyonda yeniden bekler).
    Bitmiş işlem → bitirme geri alınır (iş o istasyonda yeniden 'çalışılıyor'); düşülen malzeme stoğa döner."""
    islem = IslemKaydi.objects.select_for_update().select_related("lot", "asama", "lot__siparis").get(pk=islem.pk)
    if not duzeltebilir(kullanici, islem.lot):
        raise ValidationError("Bu işlemi geri alma yetkiniz yok.")
    if not geri_alinabilir(islem):
        raise ValidationError("Yalnız işin en son işlemi geri alınabilir.")
    lot = UretimLotu.objects.select_for_update().get(pk=islem.lot_id)
    siparis = lot.siparis
    kim = kullanici.get_full_name() or kullanici.username
    if islem.bitis is None:
        asama = islem.asama
        islem.delete()
        onceki = lot.islemler.order_by("-baslangic", "-pk").first()
        lot.durum = "bekliyor"
        lot.son_asama = onceki.asama if onceki else None
        lot.save(update_fields=["durum", "son_asama"])
        if siparis and siparis.durum == "uretimde" and not IslemKaydi.objects.filter(lot__siparis=siparis).exists():
            siparis.durum = "acik"
            siparis.save(update_fields=["durum"])
        metin = f"↩ Yönetici geri aldı: {asama.ad} başlatması silindi ({kim})."
    else:
        tamamlanmisti = lot.durum == "tamamlandi"
        for kayit in islem.stok_dusumu or []:
            if kayit[0] == "baslangic":
                lot.baslangic_m2 = Decimal(kayit[1])
                continue
            kaynak = LotKaynagi.objects.filter(uretim_lotu=lot, ham_deri_id=kayit[0]).first()
            if kaynak is not None:
                kaynak.m2 -= Decimal(kayit[1])
                if kaynak.m2 <= 0 and not kaynak.kg:
                    kaynak.delete()
                else:
                    kaynak.save(update_fields=["m2"])
        MalzemeHareketi.objects.filter(islem=islem).delete()
        islem.bitis = None
        islem.bitiren = None
        islem.cikis_kg = islem.cikis_m2 = None
        islem.cikis_en_cm = islem.cikis_boy_cm = None
        islem.stok_dusumu = []
        islem.save()
        lot.durum = "islemde"
        lot.son_asama = islem.asama
        lot.mevcut_kg, lot.mevcut_m2 = islem.giris_kg, islem.giris_m2
        lot.save(update_fields=["durum", "son_asama", "mevcut_kg", "mevcut_m2", "baslangic_m2"])
        if tamamlanmisti and siparis:
            if lot.tur == "tamir":
                TamirKaydi.objects.filter(lot=lot).update(bitis=None)
                if siparis.durum != "tamirde":
                    siparis.durum = "tamirde"
                    siparis.save(update_fields=["durum"])
            elif siparis.durum == "tamamlandi":
                siparis.durum = "uretimde"
                siparis.save(update_fields=["durum"])
        metin = f"↩ Yönetici geri aldı: {islem.asama.ad} bitirmesi geri alındı, iş yeniden bu istasyonda ({kim})."
    IsNotu.objects.create(lot=lot, metin=metin, asama=islem.asama, kullanici=kullanici)
    DuzeltmeKaydi.objects.create(tur="geri_al", lot=lot, siparis=siparis, kullanici=kullanici, metin=metin[:300])
    return metin


# --- Düzeltme yetkisi: lazer tableti Lazer / Nakış / Kaplama'daki işleri düzeltir ---------------------------


def duzeltme_istasyonu_mu(asama):
    return asama is not None and (asama.lazer_mi or asama.ad.lower() in ("nakış", "kaplama"))


def duzeltebilir(kullanici, lot):
    """Yönetici her işi; düzeltme yetkili tablet yalnız Lazer / Nakış / Kaplama'nın ötesine geçmemiş işi düzeltir."""
    from .models import hesap_duzeltme_yetkili

    if getattr(kullanici, "is_superuser", False):
        return True
    if not hesap_duzeltme_yetkili(kullanici):
        return False
    return all(duzeltme_istasyonu_mu(i.asama) for i in lot.islemler.select_related("asama"))


def _kim(kullanici):
    return kullanici.get_full_name() or kullanici.username


def _lotu_iptal_et(lot, kullanici, neden):
    """İşi iptal eder: açık işlem kapanır, stoktan alınan malzeme stoğa döner. Geri açmak için durumunu döndürür."""
    acik = lot.islemler.filter(bitis__isnull=True).first()
    veri = {"lot": lot.pk, "durum": lot.durum, "son_asama": lot.son_asama_id, "acik_islem": acik.pk if acik else None,
            "kaynaklar": [[k.ham_deri_id, str(k.kg), str(k.m2)] for k in lot.kaynaklar.all()]}
    if acik is not None:
        acik.bitis = timezone.now()
        acik.cikis_kg, acik.cikis_m2 = acik.giris_kg, acik.giris_m2
        acik.aciklama = f"{acik.aciklama}\n(İş iptal edildi)".strip()
        acik.save()
    lot.kaynaklar.all().delete()
    lot.durum = "iptal"
    lot.save(update_fields=["durum"])
    IsNotu.objects.create(lot=lot, metin=f"🗑 İş iptal edildi: {neden} ({_kim(kullanici)}).", asama=lot.son_asama,
                          kullanici=kullanici)
    return veri


def _neden(neden):
    neden = (neden or "").strip()
    if not neden:
        raise ValidationError("İptal nedenini yazın.")
    return neden[:200]


@transaction.atomic
def is_iptal(*, lot, kullanici, neden):
    lot = UretimLotu.objects.select_for_update().get(pk=lot.pk)
    neden = _neden(neden)
    if lot.durum == "iptal":
        raise ValidationError("Bu iş zaten iptal.")
    if not duzeltebilir(kullanici, lot):
        raise ValidationError("Bu işi iptal etme yetkiniz yok (iş Lazer / Nakış / Kaplama'yı geçmiş).")
    veri = _lotu_iptal_et(lot, kullanici, neden)
    return DuzeltmeKaydi.objects.create(tur="is_iptal", lot=lot, siparis=lot.siparis, kullanici=kullanici, neden=neden,
                                        metin=f"{lot} iptal edildi", veri={"lotlar": [veri]})


def siparis_iptal_edilebilir(kullanici, siparis):
    if siparis is None or siparis.durum in ("iptal", "sevk"):
        return False
    return all(duzeltebilir(kullanici, l) for l in siparis.lotlar.all())


@transaction.atomic
def siparis_iptal(*, siparis, kullanici, neden):
    """Çift girilmiş siparişi bütün işleriyle iptal eder."""
    from .models import Siparis

    siparis = Siparis.objects.select_for_update().get(pk=siparis.pk)
    neden = _neden(neden)
    if not siparis_iptal_edilebilir(kullanici, siparis):
        raise ValidationError("Bu siparişi iptal etme yetkiniz yok (bir işi Lazer / Nakış / Kaplama'yı geçmiş).")
    lotlar = [_lotu_iptal_et(l, kullanici, neden) for l in siparis.lotlar.exclude(durum="iptal")]
    veri = {"siparis_durum": siparis.durum, "lotlar": lotlar}
    siparis.durum = "iptal"
    siparis.save(update_fields=["durum"])
    return DuzeltmeKaydi.objects.create(tur="siparis_iptal", siparis=siparis, kullanici=kullanici, neden=neden,
                                        metin=f"{siparis.siparis_no} iptal edildi ({len(lotlar)} iş)", veri=veri)


@transaction.atomic
def iptali_geri_ac(*, kayit, kullanici):
    """Yönetici: iptal edilen işi / siparişi eski hâline döndürür (alınan malzeme yeniden stoktan düşer)."""
    kayit = DuzeltmeKaydi.objects.select_for_update().get(pk=kayit.pk)
    if not getattr(kullanici, "is_superuser", False):
        raise ValidationError("İptali yalnız yönetici geri açabilir.")
    if kayit.tur not in ("is_iptal", "siparis_iptal") or kayit.geri_acildi:
        raise ValidationError("Bu kayıt geri açılamaz.")
    for v in kayit.veri.get("lotlar", []):
        lot = UretimLotu.objects.select_for_update().filter(pk=v["lot"]).first()
        if lot is None or lot.durum != "iptal":
            continue
        for ham, kg, m2 in v["kaynaklar"]:
            LotKaynagi.objects.create(uretim_lotu=lot, ham_deri_id=ham, kg=Decimal(kg), m2=Decimal(m2))
        durum = v["durum"]
        if v.get("acik_islem") and not lot.islemler.filter(bitis__isnull=True).exists():
            IslemKaydi.objects.filter(pk=v["acik_islem"]).update(bitis=None, cikis_kg=None, cikis_m2=None)
        elif durum == "islemde":
            durum = "bekliyor"
        lot.durum = durum
        lot.son_asama_id = v["son_asama"]
        lot.save(update_fields=["durum", "son_asama"])
        IsNotu.objects.create(lot=lot, metin=f"↩ Yönetici iptali geri açtı ({_kim(kullanici)}).", kullanici=kullanici)
    if kayit.tur == "siparis_iptal" and kayit.siparis_id:
        kayit.siparis.durum = kayit.veri.get("siparis_durum") or "acik"
        kayit.siparis.save(update_fields=["durum"])
    kayit.geri_acildi = True
    kayit.save(update_fields=["geri_acildi"])
    DuzeltmeKaydi.objects.create(tur="geri_ac", lot=kayit.lot, siparis=kayit.siparis, kullanici=kullanici,
                                 metin=f"Geri açıldı: {kayit.metin}"[:300])


def kendi_istasyonu(kullanici):
    """İstasyon hesabının (tablet / kişisel telefon) bağlı istasyonu; ofis ve yönetici için None (her şeyi görür)."""
    from .models import hesap_istasyonu

    if getattr(kullanici, "is_staff", False):
        return None
    return hesap_istasyonu(kullanici)


# --- Stok hareketleri ---------------------------------------------------------


def malzeme_giris(*, malzeme, miktar, kullanici=None, tedarikci=None, aciklama=""):
    if miktar is None or miktar <= 0:
        raise ValidationError("Giriş miktarı sıfırdan büyük olmalı.")
    return MalzemeHareketi.objects.create(malzeme=malzeme, tur="giris", miktar=miktar, kullanici=kullanici,
                                          tedarikci=tedarikci, aciklama=aciklama)


@transaction.atomic
def malzeme_duzelt(*, malzeme, neden, miktar, kullanici=None, aciklama=""):
    """Sayımda miktar = sayılan gerçek stok (fark kaydedilir); diğer nedenlerde miktar = stoktan düşülecek."""
    if miktar is None or miktar < 0:
        raise ValidationError("Miktar negatif olamaz.")
    if neden == "sayim":
        fark = miktar - malzeme.stok
        if fark == 0:
            raise ValidationError("Sayılan miktar sistemdekiyle aynı, düzeltme gerekmiyor.")
    else:
        if miktar == 0:
            raise ValidationError("Düşülecek miktarı girin.")
        fark = -miktar
    return MalzemeHareketi.objects.create(malzeme=malzeme, tur=neden, miktar=fark, kullanici=kullanici,
                                          aciklama=aciklama)


@transaction.atomic
def deri_duzelt(*, ham_deri, neden, kg, m2, kullanici=None, aciklama=""):
    """Sayımda kg/m² = sayılan gerçek kalan; diğer nedenlerde kg/m² = stoktan düşülecek miktar."""
    ham_deri = HamDeriGirisi.objects.select_for_update().get(pk=ham_deri.pk)
    kg, m2 = kg or Decimal(0), m2 or Decimal(0)
    if kg < 0 or m2 < 0:
        raise ValidationError("Miktar negatif olamaz.")
    if neden == "sayim":
        fark_kg, fark_m2 = kg - ham_deri.kalan_kg, m2 - ham_deri.kalan_m2
        if not fark_kg and not fark_m2:
            raise ValidationError("Sayılan miktar sistemdekiyle aynı, düzeltme gerekmiyor.")
    else:
        if not kg and not m2:
            raise ValidationError("Düşülecek kg veya m² girin.")
        if kg > ham_deri.kalan_kg or m2 > ham_deri.kalan_m2:
            raise ValidationError(f"Stokta {ham_deri.kalan_kg} kg / {ham_deri.kalan_m2} m² var, daha fazlası düşülemez.")
        fark_kg, fark_m2 = -kg, -m2
    return DeriDuzeltme.objects.create(ham_deri=ham_deri, neden=neden, kg=fark_kg, m2=fark_m2,
                                       kullanici=kullanici, aciklama=aciklama)


# --- Fason (pres / lamine) ----------------------------------------------------

UST_KATMANLAR = ("rono", "rona", "suni deri")  # Birleşik malzemenin rengi ve modeli bu katmandan gelir.


def _toplam_kaynak(kaynaklar):
    toplam = {}
    for stok, kg, m2 in kaynaklar:
        onceki = toplam.get(stok.pk, (stok, Decimal(0), Decimal(0)))
        toplam[stok.pk] = (stok, onceki[1] + (kg or 0), onceki[2] + (m2 or 0))
    return toplam


@transaction.atomic
def fasona_gonder(*, fasoncu, hedef_tur, kaynaklar, kullanici=None, notlar=""):
    """Stok lotlarından fasoncuya malzeme gönderir; gönderilen miktarlar stoktan düşer.

    kaynaklar: [(stok_lotu, kg, m2), ...]
    """
    toplam = _toplam_kaynak(kaynaklar)
    if not toplam:
        raise ValidationError("Gönderilen en az bir stok lotu girin.")
    if not hedef_tur.bilesik:
        raise ValidationError(f"“{hedef_tur}” birleşik bir malzeme değil.")
    kilitli = {h.pk: h for h in HamDeriGirisi.objects.select_for_update().filter(pk__in=toplam)}
    hatalar = []
    for pk, (_, kg, m2) in toplam.items():
        stok = kilitli[pk]
        if kg <= 0 and m2 <= 0:
            hatalar.append(f"{stok.lot_no}: gönderilen m² (ya da kg) girin.")
        if kg > stok.kalan_kg or m2 > stok.kalan_m2:
            hatalar.append(f"{stok.lot_no}: stokta {stok.kalan_kg} kg / {stok.kalan_m2} m² kaldı.")
    if hatalar:
        raise ValidationError(hatalar)

    fason = FasonIsi.objects.create(fasoncu=fasoncu, hedef_tur=hedef_tur, kullanici=kullanici, notlar=notlar)
    DeriDuzeltme.objects.bulk_create(
        DeriDuzeltme(ham_deri=kilitli[pk], neden="fason", fason=fason, kg=-kg, m2=-m2, kullanici=kullanici,
                     aciklama=f"{fason.no} – {fasoncu}")
        for pk, (_, kg, m2) in toplam.items()
    )
    return fason


def ust_katman(fason):
    """Gönderilenler arasında rengi/modeli belirleyen üst katman lotu (rono ya da suni deri); yoksa renkli ilk lot."""
    lotlar = [lot for lot, _, _ in fason.gidenler()]
    for lot in lotlar:
        if lot.deri_turu.ad.lower() in UST_KATMANLAR:
            return lot
    return next((lot for lot in lotlar if lot.renk or lot.model), None)


@transaction.atomic
def fason_teslim_al(*, fason, m2, kg=None, adet=None, renk=None, model=None, kullanici=None, notlar=""):
    """Fasondan gelen malzemeyi yeni bir stok lotu olarak açar. Renk/model verilmezse üst katmandan gelir."""
    fason = FasonIsi.objects.select_for_update().get(pk=fason.pk)
    if fason.durum != "fasonda":
        raise ValidationError(f"{fason.no} {fason.get_durum_display().lower()}, yeniden teslim alınamaz.")
    if m2 is None or m2 <= 0:
        raise ValidationError("Gelen m² miktarını girin.")
    ust = ust_katman(fason)
    lot = HamDeriGirisi.objects.create(
        tedarikci=fason.fasoncu, deri_turu=fason.hedef_tur, m2=m2, kg=kg or 0, adet=adet,
        giris_birimi="m2", giris_miktari=m2,
        renk=renk if renk is not None else (ust.renk if ust else ""),
        model=model if model is not None else (ust.model if ust else ""),
        notlar=(f"{fason.no} fasondan geldi. {notlar}").strip(),
    )
    fason.durum = "teslim"
    fason.teslim = timezone.now()
    fason.gelen_lot = lot
    fason.save(update_fields=["durum", "teslim", "gelen_lot"])
    return lot


@transaction.atomic
def fason_iptal(*, fason):
    """Fasona hiç gitmediyse: gönderim düzeltmeleri silinir, miktarlar stoğa geri döner."""
    fason = FasonIsi.objects.select_for_update().get(pk=fason.pk)
    if fason.durum != "fasonda":
        raise ValidationError(f"{fason.no} {fason.get_durum_display().lower()}, iptal edilemez.")
    fason.gonderimler.all().delete()
    fason.durum = "iptal"
    fason.save(update_fields=["durum"])
    return fason
