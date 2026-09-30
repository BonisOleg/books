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
# Без --clear: WhiteNoise manifest читається Gunicorn один раз при старті.
# Якщо видалити старі хешовані файли до перезапуску — живий процес віддає
# HTML зі старими хешами, і весь CSS/JS стає 404. Старі файли не заважають.
# Разове очищення: CLEAR_STATIC=1 bash deploy/digitalocean/deploy.sh
if [[ "${CLEAR_STATIC:-0}" == "1" ]]; then
    python manage.py collectstatic --noinput --clear
else
    python manage.py collectstatic --noinput
fi
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py check

echo "==> Systemd (завжди оновлюємо unit-файл)"
cp deploy/digitalocean/gunicorn.service /etc/systemd/system/bookshop.service
systemctl daemon-reload
systemctl enable bookshop

echo "==> Права"
chown -R www-data:www-data "${APP_DIR}/staticfiles" "${APP_DIR}/media" 2>/dev/null || true

# Перезапуск застосунку — одразу після збірки, до будь-яких сторонніх кроків
# (nginx, fail2ban). Їх збій не має лишати старий процес зі старим manifest.
echo "==> Перезапуск Gunicorn"
systemctl restart bookshop
systemctl status bookshop --no-pager

# Не перезаписуємо наявний sites-available/ofion: там Certbot SSL.
if [[ ! -e /etc/nginx/sites-available/ofion && ! -e /etc/nginx/sites-enabled/ofion ]]; then
    echo "==> Перший деплой: Nginx"
    cp deploy/digitalocean/nginx-ofion.conf /etc/nginx/sites-available/ofion
    ln -sf /etc/nginx/sites-available/ofion /etc/nginx/sites-enabled/ofion
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl reload nginx
fi

# Сторонній крок: його збій не має ламати деплой (застосунок уже перезапущено).
if [[ -f deploy/digitalocean/apply_abuse_blocking.sh ]]; then
    echo "==> Abuse blocking (nginx rate limit + fail2ban)"
    if ! bash deploy/digitalocean/apply_abuse_blocking.sh; then
        echo "WARN: apply_abuse_blocking.sh завершився з помилкою; застосунок працює, перевір nginx/fail2ban вручну" >&2
    fi
fi

echo "==> Перевірка: HTML посилається на наявні static-файли"
python - <<'PY'
import os, re, sys, urllib.request
from pathlib import Path

# Host має бути з DJANGO_ALLOWED_HOSTS, інакше Django відповідає 400.
host = 'localhost'
env_file = Path('.env')
if env_file.is_file():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.startswith('DJANGO_ALLOWED_HOSTS='):
            first = line.split('=', 1)[1].strip().strip('"\'').split(',')[0].strip()
            if first:
                host = first.lstrip('.')
            break
host = os.environ.get('DEPLOY_CHECK_HOST', host)
req = urllib.request.Request('http://127.0.0.1:8000/', headers={'Host': host})
try:
    html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', 'ignore')
except Exception as exc:  # noqa: BLE001
    print(f'WARN: не вдалося отримати / з gunicorn (Host: {host}): {exc}', file=sys.stderr)
    sys.exit(0)
root = Path('staticfiles')
refs = set(re.findall(r'/static/([^"\'\s?#]+)', html))
missing = sorted(p for p in refs if not (root / p).is_file())
if missing:
    print('ERROR: у HTML є посилання на відсутні static-файли:', file=sys.stderr)
    for p in missing[:20]:
        print(f'  {p}', file=sys.stderr)
    sys.exit(1)
print(f'    OK: {len(refs)} static-посилань, усі файли на місці')
PY

echo "==> Готово"
