"""Звіт VIP / Middle / excluded — лише читання, без записів у БД."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connections

from products.feed_segments import (
    ICON_CATEGORY_NAMES,
    ICON_CATEGORY_SLUGS,
    VIP_CATEGORY_NAMES,
    VIP_CATEGORY_SLUGS,
    VIP_PRICE_THRESHOLD,
    _category_matches_names_or_slugs,
    exclusion_reason_labels,
    format_religious_text_reason,
    product_is_vip,
    product_religious_matches,
)
from products.models import Category, Product


class Command(BaseCommand):
    help = (
        'Друкує кількість VIP / Middle / excluded і список виключених '
        '(назва + причина). Read-only. --database=alias для Postgres-дампу.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            default='default',
            help='Database alias (default: default). Для відновленого Postgres: --database=restore',
        )

    def handle(self, *args, **options):
        using = options['database']
        if using not in connections:
            self.stderr.write(self.style.ERROR(f'Невідомий database alias: {using}'))
            return

        has_product_flag = self._column_exists(using, Product, 'exclude_from_feeds')
        has_category_flag = self._column_exists(using, Category, 'exclude_from_feeds')
        if not has_product_flag or not has_category_flag:
            self.stdout.write(
                self.style.WARNING(
                    'Колонки exclude_from_feeds відсутні в цій БД — '
                    'ручні прапорці пропущено (migrate не запускаємо).'
                )
            )

        categories = self._category_qs(using, has_category_flag)
        icon_ids = self._match_expand(using, categories, ICON_CATEGORY_NAMES, ICON_CATEGORY_SLUGS)
        vip_cat_ids = self._match_expand(using, categories, VIP_CATEGORY_NAMES, VIP_CATEGORY_SLUGS)
        manual_cat_ids: set[int] = set()
        if has_category_flag:
            roots = [c.id for c in categories if getattr(c, 'exclude_from_feeds', False)]
            manual_cat_ids = self._expand(using, roots)

        products = self._product_qs(using, has_product_flag)

        vip_count = 0
        middle_count = 0
        excluded_rows: list[tuple[str, str]] = []

        for product in products:
            reasons = self._collect_reasons(
                product,
                icon_ids=icon_ids,
                manual_cat_ids=manual_cat_ids,
                has_product_flag=has_product_flag,
            )
            eligible = (
                product.is_active
                and product.price > 0
                and product.images.exists()
                and not reasons
            )
            if not eligible:
                if product.is_active:
                    if not reasons:
                        if product.price <= 0:
                            reasons = ['no_price']
                        elif not product.images.exists():
                            reasons = ['no_image']
                    labels = exclusion_reason_labels(reasons) if reasons else ['не у сегменті']
                    excluded_rows.append((product.name, '; '.join(labels)))
                continue

            if product_is_vip(product, vip_cat_ids):
                vip_count += 1
            else:
                middle_count += 1

        self.stdout.write(f'Database: {using}')
        self.stdout.write(f'VIP:      {vip_count}')
        self.stdout.write(f'Middle:   {middle_count}')
        self.stdout.write(f'Excluded: {len(excluded_rows)}')
        self.stdout.write(f'VIP threshold (base price): {VIP_PRICE_THRESHOLD}')
        self.stdout.write('')
        self.stdout.write('Excluded products:')
        if not excluded_rows:
            self.stdout.write('  (немає)')
        for name, reason in excluded_rows:
            self.stdout.write(f'  - {name} | {reason}')

    def _collect_reasons(self, product, *, icon_ids, manual_cat_ids, has_product_flag) -> list[str]:
        reasons: list[str] = []
        if not product.is_active:
            reasons.append('inactive')
        if not product.images.exists():
            reasons.append('no_image')
        if product.price <= 0:
            reasons.append('no_price')
        if has_product_flag and getattr(product, 'exclude_from_feeds', False):
            reasons.append('manual_product')
        cat_ids = set(product.categories.values_list('id', flat=True))
        if manual_cat_ids and cat_ids & manual_cat_ids:
            reasons.append('manual_category')
        if icon_ids and cat_ids & icon_ids:
            reasons.append('icons_category')
        rel_matches = product_religious_matches(product)
        if rel_matches:
            reasons.append(format_religious_text_reason(rel_matches))
        return reasons

    def _category_qs(self, using: str, has_flag: bool):
        qs = Category.objects.using(using).all()
        if not has_flag:
            qs = qs.defer('exclude_from_feeds')
        return list(qs)

    def _product_qs(self, using: str, has_flag: bool):
        qs = Product.objects.using(using).all().order_by('name').prefetch_related(
            'categories', 'images',
        )
        if not has_flag:
            qs = qs.defer('exclude_from_feeds')
        return qs

    def _column_exists(self, using: str, model, field_name: str) -> bool:
        table = model._meta.db_table
        try:
            conn = connections[using]
            with conn.cursor() as cursor:
                desc = conn.introspection.get_table_description(cursor, table)
        except Exception:
            return False
        if not desc:
            return False
        return any(col.name == field_name for col in desc)

    def _match_expand(self, using, categories, names, slugs) -> set[int]:
        roots = [
            cat.id for cat in categories
            if _category_matches_names_or_slugs(cat, names, slugs)
        ]
        return self._expand(using, roots)

    def _expand(self, using: str, root_ids: list[int]) -> set[int]:
        ids: set[int] = set(root_ids)
        frontier = list(root_ids)
        while frontier:
            children = list(
                Category.objects.using(using)
                .filter(parent_id__in=frontier)
                .values_list('id', flat=True)
            )
            frontier = [cid for cid in children if cid not in ids]
            ids.update(frontier)
        return ids
