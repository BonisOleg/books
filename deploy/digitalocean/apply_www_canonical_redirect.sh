#!/usr/bin/env bash
# Inject www → ofion.com.ua 301 into live nginx site (Certbot-safe).
# Run as root on the Droplet from /var/www/bookshop (or set APP_DIR).
set -o errexit
set -o pipefail
set -o nounset

APP_DIR="${APP_DIR:-/var/www/bookshop}"
SRC="${APP_DIR}/deploy/digitalocean"
SNIPPET_SRC="${SRC}/nginx-www-to-apex.conf"
SNIPPET_DST="/etc/nginx/snippets/bookshop-www-to-apex.conf"

if [[ ! -f "${SNIPPET_SRC}" ]]; then
  echo "Missing ${SNIPPET_SRC}" >&2
  exit 1
fi

echo "==> install www→apex snippet"
mkdir -p /etc/nginx/snippets
install -m 644 "${SNIPPET_SRC}" "${SNIPPET_DST}"

echo "==> inject include into site server blocks (if missing)"
python3 - <<'PY'
from pathlib import Path
import re
import sys

candidates = [
    Path("/etc/nginx/sites-available/ofion"),
    Path("/etc/nginx/sites-available/bookshop"),
    Path("/etc/nginx/sites-available/default"),
]
site = next((p for p in candidates if p.exists()), None)
if site is None:
    enabled = Path("/etc/nginx/sites-enabled")
    for p in sorted(enabled.glob("*")):
        if p.is_file() or p.is_symlink():
            site = p.resolve()
            break
if site is None:
    print("No nginx site file found to patch", file=sys.stderr)
    sys.exit(1)

text = site.read_text()
needle = "include /etc/nginx/snippets/bookshop-www-to-apex.conf;"
if needle in text:
    print(f"  already present in {site}")
    sys.exit(0)

# Insert include right after each server_name line that mentions www.ofion.com.ua
# (covers HTTP + HTTPS Certbot blocks without wiping SSL).
pattern = re.compile(
    r'(^[ \t]*server_name[^\n]*www\.ofion\.com\.ua[^\n]*;\s*\n)',
    re.M,
)

def repl(match):
    line = match.group(1)
    indent = re.match(r'^([ \t]*)', line).group(1)
    return f"{line}{indent}{needle}\n"

new_text, n = pattern.subn(repl, text)
if n == 0:
    # Fallback: after every "server {" open — only if www is somewhere in file
    if "www.ofion.com.ua" not in text:
        print(
            "WARNING: www.ofion.com.ua not found in site config; "
            "add snippet manually",
            file=sys.stderr,
        )
        sys.exit(0)

    pattern2 = re.compile(r'(server\s*\{[ \t]*\n)')

    def repl2(match):
        return f"{match.group(1)}    {needle}\n"

    new_text, n = pattern2.subn(repl2, text)
    if n == 0:
        print(f"WARNING: could not inject into {site}", file=sys.stderr)
        sys.exit(0)

backup = Path(str(site) + ".bak-www-apex")
backup.write_text(text)
site.write_text(new_text)
print(f"  patched {site} ({n} insert(s)); backup {backup}")
PY

echo "==> nginx -t"
nginx -t
systemctl reload nginx
echo "    nginx reloaded"
echo "==> Done. Test: curl -sI https://www.ofion.com.ua/ | grep -i location"
