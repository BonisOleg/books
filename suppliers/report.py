"""Текстовий і JSON-звіт запуску."""

from __future__ import annotations

from decimal import Decimal

from suppliers.constants import MAX_EXAMPLES
from suppliers.models import SupplierSyncRun

_CENTS = Decimal('0.01')


def money(value) -> str:
    return f'{_grouped(value)} грн'


def format_percent(value) -> str:
    if value is None:
        return 'стара ціна 0'
    return f'{_grouped(value)}%'


def render_report(plan, *, status: str, dry_run: bool) -> tuple[str, dict]:
    applied = status == SupplierSyncRun.Status.OK
    price_changed = plan.price_changed if applied else 0
    pending_count = plan.pending_count if applied else 0
    marked_out = plan.marked_out if applied else 0
    restore_count = plan.restore_count if applied else 0
    link_count = plan.link_count if applied else 0
    matched = plan.matched if applied else 0
    not_in_feed = len(plan.not_in_feed) if applied else 0
    not_in_catalog = len(plan.not_in_catalog) if applied else 0

    if dry_run and applied:
        stock_line = f'Стане «Немає в наявності»: {marked_out}'
        restore_line = f'Повернеться в наявність: {restore_count}'
        link_line = f"Буде прив'язано: {link_count}"
    else:
        stock_line = f'Позначено «Немає в наявності»: {marked_out}'
        restore_line = f'Повернуто в наявність: {restore_count}'
        link_line = f'Привʼязано: {link_count}'

    lines = []
    if dry_run and applied:
        lines.append('Пробний запуск: каталог, привʼязки і чергу цін не змінено.')
    if not applied:
        lines.append('Застосування скасовано. Каталог не змінено.')
    lines.extend([
        f'Товарів у фіді: {plan.items_in_feed}',
        f'Збігів: {matched}',
        f'Змінено цін: {price_changed}',
        f'Застосовуються автоматично: {price_changed}',
        f'Потребують підтвердження: {pending_count}',
        f'Немає у фіді (з каталогу): {not_in_feed}',
        f'Немає в каталозі (з фіду): {not_in_catalog}',
        stock_line,
        restore_line,
        link_line,
        f'Помилки: {plan.error_count}',
        '',
    ])

    price_rows = []
    pending_rows = []
    feed_rows = []
    catalog_rows = []
    mark_rows = []
    restore_rows = []
    link_rows = []
    if applied:
        lines.append('Застосовуються автоматично:')
        price_rows = _price_rows(plan.price_changes)
        lines.extend(_section(price_rows, _price_line, price_changed))
        lines.append('')
        lines.append('Потребують підтвердження:')
        pending_rows = _price_rows(plan.pending_changes)
        lines.extend(_section(pending_rows, _price_line, pending_count))
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
        if dry_run:
            lines.append(stock_line)
            mark_rows = _mark_out_rows(plan)
            lines.extend(_section(mark_rows, lambda row: (
                f"- {row['name']} | {row['code']}"
            ), marked_out))
            lines.append('')
            lines.append(restore_line)
            restore_rows = _note_rows(plan.restore)
            lines.extend(_section(restore_rows, lambda row: (
                f"- {row['name']} | {row['code']}"
            ), restore_count))
            lines.append('')
            lines.append(link_line)
            link_rows = _link_rows(plan)
            lines.extend(_section(link_rows, lambda row: (
                f"- {row['name']} | {row['code']}"
            ), link_count))
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
        'pending_count': pending_count,
        'not_in_feed': not_in_feed,
        'not_in_catalog': not_in_catalog,
        'marked_out': marked_out,
        'restore_count': restore_count,
        'link_count': link_count,
        'errors': plan.error_count,
        'price_changes': price_rows,
        'pending_changes': pending_rows,
        'not_in_feed_examples': feed_rows,
        'not_in_catalog_examples': catalog_rows,
        'mark_out_examples': mark_rows,
        'restore_examples': restore_rows,
        'link_examples': link_rows,
        'error_messages': list(plan.error_messages[:MAX_EXAMPLES]),
    }
    return '\n'.join(lines).rstrip() + '\n', payload


def _price_line(row) -> str:
    return (
        f"- {row['name']} | {row['code']} | {row['old']} → {row['new']} | {row['percent']}"
    )


def _section(rows, render, total) -> list[str]:
    if not rows:
        return ['- немає']
    lines = [render(row) for row in rows]
    extra = total - len(rows)
    if extra > 0:
        lines.append(f'… і ще {extra}')
    return lines


def _price_rows(changes) -> list[dict]:
    rows = []
    for change in changes[:MAX_EXAMPLES]:
        rows.append({
            'name': change.name,
            'code': change.code,
            'old': money(change.old),
            'new': money(change.new),
            'percent': format_percent(change.percent),
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


def _mark_out_rows(plan) -> list[dict]:
    wanted = set(plan.mark_out_ids)
    rows = []
    for row in plan.not_in_feed:
        if row.product_id not in wanted:
            continue
        rows.append({
            'name': row.name,
            'code': row.code,
        })
        if len(rows) >= MAX_EXAMPLES:
            break
    return rows


def _note_rows(notes) -> list[dict]:
    return [
        {'name': note.name, 'code': note.code}
        for note in notes[:MAX_EXAMPLES]
    ]


def _link_rows(plan) -> list[dict]:
    return _note_rows(plan.to_link)


def _catalog_rows(plan) -> list[dict]:
    rows = []
    for row in plan.not_in_catalog[:MAX_EXAMPLES]:
        rows.append({
            'code': row.code,
            'title': row.title,
            'price': money(row.price),
        })
    return rows


def _grouped(value) -> str:
    quantized = Decimal(value).quantize(_CENTS)
    negative = quantized < 0
    quantized = abs(quantized)
    whole, frac = f'{quantized:.2f}'.split('.')
    parts = []
    while whole:
        parts.append(whole[-3:])
        whole = whole[:-3]
    body = ' '.join(reversed(parts))
    sign = '-' if negative else ''
    return f'{sign}{body},{frac}'
