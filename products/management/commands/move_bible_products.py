"""Move Bible-named products from dityachi-knigi → bibliya.

Default is dry-run. Pass --apply to persist. Product URLs are
/catalog/product/<slug>/ (category-independent) — no 301 needed.

Name matching is done in Python (Unicode-safe): SQLite icontains is
ASCII-only for case-folding and misses «Біблія».
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand

from products.models import Category, Product

SOURCE_SLUG = 'dityachi-knigi'
TARGET_SLUG = 'bibliya'
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


def iter_bible_products():
    qs = (
        Product.objects.filter(categories__slug=SOURCE_SLUG)
        .distinct()
        .order_by('name', 'id')
    )
    for product in qs.iterator():
        if _is_bible_product(product):
            yield product


class Command(BaseCommand):
    help = (
        'Переносить товари з «Біблі»/Bibli у назві з категорії dityachi-knigi '
        'до bibliya. За замовчуванням dry-run; --apply для запису.'
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

    def handle(self, *args, **options):
        apply = bool(options.get('apply'))
        dry_run = not apply

        source = Category.objects.filter(slug=SOURCE_SLUG).first()
        target = Category.objects.filter(slug=TARGET_SLUG).first()

        total_products = Product.objects.count()
        self.stdout.write(f'Локальна БД: товарів усього = {total_products}')
        if total_products == 0:
            self.stdout.write(self.style.WARNING(
                'Локальна БД порожня / неповна — немає товарів для переносу.'
            ))

        if not source:
            self.stdout.write(self.style.WARNING(
                f'Категорію source «{SOURCE_SLUG}» не знайдено.'
            ))
        if not target:
            self.stdout.write(self.style.WARNING(
                f'Категорію target «{TARGET_SLUG}» не знайдено.'
            ))

        rows = [(p.name, p.slug, p.pk) for p in iter_bible_products()]
        self.stdout.write(
            f'Режим: {"APPLY" if apply else "DRY-RUN"}. '
            f'Кандидатів: {len(rows)}'
        )
        for name, slug, _pid in rows:
            self.stdout.write(f'- {name} | {slug}')

        if dry_run:
            self.stdout.write(self.style.NOTICE(
                'Dry-run: змін не зроблено. URL товару /catalog/product/<slug>/ '
                'не залежить від категорії — 301 не потрібен.'
            ))
            return

        if not source or not target:
            self.stdout.write(self.style.ERROR(
                'Неможливо застосувати: відсутня source або target категорія.'
            ))
            return

        moved = 0
        for product in Product.objects.filter(pk__in=[r[2] for r in rows]):
            product.categories.remove(source)
            product.categories.add(target)
            moved += 1

        self.stdout.write(self.style.SUCCESS(f'Перенесено товарів: {moved}'))
