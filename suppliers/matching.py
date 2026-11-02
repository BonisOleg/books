"""Зіставлення g:id з артикулом виробника і план змін каталогу."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from products.models import Product

from suppliers.constants import MAX_STORED_ERRORS
from suppliers.exceptions import PriceComputeError
from suppliers.models import Supplier, SupplierProduct
from suppliers.plans import (
    MissingInCatalog,
    MissingInFeed,
    PlannedLink,
    PriceChange,
    SeenLink,
    StockNote,
    SyncPlan,
)
from suppliers.pricing import change_percent, compute_price, needs_confirmation

# Візуальні двійники кирилиці → латиниця до strip/casefold (фід і каталог).
_CYRILLIC_LOOKALIKES = str.maketrans({
    '\u0430': 'a', '\u0410': 'A',  # а А
    '\u0432': 'b', '\u0412': 'B',  # в В
    '\u0435': 'e', '\u0415': 'E',  # е Е
    '\u0456': 'i', '\u0406': 'I',  # і І
    '\u043a': 'k', '\u041a': 'K',  # к К
    '\u043c': 'm', '\u041c': 'M',  # м М
    '\u043d': 'h', '\u041d': 'H',  # н Н
    '\u043e': 'o', '\u041e': 'O',  # о О
    '\u0440': 'p', '\u0420': 'P',  # р Р
    '\u0441': 'c', '\u0421': 'C',  # с С
    '\u0442': 't', '\u0422': 'T',  # т Т
    '\u0443': 'y', '\u0423': 'Y',  # у У
    '\u0445': 'x', '\u0425': 'X',  # х Х
})

_PRODUCT_FIELDS = ('id', 'name', 'sku', 'sku_manufacturer', 'price', 'stock_status')


def normalize_code(value) -> str:
    if value is None:
        return ''
    return str(value).translate(_CYRILLIC_LOOKALIKES).strip().casefold()


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
    catalog_product_ids = set()
    rows = (
        Product.objects.exclude(sku_manufacturer__isnull=True)
        .exclude(sku_manufacturer='')
        .values(*_PRODUCT_FIELDS)
        .iterator(chunk_size=2000)
    )
    for row in rows:
        code = normalize_code(row['sku_manufacturer'])
        if not code:
            continue
        catalog[code].append(row)
        catalog_product_ids.add(row['id'])

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

    links = {
        row['product_id']: row
        for row in SupplierProduct.objects.values(
            'product_id', 'supplier_id', 'ignored', 'marked_out_by_sync',
        )
    }
    other_names = _other_supplier_names(supplier.pk, links)

    price_changes = []
    pending_changes = []
    unchanged_ids = []
    to_link = []
    seen = []
    restore = []
    clear_flag_ids = []
    matched = 0

    for code in sorted(groups):
        group = groups[code]
        found = catalog.get(code)
        if not found:
            continue
        if code in conflicts or len(found) != 1 or len(group) != 1:
            continue
        row = found[0]
        item = group[0]
        link = links.get(row['id'])
        if link is not None and link['supplier_id'] != supplier.pk:
            owner = other_names.get(link['supplier_id'], 'іншого постачальника')
            raw = (row['sku_manufacturer'] or item.id).strip()
            push(
                f'Конфлікт: код «{raw}» привʼязаний до постачальника «{owner}». '
                'Товар не змінено.'
            )
            continue
        matched += 1
        feed_code = (item.id or '').strip()
        if link is None:
            to_link.append(PlannedLink(
                product_id=row['id'],
                name=row['name'],
                code=(row['sku_manufacturer'] or '').strip(),
                feed_code=feed_code,
            ))
        else:
            seen.append(SeenLink(product_id=row['id'], feed_code=feed_code))
            if link['ignored']:
                continue
            if link['marked_out_by_sync']:
                if row['stock_status'] != 'in_stock':
                    restore.append(StockNote(
                        product_id=row['id'],
                        name=row['name'],
                        code=(row['sku_manufacturer'] or '').strip(),
                    ))
                else:
                    clear_flag_ids.append(row['id'])
        _queue_price(
            supplier, row, item, price_changes, pending_changes, unchanged_ids, push,
        )

    missing_catalog = []
    for code in sorted(groups):
        group = groups[code]
        if catalog.get(code):
            continue
        for item in group:
            missing_catalog.append(MissingInCatalog(
                code=item.id.strip(),
                title=item.title,
                price=item.price,
            ))

    not_in_feed = []
    mark_out_ids = []
    _collect_missing(
        supplier, catalog, groups, conflicts, links,
        not_in_feed, mark_out_ids,
    )
    _collect_unindexed(
        supplier, links, catalog_product_ids, groups, conflicts,
        not_in_feed, mark_out_ids,
    )

    price_changes.sort(key=lambda change: change.code.casefold())
    pending_changes.sort(key=lambda change: change.code.casefold())
    to_link.sort(key=lambda row: row.code.casefold())
    restore.sort(key=lambda row: row.code.casefold())
    not_in_feed.sort(key=lambda row: (row.code.casefold(), row.sku))
    missing_catalog.sort(key=lambda row: row.code.casefold())
    return SyncPlan(
        items_in_feed=sum(len(group) for group in groups.values()),
        matched=matched,
        price_changes=price_changes,
        pending_changes=pending_changes,
        to_link=to_link,
        seen=seen,
        not_in_feed=not_in_feed,
        not_in_catalog=missing_catalog,
        mark_out_ids=mark_out_ids,
        restore=restore,
        clear_flag_ids=clear_flag_ids,
        unchanged_ids=unchanged_ids,
        error_messages=messages,
        error_count=total_errors,
    )


def _other_supplier_names(supplier_id, links) -> dict:
    other_ids = {
        link['supplier_id']
        for link in links.values()
        if link['supplier_id'] != supplier_id
    }
    if not other_ids:
        return {}
    return dict(Supplier.objects.filter(pk__in=other_ids).values_list('pk', 'name'))


def _queue_price(supplier, row, item, price_changes, pending_changes, unchanged_ids, push) -> None:
    if not supplier.update_price:
        return
    try:
        new_price = compute_price(item.price, supplier)
    except PriceComputeError as exc:
        push(f'{item.id.strip()}: {exc}')
        return
    old_price = Decimal(row['price'])
    if old_price == new_price:
        unchanged_ids.append(row['id'])
        return
    percent = change_percent(old_price, new_price)
    change = PriceChange(
        product_id=row['id'],
        name=row['name'],
        code=(row['sku_manufacturer'] or '').strip(),
        old=old_price,
        new=new_price,
        percent=percent,
    )
    if needs_confirmation(old_price, new_price, supplier.max_price_change_percent):
        pending_changes.append(change)
    else:
        price_changes.append(change)


def _collect_missing(supplier, catalog, groups, conflicts, links, not_in_feed, mark_out_ids):
    for code in sorted(catalog):
        if code in groups:
            continue
        found = catalog[code]
        unique = len(found) == 1 and code not in conflicts
        for row in found:
            link = links.get(row['id'])
            if link is None or link['supplier_id'] != supplier.pk:
                continue
            _remember_absent(supplier, row, link, unique, not_in_feed, mark_out_ids)


def _collect_unindexed(
    supplier, links, catalog_product_ids, groups, conflicts, not_in_feed, mark_out_ids,
):
    missing_ids = [
        product_id
        for product_id, link in links.items()
        if link['supplier_id'] == supplier.pk and product_id not in catalog_product_ids
    ]
    if not missing_ids:
        return
    rows = Product.objects.filter(pk__in=missing_ids).values(*_PRODUCT_FIELDS)
    for row in rows:
        code = normalize_code(row['sku_manufacturer'])
        if code and code in groups:
            continue
        link = links[row['id']]
        unique = not code or code not in conflicts
        _remember_absent(supplier, row, link, unique, not_in_feed, mark_out_ids)


def _remember_absent(supplier, row, link, unique, not_in_feed, mark_out_ids) -> None:
    not_in_feed.append(MissingInFeed(
        product_id=row['id'],
        name=row['name'],
        code=(row['sku_manufacturer'] or '').strip(),
        sku=row['sku'],
    ))
    if (
        supplier.mark_missing_out_of_stock
        and unique
        and not link['ignored']
        and row['stock_status'] != 'out'
    ):
        mark_out_ids.append(row['id'])
