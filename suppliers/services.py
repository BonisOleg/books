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
from suppliers.models import PendingPriceChange, SupplierProduct, SupplierSyncRun
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
            apply_plan(plan, supplier=supplier, run=run)
        except Exception:
            logger.exception('Запис синхронізації постачальника %s відкочено', supplier.pk)
            return _fail(run, 'Не вдалося записати зміни. Каталог не змінено.', plan)
    return _save(run, SupplierSyncRun.Status.OK, plan)


def apply_plan(plan: SyncPlan, *, supplier, run) -> None:
    now = timezone.now()
    with transaction.atomic():
        _link_products(plan, supplier, now)
        _touch_seen(plan, supplier, now)
        _update_prices(plan, now)
        _upsert_pending(plan, supplier, run, now)
        _drop_obsolete_pending(plan)
        _mark_out(plan, supplier, now)
        _restore_stock(plan, supplier, now)
        _clear_sync_flags(plan, supplier)


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


def _link_products(plan: SyncPlan, supplier, now) -> None:
    if not plan.to_link:
        return
    SupplierProduct.objects.bulk_create([
        SupplierProduct(
            supplier=supplier,
            product_id=item.product_id,
            feed_code=item.feed_code[:200],
            linked_at=now,
            last_seen_at=now,
            marked_out_by_sync=False,
            ignored=False,
        )
        for item in plan.to_link
    ], batch_size=_BULK)


def _touch_seen(plan: SyncPlan, supplier, now) -> None:
    if not plan.seen:
        return
    feed_codes = {item.product_id: item.feed_code[:200] for item in plan.seen}
    links = list(SupplierProduct.objects.filter(
        supplier=supplier,
        product_id__in=feed_codes,
    ))
    if not links:
        return
    for link in links:
        link.feed_code = feed_codes[link.product_id]
        link.last_seen_at = now
    SupplierProduct.objects.bulk_update(
        links, ['feed_code', 'last_seen_at'], batch_size=_BULK,
    )


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


def _upsert_pending(plan: SyncPlan, supplier, run, now) -> None:
    if not plan.pending_changes:
        return
    product_ids = [change.product_id for change in plan.pending_changes]
    existing = {
        row.product_id: row
        for row in PendingPriceChange.objects.filter(
            product_id__in=product_ids,
            status=PendingPriceChange.Status.PENDING,
        )
    }
    creating = []
    updating = []
    for change in plan.pending_changes:
        row = existing.get(change.product_id)
        if row is None:
            creating.append(PendingPriceChange(
                supplier=supplier,
                product_id=change.product_id,
                run=run,
                old_price=change.old,
                new_price=change.new,
                percent=change.percent,
                status=PendingPriceChange.Status.PENDING,
                created_at=now,
            ))
            continue
        row.supplier = supplier
        row.run = run
        row.old_price = change.old
        row.new_price = change.new
        row.percent = change.percent
        updating.append(row)
    if creating:
        PendingPriceChange.objects.bulk_create(creating, batch_size=_BULK)
    if updating:
        PendingPriceChange.objects.bulk_update(
            updating,
            ['supplier', 'run', 'old_price', 'new_price', 'percent'],
            batch_size=_BULK,
        )


def _drop_obsolete_pending(plan: SyncPlan) -> None:
    """Прибирає відкрите підтвердження, якщо ця синхронізація ціну вже вирішила сама."""
    product_ids = [change.product_id for change in plan.price_changes]
    product_ids.extend(plan.unchanged_ids)
    if not product_ids:
        return
    PendingPriceChange.objects.filter(
        product_id__in=product_ids,
        status=PendingPriceChange.Status.PENDING,
    ).delete()


def _mark_out(plan: SyncPlan, supplier, now) -> None:
    if not plan.mark_out_ids or not supplier.mark_missing_out_of_stock:
        return
    link_ids = list(
        SupplierProduct.objects.filter(
            supplier=supplier,
            product_id__in=plan.mark_out_ids,
            ignored=False,
        ).values_list('product_id', flat=True)
    )
    if not link_ids:
        return
    products = list(
        Product.objects.filter(pk__in=link_ids).exclude(stock_status='out')
    )
    if not products:
        return
    for product in products:
        product.stock_status = 'out'
        product.updated_at = now
    Product.objects.bulk_update(products, ['stock_status', 'updated_at'], batch_size=_BULK)
    SupplierProduct.objects.filter(
        supplier=supplier,
        product_id__in=[product.pk for product in products],
    ).update(marked_out_by_sync=True)


def _restore_stock(plan: SyncPlan, supplier, now) -> None:
    if not plan.restore:
        return
    product_ids = [item.product_id for item in plan.restore]
    links = list(SupplierProduct.objects.filter(
        supplier=supplier,
        product_id__in=product_ids,
        marked_out_by_sync=True,
        ignored=False,
    ))
    if not links:
        return
    products = list(
        Product.objects.filter(pk__in=[link.product_id for link in links])
        .exclude(stock_status='in_stock')
    )
    for product in products:
        product.stock_status = 'in_stock'
        product.updated_at = now
    if products:
        Product.objects.bulk_update(products, ['stock_status', 'updated_at'], batch_size=_BULK)
    SupplierProduct.objects.filter(pk__in=[link.pk for link in links]).update(
        marked_out_by_sync=False,
    )


def _clear_sync_flags(plan: SyncPlan, supplier) -> None:
    if not plan.clear_flag_ids:
        return
    SupplierProduct.objects.filter(
        supplier=supplier,
        product_id__in=plan.clear_flag_ids,
        marked_out_by_sync=True,
        ignored=False,
    ).update(marked_out_by_sync=False)


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
