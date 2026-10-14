"""VIP / Middle feeds + незмінність google-merchant.xml."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from products.feed_segments import (
    RELIGIOUS_TEXT_RE,
    build_segment_feed_xml,
    find_religious_matches,
    format_religious_text_reason,
    middle_queryset,
    product_is_vip,
    product_matches_religious_text,
    vip_queryset,
)
from products.feed_utils import build_google_merchant_xml, get_base_price
from products.models import Category, Product, ProductImage

LOC_MEM = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'feed-segment-tests',
    }
}
G_NS = {'g': 'http://base.google.com/ns/1.0'}


def _jpeg() -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new('RGB', (20, 20), (200, 40, 40)).save(buf, format='JPEG')
    return SimpleUploadedFile('p.jpg', buf.getvalue(), content_type='image/jpeg')


def _add_image(product: Product) -> None:
    ProductImage.objects.create(product=product, image=_jpeg())


def _product(**kwargs) -> Product:
    defaults = {
        'name': 'Товар',
        'slug': 'tovar',
        'sku': 'SKU-1',
        'description': '<p>Опис товару</p>',
        'price': Decimal('100.00'),
        'is_active': True,
        'stock_status': 'in_stock',
    }
    defaults.update(kwargs)
    product = Product.objects.create(**defaults)
    _add_image(product)
    return product


@override_settings(
    CACHES=LOC_MEM,
    SITE_DOMAIN='ofion.test',
    SITE_PROTOCOL='https',
)
class FeedSegmentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.books = Category.objects.create(name='Книги', slug='knyhy')
        self.book_sub = Category.objects.create(
            name='Класика', slug='klasyka', parent=self.books,
        )
        self.diaries = Category.objects.create(name='Щоденники', slug='shchodennyky')
        self.pens = Category.objects.create(name='Ручки подарункові', slug='ruchky')
        self.cabinet = Category.objects.create(name='Кабінет керівника', slug='kabinet')
        self.pens.parent = self.cabinet
        self.pens.save()
        self.icons = Category.objects.create(name='Ікони', slug='ikoni')
        self.icon_sub = Category.objects.create(
            name='Ікони святих', slug='ikoni-svyatih', parent=self.icons,
        )

    def test_base_price_uses_old_price_when_higher(self):
        p = _product(
            slug='sale', sku='SALE-1',
            price=Decimal('8000.00'), old_price=Decimal('12000.00'),
        )
        self.assertEqual(get_base_price(p), Decimal('12000.00'))
        p2 = _product(slug='plain', sku='PLAIN-1', price=Decimal('5000.00'))
        self.assertEqual(get_base_price(p2), Decimal('5000.00'))

    def test_exactly_10000_is_vip(self):
        p = _product(slug='edge', sku='EDGE-10K', price=Decimal('10000.00'))
        p.categories.add(self.pens)
        self.assertTrue(product_is_vip(p))
        self.assertIn(p, list(vip_queryset()))
        self.assertNotIn(p, list(middle_queryset()))

    def test_below_10000_non_book_is_middle(self):
        p = _product(slug='pen', sku='PEN-1', price=Decimal('9999.99'))
        p.categories.add(self.pens)
        self.assertFalse(product_is_vip(p))
        self.assertIn(p, list(middle_queryset()))

    def test_book_subcategory_is_vip_any_price(self):
        p = _product(slug='classic', sku='BOOK-1', price=Decimal('50.00'))
        p.categories.add(self.book_sub)
        self.assertTrue(product_is_vip(p))
        self.assertIn(p, list(vip_queryset()))

    def test_diary_is_vip(self):
        p = _product(slug='diary', sku='DIA-1', price=Decimal('200.00'))
        p.categories.add(self.diaries)
        self.assertIn(p, list(vip_queryset()))

    def test_diary_subcategory_under_cabinet_is_vip_any_price(self):
        """Щоденники А4/А5 під «Кабінет керівника» — VIP, ніколи Middle."""
        diary_a5 = Category.objects.create(
            name='Щоденники А5', slug='shodenniki-a5', parent=self.cabinet,
        )
        diary_a4 = Category.objects.create(
            name='Щоденники А4', slug='shodenniki-a4', parent=self.cabinet,
        )
        for i, cat in enumerate((diary_a5, diary_a4)):
            p = _product(
                slug=f'diary-nested-{i}', sku=f'DIA-N-{i}',
                price=Decimal('6860.00'),
            )
            p.categories.add(cat)
            self.assertTrue(product_is_vip(p), cat.name)
            self.assertIn(p, list(vip_queryset()))
            self.assertNotIn(p, list(middle_queryset()))

    def test_books_collection_and_authors_paths_are_vip(self):
        """«Колекція книг» / «Книги та автори» на будь-якій глибині — VIP."""
        collection = Category.objects.create(
            name='Колекція книг', slug='kolektsiya-knyg',
        )
        military = Category.objects.create(
            name='Військова справа', slug='vijskova', parent=collection,
        )
        authors = Category.objects.create(
            name='Книги та автори', slug='knigi-ta-avtory',
        )
        shevchenko = Category.objects.create(
            name='Тарас Шевченко', slug='shevchenko', parent=authors,
        )
        for i, cat in enumerate((military, shevchenko, collection, authors)):
            p = _product(
                slug=f'book-path-{i}', sku=f'BK-P-{i}',
                price=Decimal('50.00'),
            )
            p.categories.add(cat)
            self.assertTrue(product_is_vip(p), cat.name)
            self.assertIn(p, list(vip_queryset()))
            self.assertNotIn(p, list(middle_queryset()))

    def test_sale_base_price_classifies_vip(self):
        # price 9000, old 11000 → base 11000 → VIP
        p = _product(
            slug='vip-sale', sku='VS-1',
            price=Decimal('9000.00'), old_price=Decimal('11000.00'),
        )
        p.categories.add(self.pens)
        self.assertIn(p, list(vip_queryset()))

    def test_religious_exclusion_icons_and_keywords(self):
        icon_prod = _product(name='Декор стіни', slug='icon-prod', sku='IC-1')
        icon_prod.categories.add(self.icon_sub)

        bible = _product(name='Подарункова Біблія', slug='bible', sku='BIB-1', price=Decimal('15000'))
        bible.categories.add(self.pens)

        avtora = _product(
            name='Книга автора класика', slug='avtora', sku='AV-1', price=Decimal('500'),
        )
        avtora.categories.add(self.pens)

        self.assertNotIn(icon_prod, list(vip_queryset()) + list(middle_queryset()))
        self.assertNotIn(bible, list(vip_queryset()) + list(middle_queryset()))
        self.assertIn(avtora, list(middle_queryset()))

    def test_tora_not_in_avtora(self):
        self.assertIsNone(RELIGIOUS_TEXT_RE.search('книга автора класика'))
        self.assertIsNotNone(RELIGIOUS_TEXT_RE.search('Тора в шкірі'))
        self.assertFalse(product_matches_religious_text(
            type('P', (), {
                'name': 'Книга автора',
                'name_uk': '', 'name_ru': '', 'name_en': '',
                'description': '', 'description_uk': '', 'description_ru': '',
                'description_en': '',
                'short_description': '', 'short_description_uk': '',
                'short_description_ru': '', 'short_description_en': '',
            })()
        ))

    def test_icon_not_iconic(self):
        self.assertIsNone(RELIGIOUS_TEXT_RE.search('iconic design notebook'))
        self.assertIsNotNone(RELIGIOUS_TEXT_RE.search('wooden icon frame'))

    def test_biblioteka_not_excluded(self):
        p = _product(name='Бібліотека класики', slug='lib', sku='LIB-1', price=Decimal('500'))
        p.categories.add(self.pens)
        self.assertIn(p, list(middle_queryset()))

    def test_religious_keyword_false_positive_regression(self):
        """Не-релігійні назви не виключаються; релігійні — так."""
        keep_titles = (
            'Бібліотека української літератури у 14 томах',
            'Історія запорізьких козаків',
            'Артур Конан Дойль в 4-х томах',
            'Глобус бар Карта світу',
            'Шахи Italfama',
            'Скіфська пектораль',
            'Конституція України з Тризубом',
            'Гаррі Поттер у 7 томах',
            'Офісне крісло',
            'Шкіряне кресло',
        )
        exclude_titles = (
            'Біблія',
            'Святе Євангеліє',
            'Молитовник',
            'Молитвослов',
            'триптих',
            'Ікона',
            'Тора',
            'Хрест наперсний',
        )
        for i, title in enumerate(keep_titles):
            with self.subTest(title=title):
                self.assertEqual(find_religious_matches(title), [])
                p = _product(
                    name=title, slug=f'keep-{i}', sku=f'KEEP-{i}',
                    price=Decimal('500'),
                )
                p.categories.add(self.pens)
                self.assertIn(p, list(middle_queryset()))
        for i, title in enumerate(exclude_titles):
            with self.subTest(title=title):
                self.assertTrue(find_religious_matches(title))
                p = _product(
                    name=title, slug=f'ex-{i}', sku=f'EXREL-{i}',
                    price=Decimal('500'),
                )
                p.categories.add(self.pens)
                self.assertNotIn(p, list(vip_queryset()) + list(middle_queryset()))

    def test_religious_reason_includes_matched_substrings(self):
        matches = find_religious_matches('Подарункова Біблія і Молитовник')
        self.assertIn('Біблія', matches)
        reason = format_religious_text_reason(matches)
        self.assertTrue(reason.startswith('Релігійні ключові слова в назві/описі ('))
        self.assertIn('Біблія', reason)

    def test_html_icon_attr_not_false_positive(self):
        """Теги HTML (class=icon, src=cross) не дають хибного спрацювання."""
        p = _product(
            name='Глобус бар Карта світу',
            slug='globe-html', sku='GLB-1', price=Decimal('500'),
            description='<p class="icon">Опис</p><img src="/media/cross.png" alt="x">',
        )
        p.categories.add(self.pens)
        self.assertFalse(product_matches_religious_text(p))
        self.assertIn(p, list(middle_queryset()))

    def test_promovy_secular_blurb_not_excluded(self):
        """Світські «Промови»: релігійних/біблійних у описі — не виключення."""
        self.assertEqual(find_religious_matches('релігійних діячів різних епох'), [])
        self.assertEqual(find_religious_matches('від біблійних пророків до політиків'), [])
        p = _product(
            name='Подарункова книга Промови, що змінили світ',
            slug='promovy', sku='PROM-1', price=Decimal('500'),
            description='політиків, мислителів, громадських і релігійних діячів',
        )
        p.categories.add(self.pens)
        self.assertIn(p, list(middle_queryset()))

    def test_religious_new_stems_and_religiynogo_mystetstva(self):
        """архангел/архістратиг/храм/церков/православ + релігійного мистецтва."""
        true_pos = (
            'Архангел Михаїл',
            'Архістратиг Михаїл',
            'Ікона для храму',
            'Церковний календар',
            'Православний хрест',
            'Святий Миколай',
            'Святе письмо',
        )
        for i, title in enumerate(true_pos):
            with self.subTest(title=title):
                self.assertTrue(find_religious_matches(title), title)
        self.assertTrue(find_religious_matches('витвір релігійного мистецтва'))
        self.assertEqual(find_religious_matches('святковий набір'), [])
        self.assertEqual(find_religious_matches('велике свято міста'), [])
        # род. відм. «свято» → «свята» у маркетингових списках — не виключення
        self.assertEqual(
            find_religious_matches('На державні свята \n Для домашньої бібліотеки'),
            [],
        )
        self.assertEqual(find_religious_matches('професійного свята чи ювілею'), [])
        # «храмів» (Єгипет / світське) — ні; «храму» — так
        self.assertEqual(find_religious_matches('фараонів, храмів та легенд'), [])
        self.assertTrue(find_religious_matches('ікона для храму'))
        self.assertIsNone(RELIGIOUS_TEXT_RE.search('суперхрамовий'))

        arch = _product(
            name='Архангел Михаїл', slug='arch-1', sku='779404',
            price=Decimal('500'),
            description='зразок релігійного мистецтва',
        )
        arch.categories.add(self.pens)
        self.assertNotIn(arch, list(vip_queryset()) + list(middle_queryset()))

    def test_religious_extra_true_positives(self):
        """Ангел / ангельськ* / Соломон / Buddha / притч — виключення з VIP/Middle."""
        true_pos = (
            ('7171', 'Садова фігура Ангел із серцем'),
            ('902', 'Садова фігура Ангел хлопчик'),
            ('406', 'Садова фігура Ангел дівчинка'),
            ('8018', 'Ангельська варта'),
            ('6191', 'Книга мудрості Соломона в шкіряній палітурці'),
            ('6192', 'Книга мудрості Соломона Подарункове видання'),
            ('6193', 'Книга мудрості Соломона на підставці'),
            ('47752', 'CowParade Buddha'),
            ('6115', 'Подарункова книга притч «Чаша мудрості»'),
            ('6109', 'Подарункова книга притч у білій шкірі'),
            ('BUDD-UK', 'Статуетка Будда'),
        )
        for sku, title in true_pos:
            with self.subTest(sku=sku, title=title):
                self.assertTrue(find_religious_matches(title), title)
                p = _product(
                    name=title, slug=f'tp-{sku}', sku=sku, price=Decimal('500'),
                )
                p.categories.add(self.pens)
                self.assertTrue(product_matches_religious_text(p), title)
                self.assertNotIn(p, list(vip_queryset()) + list(middle_queryset()))

    def test_religious_extra_false_positives_guarded(self):
        """FP з scratch DB: ангел/притч у description; Ангелина; latin angel*; буддь."""
        # Title без ангел/притч — description згадує (Анатоль Франс / горщик / Сковорода)
        desc_only_fp = (
            (
                'Зібрання творів Анатоля Франса у 5 томах',
                'Том 5. Повстання ангелів. Новели.',
            ),
            (
                'Садовий горщик квітковий великий',
                'вишуканий дизайн із рельєфними ангелами',
            ),
            (
                'Зібрання творів Григорія Сковороди у 2 томах',
                'філософські трактати, байки, притчі, листи',
            ),
            (
                'Григорій Сковорода. Найкраще',
                'Притчі з глибоким змістом і символізмом',
            ),
        )
        for i, (title, desc) in enumerate(desc_only_fp):
            with self.subTest(title=title):
                p = _product(
                    name=title, slug=f'fp-desc-{i}', sku=f'FP-DESC-{i}',
                    price=Decimal('500'), description=desc,
                )
                p.categories.add(self.pens)
                self.assertFalse(product_matches_religious_text(p), title)
                self.assertIn(p, list(middle_queryset()))

        # Імена / latin / випадкові стеми
        keep_titles = (
            'Щоденник Ангелини',
            'Ангелина Ковальова — мемуари',
            'Los Angeles skyline notebook',
            'Angelic design cover',
            'Будьдьовий набір канцтоварів',
        )
        for i, title in enumerate(keep_titles):
            with self.subTest(title=title):
                self.assertEqual(find_religious_matches(title), [], title)
                p = _product(
                    name=title, slug=f'fp-title-{i}', sku=f'FP-T-{i}',
                    price=Decimal('500'),
                )
                p.categories.add(self.pens)
                self.assertIn(p, list(middle_queryset()))

    def test_live_feed_false_positives_restored(self):
        """6 SKU з live merchant: не релігійні; 8018 лишається excluded."""
        authors = Category.objects.create(
            name='Книги та автори', slug='knigi-ta-avtory',
        )
        shevchenko = Category.objects.create(
            name='Тарас Шевченко', slug='shevchenko', parent=authors,
        )
        collection = Category.objects.create(
            name='Колекція книг', slug='kolektsiya-knyg',
        )
        military = Category.objects.create(
            name='Військова справа', slug='vijskova', parent=collection,
        )
        sets_cat = Category.objects.create(
            name='Стильні набори', slug='stylni-nabory', parent=self.cabinet,
        )
        souvenirs = Category.objects.create(
            name='Сувенірна зброя', slug='suvenirna-zbroya',
        )
        cows = Category.objects.create(
            name='Фігурки корів CowParade', slug='cowparade',
        )

        cases = (
            (
                '1017',
                'Подарункова книга Кобзар Тараса Шевченка',
                Decimal('14710'),
                shevchenko,
                'родинної бібліотеки й передаватися. без прив&rsquo;язки до '
                'конкретного свята &mdash; на знак поваги',
                'VIP',
            ),
            (
                '1328',
                'Подарункова книга Історія Українського війська',
                Decimal('9600'),
                military,
                'архівні та іконографічні матеріали, що суттєво розширюють контекст',
                'VIP',
            ),
            (
                '6033',
                'Подарунковий набір «Герб Києва» — щоденник А5 та ручка TENSO',
                Decimal('9550'),
                sets_cat,
                'зображення історичного герба Києва з Архангелом Михаїлом. '
                'Архангел Михаїл уособлює захист',
                'Middle',
            ),
            (
                '6111',
                'Сувенір Пістолет Форт та емблема СБУ',
                Decimal('7770'),
                souvenirs,
                'які присвятили своє життя службі. емблема у вигляді '
                'прямого рівностороннього хреста синього кольору',
                'Middle',
            ),
            (
                '6066',
                'Сувенір Пістолет ТТ та емблема СБУ',
                Decimal('7010'),
                souvenirs,
                'які присвятили своє життя служінню. емблема СБУ виконана '
                'у вигляді рівностороннього хреста',
                'Middle',
            ),
            (
                '46737',
                'CowParade «Heartstanding Cow»',
                Decimal('6480'),
                cows,
                'присвячена любові. Особливо доречно на День святого Валентина, '
                'річницю знайомства',
                'Middle',
            ),
        )
        for sku, title, price, cat, desc, segment in cases:
            with self.subTest(sku=sku):
                p = _product(
                    name=title, slug=f'restore-{sku}', sku=sku,
                    price=price, description=f'<p>{desc}</p>',
                )
                p.categories.add(cat)
                self.assertFalse(product_matches_religious_text(p), sku)
                if segment == 'VIP':
                    self.assertIn(p, list(vip_queryset()), sku)
                    self.assertNotIn(p, list(middle_queryset()), sku)
                else:
                    self.assertIn(p, list(middle_queryset()), sku)
                    self.assertNotIn(p, list(vip_queryset()), sku)

        angel_guard = _product(
            name='Художня композиція з ангельською вартою роду',
            slug='8018-guard', sku='8018', price=Decimal('15000'),
            description='символ української духовності',
        )
        angel_guard.categories.add(self.pens)
        self.assertTrue(product_matches_religious_text(angel_guard))
        self.assertNotIn(angel_guard, list(vip_queryset()) + list(middle_queryset()))

    def test_iconography_and_valentine_and_mdash_not_religious(self):
        self.assertEqual(find_religious_matches('архівні та іконографічні матеріали'), [])
        self.assertEqual(find_religious_matches('День святого Валентина, річниця'), [])
        self.assertEqual(
            find_religious_matches('конкретного свята &mdash; на знак поваги'),
            [],
        )
        self.assertEqual(find_religious_matches('родинної бібліотеки'), [])
        self.assertEqual(find_religious_matches('які присвятили своє життя'), [])
        # TP лишаються
        self.assertTrue(find_religious_matches('Святий Миколай'))
        self.assertTrue(find_religious_matches('деревʼяна ікона'))
        self.assertTrue(find_religious_matches('Хрест наперсний'))

    def test_archangel_cross_description_with_heraldic_window(self):
        """архангел/хрест у desc: гербове вікно → IN; реліг. контекст/title → OUT."""
        # Гербові / держ. снипети (як на live сторінках) — не виключення
        heraldic_ok = (
            'зображення історичного герба Києва з Архангелом Михаїлом. '
            'Архангел Михаїл уособлює захист',
            'Архангел Михаїл на гербі Києва',
            'емблема у вигляді прямого рівностороннього хреста синього кольору',
            'емблема СБУ виконана у вигляді рівностороннього хреста',
            'нагороджений хрестом за заслуги перед Україною',
            'військовий орден із зображенням хреста',
        )
        for snippet in heraldic_ok:
            with self.subTest(snippet=snippet[:48]):
                self.assertEqual(find_religious_matches(snippet), [], snippet)

        # Title / релігійний контекст — завжди OUT
        self.assertTrue(find_religious_matches('Архістратиг Михаїл'))
        self.assertTrue(find_religious_matches('Хрест наперсний'))
        self.assertTrue(find_religious_matches(
            'наперсний хрест із зображенням архангела на гербі',
        ))
        self.assertTrue(find_religious_matches(
            'ікона архангела Михаїла для домашньої молитви',
        ))

        g03 = _product(
            name='Архістратиг Михаїл', slug='g03', sku='G03',
            price=Decimal('500'),
            description='подарункова статуетка',
        )
        g03.categories.add(self.pens)
        self.assertTrue(product_matches_religious_text(g03))
        self.assertNotIn(g03, list(vip_queryset()) + list(middle_queryset()))

        # Лише desc, релігійний контекст (ікон/молит) — OUT навіть біля «символ»
        rel_desc = _product(
            name='Подарункова статуетка', slug='arch-rel-desc', sku='ARCH-REL',
            price=Decimal('500'),
            description='деревʼяна ікона архангела Михаїла для молитви',
        )
        rel_desc.categories.add(self.pens)
        self.assertTrue(product_matches_religious_text(rel_desc))
        self.assertNotIn(rel_desc, list(vip_queryset()) + list(middle_queryset()))

        # Лише desc без гербового вікна — OUT
        bare = _product(
            name='Декоративна фігура', slug='arch-bare', sku='ARCH-BARE',
            price=Decimal('500'),
            description='фігура архангела Михаїла з бронзи',
        )
        bare.categories.add(self.pens)
        self.assertTrue(product_matches_religious_text(bare))
        self.assertNotIn(bare, list(vip_queryset()) + list(middle_queryset()))

        # Title з «хрест» ніколи не звільняється гербом у desc
        titled = _product(
            name='Хрест сувенірний', slug='cross-title', sku='CROSS-T',
            price=Decimal('500'),
            description='емблема СБУ та герб на підставці',
        )
        titled.categories.add(self.pens)
        self.assertTrue(product_matches_religious_text(titled))
        self.assertNotIn(titled, list(vip_queryset()) + list(middle_queryset()))

    def test_segment_last_build_date_present_legacy_absent(self):
        p = _product(slug='lbd', sku='LBD-1', price=Decimal('500'))
        p.categories.add(self.pens)
        vip_xml = build_segment_feed_xml('VIP')
        mid_xml = build_segment_feed_xml('Middle')
        legacy = build_google_merchant_xml()
        for xml in (vip_xml, mid_xml):
            root = ET.fromstring(xml)
            lbd = root.find('channel/lastBuildDate')
            self.assertIsNotNone(lbd)
            self.assertTrue((lbd.text or '').endswith('GMT') or ' +' in (lbd.text or '') or ',' in (lbd.text or ''))
        self.assertIsNone(ET.fromstring(legacy).find('channel/lastBuildDate'))
        self.assertNotIn('<lastBuildDate>', legacy)

    def test_legacy_merchant_keeps_new_religious_titles(self):
        """Нові релігійні правила — лише VIP/Middle; google-merchant без змін політики."""
        angel = _product(
            name='Садова фігура Ангел хлопчик', slug='leg-angel', sku='LEG-ANG',
            price=Decimal('500'),
        )
        angel.categories.add(self.pens)
        solomon = _product(
            name='Книга мудрості Соломона', slug='leg-sol', sku='LEG-SOL',
            price=Decimal('15000'),
        )
        solomon.categories.add(self.pens)

        self.assertNotIn(angel, list(middle_queryset()))
        self.assertNotIn(solomon, list(vip_queryset()) + list(middle_queryset()))

        old_skus = {
            el.text for el in ET.fromstring(build_google_merchant_xml()).findall('.//g:id', G_NS)
        }
        self.assertIn('LEG-ANG', old_skus)
        self.assertIn('LEG-SOL', old_skus)

    def test_manual_exclude_flags(self):
        p = _product(slug='man', sku='MAN-1', price=Decimal('15000'), exclude_from_feeds=True)
        p.categories.add(self.pens)
        self.assertNotIn(p, list(vip_queryset()))

        cat = Category.objects.create(
            name='Секрет', slug='secret', exclude_from_feeds=True,
        )
        p2 = _product(slug='man2', sku='MAN-2', price=Decimal('500'))
        p2.categories.add(cat)
        self.assertNotIn(p2, list(middle_queryset()))

    def test_inactive_and_no_price_same_as_old(self):
        inactive = _product(slug='off', sku='OFF-1', price=Decimal('15000'), is_active=False)
        inactive.categories.add(self.pens)
        zero = _product(slug='zero', sku='ZERO-1', price=Decimal('0'))
        zero.categories.add(self.pens)
        self.assertNotIn(inactive, list(vip_queryset()))
        self.assertNotIn(zero, list(vip_queryset()) + list(middle_queryset()))
        old_skus = {
            el.text for el in ET.fromstring(build_google_merchant_xml()).findall('.//g:id', G_NS)
        }
        self.assertNotIn('OFF-1', old_skus)
        self.assertNotIn('ZERO-1', old_skus)

    def test_segment_xml_valid_and_fields(self):
        p = _product(
            name='Ручка Parker', slug='parker', sku='PK-1',
            price=Decimal('5000.00'), old_price=Decimal('6000.00'),
            manufacturer='Parker', sku_manufacturer='4006381333931',
        )
        p.categories.add(self.pens)
        xml = build_segment_feed_xml('Middle')
        root = ET.fromstring(xml)
        self.assertEqual(root.tag, 'rss')
        item = root.find('channel/item')
        self.assertIsNotNone(item)
        self.assertEqual(item.find('g:custom_label_0', G_NS).text, 'Middle')
        self.assertEqual(item.find('g:price', G_NS).text, '6000.00 UAH')
        self.assertEqual(item.find('g:sale_price', G_NS).text, '5000.00 UAH')
        self.assertEqual(item.find('g:condition', G_NS).text, 'new')
        ptype = item.find('g:product_type', G_NS).text
        self.assertTrue(ptype.startswith('Головна > Каталог'))
        self.assertIn('Кабінет керівника', ptype)
        self.assertIn('Ручки подарункові', ptype)
        # Нові фіди: GTIN лише для книг — ручка без gtin
        self.assertIsNone(item.find('g:gtin', G_NS))
        self.assertEqual(item.find('g:identifier_exists', G_NS).text, 'false')
        self.assertEqual(item.find('g:brand', G_NS).text, 'Parker')
        self.assertEqual(item.find('g:google_product_category', G_NS).text, '982')

    def test_segment_gtin_books_only_drops_030_internal(self):
        book = _product(
            name='Класика', slug='book-gtin', sku='3527',
            price=Decimal('100'),
            sku_manufacturer='0305002007',  # ISBN-10 checksum ok, внутрішній 030*
        )
        book.categories.add(self.book_sub)
        pen = _product(
            name='Шахи Italfama', slug='chess-gtin', sku='CH-1',
            price=Decimal('500'),
            sku_manufacturer='4006381333931',
        )
        pen.categories.add(self.pens)
        book_ok = _product(
            name='Валідна книга', slug='book-ok', sku='BK-OK',
            price=Decimal('100'),
            sku_manufacturer='9786171234567',
        )
        book_ok.categories.add(self.books)

        vip_xml = build_segment_feed_xml('VIP')
        mid_xml = build_segment_feed_xml('Middle')
        vip_root = ET.fromstring(vip_xml)
        mid_root = ET.fromstring(mid_xml)

        items = {
            el.find('g:id', G_NS).text: el
            for el in vip_root.findall('channel/item') + mid_root.findall('channel/item')
        }
        self.assertIsNone(items['3527'].find('g:gtin', G_NS))
        self.assertEqual(items['3527'].find('g:identifier_exists', G_NS).text, 'false')
        self.assertIsNone(items['CH-1'].find('g:gtin', G_NS))
        self.assertEqual(items['BK-OK'].find('g:gtin', G_NS).text, '9786171234567')
        self.assertEqual(items['CH-1'].find('g:brand', G_NS).text, 'Italfama')
        self.assertEqual(items['3527'].find('g:google_product_category', G_NS).text, '784')

    def test_segment_brand_from_name_when_manufacturer_empty(self):
        p = _product(
            name='Фігурка CowParade Classic', slug='cow-1', sku='COW-1',
            price=Decimal('500'), manufacturer='',
        )
        cow_cat = Category.objects.create(name='Статуетки', slug='statuetky')
        p.categories.add(cow_cat)
        xml = build_segment_feed_xml('Middle')
        item = ET.fromstring(xml).find('channel/item')
        self.assertEqual(item.find('g:brand', G_NS).text, 'CowParade')
        self.assertEqual(item.find('g:google_product_category', G_NS).text, '5609')

    def test_legacy_gtin_and_category_unchanged_for_030(self):
        """Старий фід: 030* що проходить ISBN-10 лишається (байтова сумісність політики)."""
        p = _product(
            name='Товар з внутр. кодом', slug='leg-030', sku='20023',
            price=Decimal('3000'),
            sku_manufacturer='0304002003',
            manufacturer='OFION',
        )
        p.categories.add(self.pens)
        root = ET.fromstring(build_google_merchant_xml())
        item = next(
            el for el in root.findall('channel/item')
            if el.find('g:id', G_NS).text == '20023'
        )
        # Не ends-with SKU → legacy лишає gtin; category завжди 784 default
        self.assertEqual(item.find('g:gtin', G_NS).text, '0304002003')
        self.assertEqual(item.find('g:google_product_category', G_NS).text, '784')
        self.assertEqual(item.find('g:brand', G_NS).text, 'OFION')

    def test_urls_and_partition(self):
        vip_p = _product(slug='v1', sku='V1', price=Decimal('20000'))
        vip_p.categories.add(self.pens)
        mid_p = _product(slug='m1', sku='M1', price=Decimal('100'))
        mid_p.categories.add(self.pens)
        book = _product(slug='b1', sku='B1', price=Decimal('10'))
        book.categories.add(self.book_sub)

        vip_xml = self.client.get('/feeds/feed_vip.xml').content
        mid_xml = self.client.get('/feeds/feed_middle.xml').content
        self.assertIn(b'V1', vip_xml)
        self.assertIn(b'B1', vip_xml)
        self.assertNotIn(b'M1', vip_xml)
        self.assertIn(b'M1', mid_xml)
        self.assertNotIn(b'V1', mid_xml)

        # Кожен eligible не-релігійний — рівно в одному
        vip_ids = {el.text for el in ET.fromstring(vip_xml).findall('.//g:id', G_NS)}
        mid_ids = {el.text for el in ET.fromstring(mid_xml).findall('.//g:id', G_NS)}
        self.assertEqual(vip_ids & mid_ids, set())
        self.assertEqual(vip_ids | mid_ids, {'V1', 'B1', 'M1'})

    def test_old_feed_byte_identical_snapshot(self):
        """Snapshot до/після викликів нових фідів — google-merchant без змін."""
        p = _product(
            name='Звичайний товар', slug='old-snap', sku='OLD-1',
            price=Decimal('3000.00'),
            manufacturer='OFION',
        )
        p.categories.add(self.pens)
        # Релігійний — у старому фіду теж виключений (існуюча логіка)
        rel = _product(name='Ікона Богородиці', slug='rel-old', sku='REL-1', price=Decimal('1000'))
        rel.categories.add(self.icons)

        snapshot = build_google_merchant_xml().encode('utf-8')
        # Нові фіди / рефакторинг shared helpers не змінюють старий XML
        build_segment_feed_xml('VIP')
        build_segment_feed_xml('Middle')
        again = build_google_merchant_xml().encode('utf-8')
        self.assertEqual(again, snapshot)

        # Старий фід: без custom_label_0 і без префікса Головна > Каталог
        root = ET.fromstring(snapshot)
        self.assertIsNone(root.find('.//g:custom_label_0', G_NS))
        for pt in root.findall('.//g:product_type', G_NS):
            self.assertFalse((pt.text or '').startswith('Головна > Каталог'))
        # HTTP endpoint
        resp = self.client.get(reverse('google_merchant_feed'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, snapshot)
        # Релігійний не в старому (існуюча політика)
        self.assertNotIn(b'REL-1', snapshot)
        self.assertIn(b'OLD-1', snapshot)
