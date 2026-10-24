# Üretim Takip – Deri / Kürk Halı Fabrikası

Sensörsüz, lot bazlı (kg + m²) üretim takip sistemi. Amaç: **hangi lot hangi aşamada, kim ne yaptı, ne kadar fire verdi** sorularına anında cevap vermek ve Excel'deki elle takibi bitirmek.

## Neler yapar? (Faz 1)

- **Ham deri girişi:** tedarikçi, deri türü, kalite, adet, kg, m². Otomatik lot no (`HD-2026-0001`). Kalan miktar takip edilir.
- **Sipariş:** müşteri, ürün, teslim tarihi. Geciken siparişler kırmızı görünür.
- **Üretim lotu:** ham deri lotundan pay ayrılır (`UL-2026-0001`), isteğe bağlı bir siparişe bağlanır.
- **İşlem başlat / bitir (tablet ekranı):** çalışan adını seçer, **PIN'ini girer**, lotu ve aşamayı seçer. Bitirirken çıkış kg ve m² girer, fark fire olarak kaydedilir.
  Bir lotta aynı anda tek açık işlem olabilir. Sıradaki işlem, bir önceki aşamanın çıkış miktarıyla başlar.
- **Pano:** şu an kim hangi lotta çalışıyor, aşamalarda kaç lot var, bugün kim ne yaptı, geciken ve yaklaşan siparişler.
- **Lot geçmişi (izlenebilirlik):** bir lotun tedarikçiden pakete kadar her adımı: kim, ne zaman, ne kadar süre, ne kadar fire.
- **Raporlar:** tarih aralığına göre personel performansı ve aşama bazında fire. **Excel'e aktarma** desteklenir.
- **Yönetim paneli (`/yonetim/`):** personel, aşamalar, tedarikçi, müşteri, deri türü, ham deri, sipariş ve lot tanımları.

Varsayılan aşamalar: Tasnif → Islatma → Tabaklama → Kurutma → Tıraş/germe → Kesim → Dikim → Astar/taban → Son işlem → Kalite kontrol → Paketleme.
Aşamalar yönetim panelinden eklenip çıkarılabilir. Sıra numaraları 10'ar arayla verildiği için araya yeni aşama eklenebilir (ör. 25).

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

## Günlük kullanım

1. **Yönetici** (`/yonetim/`): personeli PIN'leriyle ekler, ham deri girişini ve siparişi kaydeder, üretim lotunu oluşturur.
2. **Tablet** (ortak hesapla açık kalır): çalışan işe başlarken **İşlem Başlat**'a basar, iş bitince panodan **Bitir**'e basar.
3. **Yönetici:** **Raporlar** sayfasından kimin ne yaptığını ve fireyi görür, gerekirse Excel'e aktarır.

## Canlıya alırken

- `DJANGO_SECRET_KEY` ortam değişkenine uzun ve rastgele bir değer verin, `DJANGO_DEBUG=0` yapın.
- Veritabanı dosyasını (`db.sqlite3`) **her gün yedekleyin**.
- 15 kişilik kullanım için SQLite yeterlidir. Büyürseniz PostgreSQL'e geçilebilir.

## Testler

```bash
python manage.py test uretim
```

## Sonraki adımlar (Faz 2+)

- Lot etiketleri için QR kod basma ve okutma
- Bir üretim lotunun birden fazla ham deri lotundan oluşabilmesi
- Kimyasal ve malzeme stoğu
- Kalite kontrol hata türleri, yeniden işleme
- Mevcut Excel verilerinin içe aktarılması
