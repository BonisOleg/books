#!/usr/bin/env bash
# Одноразове налаштування Ubuntu Droplet для OFION bookshop.
# Запуск на сервері під root: bash deploy/digitalocean/setup_server.sh
set -o errexit
set -o pipefail
set -o nounset

APP_DIR=/var/www/bookshop
DB_NAME=bookshop
DB_USER=bookshop

echo "==> Оновлення системи"
apt-get update
apt-get upgrade -y

echo "==> Пакети"
apt-get install -y python3 python3-venv python3-pip nginx postgresql postgresql-contrib \
    git curl ufw certbot python3-certbot-nginx

echo "==> Postgres: база та користувач"
DB_PASS=$(openssl rand -base64 24)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
    || sudo -u postgres createuser --createdb "${DB_USER}"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

echo "==> DATABASE_URL для .env:"
echo "postgres://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}"

echo "==> Каталоги"
mkdir -p "${APP_DIR}/media"
chown -R www-data:www-data "${APP_DIR}"

echo "==> Firewall"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo ""
echo "==> Система готова. DATABASE_URL для .env:"
echo "postgres://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}"
echo ""
echo "==> Далі:"
echo "  1. git clone <repo> ${APP_DIR}"
echo "  2. cp deploy/digitalocean/env.production.example ${APP_DIR}/.env"
echo "  3. Заповнити .env (секрети з Render + DATABASE_URL вище)"
echo "  4. cd ${APP_DIR} && bash deploy/digitalocean/deploy.sh"
echo "  5. З Mac: bash deploy/digitalocean/sync_from_local.sh user@IP"
echo "  6. На сервері: bash deploy/digitalocean/restore_database.sh"
echo "  7. certbot --nginx -d ofion.com.ua -d www.ofion.com.ua"
