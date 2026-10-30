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
- Test: `cd uretim_takip && ../.venv/bin/python manage.py test uretim` (112 test) + `manage.py makemigrations --check --dry-run`.
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
│   ├─ Sipariş SP-…  (durum: onay → acik → uretimde → tamamlandi → sevk / iptal)
│   ├─ Halı türü + rota: Lazerli, Nakışlı, Peluş, Suni deri  (aynı sira = alternatif istasyon)
│   ├─ İstasyonlar: Lazer kesim 1/2, Nakış, Kaplama, Zig-zag, Biye, Lanfel, Kenar dikişi (+ makineler)
│   ├─ İş IS-…: yeni iş (stok QR + PIN) → işlem başlat/bitir → sıradaki istasyon
│   └─ İstasyon ekranı (20 sn yenilenir), bekleme/süre uyarıları, pano
├─ 2 Stok
│   ├─ Ana malzeme lotu HD-… (QR etiket; birim m² / metretül / ayak)
│   ├─ Malzeme türleri: deri, Keçe, Süet, Rona, Suni deri + bileşikler (3'lü lamine, Halı tabanı); renk/model
│   ├─ Yardımcı malzeme MZ-… ; düzeltme (sayım/fire)
│   ├─ Fason FS-…: gönder (stoktan düşer) → teslim al (yeni lot, renk/model üst katmandan) → fason firesi
│   └─ Geçiş dönemi düğmesi (etiketsiz eski stoktan iş)
├─ 3 Katalog + Tasarım stüdyosu
│   ├─ Katalog: 13 seri, 192 model (TOS, HMK, IPS, LTS…), 14 lazer deseni DB001–DB014
│   ├─ Stüdyo (bayi): Kürk (Toskana: dış bant → halka → iç bant → zemin → madalyon) / Suni deri (varak, peluş, kadife, sim/rugan alt, biye)
│   ├─ Hazırlar: TOS-034…LTS-006 (menü "Kürk / deri modelleri"); SD-1…SD-4 yalnız eski suni kayıtlar açılınca görünür
│   ├─ **Suni deri** (menü adı; eski "Parçalı") /tasarim/parcali/: hazır modeller = katalog lazer serileri IPS/BNA/PCH/RNO (99 foto, seri sekmeleri; 76'sı `KATALOG_DEGER` ile düzenlenebilir), "olduğu gibi sipariş" (`aynen`+`katalog`, sipariş katalog modeline bağlı, resim = katalog fotoğrafı) ya da "bu modelden başla"; orta **madalyon** (düz/nakışlı, çerçeve); malzemeler peluş 8 renk/Bienca/Rona (numune fotoğrafından); DB015 Grek bant (çizildi); gizli desenler DB002/007/010/011; nakış 14 motif (`NAKIS_MOTIFLERI`, gerçek ölçü, maske `tasarim_varlik/nakis/`, marka logoları yok) + iplik rengi; hazırlar P-1…P-12 (P-1…9 gerçek ürün fotoğraflı `tasarim_varlik/hazir_foto/`); **halkalı** (dikdörtgen/oval, ≤4 halka düz/desenli/nakışlı + orta düz/nakış paneli/enine-boyuna şerit), 5 adımlı ekran + ✕'li büyük görünüm; eski düzenler (çerçeve, oval şerit, yuvarlak, ızgara…) yalnız eski kayıtlar için, `eskiden_cevir`; 💡 fikir ver; P-1…P-8; gerçek malzeme fotoğraf dokuları; parça bölme, rulo, nakış 7 kafa, kesim listesi + malzeme bazlı DXF
│   └─ Gönderim = "Onay bekliyor" sipariş → ofis sipariş sayfasından onay/ret; lazer DXF/SVG (hat + bantlar; DB deseni yalnız not)
├─ 4 Hesaplar: Tablet (istasyona bağlı) / Ofis ("Ofis" grubu) / Yönetici / Bayi (yalnız stüdyo + kendi siparişleri)
├─ 5 Raporlar: makine, personel-istasyon, bekleme, Excel çıktı; Excel'den aktarma; tablet giriş kaydı
└─ 6 Altyapı / işletme
    ├─ PythonAnywhere ücretsiz (ayda bir "Run until 1 month"), ücretli pakete geçiş önerildi (~5 $/ay)
    ├─ /saglik/ (TAMAM / SORUN, 503) → UptimeRobot nöbetçi
    ├─ kurulum.sh: güncelleme öncesi yedek + migrate hatasında geri dönüş + sürüm arşivi ~/uretim_surumler
    ├─ geri_al.sh surum | veri | temizle ; manage.py yedekle [--onek gunluk]
    └─ belgeler/acil_durum_karti.pdf (nöbetçi kurulumu + acil durum)
```

## Dal → dosyalar (`uretim_takip/uretim/`)
| Dal | Dosyalar |
|---|---|
| 1 Üretim | `models.py` (Siparis, HaliTuru, RotaAdimi, Asama, Makine, UretimLotu, IslemKaydi), `servisler.py`, `views.py`, `istasyon_views.py`, `siparis_views.py`, `uyarilar.py` |
| 2 Stok | `models.py` (HamDeriGirisi, DeriTuru, DeriDuzeltme, FasonIsi, Malzeme), `stok_views.py`, `malzeme_views.py`, `fason_views.py`, `qr.py` |
| 3 Katalog/Tasarım | `parcali.py` (parçalar, kurallar, DXF), `parcali_gorsel.py`, `parcali_views.py`, `katalog_views.py`, `tasarim_views.py`, `tasarim_cizim.py` (değerler, hazırlar, DXF), `hali_gorsel.py` (çizim), `tasarim_varlik/` (doku/, desen/ maskeler+desenler.json, hazir/), `katalog_tohum/` |
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
- **Kağıtsız istasyon akışı (plan onaylandı, yazılmadı):** QR yalnız lazerde rulo kartından (borusuz rulo: lastik bantlı kart + iç uçta keçe tarafına yedek etiket); stok tasarımın kesim listesinden otomatik düşer, **fire %10** (sonra gerçek fireyle ayar). İstasyonlarda okutma yok: tablet listesinde halı resmi + SP no, Başla/Bitti. Rota: Lazer → (Nakış paralel, yalnız nakışlı parçalar) → Zig-zag (nakış bekleniyor işareti) → Biye/Lanfel. Lazerci büyük parçanın keçesine SP no yazar.
- **Katalog modeli yapısı kurulamayanlar (yalnız 'olduğu gibi sipariş'):** çapraz/kavisli çizgi (IPS-434, 441, 443-447, 450, 464, 472, 474, 479, 480), köşe parçası (IPS-436…438, BNA-012, 022, 023, 024), dama (BNA-020), PCH-001/007, BNA-008 vb. İleride bu yapılar eklenebilir.
- **Sıradaki (onaylı sıra):** 3) 45° gönye köşe 4) Grek karo şerit (karolar lazerle kesilir, aplike) 5) ovalde ışınsal çubuklar + uçlarda enine panel. Nakış: 7 kafa aynı motif; motif ≤40×60; uzun parçada 7'den sonra devamına 2–3 motif daha eklenebilir (tur = ⌈adet/7⌉).
- Ücretli pakete geçince: günlük yedek görevi (`yedekle --onek gunluk`), `uretim.biennafur.com` bağlama.
- Desenler: 3. fotoğraftaki işlemeli ve Grek bant için DXF/net foto → DB015/DB016; DB desenlerinin DXF'leri gelirse lazer dosyasına eklenir.
- Yeni modeller: aplike Kufi düğüm, daire patchwork, Medusa/logo madalyonu.
- Lazer makinesi IP entegrasyonu (IP + kontrol kartı modeli lazım).
- Paraşüt otomatik veri çekme (API erişimi lazım). WhatsApp sipariş yapıştırma (örnek mesaj lazım).
- Tek dokunuşla usta akışı (PIN her gün mü hatırlansın? cevap bekleniyor). Çevrimdışı kuyruk.
- Raporlar: fire nedeni, geri çağırma, kapasite.
- Kullanım kılavuzu (Claude Docs: https://claude.ai/artifact/BxoN64k1AxL1g9TQWnv4o8) fason, katalog, stüdyo, acil durum ile güncellenmedi.
- İş kolu: programı çok müşterili yapmak (firma adı/logo/istasyon/ürün ayardan).

## Günlük (en yeni üstte, bir satır)
- 2026-10-30: Suni deri = katalog lazer serileri (IPS/BNA/PCH/RNO) hazır model + olduğu gibi sipariş; madalyon; peluş/Bienca/Rona dokuları; DB015 Grek bant; nakış 14 motif, 4 lazer deseni gizlendi; menü "Suni deri"; atölye fotoğraflı P-hazırları kaldırıldı. **Kullanıcıya gönderilen son zip bu.**
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
