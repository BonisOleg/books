"""Щогодинне вивантаження виконаних замовлень KeyCRM у Google Data Manager."""

from django.core.management.base import BaseCommand, CommandError

import requests

from orders.google_ads_conversions import upload_completed_orders


class Command(BaseCommand):
    help = (
        'Вивантажує замовлення KeyCRM зі статусом «Виконано» '
        'у Google Data Manager (events:ingest).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Надіслати events:ingest з validateOnly=true, без запису логу.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Синонім --validate-only.',
        )
        parser.add_argument(
            '--order-ids',
            default='',
            help=(
                'ID замовлень KeyCRM через кому. Без вікна lookback; '
                'уже вивантажені пропускаються, невдалі надсилаються знову '
                'без ліміту спроб.'
            ),
        )

    def handle(self, *args, **options):
        flagged = options['validate_only'] or options['dry_run']
        validate_only = True if flagged else None
        raw_ids = str(options.get('order_ids') or '').strip()
        order_ids = _parse_order_ids(raw_ids) if raw_ids else None
        try:
            summary = upload_completed_orders(
                validate_only=validate_only,
                order_ids=order_ids,
            )
        except requests.RequestException as exc:
            raise CommandError(f'Вивантаження не вдалося: {exc}') from exc

        if summary.get('validate_only'):
            self.stdout.write(
                'Режим перевірки: validateOnly, лог конверсій не змінюється.'
            )
        if order_ids is not None:
            shown = ','.join(str(item) for item in order_ids)
            self.stdout.write(f'ID: {shown}')

        if summary['not_configured']:
            self.stdout.write(self.style.WARNING(summary['message']))
            return

        self.stdout.write(
            'Отримано: {fetched}, повторів: {retried}, вивантажено: {uploaded}, '
            'пропущено: {skipped}, помилки: {failed}, невалідні: {invalid}'.format(**summary)
        )


def _parse_order_ids(raw):
    order_ids = []
    seen = set()
    for part in str(raw).split(','):
        text = part.strip()
        if not text:
            continue
        if not text.isdigit():
            raise CommandError(f'Некоректний ID замовлення: {text}')
        value = int(text)
        if value <= 0:
            raise CommandError(f'Некоректний ID замовлення: {text}')
        if value in seen:
            continue
        seen.add(value)
        order_ids.append(value)
    if not order_ids:
        raise CommandError('Параметр --order-ids не містить ID.')
    return order_ids
