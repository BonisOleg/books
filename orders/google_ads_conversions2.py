"""Відбір замовлень і лог спроб для Google Data Manager."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone as dj_timezone

from orders.google_ads_conversions1 import (
    build_event,
    click_ids,
    has_contact,
    order_amount,
    order_id_of,
    order_status_label,
    order_time,
    source_event_moment,
    utm_campaign_of,
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
    orders_by_id = {}
    for order in orders:
        order_id = order_id_of(order)
        if order_id is None:
            skipped += 1
            continue
        rows.append((order_id, order))
        orders_by_id[order_id] = order

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
        try:
            event = build_event(order, now=now)
        except Exception:
            logger.exception(
                'Data Manager: помилка побудови події order_id=%s',
                order_id,
            )
            skipped += 1
            continue
        if event is None:
            skipped += 1
            continue
        pending.append((order_id, event))
    return pending, skipped, orders_by_id


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
    status_id = _status_id(order)
    if status_id is None:
        return False
    return status_id in _completed_status_ids()


def _completed_status_ids() -> set[int]:
    raw = getattr(settings, 'KEYCRM_COMPLETED_STATUS_IDS', None)
    if raw in (None, ''):
        expected = _as_int(getattr(settings, 'KEYCRM_COMPLETED_STATUS_ID', 12))
        return {expected if expected is not None else 12}
    if isinstance(raw, (list, tuple)):
        parts = [str(item) for item in raw]
    else:
        parts = str(raw).split(',')
    ids = set()
    for part in parts:
        value = _as_int(part.strip())
        if value is not None and value > 0:
            ids.add(value)
    if ids:
        return ids
    expected = _as_int(getattr(settings, 'KEYCRM_COMPLETED_STATUS_ID', 12))
    return {expected if expected is not None else 12}


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


def mark_conversion_logs(order_ids, status, error, *, orders_by_id=None):
    uploaded = status == OfflineConversionLog.STATUS_UPLOADED
    now = dj_timezone.now()
    error_text = '' if uploaded else (error or '')[:2000]
    orders_by_id = orders_by_id or {}
    for order_id in order_ids:
        meta = _log_meta(orders_by_id.get(order_id))
        log = OfflineConversionLog.objects.filter(keycrm_order_id=order_id).first()
        if log is None:
            OfflineConversionLog.objects.create(
                keycrm_order_id=order_id,
                status=status,
                uploaded_at=now if uploaded else None,
                error=error_text,
                attempts=0 if uploaded else 1,
                last_attempt_at=None if uploaded else now,
                **meta,
            )
            continue
        if uploaded:
            for key, value in meta.items():
                setattr(log, key, value)
            log.status = status
            log.error = ''
            log.uploaded_at = now
            log.save(update_fields=[
                'status', 'error', 'uploaded_at',
                *meta.keys(),
            ])
            continue
        updates = {
            'status': status,
            'error': error_text,
            'uploaded_at': None,
            'attempts': F('attempts') + 1,
            'last_attempt_at': now,
            **meta,
        }
        OfflineConversionLog.objects.filter(pk=log.pk).update(**updates)


def _log_meta(order) -> dict:
    if order is None:
        return {}
    clicks = click_ids(order)
    amount = order_amount(order)
    return {
        'order_date': order_time(order),
        'order_status': order_status_label(order),
        'amount': amount,
        'utm_campaign': utm_campaign_of(order),
        'has_gclid': bool(clicks),
        'has_contact': has_contact(order),
    }
