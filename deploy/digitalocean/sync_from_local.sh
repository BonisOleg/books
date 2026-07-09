#!/usr/bin/env bash
# Запуск з Mac (з кореня проєкту books):
#   bash deploy/digitalocean/sync_from_local.sh root@DROPLET_IP
set -o errexit
set -o pipefail
set -o nounset

SERVER="${1:?Вкажіть сервер: bash sync_from_local.sh user@ip}"

for f in bookshop_dump.pgdump update_image_paths.sql cloudinary_export; do
    [[ -e "${f}" ]] || { echo "Немає ${f} — спочатку зробіть дамп і вигрузку фото." >&2; exit 1; }
done

echo "==> Фото (~694 MB) → /var/www/bookshop/media/"
rsync -avz --progress cloudinary_export/ "${SERVER}:/var/www/bookshop/media/"

echo "==> Дамп БД + SQL → /tmp/migration/"
ssh "${SERVER}" 'mkdir -p /tmp/migration'
rsync -avz bookshop_dump.pgdump update_image_paths.sql "${SERVER}:/tmp/migration/"

echo "==> Права"
ssh "${SERVER}" 'chown -R www-data:www-data /var/www/bookshop/media'

echo "==> Готово. На сервері: bash deploy/digitalocean/restore_database.sh"
