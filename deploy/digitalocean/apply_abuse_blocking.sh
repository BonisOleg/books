#!/usr/bin/env bash
# Apply nginx rate limits + fail2ban abuse jail on the Droplet.
# Run as root from /var/www/bookshop (or set APP_DIR).
# Does NOT wipe Certbot SSL server blocks — only injects includes.
set -o errexit
set -o pipefail
set -o nounset

APP_DIR="${APP_DIR:-/var/www/bookshop}"
SRC="${APP_DIR}/deploy/digitalocean"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/ofion}"

if [[ ! -d "${SRC}" ]]; then
  echo "Missing ${SRC}" >&2
  exit 1
fi

echo "==> nginx abuse zones (conf.d)"
install -m 644 "${SRC}/nginx-bookshop-abuse-zones.conf" \
  /etc/nginx/conf.d/bookshop-abuse-zones.conf

echo "==> nginx abuse locations snippet"
mkdir -p /etc/nginx/snippets
install -m 644 "${SRC}/nginx-bookshop-abuse-locations.conf" \
  /etc/nginx/snippets/bookshop-abuse-locations.conf

echo "==> inject include into site server blocks (if missing)"
python3 - <<'PY'
from pathlib import Path
import re
import sys

candidates = [
    Path("/etc/nginx/sites-available/ofion"),
    Path("/etc/nginx/sites-available/ofion"),
    Path("/etc/nginx/sites-available/bookshop"),
    Path("/etc/nginx/sites-available/default"),
]
site = next((p for p in candidates if p.exists()), None)
if site is None:
    # try enabled symlinks
    enabled = Path("/etc/nginx/sites-enabled")
    for p in sorted(enabled.glob("*")):
        if p.is_file() or p.is_symlink():
            site = p.resolve()
            break
if site is None:
    print("No nginx site file found to patch", file=sys.stderr)
    sys.exit(1)

text = site.read_text()
needle = "include /etc/nginx/snippets/bookshop-abuse-locations.conf;"
if needle in text:
    print(f"  already present in {site}")
    sys.exit(0)

pattern = re.compile(r'(^[ \t]*)location\s+/\s*\{', re.M)

def repl(match):
    indent = match.group(1)
    return f"{indent}{needle}\n\n{indent}location / {{"

new_text, n = pattern.subn(repl, text)
if n == 0:
    print(f"WARNING: no 'location /' found in {site}; add include manually", file=sys.stderr)
    sys.exit(0)

backup = Path(str(site) + ".bak-abuse")
backup.write_text(text)
site.write_text(new_text)
print(f"  patched {site} ({n} insert(s)); backup {backup}")
PY

# Detect upstream name used on this host and align snippet if needed
UPSTREAM="$(grep -RhoE 'proxy_pass http://[A-Za-z0-9_]+;' /etc/nginx/sites-enabled/ 2>/dev/null | head -1 | sed -E 's/proxy_pass http:\/\/([A-Za-z0-9_]+);/\1/' || true)"
if [[ -n "${UPSTREAM}" ]]; then
  echo "==> aligning snippet upstream -> ${UPSTREAM}"
  sed -i "s/bookshop_gunicorn/${UPSTREAM}/g" \
    /etc/nginx/snippets/bookshop-abuse-locations.conf
  sed -i "s/bookshop_gunicorn/${UPSTREAM}/g" \
    /etc/nginx/snippets/bookshop-abuse-locations.conf
fi

echo "==> nginx -t"
nginx -t
systemctl reload nginx
echo "    nginx reloaded"

echo "==> fail2ban"
export DEBIAN_FRONTEND=noninteractive
if ! command -v fail2ban-client >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq fail2ban
fi
install -m 644 "${SRC}/fail2ban-filter-nginx-limit-req.conf" \
  /etc/fail2ban/filter.d/nginx-limit-req.conf
install -m 644 "${SRC}/fail2ban-jail-bookshop-abuse.local" \
  /etc/fail2ban/jail.d/bookshop-abuse.local
# normalize jail filter name to match installed filter
sed -i 's/^filter = .*/filter = nginx-limit-req/' \
  /etc/fail2ban/jail.d/bookshop-abuse.local
systemctl enable fail2ban
systemctl restart fail2ban
# Після restart сокет /var/run/fail2ban/fail2ban.sock з'являється не миттєво.
# Чекаємо до 15 с; перевірка статусу — інформативна, не має валити деплой.
_f2b_ready=0
for _ in $(seq 1 30); do
  if fail2ban-client ping >/dev/null 2>&1; then
    _f2b_ready=1
    break
  fi
  sleep 0.5
done
if [[ "${_f2b_ready}" == "1" ]]; then
  fail2ban-client status nginx-limit-req 2>/dev/null || fail2ban-client status || true
else
  echo "WARN: fail2ban не відповів за 15 с; перевір: systemctl status fail2ban" >&2
fi

echo "==> Done. Test: burst POST /cart/add/<id>/ should return 429"
