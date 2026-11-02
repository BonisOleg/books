"""Синхронізація цін постачальника. Порожній або зламаний фід нічого не пише в каталог."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from products.models import Product

from suppliers.constants import MAX_FEED_ITEMS
from suppliers.exceptions import FeedParseError, FeedSyncError
from suppliers.fetch import open_feed
from suppliers.matching import plan_from_items
from suppliers.models import SupplierSyncRun
from suppliers.parsers.registry import get_parser
from suppliers.plans import SyncPlan
from suppliers.report import render_report

logger = logging.getLogger(__name__)

_BULK = 500


def sync_supplier(supplier, dry_run=False, source=None) -> SupplierSyncRun:
    run = SupplierSyncRun.objects.create(
        supplier=supplier,
        dry_run=bool(dry_run),
        status=SupplierSyncRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    try:
        plan = _collect_plan(supplier, source)
    except FeedSyncError as exc:
        logger.warning('Фід постачальника %s відхилено: %s', supplier.pk, exc)
        return _fail(run, str(exc), _plan_from_error(exc))
    except Exception:
        logger.exception('Неочікувана помилка синхронізації постачальника %s', supplier.pk)
        return _fail(run, 'Неочікувана помилка синхронізації.')

    if plan.items_in_feed == 0:
        return _fail(run, 'У фіді немає жодного валідного товару.', plan)

    if not run.dry_run:
        try:
            apply_plan(plan)
        except Exception:
            logger.exception('Запис синхронізації постачальника %s відкочено', supplier.pk)
            return _fail(run, 'Не вдалося записати зміни. Каталог не змінено.', plan)
    return _save(run, SupplierSyncRun.Status.OK, plan)


def apply_plan(plan: SyncPlan) -> None:
    now = timezone.now()
    with transaction.atomic():
        _update_prices(plan, now)
        _update_stock(plan, now)


def _collect_plan(supplier, source) -> SyncPlan:
    parser = get_parser(supplier.feed_format)
    with open_feed(supplier, source) as stream:
        generator = parser.parse(stream)
        items = []
        error = None
        try:
            for item in generator:
                items.append(item)
                if len(items) > MAX_FEED_ITEMS:
                    raise FeedParseError('У фіді забагато позицій.')
        except FeedParseError as exc:
            error = exc
        finally:
            generator.close()
        if error is not None:
            raise FeedParseError(str(error), details=list(parser.errors)) from error
    return plan_from_items(supplier, items, parser.errors, parser.error_count)


def _update_prices(plan: SyncPlan, now) -> None:
    if not plan.price_changes:
        return
    ids = [change.product_id for change in plan.price_changes]
    by_id = Product.objects.in_bulk(ids)
    updating = []
    for change in plan.price_changes:
        product = by_id.get(change.product_id)
        if product is None:
            continue
        product.price = change.new
        product.updated_at = now
        updating.append(product)
    if updating:
        Product.objects.bulk_update(updating, ['price', 'updated_at'], batch_size=_BULK)


def _update_stock(plan: SyncPlan, now) -> None:
    if not plan.mark_out_ids:
        return
    products = list(
        Product.objects.filter(pk__in=plan.mark_out_ids).exclude(stock_status='out')
    )
    if not products:
        return
    for product in products:
        product.stock_status = 'out'
        product.updated_at = now
    Product.objects.bulk_update(products, ['stock_status', 'updated_at'], batch_size=_BULK)


def _plan_from_error(exc: FeedSyncError) -> SyncPlan:
    details = list(exc.details)
    return SyncPlan(error_messages=details, error_count=len(details))


def _fail(run, reason: str, plan: SyncPlan | None = None) -> SupplierSyncRun:
    if plan is None:
        plan = SyncPlan()
    if reason and reason not in plan.error_messages:
        plan.error_messages.insert(0, reason)
        plan.error_count += 1
    return _save(run, SupplierSyncRun.Status.FAILED, plan)


def _save(run, status: str, plan: SyncPlan) -> SupplierSyncRun:
    text, payload = render_report(plan, status=status, dry_run=run.dry_run)
    applied = status == SupplierSyncRun.Status.OK
    run.status = status
    run.finished_at = timezone.now()
    run.items_in_feed = plan.items_in_feed
    run.matched = plan.matched if applied else 0
    run.price_changed = plan.price_changed if applied else 0
    run.not_in_feed = len(plan.not_in_feed) if applied else 0
    run.not_in_catalog = len(plan.not_in_catalog) if applied else 0
    run.marked_out = plan.marked_out if applied else 0
    run.errors = plan.error_count
    run.report = text
    run.report_json = payload
    run.save()
    return run
