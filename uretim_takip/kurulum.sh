#!/usr/bin/env bash
# PythonAnywhere (veya herhangi bir Linux sunucu) için kurulum.
# Kullanım:  bash kurulum.sh            -> kullaniciadi.pythonanywhere.com
#            bash kurulum.sh eu         -> kullaniciadi.eu.pythonanywhere.com
#            bash kurulum.sh alan.com   -> kendi alan adınız
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  "")  ALAN="${USER}.pythonanywhere.com" ;;
  eu)  ALAN="${USER}.eu.pythonanywhere.com" ;;
  *)   ALAN="$1" ;;
esac

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for aday in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$aday" >/dev/null 2>&1; then PY="$aday"; break; fi
  done
fi
VENV="${VENV:-$HOME/.venv-uretim}"

echo "==> Python: $($PY --version)   Sanal ortam: $VENV   Adres: https://$ALAN"
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

if [ ! -f .env ]; then
  ANAHTAR="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(50))')"
  cat > .env <<ENV
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=$ANAHTAR
DJANGO_ALLOWED_HOSTS=$ALAN
SITE_ADRESI=https://$ALAN
ENV
  chmod 600 .env
  echo "==> .env oluşturuldu"
else
  echo "==> .env zaten var, dokunulmadı"
fi

# Güncellemeden önce veritabanının yedeği (geri almak için: bash geri_al.sh)
ONCEKI_YEDEK=""
if [ -f db.sqlite3 ]; then
  "$VENV/bin/python" manage.py yedekle --onek guncelleme_oncesi --tut 10
  ONCEKI_YEDEK="$(ls -1 yedekler/guncelleme_oncesi_*.sqlite3 | tail -n 1)"
fi
if ! "$VENV/bin/python" manage.py migrate --noinput; then
  echo "!!! Veritabanı güncellenemedi."
  if [ -n "$ONCEKI_YEDEK" ]; then
    cp "$ONCEKI_YEDEK" db.sqlite3
    echo "!!! Veritabanı güncelleme öncesi hâline döndürüldü. Programı da eski sürüme almak için: bash geri_al.sh surum"
  fi
  exit 1
fi
"$VENV/bin/python" manage.py collectstatic --noinput -v0

# Başarılı kurulan sürümün kopyası (geri_al.sh surum bununla bir önceki sürüme döner); son 3 tutulur
SURUMLER="$HOME/uretim_surumler"
mkdir -p "$SURUMLER"
tar -czf "$SURUMLER/surum_$(date +%Y-%m-%d_%H%M%S).tar.gz" --exclude=./db.sqlite3 --exclude=./.env \
    --exclude=./yedekler --exclude=./medya --exclude=./staticfiles --exclude='*/__pycache__' .
ls -1t "$SURUMLER"/surum_*.tar.gz | tail -n +4 | xargs -r rm -f
"$VENV/bin/python" manage.py check --deploy --fail-level ERROR >/dev/null 2>&1 \
  || "$VENV/bin/python" manage.py check --deploy --fail-level ERROR

cat <<SON

==> Kurulum tamam.
   Sıradaki adımlar:
   1) Yönetici hesabı oluşturun:
        $VENV/bin/python $(pwd)/manage.py createsuperuser
   2) Web sekmesinde şu değerleri girin:
        Source code : $(pwd)
        Virtualenv  : $VENV
        Static files: /static/  ->  $(pwd)/staticfiles
   3) WSGI dosyasının içeriğini KURULUM_PYTHONANYWHERE.md'deki örnekle değiştirip "Reload" deyin.
SON
