"""Відбір замовлень і лог спроб для Google Data Manager."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone as dj_timezone

from orders.google_ads_conversions1 import (
    build_event,
    order_id_of,
    source_event_moment,
    _as_int,
)
from orders.models import OfflineConversionLog

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ATTEMPTS = 48
_DEFAULT_RETRY_LIMIT = 100
CLICK_WINDOW_DAYS = 90


def max_retry_attempts() -> int:
    return _positive_setting('KEYCRM_MAX_RETRY_ATTEMPTS', _DEFAULT_MAX_ATTEMPTS)


def retry_fetch_limit() -> int:
    return _positive_setting('KEYCRM_RETRY_FETCH_LIMIT', _DEFAULT_RETRY_LIMIT)


def _positive_setting(name, default) -> int:
    raw = getattr(settings, name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def select_pending(orders, now, *, ignore_attempt_cap=False, require_completed=False):
    skipped = 0
    rows = []
    for order in orders:
        order_id = order_id_of(order)
        if order_id is None:
            skipped += 1
            continue
        rows.append((order_id, order))

    ids = [order_id for order_id, _order in rows]
    uploaded = _logged_ids(ids, status=OfflineConversionLog.STATUS_UPLOADED)
    capped = set()
    if not ignore_attempt_cap:
        capped = _logged_ids(
            ids,
            status=OfflineConversionLog.STATUS_FAILED,
            attempts__gte=max_retry_attempts(),
        )

    pending = []
    for order_id, order in rows:
        if order_id in uploaded:
            skipped += 1
            continue
        if order_id in capped:
            logger.info('Пропуск повтору keycrm_order_id=%s: вичерпано спроби', order_id)
            skipped += 1
            continue
        if require_completed and not order_is_completed(order):
            skipped += 1
            continue
        event = build_event(order, now=now)
        if event is None:
            skipped += 1
            continue
        pending.append((order_id, event))
    return pending, skipped


def _logged_ids(ids, **filters):
    if not ids:
        return set()
    return set(
        OfflineConversionLog.objects.filter(keycrm_order_id__in=ids, **filters)
        .values_list('keycrm_order_id', flat=True)
    )


def failed_retry_ids(exclude_ids) -> list[int]:
    qs = OfflineConversionLog.objects.filter(
        status=OfflineConversionLog.STATUS_FAILED,
        attempts__lt=max_retry_attempts(),
    )
    if exclude_ids:
        qs = qs.exclude(keycrm_order_id__in=list(exclude_ids))
    return list(
        qs.order_by(F('last_attempt_at').asc(nulls_first=True), 'id')
        .values_list('keycrm_order_id', flat=True)[:retry_fetch_limit()]
    )


def order_is_completed(order) -> bool:
    if not isinstance(order, dict):
        return False
    expected = _as_int(getattr(settings, 'KEYCRM_COMPLETED_STATUS_ID', 12))
    if expected is None:
        expected = 12
    return _status_id(order) == expected


def _status_id(order):
    value = order.get('status_id')
    if value in (None, ''):
        status = order.get('status')
        if isinstance(status, dict):
            value = status.get('id')
    return _as_int(value)


def retry_eligible(order, now) -> bool:
    if not order_is_completed(order):
        return False
    moment = source_event_moment(order)
    if moment is None:
        return False
    return moment >= now - timedelta(days=CLICK_WINDOW_DAYS)


def mark_conversion_logs(order_ids, status, error):
    uploaded = status == OfflineConversionLog.STATUS_UPLOADED
    now = dj_timezone.now()
    error_text = '' if uploaded else (error or '')[:2000]
    for order_id in order_ids:
        log = OfflineConversionLog.objects.filter(keycrm_order_id=order_id).first()
        if log is None:
            OfflineConversionLog.objects.create(
                keycrm_order_id=order_id,
                status=status,
                uploaded_at=now if uploaded else None,
                error=error_text,
                attempts=0 if uploaded else 1,
                last_attempt_at=None if uploaded else now,
            )
            continue
        if uploaded:
            log.status = status
            log.error = ''
            log.uploaded_at = now
            log.save(update_fields=['status', 'error', 'uploaded_at'])
            continue
        OfflineConversionLog.objects.filter(pk=log.pk).update(
            status=status,
            error=error_text,
            uploaded_at=None,
            attempts=F('attempts') + 1,
            last_attempt_at=now,
        )
