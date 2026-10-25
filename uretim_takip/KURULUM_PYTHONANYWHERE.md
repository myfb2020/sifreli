# Ücretsiz Buluta Kurulum – PythonAnywhere

Bu kılavuz Üretim Takip sistemini **PythonAnywhere ücretsiz planına** kurar. Sonunda sistem
`https://KULLANICIADI.pythonanywhere.com` adresinde, HTTPS ile, her yerden (fabrika, ofis, ev) açılır.
Telefona uygulama olarak kurma ve uygulama içinden QR okutma da çalışır.

Süre: yaklaşık 20-30 dakika. Kredi kartı gerekmez.

## Ücretsiz planı bilerek kullanın

| | |
|---|---|
| ✅ Ücretsiz, kalıcı disk (veriler silinmez), HTTPS dahil | ⚠️ **Her ay bir kez** "Run until 1 month from today" butonuna basmanız gerekir, yoksa site durur (veriler silinmez) |
| ✅ 15 kişilik kullanım için yeterli | ⚠️ Disk 512 MB (yıllarca yeter, raporlar az yer kaplar) |
| ✅ Sunucu bakımı yok | ⚠️ Ücretsiz hesaplara doğrudan destek verilmiyor, otomatik yedek yok. **Yedeği siz alırsınız** |

> Sistem işinizin merkezi haline gelirse aylık yaklaşık 5 dolarlık ücretli plana geçmeniz önerilir.
> Böylece aylık onay zorunluluğu kalkar, otomatik yedek kurulabilir. Kodda değişiklik gerekmez.

---

## 1. Hesap açın

1. **https://www.pythonanywhere.com** adresine girin. Avrupa sunucusu için **https://eu.pythonanywhere.com**'u tercih edebilirsiniz: Türkiye'ye daha yakındır, veriler AB'de tutulur.
2. **Pricing & signup → Create a Beginner account** yolunu izleyin.
3. Seçtiğiniz **kullanıcı adı** site adresiniz olur. Örneğin `deriatolye` → `https://deriatolye.pythonanywhere.com`.
4. E-postanızı onaylayın.

## 2. Dosyaları yükleyin

**A) Zip ile (önerilen):**
1. Size gönderilen `uretim_takip.zip` dosyasını bilgisayarınıza indirin.
2. PythonAnywhere'de üst menüden **Files**'a girin. Klasör `/home/KULLANICIADI/` olmalı.
3. **Upload a file** ile `uretim_takip.zip`'i yükleyin.

**B) GitHub'dan (kod GitHub'daysa):** 3. adımdaki konsolda `git clone https://github.com/myfb2020/sifreli.git` komutunu çalıştırın. Bu yolu seçerseniz sonraki komutlarda `uretim_takip` yerine `sifreli/uretim_takip` yazın.

## 3. Kurulum betiğini çalıştırın

1. Üst menüden **Consoles → Bash**'e tıklayın. Siyah bir komut ekranı açılır.
2. Aşağıdaki komutları sırayla yapıştırıp Enter'a basın:

```bash
unzip -o uretim_takip.zip
cd uretim_takip
bash kurulum.sh
```
> **Avrupa sunucusundaysanız** son komut `bash kurulum.sh eu` olmalı.

Betik birkaç dakika sürer. Şunları yapar: Python ortamını kurar, kütüphaneleri yükler, gizli anahtarlı `.env` dosyasını oluşturur, veritabanını hazırlar.

3. **Yönetici hesabınızı oluşturun.** Kullanıcı adı ve şifre sorar. Şifre yazılırken ekranda görünmez, bu normal.

```bash
~/.venv-uretim/bin/python manage.py createsuperuser
```

## 4. Web uygulamasını oluşturun

1. Üst menüden **Web → Add a new web app → Next** yolunu izleyin.
2. **Manual configuration**'ı seçin. **"Django" seçeneğini seçmeyin.**
3. Python sürümü olarak, kurulum betiğinin başta yazdığı sürümü seçin (ör. **Python 3.13**) → **Next**.
4. Açılan sayfada şu alanları doldurun (`KULLANICIADI` yerine kendi kullanıcı adınızı yazın):

| Bölüm | Alan | Değer |
|---|---|---|
| Code | Source code | `/home/KULLANICIADI/uretim_takip` |
| Code | Working directory | `/home/KULLANICIADI/uretim_takip` |
| Virtualenv | (yol) | `/home/KULLANICIADI/.venv-uretim` |
| Static files | URL → Directory | `/static/` → `/home/KULLANICIADI/uretim_takip/staticfiles` |
| Security | Force HTTPS | **Enabled** |

5. **Code** bölümündeki **WSGI configuration file** bağlantısına tıklayın. Dosyanın **tüm içeriğini silip** şunu yapıştırın, sonra **Save**'e basın:

```python
import os
import sys

path = "/home/KULLANICIADI/uretim_takip"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "fabrika.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

6. **Web** sekmesine dönüp yeşil **Reload** butonuna basın.
7. `https://KULLANICIADI.pythonanywhere.com` adresini açın. Giriş ekranı görünmeli. 🎉

## 5. İlk ayarlar (yönetim paneli)

`https://KULLANICIADI.pythonanywhere.com/yonetim/` adresinde yönetici hesabınızla giriş yapın:

1. **Kullanıcılar → Ekle:** Tabletler ve telefonlar için ortak bir hesap açın (ör. `tablet`). Bu hesaba "personel durumu" (staff) **vermeyin**.
2. **Personel:** 15 çalışanı ekleyin ve her birine 4-6 haneli bir **PIN** verin.
3. **Aşamalar:** Varsayılan aşamaları kendi akışınıza göre düzenleyin.
4. **Mevcut Excel verileriniz için:** üst menüden **📥 Excel'den aktar** → **Şablonu indir** → verileri yapıştırın → yükleyin → önizlemeyi kontrol edip **Kaydet**'e basın. Personeli PIN'leriyle birlikte buradan da toplu ekleyebilirsiniz. Ayrıntılar README'de.
5. **Lotlar** sayfasından **🏷 etiketleri** yazdırın.

Telefonlarda adresi açıp `tablet` hesabıyla girin, sonra **"Uygulamayı yükle"** ya da iPhone'da **Paylaş → Ana Ekrana Ekle** deyin.

## 6. Düzenli yapılacaklar ⚠️

### Her ay: siteyi uzatın
**Web** sekmesindeki **"Run until 1 month from today"** butonuna basın. PythonAnywhere süre dolmadan e-posta ile hatırlatır.
**Telefonunuza aylık bir hatırlatma kurun.** Unutursanız site durur ama veriler silinmez, butona basınca geri gelir.

### Her hafta: yedek alın
Yönetici hesabıyla girip üst menüdeki **💾 Yedek**'e tıklayın. İnen `uretim_yedek_….sqlite3` dosyasını bilgisayarınızda veya Google Drive'da saklayın.
Ayrıca **Raporlar → Excel'e aktar** ile okunabilir bir kopya da alabilirsiniz.

### Yedekten geri dönme (gerekirse)
**Files**'tan yedek dosyasını `uretim_takip/` klasörüne yükleyin. Sonra Bash konsolunda şunu çalıştırın:
```bash
cd ~/uretim_takip && cp db.sqlite3 db.sqlite3.eski && cp uretim_yedek_TARIH.sqlite3 db.sqlite3
```
Ardından **Web → Reload**.

## 7. Güncelleme (yeni sürüm geldiğinde)

Yeni `uretim_takip.zip`'i **Files**'tan yükleyin. Sonra Bash konsolunda:
```bash
unzip -o uretim_takip.zip && cd uretim_takip && bash kurulum.sh
```
Ardından **Web → Reload**. Veritabanınız (`db.sqlite3`) ve `.env` dosyanız korunur.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| "Something went wrong" sayfası | **Web** sekmesinde **Error log**'a bakın. En alttaki satırları bana iletin. |
| `DisallowedHost` / 400 hatası | `.env` dosyasındaki `DJANGO_ALLOWED_HOSTS` adresinizle aynı olmalı (eu sunucusunda `KULLANICIADI.eu.pythonanywhere.com`). Değiştirince **Reload**. |
| Giriş yaparken "CSRF" hatası | Adresi `https://` ile açtığınızdan ve **Force HTTPS**'in açık olduğundan emin olun. |
| Sayfa renksiz, tasarım bozuk | **Static files** satırını kontrol edin. Konsolda `bash kurulum.sh` komutunu tekrar çalıştırıp **Reload** deyin. |
| "This site has been disabled" | Aylık uzatma unutulmuş. **Web → Run until 1 month from today**. |
