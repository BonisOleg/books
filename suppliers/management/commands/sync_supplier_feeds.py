"""Синхронізація фідів постачальників. Без --supplier — лише активні."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from suppliers.models import Supplier, SupplierSyncRun
from suppliers.services import sync_supplier


class Command(BaseCommand):
    help = (
        'Оновлює ціни з фідів постачальників. '
        'Без --supplier обробляє всіх активних. --file читає локальний XML замість URL.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Порахувати зміни і записати звіт, не чіпаючи каталог.',
        )
        parser.add_argument(
            '--supplier',
            type=int,
            help='ID постачальника. Без параметра — усі активні.',
        )
        parser.add_argument(
            '--file',
            help='Локальний XML замість URL фіду (для одного або всіх вибраних).',
        )

    def handle(self, *args, **options):
        source = self._source(options['file'])
        suppliers = self._suppliers(options['supplier'])
        if not suppliers:
            self.stdout.write('Немає активних постачальників.')
            return

        failed = False
        for supplier in suppliers:
            run = sync_supplier(supplier, dry_run=options['dry_run'], source=source)
            header = f'=== {supplier.name} (#{supplier.pk}) ==='
            if run.status == SupplierSyncRun.Status.OK:
                self.stdout.write(self.style.SUCCESS(header))
            else:
                self.stdout.write(self.style.ERROR(header))
                failed = True
            self.stdout.write(run.report or '')
            self.stdout.write('')

        if failed:
            raise CommandError('Синхронізація завершилась з помилками.')

    def _source(self, file_path):
        if not file_path:
            return None
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise CommandError(f'Файл фіду не знайдено: {path}')
        return path

    def _suppliers(self, supplier_id):
        if supplier_id is None:
            return list(Supplier.objects.filter(is_active=True).order_by('pk'))
        try:
            return [Supplier.objects.get(pk=supplier_id)]
        except Supplier.DoesNotExist as exc:
            raise CommandError(f'Постачальника з id={supplier_id} не знайдено.') from exc
