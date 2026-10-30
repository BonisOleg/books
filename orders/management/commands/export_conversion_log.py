"""Експорт OfflineConversionLog у CSV (без відкритих контактів)."""

from __future__ import annotations

import csv
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from orders.models import OfflineConversionLog


class Command(BaseCommand):
    help = 'Експортує OfflineConversionLog у CSV.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--out',
            required=True,
            help='Шлях до CSV-файлу.',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Лише записи за останні N днів (за created_at).',
        )

    def handle(self, *args, **options):
        out_path = options['out']
        days = options.get('days')
        qs = OfflineConversionLog.objects.all().order_by('-created_at')
        if days is not None:
            if days <= 0:
                raise CommandError('--days має бути додатним числом')
            since = timezone.now() - timedelta(days=days)
            qs = qs.filter(created_at__gte=since)

        fieldnames = [
            'keycrm_order_id',
            'status',
            'order_date',
            'order_status',
            'amount',
            'utm_campaign',
            'has_gclid',
            'has_contact',
            'uploaded_at',
            'error',
            'created_at',
        ]
        count = 0
        try:
            with open(out_path, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in qs.iterator():
                    writer.writerow({
                        'keycrm_order_id': row.keycrm_order_id,
                        'status': row.status,
                        'order_date': row.order_date.isoformat() if row.order_date else '',
                        'order_status': row.order_status,
                        'amount': row.amount if row.amount is not None else '',
                        'utm_campaign': row.utm_campaign,
                        'has_gclid': int(bool(row.has_gclid)),
                        'has_contact': int(bool(row.has_contact)),
                        'uploaded_at': (
                            row.uploaded_at.isoformat() if row.uploaded_at else ''
                        ),
                        'error': (row.error or '')[:500],
                        'created_at': row.created_at.isoformat() if row.created_at else '',
                    })
                    count += 1
        except OSError as exc:
            raise CommandError(f'Не вдалося записати CSV: {exc}') from exc

        self.stdout.write(f'Записано {count} рядків у {out_path}')
