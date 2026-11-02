"""Move selected products from dityachi-knigi → bibliya.

Default is dry-run. Pass --apply to persist. Requires explicit --ids;
without --ids nothing is moved (candidates with «Біблі»/Bibli are listed).

Product URLs are /catalog/product/<slug>/ (category-independent) — no 301.

M2M: Product.categories only (FK category removed). Move = remove source,
add target; other M2M categories on the product are left intact.
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Category, Product

SOURCE_SLUG = 'dityachi-knigi'
TARGET_SLUG = 'bibliya'
TARGET_NAME_UK = 'Біблія'
TARGET_NAME_EN = 'Bible'
TARGET_NAME_RU = 'Библия'
BIBLE_NAME_RE = re.compile(r'bibli|біблі', re.IGNORECASE)
_NAME_FIELDS = ('name', 'name_uk', 'name_en', 'name_ru')


def _is_bible_product(product: Product) -> bool:
    for field in _NAME_FIELDS:
        if not hasattr(product, field):
            continue
        value = getattr(product, field, None)
        if isinstance(value, str) and value and BIBLE_NAME_RE.search(value):
            return True
    return False


def _parse_ids(raw_values) -> list[int]:
    """Accept --ids 1 2 3 and/or --ids 1,2,3."""
    if not raw_values:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for chunk in raw_values:
        for part in str(chunk).split(','):
            part = part.strip()
            if not part:
                continue
            try:
                pk = int(part)
            except ValueError as exc:
                raise CommandError(f'Некоректний id у --ids: {part!r}') from exc
            if pk not in seen:
                seen.add(pk)
                ids.append(pk)
    return ids


def iter_bible_candidates():
    """Products currently in dityachi-knigi whose name matches Біблі/Bibli."""
    qs = (
        Product.objects.filter(categories__slug=SOURCE_SLUG)
        .distinct()
        .order_by('name', 'id')
    )
    for product in qs.iterator():
        if _is_bible_product(product):
            yield product


def _resolve_target_defaults(source: Category | None) -> dict:
    """Mirror neighbouring top category (dityachi-knigi): parent/active/order/GPC."""
    if source is not None:
        parent = source.parent
        is_active = bool(source.is_active)
        order = int(source.order) + 1
        gpc = (source.google_product_category or '').strip() or '784'
    else:
        parent = None
        is_active = True
        top = (
            Category.objects.filter(parent__isnull=True)
            .order_by('-order')
            .first()
        )
        order = (int(top.order) + 1) if top else 0
        gpc = '784'
    return {
        'parent': parent,
        'is_active': is_active,
        'order': order,
        'google_product_category': gpc,
    }


def ensure_bible_category(*, create: bool) -> tuple[Category | None, bool]:
    """Return (category, created_or_would_create).

    If create=False and missing — returns (None, True) meaning «would create».
    """
    existing = Category.objects.filter(slug=TARGET_SLUG).first()
    if existing:
        return existing, False

    if not create:
        return None, True

    source = Category.objects.filter(slug=SOURCE_SLUG).first()
    defaults = _resolve_target_defaults(source)
    kwargs = {
        'slug': TARGET_SLUG,
        'name': TARGET_NAME_UK,
        'name_uk': TARGET_NAME_UK,
        'name_en': TARGET_NAME_EN,
        'name_ru': TARGET_NAME_RU,
        **defaults,
    }
    # description_* left blank like many seeded top categories
    category = Category.objects.create(**kwargs)
    return category, True


def _source_label(product: Product, source: Category | None) -> str:
    if source and product.categories.filter(pk=source.pk).exists():
        return source.slug
    src = product.categories.filter(slug=SOURCE_SLUG).first()
    if src:
        return src.slug
    first = product.categories.order_by('order', 'name').first()
    return first.slug if first else '—'


def move_product_categories(product: Product, source: Category, target: Category) -> bool:
    """Swap source→target on M2M. Returns True if membership changed."""
    had_source = product.categories.filter(pk=source.pk).exists()
    had_target = product.categories.filter(pk=target.pk).exists()
    if not had_source and had_target:
        return False
    if had_source:
        product.categories.remove(source)
    if not had_target:
        product.categories.add(target)
    elif had_source:
        # already had target; source removed above
        pass
    return True


class Command(BaseCommand):
    help = (
        'Створює категорію bibliya (якщо немає) і переносить товари з '
        'dityachi-knigi за явним --ids. Без --apply — dry-run; без --ids '
        'нічого не переносить (лише кандидати «Біблі»).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Застосувати зміни (без цього прапорця — лише dry-run).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Явний dry-run (поведінка за замовчуванням).',
        )
        parser.add_argument(
            '--ids',
            nargs='+',
            default=None,
            help=(
                'ID товарів для переносу (через пробіл і/або кому). '
                'Без --ids переносу немає.'
            ),
        )

    def handle(self, *args, **options):
        apply = bool(options.get('apply'))
        dry_run = not apply
        ids = _parse_ids(options.get('ids'))

        source = Category.objects.filter(slug=SOURCE_SLUG).first()
        target_existing = Category.objects.filter(slug=TARGET_SLUG).first()

        self.stdout.write(
            f'Режим: {"APPLY" if apply else "DRY-RUN"}.'
        )

        if target_existing:
            self.stdout.write(
                f'Категорія «{TARGET_SLUG}» уже є '
                f'(id={target_existing.pk}, order={target_existing.order}, '
                f'parent={target_existing.parent_id}, '
                f'active={target_existing.is_active}).'
            )
            would_create = False
        else:
            defaults = _resolve_target_defaults(source)
            self.stdout.write(
                f'Категорію «{TARGET_SLUG}» буде створено: '
                f'name_uk={TARGET_NAME_UK!r}, name_en={TARGET_NAME_EN!r}, '
                f'name_ru={TARGET_NAME_RU!r}, parent='
                f'{defaults["parent"].slug if defaults["parent"] else None}, '
                f'order={defaults["order"]}, is_active={defaults["is_active"]}, '
                f'google_product_category={defaults["google_product_category"]!r} '
                f'(як у сусідньої top «{SOURCE_SLUG}»: parent/active; '
                f'order = source.order+1).'
            )
            would_create = True

        if not ids:
            candidates = list(iter_bible_candidates())
            self.stdout.write(
                f'Без --ids переносу немає. Кандидатів «Біблі»/Bibli '
                f'у «{SOURCE_SLUG}»: {len(candidates)}'
            )
            for p in candidates:
                self.stdout.write(
                    f'- id={p.pk} | {p.name} | {SOURCE_SLUG} -> {TARGET_SLUG}'
                )
            if dry_run:
                self.stdout.write(self.style.NOTICE(
                    'Dry-run: змін не зроблено.'
                ))
            return

        if not source:
            self.stdout.write(self.style.ERROR(
                f'Категорію source «{SOURCE_SLUG}» не знайдено — '
                f'перенос неможливий.'
            ))
            return

        to_move: list[Product] = []
        already_ok = 0
        for pk in ids:
            product = Product.objects.filter(pk=pk).first()
            if product is None:
                self.stdout.write(self.style.WARNING(
                    f'id={pk}: товар не знайдено — пропуск.'
                ))
                continue
            in_source = product.categories.filter(pk=source.pk).exists()
            in_target = (
                target_existing is not None
                and product.categories.filter(pk=target_existing.pk).exists()
            ) or product.categories.filter(slug=TARGET_SLUG).exists()
            if not in_source:
                if in_target:
                    already_ok += 1
                    self.stdout.write(
                        f'id={pk} ({product.name}): уже в «{TARGET_SLUG}» — ок.'
                    )
                else:
                    self.stdout.write(self.style.WARNING(
                        f'id={pk} ({product.name}): не в «{SOURCE_SLUG}» — пропуск.'
                    ))
                continue
            to_move.append(product)
        if already_ok:
            self.stdout.write(f'Уже на місці (ідемпотентно): {already_ok}')

        self.stdout.write(f'До переносу: {len(to_move)}')
        for p in to_move:
            old = _source_label(p, source)
            self.stdout.write(
                f'- id={p.pk} | {p.name} | {old} -> {TARGET_SLUG}'
            )

        if dry_run:
            self.stdout.write(self.style.NOTICE(
                f'Dry-run: змін не зроблено'
                f'{" (категорію також не створено)" if would_create else ""}.'
            ))
            return

        with transaction.atomic():
            target, created = ensure_bible_category(create=True)
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'Створено категорію id={target.pk} slug={target.slug} '
                    f'order={target.order} parent={target.parent_id}.'
                ))
            moved = 0
            for product in to_move:
                # re-fetch under atomic for idempotent M2M
                product = Product.objects.get(pk=product.pk)
                if move_product_categories(product, source, target):
                    moved += 1

        self.stdout.write(self.style.SUCCESS(
            f'Перенесено / оновлено товарів: {moved} '
            f'(ідемпотентно; уже в {TARGET_SLUG} без {SOURCE_SLUG} — 0 змін).'
        ))
