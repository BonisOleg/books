#!/usr/bin/env bash
# Відновлення БД на Droplet. Запуск на сервері після sync_from_local.sh.
# Очікує: /tmp/migration/bookshop_dump.pgdump, /tmp/migration/update_image_paths.sql
set -o errexit
set -o pipefail
set -o nounset

MIGRATION_DIR=/tmp/migration
DUMP="${MIGRATION_DIR}/bookshop_dump.pgdump"
SQL="${MIGRATION_DIR}/update_image_paths.sql"
ENV_FILE=/var/www/bookshop/.env

for f in "${DUMP}" "${ENV_FILE}"; do
    [[ -f "${f}" ]] || { echo "Немає ${f}" >&2; exit 1; }
done

# Не source .env — значення з <>, пробілами ламають bash.
DATABASE_URL="$(grep -m1 '^DATABASE_URL=' "${ENV_FILE}" | cut -d= -f2- | sed 's/^["'\'']//; s/["'\'']$//')"
export DATABASE_URL

[[ -n "${DATABASE_URL:-}" ]] || { echo "DATABASE_URL не задано в .env" >&2; exit 1; }

echo "==> pg_restore"
pg_restore --clean --if-exists --no-owner --no-acl -d "${DATABASE_URL}" "${DUMP}" 2>&1 | tail -5 || true

echo "==> Оновлення шляхів до фото"
if [[ -f "${SQL}" ]]; then
    psql "${DATABASE_URL}" -f "${SQL}"
else
    echo "ПОМИЛКА: ${SQL} не знайдено!" >&2
    exit 1
fi

echo "==> migrate"
cd /var/www/bookshop
source .venv/bin/activate
python manage.py migrate --noinput

systemctl restart bookshop
echo "==> БД відновлена, Gunicorn перезапущено"
