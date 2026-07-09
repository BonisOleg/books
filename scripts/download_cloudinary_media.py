#!/usr/bin/env python3
"""Скачує з Cloudinary РІВНО ті файли, на які є посилання в БД (список з
image_refs.csv — результат scripts/extract_image_refs.py), і готує їх у
"чистому" вигляді для DigitalOcean: без префікса `media/` (який додавав
django-cloudinary-storage) і з правильним розширенням файлу.

Навіщо саме так: у БД шлях зберігається без розширення (наприклад
"media/products/11-1_xuih2f") — так працює django-cloudinary-storage. Це не
годиться для звичайного FileSystemStorage (сервер не знатиме Content-Type
файлу без розширення). Тому цей скрипт:
    1. качає оригінал з Cloudinary (дізнавшись реальний формат/розширення),
    2. зберігає його вже БЕЗ "media/" і З розширенням,
    3. пише path_mapping.csv (старий public_id -> новий шлях), який потім
       використовує scripts/generate_update_sql.py, щоб оновити БД так,
       щоб нові шляхи в БД точно збігались з файлами на диску.

Rate limit Cloudinary Admin API (зазвичай 500 запитів/годину): скрипт сам
чекає до моменту відновлення ліміту (парсить час із повідомлення помилки
"Try again on ... UTC") і продовжує — НЕ позначає такі файли як "не знайдено".
На великих каталогах (2000+ фото) це може зайняти кілька годин — скрипт
безпечно перезапускати: вже завантажені файли (status=ok у path_mapping.csv)
пропускаються повторно.

Використання:
    Значення CLOUDINARY_URL / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET /
    CLOUDINARY_CLOUD_NAME читаються автоматично з файлу .env у корені проєкту
    (не потрібно робити export вручну).

    python3 scripts/download_cloudinary_media.py image_refs.csv

Результат:
    cloudinary_export/<шлях без media/>.<ext>   — файли, готові лягти в MEDIA_ROOT
    cloudinary_export/path_mapping.csv          — old_public_id,new_path,status,error
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # має виконатись ДО import cloudinary, інакше CLOUDINARY_URL не підхопиться

import cloudinary
import cloudinary.api
import cloudinary.exceptions
import requests

RETRY_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 3
RESOURCE_TYPES_TO_TRY = ('image', 'video', 'raw')
MEDIA_PREFIX = 'media/'
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 300
SAVE_EVERY = 20

RATE_LIMIT_RESET_RE = re.compile(r'Try again on (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC')
MAPPING_FIELDS = ['old_public_id', 'new_path', 'status', 'error']


def strip_media_prefix(public_id: str) -> str:
    return public_id[len(MEDIA_PREFIX):] if public_id.startswith(MEDIA_PREFIX) else public_id


def parse_rate_limit_wait(message: str) -> int:
    match = RATE_LIMIT_RESET_RE.search(message)
    if not match:
        return DEFAULT_RATE_LIMIT_WAIT_SECONDS
    reset_at = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    wait = (reset_at - datetime.now(timezone.utc)).total_seconds() + 5
    return max(int(wait), 1)


def find_resource(public_id: str) -> dict | None:
    for resource_type in RESOURCE_TYPES_TO_TRY:
        while True:
            try:
                return cloudinary.api.resource(public_id, resource_type=resource_type)
            except cloudinary.exceptions.NotFound:
                break
            except cloudinary.exceptions.RateLimited as exc:
                wait_seconds = parse_rate_limit_wait(str(exc))
                reset_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
                print(
                    f'    [{reset_time} UTC] Досягнуто лімін Cloudinary Admin API. '
                    f'Чекаю {wait_seconds}с до відновлення...',
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)
                continue
            except cloudinary.exceptions.Error as exc:
                print(f'    Помилка API для {public_id} ({resource_type}): {exc}', file=sys.stderr)
                break
    return None


def download_one(resource: dict, output_dir: Path, new_relative: str) -> dict:
    secure_url = resource['secure_url']
    local_path = output_dir / new_relative
    local_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with requests.get(secure_url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(local_path, 'wb') as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        fh.write(chunk)
            return {'status': 'ok', 'error': None}
        except requests.RequestException as exc:
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_SLEEP_SECONDS)
            else:
                return {'status': 'failed', 'error': str(exc)}
    return {'status': 'failed', 'error': 'unknown'}


def load_existing_mapping(mapping_path: Path) -> dict[str, dict[str, str]]:
    if not mapping_path.exists():
        return {}
    with open(mapping_path, newline='', encoding='utf-8') as fh:
        return {row['old_public_id']: row for row in csv.DictReader(fh) if row.get('old_public_id')}


def write_mapping(mapping_path: Path, mapping: dict[str, dict[str, str]]) -> None:
    tmp_path = mapping_path.with_suffix('.tmp')
    with open(tmp_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=MAPPING_FIELDS)
        writer.writeheader()
        for old_public_id, row in mapping.items():
            writer.writerow({field: row.get(field, '') for field in MAPPING_FIELDS})
    tmp_path.replace(mapping_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('refs_csv', help='CSV зі стовпцем public_id (результат extract_image_refs.py)')
    parser.add_argument('--output-dir', default='cloudinary_export')
    args = parser.parse_args()

    if not cloudinary.config().cloud_name:
        print(
            'Помилка: не задано CLOUDINARY_URL (або CLOUDINARY_CLOUD_NAME/'
            'API_KEY/API_SECRET) в оточенні.',
            file=sys.stderr,
        )
        return 1

    refs_path = Path(args.refs_csv)
    if not refs_path.exists():
        print(f'Файл не знайдено: {refs_path}', file=sys.stderr)
        return 1

    with open(refs_path, newline='', encoding='utf-8') as fh:
        public_ids = sorted({row['public_id'] for row in csv.DictReader(fh) if row.get('public_id')})

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping_path = output_dir / 'path_mapping.csv'

    mapping = load_existing_mapping(mapping_path)
    already_ok = sum(1 for row in mapping.values() if row.get('status') == 'ok')

    print(f'==> Унікальних файлів у списку: {len(public_ids)}')
    if already_ok:
        print(f'    Вже завантажено раніше (буде пропущено): {already_ok}')

    pending_since_save = 0
    for i, public_id in enumerate(public_ids, start=1):
        prev = mapping.get(public_id)
        if prev and prev.get('status') == 'ok' and prev.get('new_path'):
            if (output_dir / prev['new_path']).exists():
                print(f'[{i}/{len(public_ids)}] [SKIP] {public_id} (вже завантажено)')
                continue

        resource = find_resource(public_id)
        if resource is None:
            mapping[public_id] = {
                'old_public_id': public_id, 'new_path': '',
                'status': 'not_found', 'error': 'ресурс не знайдено на Cloudinary',
            }
            print(f'[{i}/{len(public_ids)}] [NOT FOUND] {public_id}')
            pending_since_save += 1
        else:
            fmt = resource.get('format', '')
            new_relative = strip_media_prefix(public_id)
            if fmt:
                new_relative = f'{new_relative}.{fmt}'

            result = download_one(resource, output_dir, new_relative)
            mapping[public_id] = {
                'old_public_id': public_id,
                'new_path': new_relative if result['status'] == 'ok' else '',
                'status': result['status'],
                'error': result['error'] or '',
            }
            mark = 'OK ' if result['status'] == 'ok' else 'ERR'
            print(f'[{i}/{len(public_ids)}] [{mark}] {public_id} -> {new_relative}')
            pending_since_save += 1

        if pending_since_save >= SAVE_EVERY:
            write_mapping(mapping_path, mapping)
            pending_since_save = 0

    write_mapping(mapping_path, mapping)

    total = len(mapping)
    ok = sum(1 for m in mapping.values() if m['status'] == 'ok')
    not_found = sum(1 for m in mapping.values() if m['status'] == 'not_found')
    failed = total - ok - not_found

    print('\n==> Готово.')
    print(f'    Всього:                    {total}')
    print(f'    Скачано:                   {ok}')
    print(f'    Не знайдено на Cloudinary: {not_found}')
    print(f'    З помилками (мережа тощо): {failed}')
    print(f'    Файли:                     {output_dir.resolve()}')
    print(f'    Мапінг шляхів:             {mapping_path.resolve()}')

    if not_found or failed:
        print(
            '\n    Не всі файли скачались успішно. Помилки з мережею можна повторити —\n'
            '    запустіть скрипт ще раз (успішно завантажені файли пропускаються автоматично).\n'
            '    "Не знайдено" — фото, яких уже фізично немає на Cloudinary; такі доведеться\n'
            '    перезалити вручну після переносу на DigitalOcean.'
        )

    return 0 if (not_found == 0 and failed == 0) else 2


if __name__ == '__main__':
    raise SystemExit(main())
