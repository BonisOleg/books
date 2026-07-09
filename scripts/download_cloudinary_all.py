#!/usr/bin/env python3
"""[Запасний варіант] Скачує ВСІ файли (image/video/raw) з Cloudinary-акаунту
через Admin API, без прив'язки до БД.

Використовуйте це лише якщо DB-driven пайплайн (extract_image_refs.py →
download_cloudinary_media.py) з якоїсь причини не підходить — наприклад,
потрібно забрати взагалі все, що лежить в акаунті, включно з файлами-сиротами,
на які вже нема посилань у БД.

Використання:
    Значення CLOUDINARY_URL читається автоматично з файлу .env у корені
    проєкту (не потрібно робити export вручну).

    python3 scripts/download_cloudinary_all.py

Результат:
    ./cloudinary_export_all/<public_id>.<ext>
    ./cloudinary_export_all/manifest.json  — повний список усіх ресурсів + статус

Реальні API_KEY / API_SECRET / CLOUD_NAME беріть у Render Dashboard →
сервіс bookshop → Environment (там, де вони задані для продакшену).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # має виконатись ДО import cloudinary, інакше CLOUDINARY_URL не підхопиться

import cloudinary
import cloudinary.api
import requests

RESOURCE_TYPES = ('image', 'video', 'raw')
MAX_RESULTS_PER_PAGE = 500
RETRY_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 3


def iter_all_resources(resource_type: str):
    cursor = None
    while True:
        params = {
            'resource_type': resource_type,
            'type': 'upload',
            'max_results': MAX_RESULTS_PER_PAGE,
        }
        if cursor:
            params['next_cursor'] = cursor

        response = cloudinary.api.resources(**params)
        for resource in response.get('resources', []):
            yield resource

        cursor = response.get('next_cursor')
        if not cursor:
            break


def download_one(resource: dict, output_dir: Path) -> dict:
    public_id = resource['public_id']
    fmt = resource.get('format', '')
    secure_url = resource['secure_url']
    resource_type = resource.get('resource_type', 'image')

    relative_path = f'{public_id}.{fmt}' if fmt else public_id
    local_path = output_dir / relative_path
    local_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        'public_id': public_id,
        'resource_type': resource_type,
        'format': fmt,
        'bytes': resource.get('bytes'),
        'secure_url': secure_url,
        'local_path': str(local_path.relative_to(output_dir)),
        'status': 'pending',
        'error': None,
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with requests.get(secure_url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(local_path, 'wb') as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        fh.write(chunk)
            entry['status'] = 'ok'
            return entry
        except requests.RequestException as exc:
            entry['error'] = str(exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_SLEEP_SECONDS)
            else:
                entry['status'] = 'failed'
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='cloudinary_export_all')
    parser.add_argument('--resource-types', default=','.join(RESOURCE_TYPES))
    args = parser.parse_args()

    if not cloudinary.config().cloud_name:
        print(
            'Помилка: не задано CLOUDINARY_URL (або CLOUDINARY_CLOUD_NAME/'
            'API_KEY/API_SECRET) в оточенні.',
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    types_to_process = [t.strip() for t in args.resource_types.split(',') if t.strip()]

    for resource_type in types_to_process:
        print(f'==> Отримую список ресурсів типу "{resource_type}"...')
        try:
            resources = list(iter_all_resources(resource_type))
        except cloudinary.exceptions.Error as exc:
            print(f'    Не вдалося отримати список ({resource_type}): {exc}', file=sys.stderr)
            continue

        print(f'    Знайдено {len(resources)} файлів. Завантажую...')
        for i, resource in enumerate(resources, start=1):
            entry = download_one(resource, output_dir)
            manifest.append(entry)
            mark = 'OK ' if entry['status'] == 'ok' else 'ERR'
            print(f'    [{mark}] {i}/{len(resources)} {entry["public_id"]}')

    manifest_path = output_dir / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    total = len(manifest)
    ok = sum(1 for m in manifest if m['status'] == 'ok')
    failed = total - ok

    print('\n==> Готово.')
    print(f'    Всього ресурсів: {total}')
    print(f'    Успішно:         {ok}')
    print(f'    З помилками:     {failed}')
    print(f'    Файли:           {output_dir.resolve()}')
    print(f'    Маніфест:        {manifest_path.resolve()}')

    return 0 if failed == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
