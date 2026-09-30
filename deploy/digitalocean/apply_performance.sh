#!/usr/bin/env bash
# Gzip і HTTP/2 на живому vhost ofion/bookshop.
# Не копіює nginx-ofion.conf поверх Certbot і не чіпає інші сайти.
# Перед записом робить копію. Якщо nginx -t падає — повертає копії і не робить reload.
# Запуск: sudo bash deploy/digitalocean/apply_performance.sh
set -o errexit
set -o pipefail
set -o nounset

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx is not installed; nothing to apply" >&2
  exit 1
fi

BACKUP_DIR="/var/backups/bookshop-nginx-$(date +%Y%m%d%H%M%S)"
mkdir -p "${BACKUP_DIR}"

python3 - "${BACKUP_DIR}" <<'PY'
import sys
from pathlib import Path

backup_dir = Path(sys.argv[1])

GZIP = """
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/css application/javascript text/javascript application/json image/svg+xml text/plain application/xml;
"""

MEDIA_CACHE = '        add_header Cache-Control "public, max-age=2592000, immutable";\n'
STATIC_CACHE = '        add_header Cache-Control "public, max-age=2592000, immutable";\n'

NAMES = ('ofion', 'bookshop')


def site_files():
    found = []
    for root in (Path('/etc/nginx/sites-available'), Path('/etc/nginx/sites-enabled')):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_file() and not path.is_symlink():
                continue
            if path.name.endswith('.bak') or '.bak-' in path.name:
                continue
            if not any(name in path.name for name in NAMES):
                continue
            resolved = path.resolve()
            if resolved.is_file() and resolved not in found:
                found.append(resolved)
    return found


def ensure_gzip(text: str) -> str:
    if 'server {' not in text:
        return text
    head, _, rest = text.partition('server {')
    chunks = rest.split('server {')
    rebuilt = []
    for chunk in chunks:
        if 'gzip on;' not in chunk:
            nl = chunk.find('\n')
            if nl != -1:
                chunk = chunk[:nl + 1] + GZIP + chunk[nl + 1:]
        rebuilt.append(chunk)
    return head + 'server {' + 'server {'.join(rebuilt)


def ensure_http2(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if (
            stripped.startswith('listen')
            and '443' in stripped
            and 'ssl' in stripped
            and 'http2' not in stripped
        ):
            line = line.replace(';', ' http2;', 1)
        lines.append(line)
    return ''.join(lines)


def replace_cache(text: str) -> str:
    text = text.replace(
        'expires 30d;\n        add_header Cache-Control "public, immutable";\n',
        STATIC_CACHE,
    )
    text = text.replace(
        'expires 30d;\n        add_header Cache-Control "public";\n',
        MEDIA_CACHE,
    )
    return text


changed = False
for path in site_files():
    original = path.read_text(encoding='utf-8')
    updated = replace_cache(ensure_http2(ensure_gzip(original)))
    if updated == original:
        print(f'unchanged {path}')
        continue
    backup = backup_dir / (path.name + '.conf')
    backup.write_text(original, encoding='utf-8')
    (backup_dir / (path.name + '.path')).write_text(str(path), encoding='utf-8')
    path.write_text(updated, encoding='utf-8')
    print(f'updated {path}; backup {backup}')
    changed = True

if not changed:
    print('no nginx site changes')
PY

if ! nginx -t; then
  echo "nginx -t failed; restoring backups from ${BACKUP_DIR}" >&2
  python3 - "${BACKUP_DIR}" <<'PY'
import sys
from pathlib import Path
backup_dir = Path(sys.argv[1])
for pointer in backup_dir.glob('*.path'):
    target = Path(pointer.read_text(encoding='utf-8').strip())
    source = backup_dir / (pointer.name[:-len('.path')] + '.conf')
    if source.is_file():
        target.write_text(source.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'restored {target}')
PY
  nginx -t
  exit 1
fi

if [[ "${RELOAD:-1}" == "1" ]]; then
  systemctl reload nginx
  echo "nginx reloaded; backups left in ${BACKUP_DIR}"
fi
