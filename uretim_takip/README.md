# Üretim Takip – Deri / Kürk Halı Fabrikası

Sensörsüz, lot bazlı (kg + m²) üretim takip sistemi. Amaç: **hangi lot hangi aşamada, kim ne yaptı, ne kadar fire verdi** sorularına anında cevap vermek ve Excel'deki elle takibi bitirmek.

## Akış

```
Ofis:     Stok girişi (HD-2026-0001) ──► QR etiketi malın üzerine     Sipariş girişi (SP-2026-0001)
                                              │                                │
Üretim:   İşlem Başlat → Yeni iş: siparişi seç + stok etiket(ler)ini okut + alınan kg/m²
                                              │
                         Sistem işi açar (IS-2026-0001) ve ilk aşamayı başlatır
                                              │
          Sonraki aşamalar: malın üzerindeki aynı stok etiketi okutulur → işe devam / bitir
```

## Neler yapar?

- **Stok lotları:** Gelen ham deri partisi tedarikçi, deri türü, kalite, adet, kg ve m² ile girilir. Lot numarası otomatik verilir (`HD-2026-0001`). QR etiketi basılıp malın üzerine yapıştırılır. Stokta ne kadar kaldığı her an görünür.
- **Siparişler:** Müşteri, ürün ve teslim tarihi girilir. İlerleme çubuğu ve geciken siparişler gösterilir.
- **Yeni iş (tablet):** Çalışan adını seçer, **PIN'ini girer**, **siparişi seçer** ve malzeme aldığı **stok lotlarının QR'ını okutur**. Bir iş birden fazla stok lotundan malzeme alabilir. Her lottan alınan kg ve m² girilir. Sistem stokta olandan fazlasının alınmasına izin vermez. İş açılır (`IS-2026-0001`) ve ilk aşama başlar.
- **Sonraki aşamalar:** Malın üzerindeki stok etiketi okutulunca o lottan malzeme alan devam eden işler listelenir. Çalışan, açık aşamayı **bitirir** ya da **sıradaki aşamayı başlatır**. Bitirirken çıkış kg ve m² girilir, fark fire olarak kaydedilir.
- **Pano:** Kim hangi işte çalışıyor, aşamalarda kaç iş var, bugün kim ne yaptı. Ofis hesabında siparişler de görünür.
- **İzlenebilirlik:** Bir işin hangi stok lotlarından, hangi tedarikçinin malından yapıldığı, kimin hangi aşamayı ne zaman yaptığı ve ne kadar fire verdiği görünür. Stok lotu sayfasında da o lottan hangi işlere ne kadar malzeme alındığı listelenir.
- **Raporlar (ofis):** Tarih aralığına göre personel performansı ve aşama bazında fire. Excel'e aktarılabilir.
- **Yönetim paneli (`/yonetim/`):** Personel ve PIN'ler, aşamalar, tanımlar, düzeltmeler.

### Kim ne görür?

| Hesap | Menü |
|---|---|
| **Tablet** (üretim; personel durumu yok) | Pano, İstasyon, QR Okut, İşlem Başlat, Stok, İşler |
| **Ofis** (personel durumu + izinler) | Pano, Siparişler, Stok (+ Stok girişi), İşler, Raporlar, Yönetim |
| **Yönetici** (süper kullanıcı) | Hepsi + Excel'den aktar + Yedek |

### İstasyonlar, makineler ve halı türleri

| İstasyon | Makineler |
|---|---|
| Nakış | Nakış makinesi |
| Kaplama | Pres |
| Lazer kesim 1 | Lazer 1 |
| Lazer kesim 2 | Lazer 2 |
| Zig-zag | Zig-zag 1, Zig-zag 2 |
| Biye | Biye makinesi |
| Lanfel | Lanfel makinesi |
| Kenar dikişi | (yönetim panelinden eklenebilir) |

Sipariş girilirken **halı türü** seçilir; iş o türün istasyonlarından sırayla geçer:

| Halı türü | İstasyon sırası |
|---|---|
| Lazerli halı | Lazer kesim 1 / 2 → Zig-zag → Biye / Lanfel |
| Nakışlı halı | Nakış → Lazer kesim 1 / 2 → Zig-zag → Biye / Lanfel |
| Peluş halı | Kaplama → Lazer kesim 1 / 2 → Zig-zag → Biye / Kenar dikişi |

"Biye / Lanfel" ya biri ya diğeri demektir: iş iki istasyonun ekranına da düşer, hangisi başlarsa o yapar.
Çalışan işe başlarken **hangi makinede** çalıştığını seçer; raporlarda makine bazında iş sayısı ve çalışma süresi görünür.

Yönetim panelinden: **Aşamalar** (istasyonlar ve içindeki makineler), **Halı türleri** (istasyon sırası; aynı sıra numarası = alternatif).
Yeni bir istasyon eklemek için: Aşamalar → ekle, sonra ilgili halı türünün sırasına ekleyin.

## Kurulum

Python 3.10 veya üstü gerekir.

```bash
cd uretim_takip
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # yönetici hesabı
python manage.py runserver 0.0.0.0:8000
```

Tarayıcıda `http://<bilgisayarın-ip-adresi>:8000` adresini açın. Fabrikadaki tabletler aynı Wi-Fi ağında olmalıdır.
Ağdan erişim için ortam değişkenine IP'yi ekleyin: `DJANGO_ALLOWED_HOSTS=192.168.1.50,localhost`.

### Denemek için örnek veri

```bash
python manage.py ornek_veri
```

Giriş bilgileri: `yonetici / yonetici123` (yönetim) ve `tablet / tablet123` (üretim tableti). Bütün örnek personelin PIN'i `1234`.
**Bu komutu gerçek verinin olduğu veritabanında çalıştırmayın.**

## İstasyon ekranları ve süre uyarıları

Her istasyondaki tablette **🏭 İstasyon** menüsünden o istasyon seçilir. Tablet seçimi hatırlar ve ekran açık bırakılır:
- **Gelen işler:** Sipariş girilince ilk istasyonda **"Yeni sipariş"**, bir aşama bitince sıradaki istasyonda o iş belirir. Yeni iş gelince ekran **kırmızı "Yeni iş geldi" bandı** gösterir ve ses çıkarır. Ses için ekran açıldıktan sonra bir kez **"🔔 Sesli uyarıyı aç"** düğmesine basılmalıdır (tarayıcı kuralı).
- **Bu istasyonda çalışılanlar:** Kim, ne zamandan beri çalışıyor. **Bitir** düğmesi buradadır.
- Ekran her 20 saniyede bir kendini yeniler.

**Süre sınırları:** **Yönetim → Aşamalar** listesinde her istasyon için iki süre girilir (saat cinsinden, boş bırakılırsa sınır yok):
- **En fazla bekleme süresi:** İş istasyona geldikten sonra bu süre içinde başlanmazsa uyarı verilir.
- **En fazla çalışma süresi:** İş istasyonda bu süreden uzun kalırsa uyarı verilir.

Süresi aşan işler istasyon ekranında kırmızı görünür. Ofis panosunda da **"⏰ Süre sınırını aşan işler"** kartında listelenir.

## Stok: deri ve malzemeler

- **Deri stoğu (Stok sayfası):** Her deri türünün toplam kalan kg ve m² miktarı üstte görünür. **Yönetim → Deri türleri**'nde **en az stok (kg)** girilirse, toplam stok bunun altına düşünce uyarı verilir.
- **Malzemeler (Stok → Malzemeler):** Kimyasal, iplik, astar, yapıştırıcı, ambalaj gibi malzemeler kendi birimiyle (kg, litre, metre, m², adet, makara) tanımlanır. **"+ Malzeme girişi"** ile gelen mal eklenir.
- **Malzeme etiketleri:** Her malzemeye otomatik bir kod verilir (`MZ-0001`). Malzeme sayfasındaki **🏷 Etiket bas** düğmesiyle QR etiket yazdırılır. "Her etiketten N adet" seçeneğiyle örneğin 10 bidonun her birine etiket basılabilir.
- **Üretimde kullanım:** Çalışan bir aşamayı **bitirirken** kullandığı malzemeyi seçip miktarını girer. Malzemeyi listeden seçmek yerine **📷** ile bidonun etiketini okutabilir. Malzeme stoktan düşer, hangi işte ve kim tarafından kullanıldığı kaydedilir.
- **Düzeltme:** Hem deri lotunda hem malzemede **"Düzeltme (sayım / fire)"** düğmesi bulunur. *Sayım farkı* seçilirse sayılan gerçek miktar yazılır, sistem farkı kaydeder. *Fire*, *iade* ya da *diğer* seçilirse stoktan düşülecek miktar yazılır.
- **Azalan stok:** En az stok sınırının altına düşen deri türleri ve malzemeler ofis panosundaki **"📉 Azalan stok"** kartında görünür.

## Günlük kullanım

1. **Ofis, mal gelince:** **Stok → + Stok girişi**'ne girer, kaydeder, sonra **🏷 Etiket bas** ile etiketi yazdırıp malın üzerine yapıştırır.
2. **Ofis, sipariş gelince:** **Siparişler → + Yeni sipariş**.
3. **Çalışan, işe başlarken:** **İşlem Başlat → Yeni iş**'e girer, siparişi seçer, malın etiketini 📷 ile okutur, aldığı miktarı girip **İşi başlat**'a basar.
4. **Çalışan, sonraki aşamada:** **QR Okut** ile malın etiketini okutur, listeden işini seçip **Bitir** ya da **▶ sıradaki aşama**'ya basar.
5. **Ofis veya yönetici:** **Siparişler** ve **Raporlar** sayfalarından ilerlemeyi, kimin ne yaptığını ve fireyi takip eder.

## Siparişler

Üst menüdeki **Siparişler** sayfası her siparişi bir kartta gösterir:
- **İlerleme çubuğu:** Toplam m² girildiyse biten işlerin m²'sine göre, girilmediyse biten iş sayısına göre hesaplanır.
- **İşlerin dağılımı:** Siparişin işleri aşamalara göre gruplanır, örneğin "2 × Kesim · 1 × Bitti".
- **Teslime kalan gün:** Gecikenler kırmızı kenarlıkla en üstte görünür.
- **Sekmeler:** Devam eden, tamamlanan, sevk edilen, iptal edilen. Sipariş no, müşteri veya ürüne göre arama yapılabilir.

Sipariş detayında siparişin işleri ve hangi stok lotlarından malzeme alındığı listelenir. Buradan **"Sevk edildi"** işaretlenir.
Sipariş durumu kendiliğinden ilerler:
- ilk işlem başlayınca **Üretimde**,
- bütün lotlar bitince **Tamamlandı**,
- tamamlanmış bir sipariş için yeni iş açılınca yeniden **Üretimde**.

**"+ Yeni sipariş"** formu yönetim paneline girmeden kullanılır. Müşteri listede yoksa adı yazılır, sistem otomatik ekler.

### Ofis çalışanı için hesap
Siparişleri girecek kişiye yönetici şifresini vermek yerine ayrı bir hesap açın:
1. **Yönetim → Kullanıcılar → Ekle** ile kullanıcı adı (ör. `ofis`) ve şifre belirleyip kaydedin.
2. Açılan sayfada **Personel durumu** (staff) kutusunu işaretleyin. Bu, yönetim paneline girebilmesi için gerekir. **Süper kullanıcı durumu**nu işaretlemeyin.
3. **Kullanıcı izinleri** listesinden şunları seçip sağa aktarın: *sipariş* (ekle, değiştir, görüntüle), *müşteri* (ekle, değiştir, görüntüle), *stok lotu (ham deri)* (ekle, değiştir, görüntüle), *tedarikçi* (ekle, görüntüle), *iş* (görüntüle), *malzeme* (ekle, görüntüle), *malzeme hareketi* (ekle, görüntüle), *deri stok düzeltmesi* (ekle, görüntüle).
4. Kaydedin. Bu hesap sipariş, müşteri ve stok girebilir. Personel PIN'lerine, yedeğe ve Excel aktarmaya erişemez.

## Mevcut Excel verilerini aktarma

Yönetici hesabıyla üst menüden **📥 Excel'den aktar** sayfasına girin:

1. **Şablonu indirin.** Şablonda *Personel, Tedarikçiler, Müşteriler, Stok Lotları, Siparişler* ve *Devam Eden İşler* sayfaları ve her sütunun açıklaması bulunur.
2. Mevcut Excel'inizdeki verileri ilgili sütunlara **kopyalayıp yapıştırın**. Kullanmadığınız sayfaları boş bırakın.
3. Dosyayı yükleyin. Sistem önce bir **önizleme** gösterir: kaç kayıt eklenecek ya da güncellenecek, hangi tedarikçi, müşteri veya deri türü yeni tanımlanacak, hangi satırda ne hata var.
4. Hata yoksa **Kaydet**'e basın. Tek bir hatalı satır bile varsa **hiçbir şey kaydedilmez**. Excel'de düzeltip tekrar yükleyin.

İpuçları:
- Eski lot ve sipariş numaralarınızı yazarsanız aynen korunur. Boş bırakırsanız sistem numara verir.
- Aynı dosya tekrar yüklenirse kayıtlar çoğalmaz. Lot No, Sipariş No veya ad eşleşen kayıtlar güncellenir.
- Sayılar `12,5`, `12.5` ya da `1.250,75` biçiminde, tarihler `25.10.2026` biçiminde yazılabilir.
- Excel `0123` gibi PIN'lerin baştaki sıfırını silebilir. PIN sütununu **Metin** biçimine çevirin.
- Eski `.xls` dosyalarını önce **Farklı Kaydet → .xlsx** ile kaydedin.

## Telefon uygulaması ve QR etiketler

**Telefona kurma:** Android'de Chrome ile sistemi açın. Üstte çıkan **"Uygulamayı yükle"** butonuna ya da menüdeki **"Ana ekrana ekle"**ye dokunun.
iPhone'da Safari'de **Paylaş → Ana Ekrana Ekle** yolunu izleyin. Uygulama kendi simgesiyle tam ekran açılır.

**QR etiket:** Etiketler **stok lotlarına** basılır. *Stok* sayfasında **"Listedekilerin etiketleri"**, stok lotu sayfasında **"🏷 Etiket bas"** butonuyla A4'e yazdırılır.
Etiket mal üretim boyunca üzerinde kalır. Okutulunca stok lotunun sayfası açılır:
- o lottan malzeme alan **devam eden işler** listelenir. Her işin yanında **Bitir** ya da **▶ sıradaki aşama** düğmesi bulunur.
- **"Bu lottan yeni iş başlat"** düğmesiyle Yeni iş ekranı açılır, stok lotu hazır yazılı gelir.
- Yeni iş ekranında her satırın yanındaki 📷 düğmesiyle stok etiketi okutularak satır doldurulur.

Eski sürümde işlere basılmış etiketler (UL-…) de çalışmaya devam eder.

Okutmanın iki yolu var:
1. **Telefonun kendi kamera uygulaması:** Her zaman çalışır, HTTPS gerekmez.
2. **Uygulamadaki "📷 QR Okut" ekranı:** Kamera tarayıcının içinde açılır.

> ⚠️ **HTTPS gereklidir:** Tarayıcılar *uygulama olarak kurmaya* ve *uygulama içinden kamera açmaya* yalnızca güvenli bağlantıda (`https://`) izin verir.
> `http://192.168.1.50:8000` gibi düz bir yerel adreste sistem tarayıcıda çalışır ve telefonun kendi kamerasıyla QR okutulur, ama bu iki özellik çalışmaz.
> HTTPS için en kolay yollar:
> - Sistemi alan adı olan bir bulut sunucusuna kurmak (Let's Encrypt ile ücretsiz sertifika), ya da
> - fabrikadaki bilgisayarı **Cloudflare Tunnel** veya **Tailscale** ile güvenli bir adrese açmak.
>
> Etiketlerdeki QR adresi, etiketin yazdırıldığı adresten alınır. Sabit bir adres istiyorsanız `SITE_ADRESI=https://uretim.firmaniz.com` ayarlayın ve etiketleri ondan sonra basın.

## Ücretsiz buluta kurulum

Adım adım anlatım için: **[KURULUM_PYTHONANYWHERE.md](KURULUM_PYTHONANYWHERE.md)**. Sunucuda tek komutla kurulum: `bash kurulum.sh`.

Yönetici hesabıyla üst menüdeki **💾 Yedek** butonu veritabanının tam yedeğini indirir. Sunucuda `python manage.py yedekle` komutu da yedekler klasörüne kopya alır.

## Canlıya alırken

- `DJANGO_SECRET_KEY` ortam değişkenine uzun ve rastgele bir değer verin, `DJANGO_DEBUG=0` yapın.
- `python manage.py collectstatic` komutunu çalıştırın (simgeler, QR okuyucu gibi dosyalar WhiteNoise ile sunulur).
- Veritabanı dosyasını (`db.sqlite3`) **her gün yedekleyin**.
- 15 kişilik kullanım için SQLite yeterlidir. Büyürseniz PostgreSQL'e geçilebilir.

## Testler

```bash
python manage.py test uretim
```

## Sonraki adımlar (Faz 2+)

- Kalite kontrol hata türleri, yeniden işleme

### Stok birimleri
Stok girişinde malın **geldiği birim** seçilir; stok her zaman **m²** tutulur ve işe malzeme alırken m² girilir:
- **m²:** olduğu gibi
- **metretül:** metre × rulo eni (cm) ÷ 100 (ör. 50 mt × 140 cm = 70 m²)
- **ayak (ft²):** ayak × 0,0929 (ör. 1000 ayak = 92,9 m²)

### Raporlar
Personel, istasyon (aşama) ve makine bazında iş/fire/süre; **istasyonlar arası bekleme** (bir istasyonda biten işin sıradakinde başlanmasına kadar geçen ortalama ve en uzun süre) ve **kim hangi istasyonda çalıştı**. İş detayında her adımın önceki istasyondan sonra ne kadar beklediği görünür.

### Tablet girişleri
Raporlar → **📱 Tablet girişleri**: hangi hesabın ne zaman giriş/çıkış yaptığı ve hangi istasyon ekranını açtığı (cihaz bilgisiyle). Her istasyon tabletine ayrı hesap açılırsa (ör. `lazer-tablet`) tabletler ayrı ayrı izlenir. Ekran yenilemeleri 30 dakikada bir kez kaydedilir.

### Hesaplar
Yönetici menüsünde **👥 Hesaplar**: yeni hesap açarken yalnızca **hesap türü** seçilir (İstasyon tableti / Ofis / Yönetici); yetkiler otomatik verilir. Ofis yetkileri "Ofis" grubunda tutulur.
