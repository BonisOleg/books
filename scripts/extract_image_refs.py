#!/usr/bin/env python3
"""Витягує список усіх посилань на медіафайли (Cloudinary public_id) прямо
з бінарного дампа `pg_dump` (custom format), БЕЗ відновлення дампа в жодну БД.

Навіщо: щоб коректно (а не "на всяк випадок усе підряд") скачати з Cloudinary
лише ті файли, які реально використовуються на сайті — за посиланнями з БД.

Використання:
    python3 scripts/extract_image_refs.py bookshop_dump.pgdump \\
        --pg-restore-bin /opt/homebrew/opt/postgresql@16/bin/pg_restore

Версія pg_restore МАЄ збігатися (або бути новішою) за версію сервера, з якого
зроблено дамп — інакше буде помилка "server version mismatch".

Результат:
    image_refs.csv — стовпці: table, column, row_id, public_id
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

# (таблиця, колонка) для кожного ImageField/FileField у проєкті.
TARGET_FIELDS: list[tuple[str, str]] = [
    ('products_category', 'image'),
    ('products_productimage', 'image'),
    ('products_productvideo', 'video_file'),
    ('products_productvideo', 'poster'),
    ('core_sitesettings', 'logo'),
    ('core_sitesettings', 'favicon'),
    ('core_banner', 'image'),
    ('core_banner', 'image_mobile'),
    ('blog_article', 'image'),
    ('blog_news', 'image'),
]

COPY_HEADER_RE = re.compile(r'^COPY\s+(?:public\.)?"?(\w+)"?\s*\(([^)]+)\)\s+FROM stdin;')


def get_table_rows(pg_restore_bin: str, dump_path: Path, table: str) -> list[dict[str, str]]:
    """Читає дані таблиці напряму з .pgdump (--data-only, вивід у stdout)."""
    result = subprocess.run(
        [pg_restore_bin, '--data-only', '-t', table, '-f', '-', str(dump_path)],
        capture_output=True, text=True, check=True,
    )

    columns: list[str] | None = None
    rows: list[dict[str, str]] = []
    in_copy = False

    for line in result.stdout.splitlines():
        if not in_copy:
            match = COPY_HEADER_RE.match(line)
            if match and match.group(1) == table:
                columns = [c.strip().strip('"') for c in match.group(2).split(',')]
                in_copy = True
            continue
        if line == '\\.':
            in_copy = False
            continue
        values = line.split('\t')
        if columns is None or len(values) != len(columns):
            continue
        rows.append(dict(zip(columns, values)))

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('dump_path', help='Шлях до .pgdump (custom-format дамп із pg_dump -Fc)')
    parser.add_argument(
        '--pg-restore-bin', default='pg_restore',
        help='Шлях до pg_restore тієї ж (чи новішої) версії, що і сервер БД',
    )
    parser.add_argument('--output', default='image_refs.csv')
    args = parser.parse_args()

    dump_path = Path(args.dump_path)
    if not dump_path.exists():
        print(f'Файл не знайдено: {dump_path}', file=sys.stderr)
        return 1

    tables_cache: dict[str, list[dict[str, str]]] = {}
    refs: list[dict[str, str]] = []

    for table, column in TARGET_FIELDS:
        if table not in tables_cache:
            print(f'==> Читаю таблицю {table}...')
            try:
                tables_cache[table] = get_table_rows(args.pg_restore_bin, dump_path, table)
            except subprocess.CalledProcessError as exc:
                print(f'    Помилка pg_restore для {table}: {exc.stderr}', file=sys.stderr)
                tables_cache[table] = []
            except FileNotFoundError:
                print(
                    f'Не знайдено виконуваний файл "{args.pg_restore_bin}". '
                    'Вкажіть коректний шлях через --pg-restore-bin.',
                    file=sys.stderr,
                )
                return 1

        rows = tables_cache[table]
        non_empty = 0
        for row in rows:
            value = row.get(column, '')
            if value in ('', '\\N'):
                continue
            non_empty += 1
            refs.append({
                'table': table,
                'column': column,
                'row_id': row.get('id', ''),
                'public_id': value,
            })
        print(f'    {table}.{column}: {non_empty} непорожніх з {len(rows)} рядків')

    with open(args.output, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['table', 'column', 'row_id', 'public_id'])
        writer.writeheader()
        writer.writerows(refs)

    unique_ids = {r['public_id'] for r in refs}
    print(f'\n==> Всього посилань: {len(refs)} (унікальних файлів: {len(unique_ids)})')
    print(f'    Збережено у {Path(args.output).resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
