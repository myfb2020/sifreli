#!/usr/bin/env bash
# Güncellemeyi PythonAnywhere'e yükler (kullanıcı 2026-11-24: "bir sonraki güncellemeyi sen yükle").
# API anahtarı oturum ortamının ağ sırrıdır: proxy www.pythonanywhere.com isteklerine ekler (burada yazılmaz).
# Adımlar: zip yap → ~/uretim_takip.zip olarak yükle → bir kerelik zamanlanmış görevle
#   unzip + kurulum.sh (yedek, migrate, collectstatic) → görev biter → görevi sil → Reload → hata günlüğüne bak.
# Kullanım (/home/user/sifreli içinde):  bash araclar/pa_yukle.sh
set -euo pipefail
cd "$(dirname "$0")/.."
A="https://www.pythonanywhere.com/api/v0/user/uretim"
ALAN="uretim.biennafur.com"

echo "==> zip"
rm -f uretim_takip.zip
zip -qr uretim_takip.zip uretim_takip -x 'uretim_takip/db.sqlite3' 'uretim_takip/.env' 'uretim_takip/staticfiles/*' \
  'uretim_takip/yedekler/*' 'uretim_takip/medya/*' '*/__pycache__/*' '*.pyc'
ls -la uretim_takip.zip

echo "==> yükleme (~/uretim_takip.zip)"
kod=$(curl -s -m 600 -o /tmp/pa_yanit -w "%{http_code}" -F "content=@uretim_takip.zip" "$A/files/path/home/uretim/uretim_takip.zip")
[ "$kod" = 200 ] || [ "$kod" = 201 ] || { echo "!!! yükleme olmadı: HTTP $kod"; cat /tmp/pa_yanit; exit 1; }

echo "==> kurulum görevi (bir kerelik, 2 dk sonra)"
read -r SAAT DAKIKA < <(date -u -d "+2 min" "+%-H %-M")
KOMUT="cd /home/uretim && unzip -oq uretim_takip.zip && cd uretim_takip && USER=uretim HOME=/home/uretim bash kurulum.sh $ALAN"
# komuttaki & işaretleri bölünmesin: --data-urlencode (ilk denemede yalnız 'cd' çalışmıştı)
CEVAP=$(curl -s -m 60 -X POST "$A/schedule/" --data-urlencode "command=$KOMUT" -d "enabled=true" -d "interval=daily" \
  -d "hour=$SAAT" -d "minute=$DAKIKA" --data-urlencode "description=Claude güncelleme (bir kerelik)")
GOREV=$(echo "$CEVAP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
KAYITLI=$(echo "$CEVAP" | python3 -c "import sys,json; print(json.load(sys.stdin)['command'])")
echo "    görev $GOREV, $SAAT:$DAKIKA UTC"
if [ "$KAYITLI" != "$KOMUT" ]; then
  echo "!!! görev komutu bozuk kaydedildi: $KAYITLI"
  curl -s -m 30 -X DELETE "$A/schedule/$GOREV/" -o /dev/null; exit 1
fi
GUNLUK="/var/log/schedule-log-$GOREV.log"
for i in $(seq 1 60); do  # en çok ~15 dk
  sleep 15
  if curl -s -m 30 "$A/files/path$GUNLUK" | grep -q "Completed task"; then break; fi
done
curl -s -m 30 "$A/files/path$GUNLUK" | tail -n 30
curl -s -m 30 -X DELETE "$A/schedule/$GOREV/" -o /dev/null -w "    görev silindi: HTTP %{http_code}\n"
if ! curl -s -m 30 "$A/files/path$GUNLUK" | grep -q "Kurulum tamam"; then
  echo "!!! kurulum tamamlanmadı: Reload YAPILMADI (eski sürüm çalışmaya devam ediyor)"; exit 1
fi

echo "==> Reload"
curl -s -m 120 -X POST "$A/webapps/$ALAN/reload/" -w "\n    HTTP %{http_code}\n"
sleep 20
echo "==> hata günlüğü (son satırlar)"
curl -s -m 30 "$A/files/path/var/log/$ALAN.error.log" | tail -n 15
echo "==> sağlık"
curl -s -m 30 -w "  HTTP %{http_code}\n" "https://$ALAN/saglik/"
