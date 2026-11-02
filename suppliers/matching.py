"""Зіставлення g:id з артикулом виробника і план змін каталогу."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from products.models import Product

from suppliers.constants import MAX_STORED_ERRORS
from suppliers.exceptions import PriceComputeError
from suppliers.plans import MissingInCatalog, MissingInFeed, PriceChange, SyncPlan
from suppliers.pricing import compute_price


def normalize_code(value) -> str:
    if value is None:
        return ''
    return str(value).strip().casefold()


def plan_from_items(supplier, items, error_messages, error_count) -> SyncPlan:
    messages = list(error_messages)
    total_errors = int(error_count)

    def push(message: str) -> None:
        nonlocal total_errors
        total_errors += 1
        if len(messages) < MAX_STORED_ERRORS:
            messages.append(message)

    groups = defaultdict(list)
    for item in items:
        code = normalize_code(item.id)
        if not code:
            continue
        groups[code].append(item)

    if not groups:
        return SyncPlan(
            items_in_feed=0,
            error_messages=messages,
            error_count=total_errors,
        )

    catalog = defaultdict(list)
    rows = (
        Product.objects.exclude(sku_manufacturer__isnull=True)
        .exclude(sku_manufacturer='')
        .values('id', 'name', 'sku', 'sku_manufacturer', 'price', 'stock_status')
        .iterator(chunk_size=2000)
    )
    for row in rows:
        code = normalize_code(row['sku_manufacturer'])
        if not code:
            continue
        catalog[code].append(row)

    conflicts = set()
    for code, group in groups.items():
        if len(group) > 1:
            conflicts.add(code)
            raw = group[0].id.strip()
            push(
                f'Конфлікт: код «{raw}» повторюється у фіді ({len(group)}). '
                'Ціну не оновлено.'
            )
    for code, group in catalog.items():
        if len(group) > 1:
            conflicts.add(code)
            raw = group[0]['sku_manufacturer'].strip()
            push(
                f'Конфлікт: код «{raw}» повторюється в каталозі ({len(group)} товарів). '
                'Ціну не оновлено.'
            )

    price_changes = []
    missing_catalog = []
    matched = 0
    for code in sorted(groups):
        group = groups[code]
        found = catalog.get(code)
        if not found:
            for item in group:
                missing_catalog.append(MissingInCatalog(
                    code=item.id.strip(),
                    title=item.title,
                    price=item.price,
                ))
            continue
        if code in conflicts or len(found) != 1 or len(group) != 1:
            continue
        row = found[0]
        item = group[0]
        matched += 1
        if not supplier.update_price:
            continue
        try:
            new_price = compute_price(item.price, supplier)
        except PriceComputeError as exc:
            push(f'{item.id.strip()}: {exc}')
            continue
        old_price = Decimal(row['price'])
        if old_price != new_price:
            price_changes.append(PriceChange(
                product_id=row['id'],
                name=row['name'],
                code=(row['sku_manufacturer'] or '').strip(),
                old=old_price,
                new=new_price,
            ))

    not_in_feed = []
    mark_out_ids = []
    for code in sorted(catalog):
        if code in groups:
            continue
        found = catalog[code]
        unique = len(found) == 1 and code not in conflicts
        for row in found:
            not_in_feed.append(MissingInFeed(
                product_id=row['id'],
                name=row['name'],
                code=(row['sku_manufacturer'] or '').strip(),
                sku=row['sku'],
            ))
            if (
                supplier.mark_missing_out_of_stock
                and unique
                and row['stock_status'] != 'out'
            ):
                mark_out_ids.append(row['id'])

    price_changes.sort(key=lambda change: change.code.casefold())
    not_in_feed.sort(key=lambda row: (row.code.casefold(), row.sku))
    missing_catalog.sort(key=lambda row: row.code.casefold())
    return SyncPlan(
        items_in_feed=sum(len(group) for group in groups.values()),
        matched=matched,
        price_changes=price_changes,
        not_in_feed=not_in_feed,
        not_in_catalog=missing_catalog,
        mark_out_ids=mark_out_ids,
        error_messages=messages,
        error_count=total_errors,
    )
