#!/usr/bin/env bash
# Ідемпотентно ставить щогодинний cron KeyCRM → Google Ads.
# Запуск на Droplet від root: bash deploy/digitalocean/install_conversions_cron.sh
set -o errexit
set -o pipefail
set -o nounset

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Потрібен root: секрети читаються з .env" >&2
  exit 1
fi

APP_DIR="${APP_DIR:-/var/www/bookshop}"
CRON_FILE="/etc/cron.d/bookshop-keycrm-gads"
LOG_FILE="/var/log/bookshop-keycrm-gads.log"
PYTHON="${APP_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Немає ${PYTHON}. Спочатку deploy.sh" >&2
  exit 1
fi

touch "${LOG_FILE}"
chmod 640 "${LOG_FILE}"

cat > "${CRON_FILE}" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Щогодини. manage.py сам читає ${APP_DIR}/.env (load_dotenv).
0 * * * * root cd ${APP_DIR} && ${PYTHON} manage.py upload_keycrm_conversions >> ${LOG_FILE} 2>&1
EOF
chmod 644 "${CRON_FILE}"

echo "==> ${CRON_FILE}"
echo "    Ручний запуск: cd ${APP_DIR} && ${PYTHON} manage.py upload_keycrm_conversions"
