#!/usr/bin/env bash
# Acil durumda geri alma. Kullanım (Consoles → Bash, uretim_takip klasöründe):
#   bash geri_al.sh surum    -> son güncellemeyi geri al: programı bir önceki sürüme, veriyi güncelleme öncesine döndür
#   bash geri_al.sh veri     -> veriyi seçeceğiniz bir yedeğe döndür (program aynı kalır)
#   bash geri_al.sh temizle  -> disk dolduysa eski yedekleri sil (her türden son 3 kalır)
# Her geri almadan önce o anki veri "geri_alma_oncesi_..." adıyla ayrıca yedeklenir.
set -euo pipefail
cd "$(dirname "$0")"
VENV="${VENV:-$HOME/.venv-uretim}"
SURUMLER="$HOME/uretim_surumler"

onay() {
  read -r -p "$1 Devam etmek için EVET yazın: " cevap
  [ "$cevap" = "EVET" ] || { echo "Vazgeçildi, hiçbir şey değişmedi."; exit 1; }
}

simdiki_veriyi_yedekle() {
  [ -f db.sqlite3 ] && "$VENV/bin/python" manage.py yedekle --onek geri_alma_oncesi --tut 5 || true
}

case "${1:-}" in
  surum)
    mapfile -t surumler < <(ls -1t "$SURUMLER"/surum_*.tar.gz 2>/dev/null || true)
    if [ "${#surumler[@]}" -lt 2 ]; then
      echo "Geri dönülecek önceki sürüm yok (en az iki kurulum gerekir). Eski zip dosyasını yükleyip kurulum.sh çalıştırın."
      exit 1
    fi
    onceki="${surumler[1]}"
    veri="$(ls -1 yedekler/guncelleme_oncesi_*.sqlite3 2>/dev/null | tail -n 1 || true)"
    echo "Program şu sürüme dönecek : $(basename "$onceki")"
    echo "Veri şu yedeğe dönecek    : ${veri:-(yedek yok, veri olduğu gibi kalır)}"
    echo "Bu yedekten SONRA girilen kayıtlar (sipariş, işlem...) geri gelmez."
    onay ""
    simdiki_veriyi_yedekle
    tar -xzf "$onceki"
    [ -n "$veri" ] && cp "$veri" db.sqlite3
    rm -f "${surumler[0]}"  # sorunlu sürüm listeden çıkar; bir sonraki geri alma daha eskiye gider
    "$VENV/bin/python" manage.py collectstatic --noinput -v0 || true
    ;;
  veri)
    mapfile -t yedekler < <(ls -1tr yedekler/*.sqlite3 2>/dev/null || true)
    if [ "${#yedekler[@]}" -eq 0 ]; then echo "yedekler/ klasöründe yedek yok."; exit 1; fi
    echo "Yedekler (en yeni en altta):"
    for i in "${!yedekler[@]}"; do printf "  %2d) %s\n" "$((i + 1))" "$(basename "${yedekler[$i]}")"; done
    read -r -p "Hangi numaraya dönülsün? " no
    [[ "$no" =~ ^[0-9]+$ ]] && [ "$no" -ge 1 ] && [ "$no" -le "${#yedekler[@]}" ] || { echo "Geçersiz numara."; exit 1; }
    secilen="${yedekler[$((no - 1))]}"
    echo "Veri şu yedeğe dönecek: $(basename "$secilen"). Bu yedekten SONRA girilen kayıtlar geri gelmez."
    onay ""
    simdiki_veriyi_yedekle
    cp "$secilen" db.sqlite3
    ;;
  temizle)
    for onek in gunluk guncelleme_oncesi geri_alma_oncesi uretim_yedek; do
      { ls -1 yedekler/${onek}_*.sqlite3 2>/dev/null || true; } | head -n -3 | xargs -r rm -f
    done
    { ls -1t "$SURUMLER"/surum_*.tar.gz 2>/dev/null || true; } | tail -n +3 | xargs -r rm -f
    echo "Eski yedekler silindi. Kalan:"; ls -1 yedekler/ 2>/dev/null || true
    du -sh "$HOME" 2>/dev/null || true
    exit 0
    ;;
  *)
    sed -n '2,6p' "$0"; exit 1 ;;
esac
"$VENV/bin/python" manage.py migrate --noinput >/dev/null || true
echo
echo "==> Tamam. Şimdi PythonAnywhere'de Web sekmesine girip yeşil Reload düğmesine basın."
