"""Щогодинне вивантаження виконаних замовлень KeyCRM у Google Ads."""

from django.core.management.base import BaseCommand, CommandError

import requests

from orders.google_ads_conversions import upload_completed_orders


class Command(BaseCommand):
    help = (
        'Вивантажує замовлення KeyCRM зі статусом «Виконано» '
        'у Google Ads як офлайн-конверсії.'
    )

    def handle(self, *args, **options):
        try:
            summary = upload_completed_orders()
        except requests.RequestException as exc:
            raise CommandError(f'Вивантаження не вдалося: {exc}') from exc

        if summary['not_configured']:
            self.stdout.write(self.style.WARNING(summary['message']))
            return

        self.stdout.write(
            'Отримано: {fetched}, вивантажено: {uploaded}, '
            'пропущено: {skipped}, помилки: {failed}'.format(**summary)
        )
