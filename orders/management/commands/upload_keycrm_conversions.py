"""Щогодинне вивантаження виконаних замовлень KeyCRM у Google Data Manager."""

from django.core.management.base import BaseCommand

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
            '--days',
            type=int,
            default=None,
            help='Вікно днів (7–14, інакше clamp; default 10).',
        )
        parser.add_argument(
            '--summary',
            action='store_true',
            help='Надіслати щоденний підсумок у Telegram.',
        )

    def handle(self, *args, **options):
        flagged = options['validate_only'] or options['dry_run']
        validate_only = True if flagged else None
        summary = upload_completed_orders(
            validate_only=validate_only,
            days=options.get('days'),
            send_summary=bool(options.get('summary')),
        )

        if summary.get('validate_only'):
            self.stdout.write(
                'Режим перевірки: validateOnly, лог конверсій не змінюється.'
            )

        if summary['not_configured']:
            self.stdout.write(self.style.WARNING(summary['message']))
            return

        self.stdout.write(
            'Отримано: {fetched}, вивантажено: {uploaded}, '
            'пропущено: {skipped}, помилки: {failed}, '
            'вікно: {lookback_days} дн.'.format(**summary)
        )
        if summary.get('failed'):
            self.stdout.write(self.style.WARNING(
                'Були помилки імпорту; деталі в логах / Telegram.'
            ))
