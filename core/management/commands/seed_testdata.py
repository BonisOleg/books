from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


CATEGORIES = [
    {
        'name': 'Бібліотека, книги в шкірі',
        'slug': 'biblioteka-knyhy-v-shkiri',
        'description': 'Ексклюзивні книги у шкіряній палітурці ручної роботи.',
        'order': 1,
        'children': [
            {'name': 'Класична література', 'slug': 'klasychna-literatura', 'order': 1},
            {'name': 'Історичні книги', 'slug': 'istorychni-knyhy', 'order': 2},
            {'name': 'Філософія', 'slug': 'filosofiya', 'order': 3},
        ],
    },
    {
        'name': 'Колекційні книги',
        'slug': 'kolektsijni-knyhy',
        'description': 'Рідкісні та колекційні видання для справжніх поціновувачів.',
        'order': 2,
        'children': [
            {'name': 'Мініатюрні книги', 'slug': 'miniaturni-knyhy', 'order': 1},
            {'name': 'Факсимільні видання', 'slug': 'faksymilni-vydannya', 'order': 2},
        ],
    },
    {
        'name': 'Релігійні книги',
        'slug': 'relihijni-knyhy',
        'description': 'Біблії, молитовники та духовна література у розкішному оформленні.',
        'order': 3,
        'children': [],
    },
    {
        'name': 'Подарункові набори',
        'slug': 'podarunkovi-nabory',
        'description': 'Готові подарункові комплекти для будь-якого свята.',
        'order': 4,
        'children': [
            {'name': 'Для чоловіків', 'slug': 'dlya-cholovikiv', 'order': 1},
            {'name': 'Для жінок', 'slug': 'dlya-zhinok', 'order': 2},
        ],
    },
    {
        'name': 'Настільні ігри',
        'slug': 'nastilni-ihry',
        'description': 'Шахи, нарди, карти та інші настільні ігри преміум-класу.',
        'order': 5,
        'children': [
            {'name': 'Шахи', 'slug': 'shakhy', 'order': 1},
            {'name': 'Нарди', 'slug': 'nardy', 'order': 2},
            {'name': 'Гральні карти', 'slug': 'hralni-karty', 'order': 3},
        ],
    },
    {
        'name': 'Статуетки',
        'slug': 'statuetky',
        'description': 'Декоративні статуетки з бронзи, порцеляни та каменю.',
        'order': 6,
        'children': [],
    },
    {
        'name': 'Альбоми для фотографій',
        'slug': 'albomy-dlya-fotohrafij',
        'description': 'Фотоальбоми у шкіряній обкладинці ручної роботи.',
        'order': 7,
        'children': [],
    },
    {
        'name': 'Аксесуари',
        'slug': 'aksesuary',
        'description': 'Шкіряні аксесуари, ручки, візитниці преміум-класу.',
        'order': 8,
        'children': [],
    },
]

PRODUCTS = [
    {
        'name': 'Кобзар Т.Г. Шевченка у шкіряній палітурці',
        'slug': 'kobzar-shevchenka-shkiryana-paliturka',
        'sku': 'BK-001',
        'category_slug': 'klasychna-literatura',
        'price': Decimal('4890.00'),
        'old_price': Decimal('5490.00'),
        'badge': 'top',
        'stock_status': 'in_stock',
        'manufacturer': 'Майстерня "Арт-Книга"',
        'country': 'Україна',
        'weight': Decimal('1.8'),
        'description': (
            'Розкішне видання "Кобзаря" Тараса Григоровича Шевченка у натуральній шкіряній палітурці '
            'ручної роботи. Золоте тиснення на обкладинці та корінці. Шовкова закладка. '
            'Друк на офсетному папері преміум-якості.\n\n'
            'Ідеальний подарунок для поціновувачів української класичної літератури.'
        ),
        'short_description': 'Класичне видання Кобзаря у шкіряній палітурці з золотим тисненням.',
        'attributes': [
            ('Палітурка', 'Натуральна шкіра'),
            ('Папір', 'Офсетний, 120 г/м²'),
            ('Кількість сторінок', '420'),
            ('Розмір', '240 × 170 мм'),
            ('Тиснення', 'Золоте'),
        ],
    },
    {
        'name': 'Біблія у шкіряній палітурці з футляром',
        'slug': 'bibliya-shkiryana-paliturka-futlyar',
        'sku': 'BK-002',
        'category_slug': 'relihijni-knyhy',
        'price': Decimal('7990.00'),
        'badge': 'new',
        'stock_status': 'in_stock',
        'manufacturer': 'Свято-Успенська Лавра',
        'country': 'Україна',
        'weight': Decimal('2.4'),
        'description': (
            'Біблія в розкішному виданні. Палітурка з натуральної шкіри темно-коричневого кольору. '
            'Золоте тиснення хреста на обкладинці. Кольорові ілюстрації. '
            'Поставляється у подарунковому дерев\'яному футлярі з оксамитовою підкладкою.\n\n'
            'Переклад Івана Огієнка.'
        ),
        'short_description': 'Розкішна Біблія у шкіряній палітурці з дерев\'яним футляром.',
        'attributes': [
            ('Палітурка', 'Натуральна шкіра, темно-коричнева'),
            ('Папір', 'Крейдований, 150 г/м²'),
            ('Кількість сторінок', '1360'),
            ('Розмір', '260 × 190 мм'),
            ('Переклад', 'Іван Огієнко'),
        ],
    },
    {
        'name': 'Шахи "Мускетери" бронзові з дошкою',
        'slug': 'shakhy-musketery-bronzovi-doshka',
        'sku': 'IG-001',
        'category_slug': 'shakhy',
        'price': Decimal('12490.00'),
        'old_price': Decimal('14990.00'),
        'badge': 'sale',
        'stock_status': 'in_stock',
        'manufacturer': 'Manopoulos',
        'country': 'Греція',
        'weight': Decimal('4.2'),
        'description': (
            'Ексклюзивний набір шахів "Мускетери" від грецького виробника Manopoulos. '
            'Фігури виготовлені з бронзи методом лиття з ручним розписом. '
            'Шахова дошка з натурального горіха з інкрустацією.\n\n'
            'Розмір дошки: 440 × 440 мм. Висота короля: 97 мм.'
        ),
        'short_description': 'Бронзові шахи з ручним розписом на дошці з горіха.',
        'attributes': [
            ('Матеріал фігур', 'Бронза'),
            ('Матеріал дошки', 'Горіх з інкрустацією'),
            ('Розмір дошки', '440 × 440 мм'),
            ('Висота короля', '97 мм'),
            ('Тип', 'Колекційні'),
        ],
    },
    {
        'name': 'Гральні карти у скриньці з каліфорнійського горіха',
        'slug': 'hralni-karty-skrynka-horikha',
        'sku': 'IG-002',
        'category_slug': 'hralni-karty',
        'price': Decimal('2490.00'),
        'stock_status': 'in_stock',
        'manufacturer': 'Manopoulos',
        'country': 'Греція',
        'weight': Decimal('1.6'),
        'description': (
            'Скринька виготовлена з дерева, внутрішнє оздоблення велюр, '
            'що надає їй неповторної елегантності. Усередині коробки знаходяться '
            'дві колоди гральних карт із пластиковим покриттям темно-синього та червоного кольорів.\n\n'
            'Ідеальний подарунок для любителів карткових ігор.'
        ),
        'short_description': 'Дві колоди карт у дерев\'яній скриньці з каліфорнійського горіха.',
        'attributes': [
            ('Матеріал карт', 'Пластикове покриття'),
            ('Матеріал скриньки', 'Каліфорнійський горіх'),
            ('Розмір скриньки', '240 × 170 мм'),
            ('Кількість колод', '2'),
        ],
    },
    {
        'name': '«Мистецтво війни» Сунь-Цзи. Подарункове видання',
        'slug': 'mystetstvo-vijny-sun-tzi',
        'sku': 'BK-003',
        'category_slug': 'istorychni-knyhy',
        'price': Decimal('3690.00'),
        'badge': 'new',
        'stock_status': 'in_stock',
        'manufacturer': 'Видавництво "Фоліо"',
        'country': 'Україна',
        'weight': Decimal('1.2'),
        'description': (
            'Класичний трактат китайського стратега Сунь-Цзи у подарунковому виданні. '
            'Шкіряна палітурка з тисненням. Кольорові ілюстрації з давньокитайськими гравюрами. '
            'Коментарі та примітки відомих військових теоретиків.\n\n'
            'Розкішне видання для поціновувачів стратегічної думки.'
        ),
        'short_description': 'Подарунковий Сунь-Цзи у шкіряній палітурці з ілюстраціями.',
        'attributes': [
            ('Палітурка', 'Натуральна шкіра'),
            ('Кількість сторінок', '256'),
            ('Розмір', '220 × 160 мм'),
            ('Ілюстрації', 'Кольорові гравюри'),
        ],
    },
    {
        'name': 'Нарди "Грецькі воїни" ручної роботи',
        'slug': 'nardy-hretski-voyiny',
        'sku': 'IG-003',
        'category_slug': 'nardy',
        'price': Decimal('8990.00'),
        'stock_status': 'in_stock',
        'manufacturer': 'Manopoulos',
        'country': 'Греція',
        'weight': Decimal('3.8'),
        'description': (
            'Нарди преміум-класу з натурального горіха з інкрустацією. '
            'Фішки з бронзи у стилізації давньогрецьких воїнів. '
            'Ручна робота грецьких майстрів.\n\n'
            'Ідеальний подарунок для поціновувачів настільних ігор.'
        ),
        'short_description': 'Нарди з горіха з бронзовими фішками у грецькому стилі.',
        'attributes': [
            ('Матеріал дошки', 'Горіх'),
            ('Матеріал фішок', 'Бронза'),
            ('Розмір у закритому вигляді', '480 × 260 мм'),
        ],
    },
    {
        'name': 'Повне зібрання творів Лесі Українки (5 томів)',
        'slug': 'lesya-ukrayinka-5-tomiv',
        'sku': 'BK-004',
        'category_slug': 'klasychna-literatura',
        'price': Decimal('18900.00'),
        'old_price': Decimal('21500.00'),
        'badge': 'sale',
        'stock_status': 'ready',
        'manufacturer': 'Майстерня "Арт-Книга"',
        'country': 'Україна',
        'weight': Decimal('8.5'),
        'description': (
            'П\'ятитомне повне зібрання творів Лесі Українки у розкішному виконанні. '
            'Кожен том — у палітурці з натуральної шкіри з золотим тисненням. '
            'Подарункова коробка з оксамитовою підкладкою.\n\n'
            'Видання містить усі поетичні, прозові та драматичні твори.'
        ),
        'short_description': '5-томне зібрання у шкірі з золотим тисненням та подарунковій коробці.',
        'attributes': [
            ('Палітурка', 'Натуральна шкіра'),
            ('Кількість томів', '5'),
            ('Загальна кількість сторінок', '2800'),
            ('Тиснення', 'Золоте'),
        ],
    },
    {
        'name': 'Статуетка "Феміда" бронзова, 35 см',
        'slug': 'statuetka-femida-bronzova-35cm',
        'sku': 'ST-001',
        'category_slug': 'statuetky',
        'price': Decimal('5490.00'),
        'stock_status': 'in_stock',
        'manufacturer': 'Veronese',
        'country': 'Італія',
        'weight': Decimal('2.1'),
        'description': (
            'Бронзова статуетка богині правосуддя Феміди. '
            'Ручна робота, покриття — бронзовий порошок з патинуванням. '
            'Ідеальний подарунок для юристів та суддів.\n\n'
            'Висота: 35 см. Підставка з натурального мармуру.'
        ),
        'short_description': 'Бронзова Феміда 35 см з мармуровою підставкою.',
        'attributes': [
            ('Матеріал', 'Бронзовий порошок, полістоун'),
            ('Висота', '35 см'),
            ('Підставка', 'Натуральний мармур'),
        ],
    },
    {
        'name': '«Філософія» Григорія Сковороди. Ексклюзивне видання',
        'slug': 'filosofiya-skovorody-ekskluzyvne',
        'sku': 'BK-005',
        'category_slug': 'filosofiya',
        'price': Decimal('6290.00'),
        'stock_status': 'order',
        'manufacturer': 'Видавництво "Фоліо"',
        'country': 'Україна',
        'weight': Decimal('1.5'),
        'description': (
            'Збірка основних філософських творів Григорія Сковороди у подарунковому виданні. '
            'Шкіряна палітурка бордового кольору з рельєфним тисненням. '
            'Вступна стаття академіка Мирослава Поповича.\n\n'
            'Тираж обмежений — 500 примірників.'
        ),
        'short_description': 'Філософські твори Сковороди у лімітованому шкіряному виданні.',
        'attributes': [
            ('Палітурка', 'Шкіра, бордова'),
            ('Кількість сторінок', '380'),
            ('Тираж', '500 примірників'),
        ],
    },
    {
        'name': 'Подарунковий набір "Бізнес-партнер"',
        'slug': 'nabir-biznes-partner',
        'sku': 'GF-001',
        'category_slug': 'dlya-cholovikiv',
        'price': Decimal('3990.00'),
        'badge': 'top',
        'stock_status': 'in_stock',
        'manufacturer': 'Birca',
        'country': 'Україна',
        'weight': Decimal('1.0'),
        'description': (
            'Подарунковий набір у дерев\'яній коробці: шкіряна візитниця, '
            'ручка Parker з гравіюванням, блокнот у шкіряній обкладинці.\n\n'
            'Можливість індивідуального гравіювання за запитом.'
        ),
        'short_description': 'Набір: візитниця + ручка Parker + блокнот у шкірі.',
        'attributes': [
            ('Комплектація', 'Візитниця, ручка, блокнот'),
            ('Матеріал', 'Натуральна шкіра'),
            ('Упаковка', 'Дерев\'яна подарункова коробка'),
        ],
    },
    {
        'name': 'Фотоальбом "Родинний" у шкіряній обкладинці',
        'slug': 'fotoalbom-rodynnyi-shkira',
        'sku': 'AL-001',
        'category_slug': 'albomy-dlya-fotohrafij',
        'price': Decimal('2790.00'),
        'stock_status': 'in_stock',
        'manufacturer': 'Birca',
        'country': 'Україна',
        'weight': Decimal('1.3'),
        'description': (
            'Фотоальбом на 200 фотографій формату 10×15 см. '
            'Обкладинка з натуральної шкіри. Сторінки з щільного картону '
            'з прозорими кишеньками. Можливість тиснення імені на обкладинці.'
        ),
        'short_description': 'Шкіряний фотоальбом на 200 фото з можливістю тиснення.',
        'attributes': [
            ('Кількість фото', '200 (10×15 см)'),
            ('Обкладинка', 'Натуральна шкіра'),
            ('Розмір', '280 × 220 мм'),
        ],
    },
    {
        'name': 'Подарунковий набір "Елегантність" для жінок',
        'slug': 'nabir-elehantnist-zhinky',
        'sku': 'GF-002',
        'category_slug': 'dlya-zhinok',
        'price': Decimal('4590.00'),
        'old_price': Decimal('5200.00'),
        'badge': 'sale',
        'stock_status': 'in_stock',
        'manufacturer': 'Birca',
        'country': 'Україна',
        'weight': Decimal('0.8'),
        'description': (
            'Вишуканий набір у подарунковій коробці: шкіряний гаманець, '
            'шовковий шарф, косметичка з натуральної шкіри.\n\n'
            'Кольори: бордо, беж, чорний — на вибір.'
        ),
        'short_description': 'Жіночий набір: гаманець + шарф + косметичка у подарунковій коробці.',
        'attributes': [
            ('Комплектація', 'Гаманець, шарф, косметичка'),
            ('Матеріал', 'Натуральна шкіра, шовк'),
            ('Кольори', 'Бордо / Беж / Чорний'),
        ],
    },
]

REVIEWS = [
    {'product_sku': 'BK-001', 'author': 'Олександр М.', 'rating': 5,
     'text': 'Чудове видання! Шкіра натуральна, тиснення акуратне. Подарував батькові — дуже задоволений.'},
    {'product_sku': 'BK-001', 'author': 'Ірина К.', 'rating': 5,
     'text': 'Дякую за швидку доставку. Книга виглядає розкішно, якість друку відмінна.'},
    {'product_sku': 'IG-001', 'author': 'Віталій С.', 'rating': 5,
     'text': 'Шахи неймовірні! Бронзові фігури дуже деталізовані. Подарунок для справжніх поціновувачів.'},
    {'product_sku': 'IG-002', 'author': 'Дмитро Л.', 'rating': 4,
     'text': 'Гарна скринька, карти якісні. Трішки дорого, але як подарунок — ідеально.'},
    {'product_sku': 'BK-002', 'author': 'Марія В.', 'rating': 5,
     'text': 'Біблія просто казкова! Футляр дерев\'яний, оксамит всередині. Купувала для мами — розплакалась від радості.'},
    {'product_sku': 'ST-001', 'author': 'Андрій Р.', 'rating': 5,
     'text': 'Феміда виглядає чудово на робочому столі. Бронзове покриття якісне, патина красива.'},
    {'product_sku': 'GF-001', 'author': 'Наталія П.', 'rating': 4,
     'text': 'Набір виглядає дуже солідно. Ручка Parker пише чудово. Рекомендую як діловий подарунок.'},
    {'product_sku': 'BK-003', 'author': 'Сергій Б.', 'rating': 5,
     'text': 'Мистецтво війни — класика. А це видання ще й виглядає як витвір мистецтва. Дякую!'},
]


class Command(BaseCommand):
    help = 'Заповнює базу тестовими даними (категорії, товари, відгуки, налаштування)'

    def handle(self, *args, **options):
        self._create_site_settings()
        cat_map = self._create_categories()
        self._create_products(cat_map)
        self._create_reviews()
        self._create_blog()
        self.stdout.write(self.style.SUCCESS('Тестові дані успішно створено!'))

    def _create_site_settings(self):
        from core.models import SiteSettings
        obj, created = SiteSettings.objects.get_or_create(pk=1)
        obj.site_name = 'Магазин книжок'
        obj.site_description = 'Інтернет-магазин елітних подарунків, книг у шкірі, статуеток та ексклюзивних товарів'
        obj.email = 'info@bookshop.com.ua'
        obj.address = 'проспект Корольова 1, Київ, Україна'
        obj.phone_1 = '+380 (96) 846-67-58'
        obj.phone_2 = '+380 (63) 964-85-33'
        obj.phone_3 = '+380 (99) 559-88-64'
        obj.contact_person = 'Людмила'
        obj.work_schedule = 'Пн-Пт: 09:00 - 19:00\nСб: 10:00 - 18:00\nНд: 10:00 - 18:00'
        obj.return_policy = (
            'Компанія здійснює повернення і обмін цього товару відповідно до вимог законодавства.\n\n'
            'Повернення можливе протягом 14 днів після отримання (для товарів належної якості).\n'
            'Зворотня доставка товарів здійснюється за домовленістю.\n\n'
            'Ви можете повернути товар належної якості або обміняти його, якщо:\n'
            '• товар не був у вжитку і не має слідів використання;\n'
            '• товар повністю укомплектований і збережена фабрична упаковка;\n'
            '• збережені всі ярлики і заводське маркування;\n'
            '• товар зберігає товарний вигляд і свої споживчі властивості.'
        )
        obj.promo_banner_text = 'При замовленні від 3000 ₴ — доставка БЕЗКОШТОВНО!'
        obj.promo_banner_url = '/catalog/'
        obj.telegram_url = 'https://t.me/bookshop_ua'
        obj.facebook_url = 'https://facebook.com/bookshop.ua'
        obj.instagram_url = 'https://instagram.com/bookshop_ua'
        obj.seo_home_title = 'Магазин книжок — елітні книги, подарунки та ексклюзивні товари'
        obj.seo_home_description = (
            'Інтернет-магазин книг у шкіряній палітурці, колекційних видань, '
            'настільних ігор преміум-класу та подарункових наборів. Доставка по Україні.'
        )
        obj.save()
        self.stdout.write(f'  SiteSettings: {"створено" if created else "оновлено"}')

    def _create_categories(self):
        from products.models import Category
        cat_map = {}
        for cat_data in CATEGORIES:
            parent, _ = Category.objects.update_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'order': cat_data['order'],
                    'is_active': True,
                    'parent': None,
                },
            )
            cat_map[cat_data['slug']] = parent
            for child_data in cat_data.get('children', []):
                child, _ = Category.objects.update_or_create(
                    slug=child_data['slug'],
                    defaults={
                        'name': child_data['name'],
                        'parent': parent,
                        'order': child_data['order'],
                        'is_active': True,
                    },
                )
                cat_map[child_data['slug']] = child
        self.stdout.write(f'  Категорій: {len(cat_map)}')
        return cat_map

    def _create_products(self, cat_map):
        from products.models import Product, ProductAttribute
        count = 0
        for p_data in PRODUCTS:
            category = cat_map.get(p_data['category_slug'])
            product, created = Product.objects.update_or_create(
                sku=p_data['sku'],
                defaults={
                    'name': p_data['name'],
                    'slug': p_data.get('slug') or slugify(p_data['name']) or p_data['sku'].lower(),
                    'category': category,
                    'price': p_data['price'],
                    'old_price': p_data.get('old_price'),
                    'badge': p_data.get('badge', ''),
                    'stock_status': p_data.get('stock_status', 'in_stock'),
                    'manufacturer': p_data.get('manufacturer', ''),
                    'country': p_data.get('country', ''),
                    'weight': p_data.get('weight'),
                    'description': p_data['description'],
                    'short_description': p_data.get('short_description', ''),
                    'condition': 'Новий',
                    'is_active': True,
                },
            )
            if created or not product.attributes.exists():
                product.attributes.all().delete()
                for i, (attr_name, attr_value) in enumerate(p_data.get('attributes', [])):
                    ProductAttribute.objects.create(
                        product=product, name=attr_name, value=attr_value, order=i
                    )
            count += 1
        self.stdout.write(f'  Товарів: {count}')

    def _create_reviews(self):
        from products.models import Product
        from reviews.models import Review
        count = 0
        for r_data in REVIEWS:
            try:
                product = Product.objects.get(sku=r_data['product_sku'])
            except Product.DoesNotExist:
                continue
            _, created = Review.objects.get_or_create(
                product=product,
                author_name=r_data['author'],
                defaults={
                    'rating': r_data['rating'],
                    'text': r_data['text'],
                    'is_approved': True,
                },
            )
            if created:
                count += 1
        self.stdout.write(f'  Відгуків: {count}')

    def _create_blog(self):
        from blog.models import Article, News
        articles = [
            {
                'title': 'Як обрати книгу в подарунок: поради від експертів',
                'slug': 'yak-obraty-knyhu-v-podarunok',
                'content': (
                    'Обрати книгу в подарунок — це мистецтво. Потрібно враховувати інтереси '
                    'отримувача, привід та бюджет. У цій статті ми зібрали поради від наших '
                    'експертів, які допоможуть вам зробити правильний вибір.\n\n'
                    '1. Визначте інтереси отримувача\n'
                    '2. Оберіть відповідний формат\n'
                    '3. Зверніть увагу на якість палітурки\n'
                    '4. Подумайте про додаткове гравіювання\n\n'
                    'Книга у шкіряній палітурці — це не просто подарунок, це інвестиція у '
                    'бібліотеку, яка буде радувати її власника десятиліттями.'
                ),
                'excerpt': 'Поради від експертів: як обрати ідеальну книгу в подарунок.',
            },
            {
                'title': 'Шахи як подарунок: гід по вибору',
                'slug': 'shakhy-yak-podarunok',
                'content': (
                    'Шахи — це класичний подарунок, який ніколи не вийде з моди. '
                    'У нашому каталозі представлені набори від провідних виробників: '
                    'Manopoulos (Греція), Italfama (Італія) та інших.\n\n'
                    'На що звернути увагу при виборі:\n'
                    '• Матеріал фігур (бронза, дерево, полістоун)\n'
                    '• Розмір дошки (від 28 до 54 см)\n'
                    '• Стиль фігур (класичні, тематичні, колекційні)\n'
                    '• Якість інкрустації дошки'
                ),
                'excerpt': 'Повний гід по вибору шахів у подарунок: матеріали, розміри, стилі.',
            },
        ]
        news_items = [
            {
                'title': 'Нове надходження: колекційні шахи Manopoulos 2026',
                'slug': 'nove-nadhodzhennya-manopoulos-2026',
                'content': (
                    'Раді повідомити про нове надходження колекційних шахів від грецького '
                    'виробника Manopoulos. У колекції 2026 року — 5 нових наборів з унікальними '
                    'тематиками: Мускетери, Грецькі воїни, Римська імперія, Середньовіччя та Козаки.\n\n'
                    'Кожен набір — це витвір мистецтва: бронзові фігури ручної роботи '
                    'та дошки з натурального горіха.'
                ),
                'excerpt': 'Нові колекційні шахи Manopoulos вже у нашому магазині!',
            },
            {
                'title': 'Акція: знижка 15% на книги у шкіряній палітурці',
                'slug': 'aktsiya-znyzhka-15-na-knyhy',
                'content': (
                    'З 1 по 30 квітня 2026 — знижка 15% на всі книги у шкіряній палітурці. '
                    'Акція поширюється на всі наявні видання.\n\n'
                    'Встигніть замовити улюблені книги за вигідною ціною! '
                    'Доставка безкоштовна при замовленні від 3000 ₴.'
                ),
                'excerpt': 'Знижка 15% на книги у шкірі до кінця квітня!',
            },
        ]
        a_count = 0
        for a_data in articles:
            _, created = Article.objects.get_or_create(
                slug=a_data['slug'],
                defaults={
                    'title': a_data['title'],
                    'content': a_data['content'],
                    'excerpt': a_data['excerpt'],
                    'is_published': True,
                },
            )
            if created:
                a_count += 1

        n_count = 0
        for n_data in news_items:
            _, created = News.objects.get_or_create(
                slug=n_data['slug'],
                defaults={
                    'title': n_data['title'],
                    'content': n_data['content'],
                    'excerpt': n_data['excerpt'],
                    'is_published': True,
                },
            )
            if created:
                n_count += 1

        self.stdout.write(f'  Статей: {a_count}, Новин: {n_count}')
