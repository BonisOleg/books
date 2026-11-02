"""Меню категорій без ліміту та видимість закріплених груп."""
from __future__ import annotations

import re
from datetime import timedelta

from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from products.models import Category, Product, ProductGroup

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'header-menu-tests',
    }
}


def _product(name, slug, sku, price, *, is_active=True, is_bestseller=False):
    return Product.objects.create(
        name=name,
        slug=slug,
        sku=sku,
        description='Опис',
        price=price,
        is_active=is_active,
        is_bestseller=is_bestseller,
    )


def _form_value(value):
    if value is None:
        return ''
    if hasattr(value, 'values_list'):
        return [str(pk) for pk in value.values_list('pk', flat=True)]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return value


def _posted_admin_data(form, overrides=None):
    data = {name: _form_value(form[name].value()) for name in form.fields}
    if overrides:
        data.update(overrides)
    return data


def _block(html, pattern):
    match = re.search(pattern, html, re.S)
    return match.group(1) if match else ''


@override_settings(CACHES=LOC_MEM)
class NavCategoryMenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.expected = []
        for index in range(1, 16):
            slug = f'menu-cat-{index:02d}'
            Category.objects.create(
                name=f'Яблуко {16 - index:02d}',
                slug=slug,
                order=index,
                is_active=True,
            )
            cls.expected.append(slug)
        Category.objects.create(
            name='Прихована категорія',
            slug='menu-hidden',
            order=0,
            is_active=False,
        )
        parent = Category.objects.get(slug='menu-cat-01')
        Category.objects.create(
            name='Підкатегорія меню',
            slug='menu-child',
            parent=parent,
            order=0,
            is_active=True,
        )

    def test_menu_and_catalog_show_every_active_root_in_order(self):
        home = self.client.get('/').content.decode()
        mega_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(home, r'class="megamenu" role="menu">(.*?)</div>\s*</div>'),
        )
        mobile_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(home, r'id="mobile-menu"(.*?)</nav>'),
        )
        self.assertEqual(mega_slugs, self.expected)
        self.assertEqual(mobile_slugs, self.expected)
        self.assertGreater(len(mega_slugs), 12)
        self.assertNotIn('menu-hidden', home)
        self.assertNotIn('menu-child', mega_slugs)

        catalog = self.client.get('/catalog/').content.decode()
        grid_slugs = re.findall(
            r'/catalog/([^"/]+)/',
            _block(catalog, r'class="categories-grid">(.*?)<div class="catalog-toolbar"'),
        )
        self.assertEqual(grid_slugs, self.expected)
        self.assertNotIn('menu-hidden', catalog)

    def test_category_queries_have_no_limit(self):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        category_sql = [
            query['sql'] for query in captured.captured_queries
            if 'products_category' in query['sql'].lower()
        ]
        self.assertTrue(category_sql)
        for sql in category_sql:
            self.assertNotIn('LIMIT', sql.upper())


@override_settings(CACHES=LOC_MEM)
class ProductGroupVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        ProductGroup.objects.create(
            name='Минула група',
            slug='mynula-grupa',
            show_in_header=True,
            is_active=True,
            order=1,
            date_from=now - timedelta(days=10),
            date_to=now - timedelta(hours=1),
        )
        cls.current = ProductGroup.objects.create(
            name='Поточна група',
            slug='potochna-grupa',
            show_in_header=True,
            is_active=True,
            order=2,
            date_from=now - timedelta(hours=1),
            date_to=now + timedelta(days=2),
            meta_title='Поточна група SEO',
            meta_description='Опис поточної групи',
        )
        ProductGroup.objects.create(
            name='Друга поточна',
            slug='druha-potochna',
            show_in_header=True,
            is_active=True,
            order=5,
        )
        ProductGroup.objects.create(
            name='Майбутня група',
            slug='maibutnia-grupa',
            show_in_header=True,
            is_active=True,
            order=0,
            date_from=now + timedelta(days=1),
            date_to=now + timedelta(days=5),
        )
        ProductGroup.objects.create(
            name='Неактивна група',
            slug='neaktyvna-grupa',
            show_in_header=True,
            is_active=False,
            order=3,
            date_from=now - timedelta(days=1),
            date_to=now + timedelta(days=1),
        )
        ProductGroup.objects.create(
            name='Без шапки',
            slug='bez-shapky',
            show_in_header=False,
            is_active=True,
            order=4,
        )
        Category.objects.create(
            name='Пункт каталогу',
            slug='punkt-katalohu',
            order=0,
            is_active=True,
        )
        cheap = _product('Дешевий альбом', 'deshevyi-albom', 'GRP-1', '100.00')
        pricey = _product('Дорогий альбом', 'dorohyi-albom', 'GRP-2', '900.00')
        hidden = _product(
            'Прихований альбом', 'prykhovanyi-albom', 'GRP-3', '50.00', is_active=False,
        )
        cls.current.products.add(pricey, cheap, hidden)

    def test_header_respects_dates_activity_and_order(self):
        html = self.client.get('/').content.decode()
        nav = _block(html, r'class="category-nav__list">(.*?)</div>')
        for slug in (
            'potochna-grupa', 'druha-potochna', 'mynula-grupa',
            'maibutnia-grupa', 'neaktyvna-grupa', 'bez-shapky',
        ):
            self.assertNotIn(slug, nav)
        self.assertNotIn('category-nav__link">Поточна група', html)

        mega = _block(html, r'class="megamenu" role="menu">(.*?)</div>\s*</div>')
        self.assertIn('/group/potochna-grupa/', mega)
        self.assertIn('/group/druha-potochna/', mega)
        self.assertIn('megamenu__title">Поточна група', mega)
        self.assertLess(mega.find('potochna-grupa'), mega.find('druha-potochna'))
        self.assertNotIn('mynula-grupa', mega)
        self.assertNotIn('maibutnia-grupa', mega)
        self.assertNotIn('neaktyvna-grupa', mega)
        self.assertNotIn('bez-shapky', mega)
        self.assertNotIn('neaktyvna-grupa', html)

        mobile = _block(html, r'id="mobile-menu"(.*?)</nav>')
        self.assertIn('/group/potochna-grupa/', mobile)
        self.assertNotIn('mynula-grupa', mobile)
        self.assertNotIn('maibutnia-grupa', mobile)

        with CaptureQueriesContext(connection) as captured:
            self.client.get('/catalog/')
        group_sql = [
            query['sql'] for query in captured.captured_queries
            if 'productgroup' in query['sql'].lower()
        ]
        self.assertEqual(len(group_sql), 1)

    def test_page_is_open_inside_range_and_missing_outside(self):
        ok = self.client.get(reverse('product_group', kwargs={'slug': 'potochna-grupa'}))
        self.assertEqual(ok.status_code, 200)
        body = ok.content.decode()
        self.assertIn('Дешевий альбом', body)
        self.assertIn('Дорогий альбом', body)
        self.assertNotIn('Прихований альбом', body)
        self.assertIn('Поточна група SEO', body)
        self.assertIn('Опис поточної групи', body)
        self.assertContains(ok, 'rel="canonical"')

        for slug in ('mynula-grupa', 'maibutnia-grupa', 'neaktyvna-grupa'):
            missing = self.client.get(reverse('product_group', kwargs={'slug': slug}))
            self.assertEqual(missing.status_code, 404)

        quiet = self.client.get(reverse('product_group', kwargs={'slug': 'bez-shapky'}))
        self.assertEqual(quiet.status_code, 200)

    def test_sort_by_price(self):
        url = reverse('product_group', kwargs={'slug': 'potochna-grupa'})
        asc = self.client.get(url, {'sort': 'price_asc'})
        desc = self.client.get(url, {'sort': 'price_desc'})
        self.assertEqual(asc.status_code, 200)
        self.assertEqual(desc.status_code, 200)
        asc_html = asc.content.decode()
        desc_html = desc.content.decode()
        self.assertLess(asc_html.find('Дешевий альбом'), asc_html.find('Дорогий альбом'))
        self.assertLess(desc_html.find('Дорогий альбом'), desc_html.find('Дешевий альбом'))

    def test_visible_now_includes_range_edges(self):
        moment = timezone.now()
        group = ProductGroup(
            name='Межа',
            slug='mezha',
            is_active=True,
            date_from=moment,
            date_to=moment,
        )
        self.assertTrue(group.visible_now(moment))
        self.assertFalse(group.visible_now(moment - timedelta(seconds=1)))
        self.assertFalse(group.visible_now(moment + timedelta(seconds=1)))
        group.date_from = moment - timedelta(minutes=1)
        group.date_to = moment + timedelta(minutes=1)
        group.save()
        self.assertTrue(
            ProductGroup.objects.visible_now(moment).filter(pk=group.pk).exists()
        )
        self.assertFalse(
            ProductGroup.objects.visible_now(moment + timedelta(minutes=2)).filter(pk=group.pk).exists()
        )


@override_settings(CACHES=LOC_MEM)
class ProductGroupBestsellerTests(TestCase):
    def test_bestseller_flag_joins_manual_products_on_the_page(self):
        manual = _product('Ручний альбом', 'ruchnyi-albom', 'TOP-1', '300.00')
        flagged = _product(
            'Хіт альбом', 'khit-albom', 'TOP-2', '120.00', is_bestseller=True,
        )
        both = _product(
            'І ручний і топ', 'i-ruchnyi-i-top', 'TOP-3', '80.00', is_bestseller=True,
        )
        plain = _product('Звичайний альбом', 'zvychainyi-albom', 'TOP-4', '50.00')
        hidden = _product(
            'Прихований хіт', 'prykhovanyi-khit', 'TOP-5', '10.00',
            is_active=False, is_bestseller=True,
        )
        group = ProductGroup.objects.create(
            name='Топ продажів',
            slug='top-prodazhiv',
            auto_source=ProductGroup.AUTO_BESTSELLER,
            is_active=True,
            show_in_header=True,
        )
        group.products.add(manual, both)

        picked = set(group.get_products().values_list('pk', flat=True))
        self.assertEqual(picked, {manual.pk, flagged.pk, both.pk, hidden.pk})
        self.assertEqual(group.get_products().filter(pk=both.pk).count(), 1)

        page = self.client.get(reverse('product_group', kwargs={'slug': 'top-prodazhiv'}))
        self.assertEqual(page.status_code, 200)
        body = page.content.decode()
        self.assertIn('Ручний альбом', body)
        self.assertIn('Хіт альбом', body)
        self.assertIn('І ручний і топ', body)
        self.assertNotIn('Звичайний альбом', body)
        self.assertNotIn('Прихований хіт', body)

    def test_manual_source_ignores_bestseller_flag(self):
        flagged = _product(
            'Хіт поза групою', 'khit-poza-hrupoiu', 'TOP-6', '40.00', is_bestseller=True,
        )
        group = ProductGroup.objects.create(
            name='Лише руками',
            slug='lyshe-rukamy',
            auto_source='',
            is_active=True,
        )
        self.assertNotIn(flagged.pk, set(group.get_products().values_list('pk', flat=True)))
        page = self.client.get(reverse('product_group', kwargs={'slug': 'lyshe-rukamy'}))
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('Хіт поза групою', page.content.decode())


@override_settings(CACHES=LOC_MEM)
class ProductAdminGroupsFormTests(TestCase):
    def test_admin_form_saves_reverse_groups(self):
        import products.admin  # noqa: F401

        product = _product('Товар з групами', 'tovar-z-hrupamy', 'ADM-1', '210.00')
        for field in ('name', 'description'):
            base = getattr(product, field)
            for lang in ('uk', 'en', 'ru'):
                attr = f'{field}_{lang}'
                if hasattr(product, attr) and not getattr(product, attr):
                    setattr(product, attr, base)
        product.save()

        keep = ProductGroup.objects.create(name='Лишається', slug='lyshaietsia')
        drop = ProductGroup.objects.create(name='Забрати', slug='zabraty')
        product.groups.add(drop)

        user = get_user_model().objects.create_superuser(
            username='groups-editor',
            email='groups-editor@example.com',
            password='test-pass-123',
        )
        request = RequestFactory().get(f'/admin/products/product/{product.pk}/change/')
        request.user = user
        self.client.force_login(user)
        change_url = reverse('admin:products_product_change', args=[product.pk])
        page = self.client.get(change_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="groups"')
        self.assertContains(page, 'Забрати')

        model_admin = django_admin.site._registry[Product]
        form_class = model_admin.get_form(request, product)
        unbound = form_class(instance=product)
        self.assertEqual(
            {item.pk for item in unbound.fields['groups'].initial},
            {drop.pk},
        )

        bound = form_class(
            _posted_admin_data(unbound, {'groups': [str(keep.pk)]}),
            instance=product,
        )
        self.assertTrue(bound.is_valid(), bound.errors)
        obj = bound.save(commit=False)
        model_admin.save_model(request, obj, bound, True)
        model_admin.save_related(request, bound, [], True)
        self.assertEqual(set(obj.groups.values_list('slug', flat=True)), {'lyshaietsia'})
