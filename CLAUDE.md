# Proje haritası – Bienna Fur Üretim Takip

Bu dosya Claude'un hafızasıdır. Her oturumda önce bunu oku; her şeyi baştan okuma.
Yalnızca işin ilgili olduğu **dala** in ve orada adı geçen dosyaları aç. İş bitince bu haritayı güncelle (dal + günlük).

## Kök
- **Kullanıcı:** Bienna Fur sahibi (deri/kürk halı atölyesi, ~15 çalışan). Yazılımcı değil, **Türkçe**, sade anlatım ister; önce fikir/plan isteyebilir.
- **Ürün:** `uretim_takip/` – Django 5.2 + SQLite, Türkçe arayüz, telefona yüklenen PWA. Canlı: https://uretim.pythonanywhere.com (ücretsiz PythonAnywhere).
- **Depo:** `myfb2020/sifreli`, dal `claude/ben-code-capabilities-te6dv6`. Normal push (force push yok).
- **Kullanıcının hedefi:** programı kendi atölyesinde oturtup başka atölyelere satılabilir hâle getirmek (yeni iş kolu).

## Çalışma kuralları
- **Kullanıcının kuralı (2026-10-29):** Her isteğinden önce önce düşün ve planı yaz; kullanıcı onaylamadan program yazmaya başlama.
- Test: `cd uretim_takip && ../.venv/bin/python manage.py test uretim` (140 test; `--parallel` bu ortamda çalışmaz) + `manage.py makemigrations --check --dry-run`.
- Teslim: zip → `SendUserFile`. Komut (`/home/user/sifreli`'de):
  `rm -f uretim_takip.zip && zip -qr uretim_takip.zip uretim_takip -x 'uretim_takip/db.sqlite3' 'uretim_takip/.env' 'uretim_takip/staticfiles/*' 'uretim_takip/yedekler/*' 'uretim_takip/medya/*' '*/__pycache__/*' '*.pyc'`
- Kullanıcının yükleme adımı: Yedek indir → Files'a zip → Bash: `cd ~ && unzip -o uretim_takip.zip && cd uretim_takip && bash kurulum.sh` → Web → Reload.
- Commit sonu: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` + `Claude-Session:` satırı. Commit/PR'da model adı geçmez.
- Kod Türkçe adlandırılır (`siparis`, `lot`, `asama`…). Ekran kontrolü: Playwright node betiği, giriş için `form.dikey button[type=submit]`.
- **Dikkat:** `kurulum.sh` / `geri_al.sh` denemelerini yalnızca geçici kopyada ve `( set -e; … )` içinde yap. Gerçek klasörde bir kez yanlışlıkla çalıştı.
- Ağ: biennafur.com bu ortamdan kapalı (proxy 403).

## Dallar
```
Üretim Takip
├─ 1 Üretim akışı
│   ├─ Sipariş SP-…  (durum: onay → acik → uretimde → tamamlandi → sevk / iptal); **müşteri fotoğrafı** (`SiparisFotografi`, ≤3, 1600 px JPEG, `fotograf.py`; liste/detay/istasyon/iş; tam ekran `a.buyut` base.html; ⭐ Modellere ekle → seri "Müşteri modelleri" MM-001…, bayi Suni deri sayfasında olduğu gibi sipariş; bayi /medya/siparis/ göremez)
│   ├─ Halı türü + rota: Lazerli, Nakışlı, Peluş, Suni deri  (aynı sira = alternatif istasyon)
│   ├─ İstasyonlar: Lazer kesim 1/2, Nakış, Kaplama, Zig-zag, Biye, Lanfel, Kenar dikişi (+ makineler)
│   ├─ İş IS-…: yeni iş (stok QR isteğe bağlı; Pano'da "Stok okutma zorunlu" `SistemAyari.stok_zorunlu`) → başlat/bitir → sıradaki istasyon; ilk istasyonda (lazer) bitirirken malzeme + en×boy → stoktan FIFO düşer (`servisler.malzeme_dus`), fire = kullanılan − sipariş net m²; diğerleri yalnız Başlat/Bitir
│   ├─ Sipariş **ölçü satırları** `SiparisKalemi` (en×boy×adet; her satıra iş otomatik `servisler.siparis_islerini_ac`, `kalemleri_kaydet`; `UretimLotu.kalem`, `lot.olcu_metni`; yeni_is bekleyen işi kullanır); ofis **✏️ Düzenle** `siparis_duzenle` (ölçü + foto ekle/sil, `siparis_yeni.html` ortak); **istasyon notu** `IsNotu` (`/isler/<pk>/not/`, bitirme açıklaması da not); pano `raporlar.bugun_kim_ne_yapti` (bitiren, biten halı son istasyonda, fire yalnız ilk istasyon); `sevk_tarihi`, sevkten 6 ay sonra foto 600 px `fotograf.arsiv_kucult` (pano açılınca günde bir); Sipariş en_cm×boy_cm×adet → toplam_m2; ⚡ acil; istasyon sırası acil → teslim (`uyarilar.oncelik`), satırda ölçü/teslim/not (`_is_bilgisi.html`); iş yeri yazıyla `UretimLotu.konum_metni`
│   └─ İstasyon ekranı (20 sn yenilenir), bekleme/süre uyarıları, pano
├─ 2 Stok
│   ├─ Ana malzeme lotu HD-… (QR etiket; rulo en cm × boy m / plaka en×boy cm × adet / m² / ayak)
│   ├─ Malzeme türleri: deri, Keçe, Süet, Rona, Suni deri + bileşikler (3'lü lamine, Halı tabanı); renk/model
│   ├─ Yardımcı malzeme MZ-… ; düzeltme (sayım/fire)
│   ├─ Fason FS-…: gönder (stoktan düşer) → teslim al (yeni lot, renk/model üst katmandan) → fason firesi
│   └─ Geçiş dönemi düğmesi (etiketsiz eski stoktan iş)
├─ 3 Katalog + Tasarım stüdyosu
│   ├─ Katalog: 13 seri, 192 model (TOS, HMK, IPS, LTS…), 14 lazer deseni DB001–DB014
│   ├─ Stüdyo (bayi): Kürk (Toskana: dış bant → halka → iç bant → zemin → madalyon) / Suni deri (varak, peluş, kadife, sim/rugan alt, biye)
│   ├─ Hazırlar: TOS-034…LTS-006 (menü "Kürk / deri modelleri"); SD-1…SD-4 yalnız eski suni kayıtlar açılınca görünür
│   ├─ **Suni deri** (menü adı; eski "Parçalı") /tasarim/parcali/: hazır modeller = katalog lazer serileri IPS/BNA/PCH/RNO (99 foto, seri sekmeleri; 76'sı `KATALOG_DEGER` ile düzenlenebilir), "olduğu gibi sipariş" (`aynen`+`katalog`, sipariş katalog modeline bağlı, resim = katalog fotoğrafı) ya da "bu modelden başla"; orta **madalyon** (düz/nakışlı, çerçeve); malzemeler peluş 8 renk/Bienca/Rona (numune fotoğrafından); DB015 Grek bant (çizildi); gizli desenler DB002/007/010/011; nakış 14 motif (`NAKIS_MOTIFLERI`, gerçek ölçü, maske `tasarim_varlik/nakis/`, marka logoları yok) + iplik rengi; hazırlar P-1…P-12 (P-1…9 gerçek ürün fotoğraflı `tasarim_varlik/hazir_foto/`); **halkalı** (dikdörtgen/oval, ≤4 halka düz/desenli/nakışlı + orta düz/nakış paneli/enine-boyuna şerit), 5 adımlı ekran + ✕'li büyük görünüm; eski düzenler (çerçeve, oval şerit, yuvarlak, ızgara…) yalnız eski kayıtlar için, `eskiden_cevir`; 💡 fikir ver; P-1…P-8; gerçek malzeme fotoğraf dokuları; parça bölme, rulo, nakış 7 kafa, kesim listesi + malzeme bazlı DXF
│   ├─ **Fotoğraflı modeller** RNO-006…012 (`foto_model.py`, `tasarim_varlik/foto_model/KOD.jpg` + `KOD.png` bölge haritası, üretici `is_belgeleri/foto_model_maske.py` OpenCV yalnız geliştirmede): bayi Sipariş ver'de bölge bölge kartela rengi (RN/BN, desende +Altın, iplik ayrı) → fotoğraf Pillow ile boyanır (`/bayi/foto-model/KOD.jpg?…&w=k|o|b`, önbellek medya/foto_model ≤600), 💡 6 fikir; sipariş renk_notu + boyanmış foto. FF (marka) eklenmedi, pirinç köşeler fotoğraftan silindi
│   └─ Gönderim = "Onay bekliyor" sipariş → ofis sipariş sayfasından onay/ret; lazer DXF/SVG (hat + bantlar; DB deseni yalnız not)
├─ **Bayi (2. güncelleme):** `bayi_views.py`: Siparişlerim tüm siparişler tek satır `Siparis.bayi_durumu` ('Üretimde · istasyon', bekliyor/personel/gecikme/tamir yok); 🛒 Sipariş ver (katalog + kartela `Renk` RN01–07/BN01–04 `KatalogSerisi.kartela`, kartelasız seride renk yazılır, ölçü satırları → 'onay'); `Musteri.studyo_acik` (kapalıysa stüdyo sayfaları → sipariş ver, `bayi_siniri.STUDYO`); ofis 🤝 Bayiler (+ yeni bayi, `BayiDavet` 7 gün tek kullanım `/davet/<anahtar>/`, wa.me, stüdyo aç/kapa, hesap kapat yalnız yönetici); bildirim: ofis sayfası her dk `/bildirim/durum/` → ses + bant; telefona web push `bildirim.py` (yalnız cryptography, RFC8291+VAPID, anahtar SistemAyari, sw.js push), `/bildirim/abone/`
├─ **Tamir/iade:** `TamirKaydi` TM-…, `servisler.tamir_ac/tamir_bitti`, `UretimLotu.tur='tamir'` + `rota()` ofisin seçtiği istasyonlar, sipariş 'tamirde' (bayi önceki durumu görür), 🔧 TAMİR rozeti, rapor `raporlar.tamir_ozeti`; istasyonda '(Nakışlı)/(Kaplamalı)' `Kalem.on_islem`; Rona → Rono (0031), stüdyoda keten = Rono RN01–07 (`parcali.ESKI_MALZEME`)
├─ 4 Hesaplar: Tablet (istasyona bağlı; "Bu hesap kimin?" `HesapAyari.personel` → ad/PIN sorulmaz, `hesap_personeli`) / Ofis ("Ofis" grubu) / Yönetici / Bayi (yalnız stüdyo + kendi siparişleri)
├─ 5 Raporlar: makine, personel-istasyon, bekleme, Excel çıktı; Excel'den aktarma; tablet giriş kaydı
└─ 6 Altyapı / işletme
    ├─ PythonAnywhere ücretsiz (ayda bir "Run until 1 month"), ücretli pakete geçiş önerildi (~5 $/ay)
    ├─ /saglik/ (TAMAM / SORUN, 503) → UptimeRobot nöbetçi
    ├─ kurulum.sh: güncelleme öncesi yedek + migrate hatasında geri dönüş + sürüm arşivi ~/uretim_surumler
    ├─ geri_al.sh surum | veri | temizle ; manage.py yedekle [--onek gunluk]
    ├─ belgeler/acil_durum_karti.pdf (nöbetçi kurulumu + acil durum)
    └─ belgeler/kullanim_rehberi.html → PDF: büro (3 s), istasyon (1 s, asılır), bayi (2 s); Playwright ile basılır
```

## Dal → dosyalar (`uretim_takip/uretim/`)
| Dal | Dosyalar |
|---|---|
| 1 Üretim | `models.py` (Siparis, HaliTuru, RotaAdimi, Asama, Makine, UretimLotu, IslemKaydi), `servisler.py`, `views.py`, `istasyon_views.py`, `siparis_views.py`, `uyarilar.py` |
| 2 Stok | `models.py` (HamDeriGirisi, DeriTuru, DeriDuzeltme, FasonIsi, Malzeme), `stok_views.py`, `malzeme_views.py`, `fason_views.py`, `qr.py` |
| 3 Katalog/Tasarım | `foto_model.py` (fotoğraflı modeller), `parcali.py` (parçalar, kurallar, DXF), `parcali_gorsel.py`, `parcali_views.py`, `katalog_views.py`, `tasarim_views.py`, `tasarim_cizim.py` (değerler, hazırlar, DXF), `hali_gorsel.py` (çizim), `tasarim_varlik/` (doku/, desen/ maskeler+desenler.json, hazir/), `katalog_tohum/` |
| 4 Hesaplar | `hesaplar.py`, `bayi_siniri.py` (bayi erişim sınırı), `baglam.py`, `oturum.py` |
| 5 Raporlar | `raporlar.py`, `excel_aktar.py`, `aktarim_views.py` |
| 6 Altyapı | `saglik.py`, `yedek.py`, `management/commands/yedekle.py`, `../kurulum.sh`, `../geri_al.sh`, `pwa.py`, `../fabrika/settings.py` |
Formlar `forms.py`, ekranlar `templates/uretim/`, menü `../templates/base.html`, testler `tests.py`.

## Karar: stüdyonun yeni yönü (2026-10-29) — ilk sürüm yazıldı
- Halı = **parçaların birleşimi** (lazer kesim parça/desen + nakış motifi + panel, dikiş makinesinde "lego" gibi birleşir). Deri/kürk da aynı.
- Önce **suni deri**: parça kütüphanesi + ızgara (lego) düzenleyici; motif/desen her yere, simetri, geçiş = panel renk/desen dizisi.
- Hedef: tasarımdan üretime tek hat → kesim listesi, malzeme bazlı lazer DXF, nakış listesi, montaj sırası, istasyonlara parça bazında iş, maliyet.
- Yol haritası: 1 kullanıcıdan bilgi → 2 parça modeli + ızgara editörü → 3 üretim çıktıları → 4 maliyet/fire/rulo yerleşimi → 5 deri/kürk.
- **Gelen bilgi (2026-10-29, atölye + bitmiş halı fotoğrafları):** tüm parçalar lazerle kesilir (desen delikleri dahil); nakış ayrı panel; parçalar zig-zag ile birleşir, kenar Lanfel veya Biye. Suni deri rulo **140 cm en × 30 m**; nakış alanı en fazla **40×60 cm**; dikiş payı modele göre **en fazla 2 cm**.
- Fotoğraflardan çıkan parça türleri: zemin paneli (140 cm'den büyükse dikişle bölünür; zikzak/V uçlu paneller), düz desenli bant (köşelerde üst/alt bant yan bantların arasına uç uca), kavisli bant segmentleri (yuvarlak halkada ~5 yay parçası; dış kadife halka da segmentli), orta disk/oval, nakış şeridi (tekrar eden motif, her motif ≤40×60), desen altı katman (siyah/kahve/altın görünür), kenar biyesi. Deri/kürk: kare, 45° elmas, dikey şerit (rastgele boy), daire patchwork; merkezden kenara renk geçişi.
- Lazer tablası **140×300 cm**. Nakış: **7 kafalı** makine (aynı motif aynı anda 7 adet), keçe+rona+suni deri birleşik (lamine) malzemeye iplikle işleniyor. Desen altı = lamine malzeme.
- **Yeni karar (2026-10-29, foto: krem + koyu desenli çerçeveli halı):** parçalı halı = **iç içe halkalar** (en fazla 4) + orta. Dikdörtgende her halka 4 dikdörtgen parça: uzun yanlar tam boy, kısa üst/alt araya girer; hepsi zig-zag. Ovalde oval halkalar. Halka türü: düz / lazer desenli / nakışlı. **Desen altında bir şey yok** (delikler boş). Orta: düz, nakış paneli veya desenli şerit. **Yazıldı** (aşağıda günlük).
- **Hâlâ eksik:** DXF desen dosyaları; nakış motifi yalnız Grek kare (başka motif dosyası gelirse eklenir).

## Bekleyenler (kullanıcı onayı / bilgi gerekli)
- **EKSİKLER LİSTESİ (2026-11-04, kullanıcı: "şimdi yazma, not et, en son program yazacağız")** – yazmadan önce plan + onay:
  **HEPSİ YAZILDI: 1–4, 6 (2026-11-04), 12–14 (2026-11-05), 5, 7, 8, 10, 11 + kartelalar (2026-11-05, 2. güncelleme).** Açık kalan: seri→halı türü bağlantısı (Rono/Bienca/IPS/PCH serilerinde halı türü boş; bayi siparişinde ofis onayda seçiyor), stüdyodaki Bienca dokuları hâlâ 2 eski doku (kartela BN01–04 değil).
  1. İstasyonda personel işe not/açıklama girebilsin (başlatırken/bitirirken + iş sırasında; not ekranda ve sipariş/iş sayfasında görünsün).
  2. Tek siparişte aynı model, farklı ölçü ve adetler (sipariş kalemleri: en×boy×adet satırları; her kalem ayrı iş/lot, m² toplamı).
  3. Ofis siparişi düzenlerken fotoğraf ekle/değiştir (şu an düzenleme admin'de; sipariş düzenleme ekranı + foto).
  4. Pano "Bugün kim ne yaptı" çıkış/fire m² yanlış görünebiliyor. Bulunan olası nedenler: (a) aynı halı her istasyonda yeniden sayılıyor (çıkış m² = istasyon sayısı × halı); (b) kişi = işi BAŞLATAN, bitiren değil (`raporlar.personel_ozeti`); (c) stok okutulmayan işte giriş = siparişin TOPLAM m²'si, siparişte birden çok iş varsa her işe tam toplam yazılıyor; (d) fire yalnız lazerde malzeme girilince anlamlı, diğer istasyonlarda 0. Öneri: panoda m² yerine iş sayısı + bitirilen halı m²'si (son istasyon), fire yalnız ilk istasyon.
  5. **Bayi görünümü (2026-11-05 karar):** bayi istasyon adını görebilir ama 'bekliyor/çalışılıyor' yerine hep **'Üretimde · <istasyon>'**; sipariş **tek satır** (çok ölçülü siparişte istasyonlar + 'x/y halı hazır'). Müşteri portalı: müşteri/bayi kendi siparişinin aşamasını canlı görsün (bayi 'Siparişlerim' güçlendirme: aşama çizgisi, konum_metni, tahmini teslim; rol bazlı yetki sıkılaştırma; belki giriş gerektirmeyen gizli takip bağlantısı).
  6. Sevk edilmiş siparişlerin fotoğrafları ~6 ay sonra otomatik silinsin veya küçültülsün (disk).
  7. Bayi girişi bağlantıyla (kullanıcı: 1 ve 2 evet, fiyat şimdilik yok): bugün ofiste bayi sayfası YOK (bayi hesabı yalnız Hesaplar'da, o da yalnız yönetici; müşteri listesi yalnız yönetim paneli). Plan: menüde **🤝 Bayiler** sayfası (ofis + yönetici): bayi listesi (hesap var/yok, son giriş, bekleyen/aktif sipariş, stüdyo açık/kapalı), **+ Yeni bayi** (ad, telefon, stüdyo açık mı → hesap kendiliğinden, kullanıcı adı addan), **🔗 Davet bağlantısı** (tek kullanımlık, 7 gün; bayi açınca kendi şifresini koyar) + **WhatsApp'ta gönder** (wa.me, telefon kayıtlıysa doğrudan) + Kopyala; hesabı kapat yalnız yönetici. Basit mod: stüdyo kapalıysa katalog + kartela + olduğu gibi sipariş (model, renk, ölçü, adet) + Siparişlerim.
  8. Bayi sipariş gönderince ofise bildirim (kullanıcı: evet): menü rozeti (var) + ofis ekranı açıkken ses/üst bant + telefona anlık bildirim (PWA web push; Android kurulu/kurulmamış, iPhone yalnız ana ekrana ekliyse iOS 16.4+). PythonAnywhere ücretsizde dışarı bağlantı beyaz listeli → push servisine (FCM/Apple) erişim denenmeli; olmazsa yedek: e-posta veya Telegram botu.
  10. **Nakış/Kaplama etiketi (2026-11-05):** rotalar: Nakışlı = Nakış → Lazer → Zig-zag → Biye/Lanfel; Peluş = Kaplama → Lazer → …. Sonraki istasyonlarda işin yanında '(Nakışlı)' / '(Kaplamalı)' yazsın. Malzeme + en×boy ilk istasyonda (Nakış/Kaplama) KALSIN (kullanıcı 2026-11-05).
  11. **İade / tamir / düzeltme takibi (2026-11-05 karar: yalnız ofis açar; bayi GÖRMEZ; hata kimin = personel (+istasyon) kaydedilir; iade stoğa girmez, yalnız kayıt):** biten/sevk siparişte '↩ Tamir / iade aç' → neden (iade, tamir, düzeltme, garanti), açıklama, foto, hangi halı; seçilen istasyonlardan geçen tamir işi (🔧 TAMİR rozeti), sipariş 'Tamirde'; hata kaynağı istasyon (isteğe bağlı); rapor: tamir sayısı/neden/istasyon.
  **12–14 YAZILDI (2026-11-05).** 12. **İstasyon kendi işini görsün (2026-11-05):** tablet/kişisel hesapta Pano'da 'Şu an çalışılan işler' ve istasyon kutuları yalnız kendi istasyonu (ofis/yönetici hepsini görür).
  13. **Lazerde fire + en×boy (2026-11-05):** fire kutusu yalnız lazerde, isteğe bağlı, açık görünür; lazerde başlarken ve bitirirken en×boy isteğe bağlı. Diğer istasyonlarda 'Ayrıntı kg/m²' kalkacak (deri/kürk kg?) – plan sunuldu.
  14. **Menü:** 'İşler' 'QR Okut'un yanına.
  15. **2. güncelleme kararları (2026-11-05):** peluş (IPS/PCH) basit modda renk YAZILIR (kartela yok); ofisin girdiği siparişler de bayinin Siparişlerim'inde görünür (müşteri = bayi); tamir istasyonlarını ofis her seferinde seçer. Push testi (2. deneme): fcm.googleapis.com, web.push.apple.com, api.telegram.org üçü de '200 Connection established' (PA proxy izin veriyor) → telefon bildirimi web push ile yapılabilir (pywebpush + VAPID; sunucuda pip kurulumu gerekir), yedek Telegram. Plan onayı + stüdyodaki 8 peluş rengi kalsın mı sorusu bekleniyor.
  16. **YAZILDI (2026-11-05).** Suni deri stüdyosu Bienca/Rono sorunu: '💡 Fikir ver' seçili modeli hiç kullanmıyor (`parcali.fikirler` tüm malzemelerden rastgele 6 tasarım) → başka modele gidiyor. Ayrıca KATALOG_DEGER hazırları yanlış malzeme ailesiyle: BNA 21 düzenlenebilir modelde peluş + bienca_gri/krem + bakır varak; RNO 5 modelde peluş/bienca + 1 Rono. İstenen: Rono modelleri yalnız RN01–07, Bienca yalnız BN01–04 ile değiştirilsin; 'bu modelden başla' ve 'fikir ver' seçili modelin yapısını koruyup yalnız kartela renklerini değiştirsin. Bienca için 4 desenin ölçekli yakın foto dokusu gerekli.
  17. **Canlı yükleme sonrası sorunlar (2026-11-05, kullanıcı; plan sunuldu, cevap bekleniyor):** (1) istasyona bağlı hesap başka istasyona geçemiyor (kendi_istasyonu kilidi + yönlendirme, 'Bu hesap kimin' seçili hesapta PIN yok) → bir kişi birden çok istasyonda çalışamıyor; (2) lazer, Nakış ve Kaplama işlerini görsün ve başlatabilsin; (3) Biye / Lanfel / Kenar dikişi her biri kendi ekranında görünsün, iş girebilsin (rota: Lazerli/Nakışlı = Biye/Lanfel, Peluş/Suni deri = Biye/Kenar dikişi; ne istendiği soruldu); (4) sürüm farkları anlatıldı. Öneri: hesaba çoklu istasyon (HesapAyari.istasyonlar), istasyon değiştir düğmesi, ortak tablette PIN.
  9. ~~"Sunni deri" yazımı~~ – kullanıcı 2026-11-04 sunucuda kendisi düzeltti, iş kalmadı.
- Fotoğraflarla disk dolar → ücretli paket önerisi.
- **Kağıtsız istasyon akışı (kısmen yazıldı 2026-11-02: okutma isteğe bağlı, lazerde en×boy stok düşümü, yalnız Başlat/Bitir; kalan: kesim listesinden otomatik düşüm %10 fire, nakış paralel rota):** QR yalnız lazerde rulo kartından (borusuz rulo: lastik bantlı kart + iç uçta keçe tarafına yedek etiket); stok tasarımın kesim listesinden otomatik düşer, **fire %10** (sonra gerçek fireyle ayar). İstasyonlarda okutma yok: tablet listesinde halı resmi + SP no, Başla/Bitti. Rota: Lazer → (Nakış paralel, yalnız nakışlı parçalar) → Zig-zag (nakış bekleniyor işareti) → Biye/Lanfel. Lazerci büyük parçanın keçesine SP no yazar.
- **Katalog modeli yapısı kurulamayanlar (yalnız 'olduğu gibi sipariş'):** çapraz/kavisli çizgi (IPS-434, 441, 443-447, 450, 464, 472, 474, 479, 480), köşe parçası (IPS-436…438, BNA-012, 022, 023, 024), dama (BNA-020), PCH-001/007, BNA-008 vb. İleride bu yapılar eklenebilir.
- **Sıradaki (onaylı sıra):** 3) 45° gönye köşe 4) Grek karo şerit (karolar lazerle kesilir, aplike) 5) ovalde ışınsal çubuklar + uçlarda enine panel. Nakış: 7 kafa aynı motif; motif ≤40×60; uzun parçada 7'den sonra devamına 2–3 motif daha eklenebilir (tur = ⌈adet/7⌉).
- Ücretli pakete geçince: günlük yedek görevi (`yedekle --onek gunluk`), `uretim.biennafur.com` bağlama.
- Desenler: 3. fotoğraftaki işlemeli ve Grek bant için DXF/net foto → DB015/DB016; DB desenlerinin DXF'leri gelirse lazer dosyasına eklenir.
- Yeni modeller: aplike Kufi düğüm, daire patchwork, Medusa/logo madalyonu.
- Lazer makinesi IP entegrasyonu (IP + kontrol kartı modeli lazım).
- **Paraşüt Excel'leri (2026-10-30, BEKLEMEDE – kullanıcı: önce atölyede deneme, sonra karar):** ürün listesi (5.438 kart, halı kartları eksi stok = satış; ~35.000 m²; Dana/Toskana m², Rono/Peluş adet önde; 160×230 en çok) ve tahsilatlar (1.680, 189 müşteri; 2024 ~304K$ → 2026 10 ay ~1,94M$; Özdallar %36, ilk 10 %60; 20 müşteri 6+ ay ödemesiz). Fikirler: yönetici paneli, Paraşüt'e fatura, müşteri takibi, maliyet/kâr. Dosyalar yalnız oturum yüklemesinde, kalıcı değil.
- **Müşteri kartelaları (2026-11-04, programa SONRA eklenecek – kullanıcı: şimdi ekleme):** Ad **Rono** (programdaki 'Rona' → Rono). Rono yalnız 7 renk: RN01 Gri/vizon, RN02 Koyu gri/gümüş, RN03 Krem/bej, RN04 Antrasit/siyah, RN05 Vizon/sütlü kahve, RN06 Koyu kahve, RN07 Ekru/beyaz (Dore/altın bej YOK). Numune foto `is_belgeleri/kartela_foto/rona_numuneler.jpg`. Bienca 4 desen/renk BN01–04 (`bienca_kartela.jpg`). Bayi/sipariş verenlere yalnız bunlar sunulacak; keten görünümlü malzemeler = Rono, programdan çıkacak.
- **Ürün kodlaması (2026-11-03):** kullanıcı Excel listesini dolduruyor; sonra programa: renk kartelası tablosu (stok + stüdyo ortak), model renk seçenekleri (01, 02…, parça renkleri + foto), sipariş/etiket/Paraşüt'te ürün kodu, BF-… stüdyo modelleri.
- Paraşüt otomatik veri çekme (API erişimi lazım). WhatsApp sipariş yapıştırma (örnek mesaj lazım).
- Çevrimdışı kuyruk. (PIN: kişisel hesapta artık sorulmuyor — yazıldı.)
- Raporlar: fire nedeni, geri çağırma, kapasite.
- Eski kullanım kılavuzu (Claude Docs: https://claude.ai/artifact/BxoN64k1AxL1g9TQWnv4o8) güncel değil; yerine `belgeler/kullanim_rehberi.html` (+ rehber_buro/istasyon/bayi.pdf) geçerli. Program değişince rehber de güncellenmeli.
- İş kolu: programı çok müşterili yapmak (firma adı/logo/istasyon/ürün ayardan).

## Günlük (en yeni üstte, bir satır)
- 2026-11-05: Gerçekçi görünüm 1. adım (migration 0032): kullanıcının 7 Rono fotoğrafı RNO-006…012 kataloğa (FF logolu koyulmadı; pirinç köşe/çerçeve yok → fotoğraftan temizlendi), bayi Sipariş ver'de fotoğraf üzerinde bölge renkleri + fikir ver, siparişe boyanmış foto. Sıradaki (kullanıcı 'evet'): beğenirse öteki Rono/Bienca katalog modelleri; sonra siyah simli/ayna altın/gümüş kaldırma, iplik-kenar ayrımı, Bienca/Rono'da şerit+nakış, bayi ana sayfa iki düğme + güzelleştirme.
- 2026-11-05: Stüdyo kartela: Bienca BN01–04 gerçek dokular (kartla ölçülü, `doku/bienca_bn0X.jpg`, olcek.json), eski bienca_krem/gri → BN01/BN03 (`ESKI_MALZEME`); `parcali.KARTELA_MALZEMELERI` (RNO 7, BNA 4) + `METALIK` (altın, gümüş, ayna altın, siyah simli – ince çizgi); katalog RNO/BNA modelinde `kartelaya_uydur` (temizle + hazir_degerler; `KARTELA_ESLEME`), kenar rengi kartelaya bağlı (`kenar_secenekleri`, `KENAR_AD`); arayüzde `kartelaFiltre()` (data-grup); 💡 fikir ver seçili model/sekme ile (`fikirler(katalog, seri)`, `_kartela_renklendir`: yapı aynı, zemin + vurgu + metal + kenar); Sipariş ver'de '✏️ Renklerini değiştir' (?hazir=KOD).
- 2026-11-05: Hızlı düzeltme: istasyon kilidi kaldırıldı (istasyon_secimi/ekrani/parca yönlendirmesi yok; bağlı istasyon yalnız kısayol + Pano/İşler süzgeci + başlatta varsayılan). Çoklu istasyon / ortak tablet PIN planı kullanıcı cevabını bekliyor (madde 17).
- 2026-11-05: 2. güncelleme (migration 0031, requirements + cryptography, SW v6): kartela, Bayiler + davet + WhatsApp, basit mod, bayi tek satır görünüm, ofis bildirimi (ses/bant + web push), tamir/iade + rapor, Nakışlı/Kaplamalı etiketi, Rona→Rono. Rehberler güncellendi.
- 2026-11-05: Atölye düzeltmeleri (migration 0030): istasyon hesabı (`servisler.kendi_istasyonu`, staff değil + bağlı istasyon) Pano/İşler/istasyon ekranında yalnız kendi istasyonu, başka istasyon ekranı → kendi ekranına yönlenir; lazerde (`Asama.lazer_mi`) başlarken giren en×boy, bitirirken çıkan en×boy + fire m² (isteğe bağlı, IslemKaydi giris/cikis_en/boy_cm); diğer istasyonlarda kg/m² kutusu kalktı; menüde İşler QR Okut'un yanında; başlatta kendi istasyonu seçili gelir.
- 2026-11-04: 1. güncelleme (migration 0028–0029): sipariş ölçü satırları + her satıra otomatik iş, sipariş düzenleme ekranı (foto ekle/sil), istasyon 📝 notu, pano 'kim ne yaptı' düzeltmesi, sevk tarihi + 6 ay sonra foto küçültme. Rehber PDF'leri güncellendi. Kullanıcı kararları: iki güncelleme; ölçü başına iş otomatik; foto silme değil küçültme; kartelalar 2. güncellemede.
- 2026-11-03: Kullanıcının basılı kartelaları Excel'e işlendi: Bienca BN01–BN04 (varak/eskitme), Rono RN01–RN08 (üçlü lamine süet+keçe+Rono; basılı kartelada 02/04/05 numarasızdı, önerildi). Programdaki 'keten görünümlü' = Rono (kullanıcı onayı) → programa aktarırken keten malzemeleri Rono 8 renkle değiştirilecek. Bienca/Rono tek malzeme: renk no = kartela no (RNO-003-06). Örnek kesitler `is_belgeleri/kartela_ornek/`.
- 2026-11-03: Ürün kod listesi taslağı (program dışı Excel) `is_belgeleri/Bienna_Fur_urun_kodlari.xlsx` (üretici: `urun_kodlari_olustur.py`): kod = MODEL-RENKNO(-ölçü); 192 model fotoğraflı, zemin rengi tahmini, renk kartelası (PL/BN/RN/KT/VR/KD/SD/MT/KR/IP kodları), lazer desenleri, nakış motifleri. Kullanıcı doldurunca programa aktarılacak (açık sorular: Paraşüt kod düzeni, ölçü koda girsin mi, eski siparişler).
- 2026-11-02: Suni deri: değiştirilemeyen katalog modelinde "Bu modelden başla" iPhone'da gizlenmiyordu → base.html'e genel `[hidden]{display:none!important}`; model seçilince önizlemede katalog fotoğrafı, açıklayıcı not.
- 2026-11-02: Atölye denemesi düzeltmeleri (migration 0027): sipariş en×boy + acil + istasyon önceliği/not/teslim; stok rulo/plaka en×boy; lazerde malzeme + en×boy → FIFO stok düşümü, fire; stok okutma isteğe bağlı (Pano düğmesi); kişisel hesapta PIN yok; iş yeri yazıyla. Rehber PDF'leri güncellendi. Kurulumdan sonra: Hesaplar'da her çalışana "Bu hesap kimin?" + istasyon.
- 2026-10-30: Kullanıcı rehberi: büro / istasyon (tek sayfa) / bayi PDF'leri (`belgeler/`). Program kodu değişmedi.
- 2026-10-30: Android Paylaş → Üretim Takip (manifest share_target, sw.js POST /paylas/ → "paylasilan" önbelleği → paylas.html: yeni sipariş / var olan siparişe ekle; SURUM v5). **Kullanıcıya gönderilen son zip bu.**
- 2026-10-30: Sipariş fotoğrafı (ofis yükler, ≤3, küçültülür; listede, detayda, istasyon ekranında, dokununca tam ekran ✕), ⭐ Modellere ekle (MM-…, bayi görür).
- 2026-10-30: Suni deri = katalog lazer serileri (IPS/BNA/PCH/RNO) hazır model + olduğu gibi sipariş; madalyon; peluş/Bienca/Rona dokuları; DB015 Grek bant; nakış 14 motif, 4 lazer deseni gizlendi; menü "Suni deri"; atölye fotoğraflı P-hazırları kaldırıldı.
- 2026-10-30: Nakış motif kataloğu (27 motif, gerçek ölçü, 'motif ölçüsü' kutusu kalktı; panel = motif + 4 cm, 1–3 motif), iplik rengi, gerçek ürün fotoğraflı hazırlar P-1…P-9 + P-10…12, kürk/deri sekmesinden suni deri kaldırıldı.
- 2026-10-30: Bayi uyarıları tek satır rozet (dokununca açılır) + ilgili halka/adımda; teknik uyarı yalnız kesim listesinde; yer yoksa "+ halka" kapalı, genişlik sınırı. kurulum.sh: zip + pip önbelleği silinir, `--no-cache-dir`, son 2 sürüm, sürüm kopyasında katalog_tohum/doku yok (~1 MB). Sunucu ölçümü: surumler 43M, takip 34M, .cache 18M, zip 15M. 
- 2026-10-29: Halkalı parçalı halı (≤4 halka + orta panel/şerit, desen delikleri boş), sade 5 adımlı ekran, ✕'li büyük görünüm, yeni P-1…P-8, eski tasarım çevirme.
- 2026-10-29: Lanfel hatası düzeltildi (e1c9c76); 16 malzeme fotoğrafından gerçek dokular (kart ölçeği 92.6 px/cm), kabartma + yakınlaştırma; yeni düzenler (şerit/ızgara/elmas/iki parça), renk aileleri, 💡 Bana fikir ver. Bekleyen: malzeme adları (geçici), Odamda gör, istasyonlara parça bazında iş, desen DXF'leri.
- 2026-10-29: Parçalı suni deri tasarım ilk sürüm (3 düzen, kesim listesi, malzeme bazlı DXF). Sıradaki: kullanıcı denemesi, desen DXF'leri, deri/kürk ızgara (kare/elmas/şerit/daire, renk geçişi), istasyonlara parça bazında iş.
- 2026-10-29: Stüdyo ve katalogda desen seçimi artık desenin halı köşesindeki görünüşüyle (`tasarim_varlik/desen_onizleme/`).
- 2026-10-28: Nöbetçi /saglik/, güncelleme öncesi yedek, geri_al.sh, acil durum kartı (349dd1e). 
- 2026-10-28: Suni deri stüdyo modeli SD-1…4 (31aa3a1); gerçekçi stüdyo + onay siparişte (ffe9748); stüdyo ilk sürüm (e7da1d9); katalog (25cd34c).
- 2026-10-28: Fason + Suni deri halı rotası; ana malzeme türleri, renk/model; geçiş dönemi.
- Öncesi: üretim takip çekirdeği, istasyonlar/rotalar, hesaplar, raporlar, PWA, Excel aktarma (README'de ayrıntı).
