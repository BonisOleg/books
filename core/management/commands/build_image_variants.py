from django.core.management.base import BaseCommand

from core.imaging.sources import iter_image_files
from core.imaging.variants import field_local_path, process_stored_file


class Command(BaseCommand):
    help = 'Додає WebP-варіанти поруч із наявними зображеннями. Оригінали не змінює.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Лише показати файли, без запису.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        seen = 0
        built = 0
        skipped = 0
        for _obj, field_name, field in iter_image_files():
            seen += 1
            path = field_local_path(field)
            label = getattr(field, 'name', '') or str(path)
            if path is None or not path.is_file():
                skipped += 1
                self.stdout.write(f'skip (немає локального файлу): {label}')
                continue
            if dry_run:
                self.stdout.write(f'would process {field_name}: {path}')
                continue
            meta = process_stored_file(path)
            if meta:
                built += 1
                self.stdout.write(f'ok {path.name} → {len(meta.get("variants") or [])} варіанти')
            else:
                skipped += 1
                self.stdout.write(f'skip {path}')
        self.stdout.write(self.style.SUCCESS(
            f'Зображень: {seen}, зібрано: {built}, пропущено: {skipped}, dry-run: {dry_run}'
        ))
