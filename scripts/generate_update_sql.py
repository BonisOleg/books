#!/usr/bin/env python3
"""Генерує SQL з UPDATE-запитами, які приводять шляхи до фото в БД у
відповідність до файлів, підготовлених download_cloudinary_media.py
(без префікса `media/`, з розширенням).

Виконати цей SQL потрібно ОДИН РАЗ на новій базі (DigitalOcean), одразу
після відновлення дампа (`pg_restore`) і ПЕРЕД тим, як сайт почне
використовувати FileSystemStorage — інакше шляхи в БД не збігатимуться
з реальними файлами на диску.

Використання:
    python3 scripts/generate_update_sql.py image_refs.csv cloudinary_export/path_mapping.csv

Результат:
    update_image_paths.sql — застосувати так:
        psql "$NEW_DATABASE_URL" -f update_image_paths.sql
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('refs_csv', help='Результат extract_image_refs.py')
    parser.add_argument('mapping_csv', help='path_mapping.csv з download_cloudinary_media.py')
    parser.add_argument('--output', default='update_image_paths.sql')
    args = parser.parse_args()

    mapping: dict[str, str] = {}
    with open(args.mapping_csv, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            if row.get('status') == 'ok' and row.get('new_path'):
                mapping[row['old_public_id']] = row['new_path']

    statements: list[str] = []
    skipped: list[str] = []

    with open(args.refs_csv, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            new_path = mapping.get(row['public_id'])
            if not new_path:
                skipped.append(f"{row['table']}.{row['column']} (id={row['row_id']}, {row['public_id']})")
                continue
            statements.append(
                f"UPDATE {row['table']} SET {row['column']} = {sql_quote(new_path)} "
                f"WHERE id = {row['row_id']};"
            )

    output_path = Path(args.output)
    header = (
        '-- Автоматично згенеровано generate_update_sql.py\n'
        '-- Приводить шляхи до фото в БД у відповідність до файлів на диску (без media/, з розширенням).\n'
        f'-- Всього запитів: {len(statements)}\n\n'
    )
    output_path.write_text(header + '\n'.join(statements) + '\n', encoding='utf-8')

    print(f'==> Згенеровано {len(statements)} UPDATE-запитів у {output_path.resolve()}')
    if skipped:
        print(f'\n    Пропущено {len(skipped)} посилань (немає успішно скачаного файлу):')
        for item in skipped[:20]:
            print(f'      - {item}')
        if len(skipped) > 20:
            print(f'      ... і ще {len(skipped) - 20}')
        print('    Ці фото недоступні на Cloudinary — потрібно перезалити вручну після переносу.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
