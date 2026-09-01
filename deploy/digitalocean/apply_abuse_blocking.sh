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
if [[ -f "${NGINX_SITE}" ]]; then
  python3 - <<'PY'
from pathlib import Path
import re
import sys

site = Path("/etc/nginx/sites-available/ofion")
if not site.exists():
    # fallback common names
    for candidate in (
        Path("/etc/nginx/sites-available/ofion"),
        Path("/etc/nginx/sites-available/default"),
        Path("/etc/nginx/sites-available/bookshop"),
    ):
        if candidate.exists():
            site = candidate
            break
    else:
        print("No nginx site file found to patch", file=sys.stderr)
        sys.exit(1)

text = site.read_text()
needle = "include /etc/nginx/snippets/bookshop-abuse-locations.conf;"
if needle in text:
    print(f"  already present in {site}")
    sys.exit(0)

# Insert include immediately before each top-level "location / {" inside server blocks.
pattern = re.compile(r'(^[ \t]*)location\s+/\s*\{', re.M)

def repl(match):
    indent = match.group(1)
    return f"{indent}{needle}\n\n{indent}location / {{"

new_text, n = pattern.subn(repl, text)
if n == 0:
    print(f"WARNING: no 'location /' found in {site}; add include manually", file=sys.stderr)
    sys.exit(0)

backup = site.with_suffix(site.suffix + ".bak-abuse")
backup.write_text(text)
site.write_text(new_text)
print(f"  patched {site} ({n} insert(s)); backup {backup}")
PY
else
  echo "WARNING: ${NGINX_SITE} missing — zones installed, locations not wired" >&2
fi

# Detect upstream name used on this host and align snippet if needed
if [[ -f "${NGINX_SITE}" ]] || ls /etc/nginx/sites-enabled/* >/dev/null 2>&1; then
  UPSTREAM="$(grep -RhoE 'proxy_pass http://[A-Za-z0-9_]+' /etc/nginx/sites-enabled/ 2>/dev/null | head -1 | sed 's|proxy_pass http://||' || true)"
  if [[ -n "${UPSTREAM}" && "${UPSTREAM}" != "bookshop_gunicorn" ]]; then
    echo "==> aligning snippet upstream -> ${UPSTREAM}"
    sed -i "s/bookshop_gunicorn/${UPSTREAM}/g" \
      /etc/nginx/snippets/bookshop-abuse-locations.conf
  fi
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
systemctl enable fail2ban
systemctl restart fail2ban
fail2ban-client status nginx-limit-req || fail2ban-client status

echo "==> Done. Test: burst POST /cart/add/<id>/ should return 429"
