"""SEO-дані категорій: дитячі книги, Біблія, книги, короткі meta.

Контент пишеться в базове поле і в *_uk, щоб його можна було правити в адмінці.
Довгий опис dityachi-knigi (есе про подарункову Біблію) переноситься в bibliya
і не затирає вже наявний опис. Невідомі slug товарів пропускаються.
"""
from django.db import migrations

KIDS_SLUG = 'dityachi-knigi'
BIBLE_SLUG = 'bibliya'
KNIGI_SLUG = 'knigi'

KIDS_NAME = 'Дитячі книги на подарунок'
KIDS_META_TITLE = 'Дитячі книги на подарунок — Біблія для дітей'
KIDS_META_DESCRIPTION = (
    'Дитячі книги на подарунок в OFION: «Біблія у переказі для дітей» '
    'у шкіряній палітурці з картиною на металі. '
    "Пам'ятний дарунок на хрестини чи Різдво."
)
KIDS_DESCRIPTION_HTML = (
    '<p>Книга, яку дитина отримує в подарунок, часто залишається з нею на все життя. '
    'Особливо якщо це не просто видання для читання, а гарна річ, яку хочеться берегти '
    'й передавати далі. У розділі «Дитячі книги» OFION зібрано подарункові видання, '
    "що стануть пам'ятним дарунком для дитини та всієї родини.</p>\n"
    '<h2>Біблія у переказі для дітей</h2>\n'
    '<p>Подарункова «Біблія у переказі для дітей» у шкіряній палітурці з картиною на металі. '
    'Біблійні історії викладено зрозумілою для дитини мовою, а оформлення робить книгу '
    'справжньою сімейною цінністю. Її можна читати разом із дитиною, а згодом передати '
    'наступному поколінню.</p>\n'
    '<h2>Коли подарувати</h2>\n'
    '<p>Така книга доречна на хрестини, день ангела, перше причастя, день народження чи Різдво. '
    'Це подарунок, який нагадуватиме про важливу подію ще багато років.</p>'
)
BIBLE_META_DESCRIPTION = (
    'Подарункова Біблія в шкірі, Євангеліє та Псалтир в OFION: '
    'елітні видання Святого Письма ручної роботи з металом та емалями. '
    'Подарунок на хрестини, вінчання, свято.'
)
KNIGI_NAME = 'Подарункові книги'
# Маркер поточного довгого опису dityachi-knigi (есе про подарункову Біблію).
BIBLE_ESSAY_MARKER = 'Оберіть подарункову Біблію в OFION'

# Скорочені meta. Джерела — поточні українські description з вітрини (довжина в дужках).
# knigi-ta-avtori (213): Подарункові книги відомих українських і світових авторів.
#   Класика, історія, філософія, політика, саморозвиток і культові твори у преміальному
#   оформленні. Обирайте книги для власної бібліотеки та подарунка в OFION.
# rodinni-knigi (189): Купити родинну книгу преміум класу для збереження сімейної
#   історії, традицій та спогадів. Елітний подарунок для родини, який передається
#   поколіннями. Швидка доставка по Україні і за кордон.
# samorozvitok-motivaciya (191): Купити подарункові книги із саморозвитку та мотивації
#   в шкіряній палітурці. Найкращі книги про лідерство, успіх, звички, психологію та
#   особистісне зростання. Доставка по Україні та за кордон.
# lina-kostenko (195): Подарункові книги Ліни Костенко у преміальному оформленні.
#   Поезія, вибрані твори та колекційні видання у шкіряній палітурці для подарунка
#   й особистої бібліотеки. Доставка по Україні та за кордон.
# taras-shevchenko (191): Подарункові книги Тараса Шевченка: «Кобзар», поезія та
#   колекційні видання у шкіряній палітурці. Статусний подарунок і цінне видання
#   для домашньої бібліотеки. Доставка по Україні та за кордон.
# lesya-ukrayinka (200): Подарункові книги Лесі Українки у преміальному оформленні.
#   Поезія, драматичні твори та колекційні видання у шкіряній палітурці для подарунка
#   й української бібліотеки. Доставка по Україні та за кордон.
# shahi (170): Подарункові шахи преміум класу ♟ Елітні шахові набори Italfama,
#   колекційні шахи з дерева, латуні та мармуру. Статусний подарунок для чоловіка,
#   керівника або колекціонера.
SHORT_META_DESCRIPTION = {
    'knigi-ta-avtori': (
        'Подарункові книги відомих українських і світових авторів: класика, історія, '
        'філософія, політика, саморозвиток і культові твори у преміальному оформленні.'
    ),
    'rodinni-knigi': (
        'Родинна книга преміум класу для збереження сімейної історії, традицій та спогадів. '
        'Елітний подарунок для родини, який передається поколіннями.'
    ),
    'samorozvitok-motivaciya': (
        'Подарункові книги із саморозвитку та мотивації в шкіряній палітурці: лідерство, '
        'успіх, звички, психологія та особистісне зростання. Доставка по Україні.'
    ),
    'lina-kostenko': (
        'Подарункові книги Ліни Костенко: поезія, вибрані твори та колекційні видання '
        'у шкіряній палітурці для подарунка й особистої бібліотеки. Доставка по Україні.'
    ),
    'taras-shevchenko': (
        'Подарункові книги Тараса Шевченка: «Кобзар», поезія та колекційні видання '
        'у шкіряній палітурці. Статусний подарунок для домашньої бібліотеки.'
    ),
    'lesya-ukrayinka': (
        'Подарункові книги Лесі Українки: поезія, драматичні твори та колекційні видання '
        'у шкіряній палітурці для подарунка й української бібліотеки.'
    ),
    'shahi': (
        'Подарункові шахи преміум класу: елітні набори Italfama, колекційні шахи '
        'з дерева, латуні та мармуру. Статусний подарунок для керівника або колекціонера.'
    ),
}


def _field_names(model):
    return {field.name for field in model._meta.concrete_fields}


def _qs(model, slug):
    qs = model.objects.filter(slug=slug)
    rewrite = getattr(qs, 'rewrite', None)
    if callable(rewrite):
        qs = rewrite(False)
    return qs


def _row(model, slug, fields):
    cols = [name for name in fields if name in _field_names(model)]
    if not cols:
        return None
    return _qs(model, slug).values(*cols).first()


def _update(model, slug, values):
    names = _field_names(model)
    payload = {key: value for key, value in values.items() if key in names}
    if not payload:
        return 0
    return _qs(model, slug).update(**payload)


def _squash(parts):
    kept = []
    for part in parts:
        part = (part or '').strip()
        if not part:
            continue
        if any(part in existing for existing in kept):
            continue
        kept = [existing for existing in kept if existing not in part]
        kept.append(part)
    return '\n'.join(kept)


def _is_bible_essay(value):
    text = (value or '').strip()
    if not text or text == KIDS_DESCRIPTION_HTML.strip():
        return False
    if BIBLE_ESSAY_MARKER in text:
        return True
    return len(text) >= 3000


def _log(message):
    print(f'seo-fixes: {message}')


def apply_category_seo(apps, schema_editor):
    from core.seo import strip_site_suffix
    from products.management.commands.move_bible_products import (
        SLUGS_MOVE_TO_BIBLE,
        ensure_bible_category,
        move_slugs_to_bible,
    )

    Category = apps.get_model('products', 'Category')
    Product = apps.get_model('products', 'Product')
    desc_fields = ('description', 'description_uk')

    kids_row = _row(Category, KIDS_SLUG, desc_fields)
    bible_row = _row(Category, BIBLE_SLUG, desc_fields)
    kids_base = ((kids_row or {}).get('description') or '')
    kids_uk = ((kids_row or {}).get('description_uk') or '')
    bible_base = ((bible_row or {}).get('description') or '')
    bible_uk = ((bible_row or {}).get('description_uk') or '')
    _log(
        'bibliya description before: '
        f'base_len={len(bible_base)} uk_len={len(bible_uk)} '
        f'base_preview={bible_base[:180]!r} uk_preview={bible_uk[:180]!r}'
    )
    _log(
        'dityachi-knigi description before move: '
        f'base_len={len(kids_base)} uk_len={len(kids_uk)}'
    )

    move_slugs_to_bible(
        list(SLUGS_MOVE_TO_BIBLE),
        apply=True,
        log=_log,
        ProductModel=Product,
        CategoryModel=Category,
    )

    essay = _squash([
        kids_uk if _is_bible_essay(kids_uk) else '',
        kids_base if _is_bible_essay(kids_base) else '',
    ])
    if essay:
        if _row(Category, BIBLE_SLUG, ('slug',)) is None:
            ensure_bible_category(create=True, CategoryModel=Category)
            _log('bibliya не було — категорію створено, щоб зберегти довгий опис.')
        existing = _squash([bible_uk, bible_base])
        combined = _squash([existing, essay])
        _update(Category, BIBLE_SLUG, {
            'description': combined,
            'description_uk': combined,
        })
        _log(f'bibliya description after: len={len(combined)} essay_len={len(essay)}')
    else:
        _log('Довгий опис Біблії в dityachi-knigi не знайдено — опис bibliya не змінювався.')

    _update(Category, KIDS_SLUG, {
        'name': KIDS_NAME,
        'name_uk': KIDS_NAME,
        'meta_title': KIDS_META_TITLE,
        'meta_title_uk': KIDS_META_TITLE,
        'meta_description': KIDS_META_DESCRIPTION,
        'meta_description_uk': KIDS_META_DESCRIPTION,
        'description': KIDS_DESCRIPTION_HTML,
        'description_uk': KIDS_DESCRIPTION_HTML,
    })
    _update(Category, BIBLE_SLUG, {
        'meta_description': BIBLE_META_DESCRIPTION,
        'meta_description_uk': BIBLE_META_DESCRIPTION,
    })

    knigi = _row(Category, KNIGI_SLUG, (
        'meta_title', 'meta_title_uk', 'meta_title_en', 'meta_title_ru',
    ))
    knigi_payload = {'name': KNIGI_NAME, 'name_uk': KNIGI_NAME}
    if knigi:
        for field, old in knigi.items():
            if not old:
                continue
            cleaned = strip_site_suffix(old)
            if cleaned != old:
                _log(f'knigi {field}: {old!r} -> {cleaned!r}')
            knigi_payload[field] = cleaned
    _update(Category, KNIGI_SLUG, knigi_payload)

    for slug, text in SHORT_META_DESCRIPTION.items():
        _update(Category, slug, {
            'meta_description': text,
            'meta_description_uk': text,
        })


def noop_reverse(apps, schema_editor):
    """Попередні тексти залежать від бази клієнта — відкат їх не відновлює."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0025_category_kids_and_bible_seo'),
    ]

    operations = [
        migrations.RunPython(apply_category_seo, noop_reverse),
    ]
