"""Текстовий і JSON-звіт запуску."""

from __future__ import annotations

from decimal import Decimal

from suppliers.constants import MAX_EXAMPLES
from suppliers.models import SupplierSyncRun

_CENTS = Decimal('0.01')


def money(value) -> str:
    return f'{Decimal(value).quantize(_CENTS)}'


def render_report(plan, *, status: str, dry_run: bool) -> tuple[str, dict]:
    applied = status == SupplierSyncRun.Status.OK
    price_changed = plan.price_changed if applied else 0
    marked_out = plan.marked_out if applied else 0
    matched = plan.matched if applied else 0
    not_in_feed = len(plan.not_in_feed) if applied else 0
    not_in_catalog = len(plan.not_in_catalog) if applied else 0

    lines = []
    if dry_run and applied:
        lines.append('Пробний запуск: каталог не змінювався.')
    if not applied:
        lines.append('Застосування скасовано. Каталог не змінено.')
    lines.extend([
        f'Товарів у фіді: {plan.items_in_feed}',
        f'Збігів: {matched}',
        f'Змінено цін: {price_changed}',
        f'Немає у фіді (з каталогу): {not_in_feed}',
        f'Немає в каталозі (з фіду): {not_in_catalog}',
        f'Позначено «Немає в наявності»: {marked_out}',
        f'Помилки: {plan.error_count}',
        '',
    ])

    price_rows = []
    feed_rows = []
    catalog_rows = []
    if applied:
        lines.append('Зміни цін:')
        price_rows = _price_rows(plan)
        lines.extend(_section(price_rows, lambda row: (
            f"- {row['name']} | {row['code']} | {row['old']} → {row['new']}"
        ), plan.price_changed))
        lines.append('')
        lines.append('Немає у фіді (з каталогу):')
        feed_rows = _feed_rows(plan)
        lines.extend(_section(feed_rows, lambda row: (
            f"- {row['name']} | код {row['code']} | артикул {row['sku']}"
        ), not_in_feed))
        lines.append('')
        lines.append('Немає в каталозі (з фіду):')
        catalog_rows = _catalog_rows(plan)
        lines.extend(_section(catalog_rows, lambda row: (
            f"- {row['title']} | код {row['code']} | ціна фіду {row['price']}"
        ), not_in_catalog))
        lines.append('')

    if plan.error_messages:
        lines.append('Помилки:')
        for message in plan.error_messages[:MAX_EXAMPLES]:
            lines.append(f'- {message}')
        extra = plan.error_count - len(plan.error_messages[:MAX_EXAMPLES])
        if extra > 0:
            lines.append(f'… і ще {extra}')

    payload = {
        'status': status,
        'dry_run': dry_run,
        'items_in_feed': plan.items_in_feed,
        'matched': matched,
        'price_changed': price_changed,
        'not_in_feed': not_in_feed,
        'not_in_catalog': not_in_catalog,
        'marked_out': marked_out,
        'errors': plan.error_count,
        'price_changes': price_rows,
        'not_in_feed_examples': feed_rows,
        'not_in_catalog_examples': catalog_rows,
        'error_messages': list(plan.error_messages[:MAX_EXAMPLES]),
    }
    return '\n'.join(lines).rstrip() + '\n', payload


def _section(rows, render, total) -> list[str]:
    if not rows:
        return ['- немає']
    lines = [render(row) for row in rows]
    extra = total - len(rows)
    if extra > 0:
        lines.append(f'… і ще {extra}')
    return lines


def _price_rows(plan) -> list[dict]:
    rows = []
    for change in plan.price_changes[:MAX_EXAMPLES]:
        rows.append({
            'name': change.name,
            'code': change.code,
            'old': money(change.old),
            'new': money(change.new),
        })
    return rows


def _feed_rows(plan) -> list[dict]:
    rows = []
    for row in plan.not_in_feed[:MAX_EXAMPLES]:
        rows.append({
            'name': row.name,
            'code': row.code,
            'sku': row.sku,
        })
    return rows


def _catalog_rows(plan) -> list[dict]:
    rows = []
    for row in plan.not_in_catalog[:MAX_EXAMPLES]:
        rows.append({
            'code': row.code,
            'title': row.title,
            'price': money(row.price),
        })
    return rows
