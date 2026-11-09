import re
from pathlib import Path

from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from products.filters import filter_products
from products.models import (
    Category, FilterAttribute, FilterGroup, FilterOption, FilterValue, Product,
)

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'catalog-filter-tests',
    }
}


def make_product(**kwargs):
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': 'Опис',
        'price': '100.00',
        'stock_status': 'in_stock',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def _cards(html):
    return html.count('class="product-card"')


def _canonical(html):
    match = re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']',
        html,
        re.I,
    )
    return match.group(1) if match else ''


def _robots(html):
    match = re.search(
        r'<meta\s+name=["\']robots["\']\s+content=["\'](.*?)["\']',
        html,
        re.I,
    )
    return match.group(1) if match else ''


@override_settings(CACHES=LOC_MEM)
class AttributeFilterQueryTests(TestCase):
    def setUp(self):
        self.books = Category.objects.create(name='Книги', slug='books')
        self.leather = Category.objects.create(
            name='Шкіра', slug='leather', parent=self.books,
        )
        self.mini = Category.objects.create(
            name='Міні', slug='mini', parent=self.leather,
        )
        self.gifts = Category.objects.create(name='Подарунки', slug='gifts')
        self.color = FilterAttribute.objects.create(name='Колір', slug='color', position=2)
        self.size = FilterAttribute.objects.create(name='Розмір', slug='size', position=0)
        self.cover = FilterAttribute.objects.create(name='Обкладинка', slug='cover', position=3)
        self.cover.categories.add(self.gifts)
        self.hidden = FilterAttribute.objects.create(
            name='Прихований', slug='hidden', is_active=False,
        )
        self.red = FilterValue.objects.create(attribute=self.color, name='Червоний', slug='red', position=1)
        self.blue = FilterValue.objects.create(attribute=self.color, name='Синій', slug='blue', position=0)
        self.green = FilterValue.objects.create(attribute=self.color, name='Зелений', slug='green')
        self.gold = FilterValue.objects.create(attribute=self.color, name='Золотий', slug='gold')
        self.large = FilterValue.objects.create(attribute=self.size, name='Великий', slug='large')
        self.leather_cover = FilterValue.objects.create(
            attribute=self.cover, name='Шкіряна', slug='leather-cover',
        )
        self.secret = FilterValue.objects.create(attribute=self.hidden, name='Таємний', slug='x')

        self.red_book = make_product(
            name='Червона', slug='red-book', sku='R', price='100.00', badge='sale',
        )
        self.red_book.categories.add(self.books)
        self.blue_book = make_product(name='Синя', slug='blue-book', sku='B', price='40.00')
        self.blue_book.categories.add(self.books)
        self.both = make_product(
            name='Обидва', slug='both-book', sku='BOTH', price='10.00', stock_status='order',
        )
        self.both.categories.add(self.books, self.leather)
        self.child = make_product(name='Дитяча', slug='child-book', sku='CH', price='60.00')
        self.child.categories.add(self.leather)
        self.grand = make_product(name='Мініатюра', slug='mini-book', sku='MN', price='70.00')
        self.grand.categories.add(self.mini)
        self.other = make_product(name='Подарунок', slug='gift-book', sku='GF', price='80.00')
        self.other.categories.add(self.gifts)
        self.inactive = make_product(
            name='Неактивна', slug='inactive-book', sku='OFF', is_active=False,
        )
        self.inactive.categories.add(self.books)
        self.out = make_product(
            name='Немає', slug='out-book', sku='OUT', price='5.00', stock_status='out',
        )
        self.out.categories.add(self.books)

        self.red.products.add(self.red_book, self.both, self.other)
        self.blue.products.add(self.blue_book, self.both)
        self.green.products.add(self.child)
        self.gold.products.add(self.grand)
        self.large.products.add(self.both)
        self.leather_cover.products.add(self.other)
        self.secret.products.add(self.red_book, self.inactive)

    def test_or_and_without_duplicates(self):
        params = QueryDict('f_color=red&f_color=blue')
        matched = filter_products(Product.objects.filter(is_active=True), params)
        self.assertIn('EXISTS', str(matched.query))
        self.assertCountEqual(
            list(matched.values_list('slug', flat=True)),
            ['red-book', 'blue-book', 'both-book', 'gift-book'],
        )
        self.assertEqual(list(matched.values_list('slug', flat=True)).count('both-book'), 1)

        both_only = filter_products(
            Product.objects.all(),
            QueryDict('f_color=red&f_size=large'),
        )
        self.assertEqual(list(both_only.values_list('slug', flat=True)), ['both-book'])

    def test_inactive_attribute_is_ignored(self):
        matched = filter_products(
            Product.objects.filter(is_active=True),
            QueryDict('f_hidden=x'),
        )
        self.assertEqual(matched.count(), Product.objects.filter(is_active=True).count())

    def test_category_page_shows_only_relevant_values(self):
        url = reverse('products:category', kwargs={'slug': 'books'})
        response = self.client.get(url)
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('name="f_color"', html)
        self.assertIn('value="red"', html)
        self.assertIn('value="blue"', html)
        self.assertIn('value="green"', html)
        self.assertNotIn('value="gold"', html)
        self.assertNotIn('name="f_cover"', html)
        self.assertNotIn('name="f_hidden"', html)
        self.assertNotIn('mini-book', html)
        self.assertNotIn('inactive-book', html)
        self.assertLess(html.index('name="f_size"'), html.index('name="f_color"'))
        self.assertEqual(_cards(html), 5)

        child_page = self.client.get(reverse('products:category', kwargs={'slug': 'leather'}))
        child_html = child_page.content.decode()
        self.assertIn('value="gold"', child_html)
        self.assertIn('mini-book', child_html)

    def test_catalog_hides_category_limited_attribute(self):
        response = self.client.get(reverse('products:catalog'), {'q': 'Червона', 'f_color': 'red'})
        html = response.content.decode()
        # Attr filters тепер лише в сайдбарі category_detail; catalog toolbar їх не показує
        self.assertNotIn('name="f_cover"', html)
        self.assertIn('red-book', html)
        self.assertNotIn('blue-book', html)

    def test_price_sort_with_filter(self):
        response = self.client.get(
            reverse('products:category', kwargs={'slug': 'books'}),
            {'f_color': ['red', 'blue'], 'sort': 'price_asc'},
        )
        html = response.content.decode()
        self.assertLess(html.index('both-book'), html.index('blue-book'))
        self.assertLess(html.index('blue-book'), html.index('red-book'))

    def test_duplicate_category_membership_stays_one_card(self):
        response = self.client.get(
            reverse('products:category', kwargs={'slug': 'books'}),
            {'f_size': 'large'},
        )
        self.assertEqual(_cards(response.content.decode()), 1)

    def test_attribute_on_ancestor_is_visible_in_descendants_only(self):
        binding = FilterAttribute.objects.create(name='Палітурка', slug='binding')
        binding.categories.add(self.books)
        sewn = FilterValue.objects.create(attribute=binding, name='Зшита', slug='sewn')
        sewn.products.add(self.grand, self.other)
        self.leather_cover.products.add(self.grand)

        child_html = self.client.get(
            reverse('products:category', kwargs={'slug': 'mini'}),
        ).content.decode()
        self.assertIn('name="f_binding"', child_html)
        self.assertIn('Зшита', child_html)
        self.assertNotIn('name="f_cover"', child_html)

        parent_html = self.client.get(
            reverse('products:category', kwargs={'slug': 'leather'}),
        ).content.decode()
        self.assertIn('name="f_binding"', parent_html)
        self.assertNotIn('name="f_cover"', parent_html)

        sibling_html = self.client.get(
            reverse('products:category', kwargs={'slug': 'gifts'}),
        ).content.decode()
        self.assertNotIn('name="f_binding"', sibling_html)
        self.assertIn('name="f_cover"', sibling_html)

    def test_catalog_shows_only_attributes_bound_nowhere(self):
        # Attr filters тепер лише в сайдбарі category_detail; catalog toolbar їх не рендерить
        html = self.client.get(reverse('products:catalog')).content.decode()
        self.assertNotIn('name="f_cover"', html)
        self.assertNotIn('name="f_hidden"', html)

    def test_value_rows_have_no_product_counts(self):
        html = self.client.get(
            reverse('products:category', kwargs={'slug': 'books'}),
            {'f_color': 'red'},
        ).content.decode()
        # Attr filters тепер в сайдбарі з класом filter-checkbox
        options = re.findall(
            r'<label class="filter-checkbox">(.*?)</label>',
            html,
            re.S,
        )
        self.assertGreaterEqual(len(options), 1)
        for option in options:
            self.assertNotRegex(option, r'\(\s*\d+\s*\)')
        self.assertIn('Колір (1)', html)
        self.assertRegex(
            html,
            r'<button[^>]*type="submit"[^>]*class="[^"]*filter-panel__submit[^"]*"[^>]*>\s*Застосувати\s*</button>',
        )


@override_settings(CACHES=LOC_MEM)
class LegacyFilterGroupTests(TestCase):
    def setUp(self):
        self.books = Category.objects.create(name='Книги', slug='books-legacy')
        self.child = Category.objects.create(
            name='Дитячі', slug='kids-legacy', parent=self.books,
        )
        self.sale = make_product(
            name='Акція', slug='sale-legacy', sku='S1', price='100.00', badge='sale',
        )
        self.sale.categories.add(self.books)
        self.cheap = make_product(
            name='Дешева', slug='cheap-legacy', sku='S2', price='10.00', stock_status='out',
        )
        self.cheap.categories.add(self.books)
        self.kid = make_product(name='Дитяча', slug='kid-legacy', sku='S3', price='30.00')
        self.kid.categories.add(self.child)

    def _groups(self, *, with_subcategory):
        price = FilterGroup.objects.create(name='Бюджет', filter_type='price_range', order=1)
        stock = FilterGroup.objects.create(name='Наявність', filter_type='stock', order=2)
        badge = FilterGroup.objects.create(name='Мітки', filter_type='badge', order=3)
        FilterOption.objects.create(group=stock, label='В наявності', value='in_stock')
        FilterOption.objects.create(group=badge, label='Акція', value='sale')
        if with_subcategory:
            FilterGroup.objects.create(name='Підкатегорії', filter_type='subcategory', order=4)
        return price, stock, badge

    def test_three_existing_group_types_keep_filtering_and_labels(self):
        self._groups(with_subcategory=False)
        self.assertEqual(FilterGroup.objects.count(), 3)
        url = reverse('products:category', kwargs={'slug': 'books-legacy'})
        page = self.client.get(url)
        html = page.content.decode()
        self.assertIn('Бюджет', html)
        self.assertIn('Наявність', html)
        self.assertIn('Мітки', html)
        self.assertNotIn('Підкатегорії', html)

        by_price = self.client.get(url, {'price_min': '50'})
        self.assertIn('sale-legacy', by_price.content.decode())
        self.assertNotIn('cheap-legacy', by_price.content.decode())

        by_stock = self.client.get(url, {'stock': 'in_stock'})
        stock_html = by_stock.content.decode()
        self.assertIn('sale-legacy', stock_html)
        self.assertNotIn('cheap-legacy', stock_html)

        by_badge = self.client.get(url, {'badge': 'sale'})
        badge_html = by_badge.content.decode()
        self.assertIn('sale-legacy', badge_html)
        self.assertNotIn('kid-legacy', badge_html)

    def test_all_four_filter_group_types(self):
        self._groups(with_subcategory=True)
        url = reverse('products:category', kwargs={'slug': 'books-legacy'})
        page = self.client.get(url)
        self.assertIn('Підкатегорії', page.content.decode())
        narrowed = self.client.get(url, {'subcategory': 'kids-legacy'})
        html = narrowed.content.decode()
        self.assertIn('kid-legacy', html)
        self.assertNotIn('sale-legacy', html)


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class FilterSeoTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Ікони', slug='ikoni-filters')
        self.color = FilterAttribute.objects.create(name='Колір', slug='color')
        self.red = FilterValue.objects.create(attribute=self.color, name='Червоний', slug='red')
        for index in range(25):
            product = make_product(
                name=f'Ікона {index}',
                slug=f'icon-{index}',
                sku=f'IC-{index}',
                price='10.00',
            )
            product.categories.add(self.category)
            self.red.products.add(product)

    def test_pagination_without_filters_keeps_canonical_and_index(self):
        url = reverse('products:category', kwargs={'slug': 'ikoni-filters'})
        page = self.client.get(url, {'page': 2, 'sort': 'price_asc'})
        html = page.content.decode()
        canon = _canonical(html)
        self.assertIn('page=2', canon)
        self.assertNotIn('f_', canon)
        self.assertNotIn('sort=', canon)
        self.assertEqual(_robots(html), 'index, follow')

        catalog = self.client.get(reverse('products:catalog'), {'page': 2})
        catalog_canon = _canonical(catalog.content.decode())
        self.assertIn('/catalog/?page=2', catalog_canon)
        self.assertEqual(_robots(catalog.content.decode()), 'index, follow')

    def test_facet_url_is_noindex_and_canonical_without_filters_or_page(self):
        url = reverse('products:category', kwargs={'slug': 'ikoni-filters'})
        page = self.client.get(url, {'f_color': 'red', 'page': 2, 'sort': 'newest'})
        html = page.content.decode()
        canon = _canonical(html)
        self.assertTrue(canon.endswith('/catalog/ikoni-filters/'))
        self.assertNotIn('page=', canon)
        self.assertNotIn('f_', canon)
        self.assertEqual(_robots(html), 'noindex,follow')
        self.assertIn('f_color=red', html)

        catalog = self.client.get(reverse('products:catalog'), {'f_color': 'red', 'page': 2})
        catalog_html = catalog.content.decode()
        self.assertTrue(_canonical(catalog_html).endswith('/catalog/'))
        self.assertNotIn('page=', _canonical(catalog_html))
        self.assertEqual(_robots(catalog_html), 'noindex,follow')

    def test_empty_facet_param_does_not_noindex(self):
        url = reverse('products:category', kwargs={'slug': 'ikoni-filters'})
        page = self.client.get(url, {'f_color': '', 'page': 2})
        html = page.content.decode()
        self.assertIn('page=2', _canonical(html))
        self.assertEqual(_robots(html), 'index, follow')


class AttributeFilterApplyTests(SimpleTestCase):
    def test_script_does_not_submit_on_change_and_template_has_apply(self):
        root = Path(__file__).resolve().parents[2]
        script = (root / 'static/js/catalog-filters.js').read_text(encoding='utf-8')
        code = re.sub(r'/\*[\s\S]*?\*/', '', script)
        code = re.sub(r'//.*?$', '', code, flags=re.M)
        self.assertIsNone(re.search(r'requestSubmit\s*\(', code))
        self.assertIsNone(re.search(r'\.submit\s*\(', code))
        self.assertIsNone(re.search(
            r"""addEventListener\(\s*['"]change['"][\s\S]{0,600}?(?:\.submit\s*\(|requestSubmit\s*\()""",
            code,
        ))

        # Attr filters тепер в filter_panel, кнопка Застосувати — filter-panel__submit
        template = (
            root / 'templates/products/partials/filter_panel.html'
        ).read_text(encoding='utf-8')
        self.assertRegex(
            template,
            r'<button[^>]*\btype="submit"[^>]*class="[^"]*filter-panel__submit[^"]*"[^>]*>\s*\{%[^%]*Застосувати[^%]*%\}\s*</button>',
        )
        self.assertNotRegex(
            template,
            r'onchange\s*=\s*["\'][^"\']*(?:\.submit\s*\(|requestSubmit)',
        )

    def test_filter_panel_hx_trigger_includes_submit(self):
        """hx-trigger повинен містити 'submit', щоб кнопка «Застосувати» йшла через htmx."""
        root = Path(__file__).resolve().parents[2]
        template = (
            root / 'templates/products/partials/filter_panel.html'
        ).read_text(encoding='utf-8')
        self.assertRegex(
            template,
            r'hx-trigger=["\'][^"\']*\bsubmit\b',
            'hx-trigger у filter_panel.html має включати "submit"',
        )

    def test_scroll_has_no_mobile_gate(self):
        """scrollIntoView не повинен бути захований за matchMedia/innerWidth/isMobile."""
        root = Path(__file__).resolve().parents[2]
        script = (root / 'static/js/catalog-filters.js').read_text(encoding='utf-8')
        code = re.sub(r'/\*[\s\S]*?\*/', '', script)
        code = re.sub(r'//.*?$', '', code, flags=re.M)
        self.assertIsNone(
            re.search(r'matchMedia|innerWidth|isMobile', code),
            'catalog-filters.js не повинен мати mobile-only gate для scrollIntoView',
        )
        self.assertIsNotNone(
            re.search(r'scrollIntoView', code),
            'catalog-filters.js повинен викликати scrollIntoView',
        )


LEGACY_PANEL_MARKERS = (
    '<aside class="catalog-sidebar">',
    'id="open-filters"',
    'id="mobile-filters"',
    'class="filter-panel"',
    'filter-panel__submit',
)

SORT_HX_INCLUDE = (
    'hx-include=".filter-panel input[name], .filter-panel select[name]"'
)


@override_settings(CACHES=LOC_MEM)
class LegacyFilterPanelVisibilityTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Книги', slug='books-panel')
        self.sale = make_product(
            name='Акція', slug='sale-panel', sku='P1', price='100.00', badge='sale',
        )
        self.sale.categories.add(self.category)
        self.cheap = make_product(
            name='Дешева', slug='cheap-panel', sku='P2', price='10.00', stock_status='out',
        )
        self.cheap.categories.add(self.category)

    def _page(self, name='category', query=None):
        if name == 'category':
            url = reverse('products:category', kwargs={'slug': self.category.slug})
        else:
            url = reverse('products:catalog')
        return self.client.get(url, query or {}).content.decode()

    def test_without_groups_category_and_catalog_omit_legacy_panel(self):
        category_html = self._page()
        catalog_html = self._page('catalog')
        for html in (category_html, catalog_html):
            for marker in LEGACY_PANEL_MARKERS:
                self.assertNotIn(marker, html)
            self.assertNotIn('id="filter-overlay"', html)
        self.assertIn('catalog-layout--full', category_html)
        self.assertNotIn('product-grid--with-sidebar', category_html)
        self.assertIn(SORT_HX_INCLUDE, category_html)
        self.assertIn('name="sort"', category_html)

    def test_groups_without_renderable_options_stay_hidden(self):
        stock = FilterGroup.objects.create(name='Наявність', filter_type='stock', order=1)
        FilterOption.objects.create(
            group=stock, label='В наявності', value='in_stock', is_active=False,
        )
        FilterGroup.objects.create(name='Підкатегорії', filter_type='subcategory', order=2)
        FilterGroup.objects.create(
            name='Вимкнений бюджет', filter_type='price_range', order=3, is_active=False,
        )
        other = Category.objects.create(name='Інша', slug='other-panel')
        foreign = FilterGroup.objects.create(name='Чужий бюджет', filter_type='price_range', order=4)
        foreign.categories.add(other)

        html = self._page()
        for marker in LEGACY_PANEL_MARKERS:
            self.assertNotIn(marker, html)
        self.assertIn('catalog-layout--full', html)
        self.assertNotIn('Підкатегорії', html)
        self.assertNotIn('Чужий бюджет', html)
        self.assertNotIn('name="price_min"', html)

    def test_three_production_groups_show_working_sidebar(self):
        stock = FilterGroup.objects.create(name='Наявність', filter_type='stock', order=2)
        badge = FilterGroup.objects.create(name='Мітки', filter_type='badge', order=3)
        FilterGroup.objects.create(name='Бюджет', filter_type='price_range', order=1)
        FilterOption.objects.create(group=stock, label='В наявності', value='in_stock')
        FilterOption.objects.create(group=badge, label='Акція', value='sale')
        self.assertEqual(FilterGroup.objects.count(), 3)

        html = self._page()
        for marker in LEGACY_PANEL_MARKERS:
            self.assertIn(marker, html)
        self.assertIn('id="filter-overlay"', html)
        self.assertIn('product-grid--with-sidebar', html)
        self.assertNotIn('catalog-layout--full', html)
        self.assertIn(SORT_HX_INCLUDE, html)
        self.assertEqual(html.count('class="filter-panel"'), 2)
        self.assertEqual(html.count('filter-panel__submit'), 2)
        self.assertIn('Бюджет', html)
        self.assertIn('Наявність', html)
        self.assertIn('Мітки', html)
        self.assertIn('name="price_min"', html)
        self.assertIn('value="in_stock"', html)
        self.assertIn('value="sale"', html)
        self.assertRegex(
            html,
            r'<button[^>]*type="submit"[^>]*class="[^"]*filter-panel__submit[^"]*"[^>]*>\s*Застосувати\s*</button>',
        )

        catalog_html = self._page('catalog')
        for marker in LEGACY_PANEL_MARKERS:
            self.assertNotIn(marker, catalog_html)

        filtered = self._page(query={'price_min': '50'})
        self.assertIn('sale-panel', filtered)
        self.assertNotIn('cheap-panel', filtered)
        self.assertIn('<aside class="catalog-sidebar">', filtered)

        by_stock = self._page(query={'stock': 'in_stock'})
        self.assertIn('sale-panel', by_stock)
        self.assertNotIn('cheap-panel', by_stock)


@override_settings(CACHES=LOC_MEM, SITE_DOMAIN='example.test', SITE_PROTOCOL='https')
class FilterPaginationUrlTests(TestCase):
    """Фільтри в URL + пагінація зберігає f_*/sort; HTMX оновлює пагінацію OOB."""

    def setUp(self):
        self.category = Category.objects.create(name='Шахи', slug='shahi-filter-pag')
        self.attr = FilterAttribute.objects.create(name='Комплектація', slug='komplektaciya')
        self.tables = FilterValue.objects.create(
            attribute=self.attr, name='Шахові столи', slug='shahovi-stoli',
        )
        self.sets = FilterValue.objects.create(
            attribute=self.attr, name='Шахи', slug='shahi',
        )
        self.table_products = []
        for index in range(30):
            product = make_product(
                name=f'Стіл {index}',
                slug=f'table-pag-{index}',
                sku=f'TP-{index}',
                price=f'{10 + index}.00',
            )
            product.categories.add(self.category)
            self.tables.products.add(product)
            self.table_products.append(product)
        for index in range(10):
            product = make_product(
                name=f'Набір {index}',
                slug=f'set-pag-{index}',
                sku=f'SP-{index}',
                price='5.00',
            )
            product.categories.add(self.category)
            self.sets.products.add(product)
        self.url = reverse('products:category', kwargs={'slug': self.category.slug})

    def test_filtered_page2_returns_only_matching_products(self):
        response = self.client.get(
            self.url,
            {'f_komplektaciya': 'shahovi-stoli', 'page': 2},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(_cards(html), 6)
        self.assertIn('table-pag-24', html)
        self.assertNotIn('set-pag-', html)

    def test_pagination_links_preserve_filters_sort_and_multivalue(self):
        response = self.client.get(
            self.url,
            {
                'f_komplektaciya': ['shahovi-stoli', 'shahi'],
                'sort': 'price_asc',
                'page': 2,
            },
        )
        html = response.content.decode()
        self.assertIn('f_komplektaciya=shahovi-stoli', html)
        self.assertIn('f_komplektaciya=shahi', html)
        self.assertIn('sort=price_asc', html)
        self.assertRegex(
            html,
            r'href="\?[^"]*f_komplektaciya=shahovi-stoli[^"]*page=1"',
        )
        self.assertRegex(
            html,
            r'href="\?[^"]*f_komplektaciya=shahi[^"]*page=1"',
        )
        self.assertRegex(html, r'href="\?[^"]*sort=price_asc[^"]*page=1"')
        # 40 товарів → 2 сторінки; лінк «1» і ««» ведуть на page=1 з фільтрами
        self.assertIn('page=1', html)
        self.assertNotIn('set-pag-9', html)  # page 2 при price_asc — дорожчі столи

    def test_htmx_filter_response_includes_pagination_with_filter_params(self):
        response = self.client.get(
            self.url,
            {
                'f_komplektaciya': ['shahovi-stoli', 'shahi'],
                'sort': 'newest',
                'price_min': '',
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="catalog-pagination"', html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn('catalog-pagination', html)
        self.assertIn('f_komplektaciya=shahovi-stoli', html)
        self.assertIn('f_komplektaciya=shahi', html)
        self.assertIn('sort=newest', html)
        self.assertIn('page=2', html)
        self.assertNotIn('price_min=', html)
        push = response.headers.get('HX-Push-Url') or response.get('HX-Push-Url')
        self.assertEqual(
            push,
            f'{self.url}?f_komplektaciya=shahovi-stoli&f_komplektaciya=shahi&sort=newest',
        )
        self.assertNotIn('page=', push)

    def test_htmx_push_url_drops_page_and_empty_params(self):
        response = self.client.get(
            self.url,
            {'f_komplektaciya': 'shahovi-stoli', 'page': '2', 'price_max': ''},
            HTTP_HX_REQUEST='true',
        )
        push = response.headers.get('HX-Push-Url') or response.get('HX-Push-Url')
        self.assertEqual(push, f'{self.url}?f_komplektaciya=shahovi-stoli')

    def test_seo_unchanged_for_filtered_and_paginated_urls(self):
        cases = [
            ({}, 'index, follow', True),
            ({'page': 2}, 'index, follow', True),
            ({'f_komplektaciya': 'shahovi-stoli'}, 'noindex,follow', False),
            (
                {'f_komplektaciya': 'shahovi-stoli', 'page': 2},
                'noindex,follow',
                False,
            ),
        ]
        for query, robots, page_in_canonical in cases:
            with self.subTest(query=query):
                html = self.client.get(self.url, query).content.decode()
                self.assertEqual(_robots(html), robots)
                canon = _canonical(html)
                self.assertTrue(canon.endswith(f'/catalog/{self.category.slug}/') or 'page=' in canon)
                if query.get('f_komplektaciya'):
                    self.assertTrue(canon.rstrip('/').endswith(self.category.slug))
                    self.assertNotIn('f_', canon)
                    self.assertNotIn('page=', canon)
                elif page_in_canonical and int(query.get('page', 1)) >= 2:
                    self.assertIn('page=2', canon)
                    self.assertNotIn('f_', canon)

    def test_filter_panel_has_hx_push_url(self):
        root = Path(__file__).resolve().parents[2]
        template = (
            root / 'templates/products/partials/filter_panel.html'
        ).read_text(encoding='utf-8')
        self.assertIn('hx-push-url="true"', template)
        category = (
            root / 'templates/products/category_detail.html'
        ).read_text(encoding='utf-8')
        self.assertIn('hx-push-url="true"', category)
        self.assertIn('id="catalog-pagination"', category)
