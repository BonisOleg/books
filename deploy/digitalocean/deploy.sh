#!/usr/bin/env bash
# Деплой/оновлення коду на Droplet. Запуск з кореня проєкту під www-data або root.
set -o errexit
set -o pipefail
set -o nounset

APP_DIR="${APP_DIR:-/var/www/bookshop}"
cd "${APP_DIR}"

echo "==> Python venv"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install --no-cache-dir -r requirements.txt

echo "==> Django build"
# manage.py за замовчуванням — develop; для collectstatic потрібен production (manifest).
if [[ -f .env ]]; then
    _dsm="$(grep -E '^DJANGO_SETTINGS_MODULE=' .env | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
    export DJANGO_SETTINGS_MODULE="${_dsm:-config.settings.production}"
else
    export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
fi
echo "    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}"
python manage.py compilemessages
python scripts/bundle_site_css.py
# --clear чистить лише STATIC_ROOT (staticfiles/), не MEDIA_ROOT.
python manage.py collectstatic --noinput --clear
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py check

echo "==> Systemd (завжди оновлюємо unit-файл)"
cp deploy/digitalocean/gunicorn.service /etc/systemd/system/bookshop.service
systemctl daemon-reload
systemctl enable bookshop

# Не перезаписуємо наявний sites-available/ofion: там Certbot SSL.
if [[ ! -e /etc/nginx/sites-available/ofion && ! -e /etc/nginx/sites-enabled/ofion ]]; then
    echo "==> Перший деплой: Nginx"
    cp deploy/digitalocean/nginx-ofion.conf /etc/nginx/sites-available/ofion
    ln -sf /etc/nginx/sites-available/ofion /etc/nginx/sites-enabled/ofion
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl reload nginx
fi

if [[ -f deploy/digitalocean/apply_abuse_blocking.sh ]]; then
    echo "==> Abuse blocking (nginx rate limit + fail2ban)"
    bash deploy/digitalocean/apply_abuse_blocking.sh
fi

echo "==> Права"
chown -R www-data:www-data "${APP_DIR}/staticfiles" "${APP_DIR}/media" 2>/dev/null || true

echo "==> Перезапуск Gunicorn"
systemctl restart bookshop
systemctl status bookshop --no-pager

echo "==> Готово"
