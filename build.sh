#!/usr/bin/env bash
# Render build script for Django + Cloudinary + WhiteNoise.
# Виконується на кожному деплої перед стартом сервісу.
# Тут НЕ робимо жорсткого `check --deploy` — деякі секрети (CLOUDINARY_URL,
# SMTP, домен) можуть бути ще не задані під час першого build, але вони
# обов'язково перевіряються в runtime у config/settings/production.py.

set -o errexit
set -o pipefail
set -o nounset

echo "==> Python: $(python --version)"
echo "==> Pip:    $(pip --version)"

echo "==> Upgrading pip toolchain"
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing dependencies"
pip install --no-cache-dir -r requirements.txt

echo "==> Compiling translation messages"
python manage.py compilemessages

echo "==> Collecting static files (WhiteNoise compressed manifest)"
python manage.py collectstatic --noinput --clear

echo "==> Running Django system checks (without --deploy)"
python manage.py check

echo "==> Build finished"
