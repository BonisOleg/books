"""Мапінг категорій сайту → Google Taxonomy та бренд для VIP/Middle фідів.

Старий google-merchant.xml ці функції не використовує.
IDs з https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt
"""
from __future__ import annotations

import re

# slug (lower) → (google_id, human label for docs/tests)
SEGMENT_CATEGORY_GOOGLE_MAP: dict[str, tuple[str, str]] = {
    # Книги (prod + seed slug-и)
    'knigi': ('784', 'Media > Books'),
    'knyhy': ('784', 'Media > Books'),
    'books': ('784', 'Media > Books'),
    'biblioteki': ('784', 'Media > Books'),
    'biblioteka-knyhy-v-shkiri': ('784', 'Media > Books'),
    'biografiya-ta-memuari': ('784', 'Media > Books'),
    'dityachi-knigi': ('784', 'Media > Books'),
    'hobi-ta-sport': ('784', 'Media > Books'),
    'istoriya': ('784', 'Media > Books'),
    'istorychni-knyhy': ('784', 'Media > Books'),
    'klasika': ('784', 'Media > Books'),
    'klasyka': ('784', 'Media > Books'),
    'klasychna-literatura': ('784', 'Media > Books'),
    'knigi-anglijskoyu': ('784', 'Media > Books'),
    'mudrist-i-aforizmi': ('784', 'Media > Books'),
    'napoyi-ta-sigari': ('784', 'Media > Books'),
    'rodinni-knigi': ('784', 'Media > Books'),
    'vijskova-sprava': ('784', 'Media > Books'),
    'vlada-i-politika': ('784', 'Media > Books'),
    'kolektsijni-knyhy': ('784', 'Media > Books'),
    'filosofiya': ('784', 'Media > Books'),
    # Щоденники / планери / блокноти
    'shodenniki-a4': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'shodenniki-a5': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'shchodennyky': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'schodenniki': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'shchodenniki': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'ezhednevniki': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'diaries': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    # Шахи / настільні ігри
    'shahi': ('1246', 'Toys & Games > Games > Board Games'),
    'shakhy': ('1246', 'Toys & Games > Games > Board Games'),
    'nastilni-igri': ('1246', 'Toys & Games > Games > Board Games'),
    'nastilni-ihry': ('1246', 'Toys & Games > Games > Board Games'),
    'nardy': ('1246', 'Toys & Games > Games > Board Games'),
    # Статуетки / декор / CowParade
    'statuetki': ('5609', 'Home & Garden > Decor > Figurines'),
    'statuetky': ('5609', 'Home & Garden > Decor > Figurines'),
    'bronzovi-statuetki': ('11', 'Home & Garden > Decor > Artwork > Sculptures & Statues'),
    'bronza': ('11', 'Home & Garden > Decor > Artwork > Sculptures & Statues'),
    'cowparade': ('5609', 'Home & Garden > Decor > Figurines'),
    'sadovij-dekor': ('6547', 'Home & Garden > Decor > Lawn Ornaments & Garden Sculptures'),
    'sadovyi-dekor': ('6547', 'Home & Garden > Decor > Lawn Ornaments & Garden Sculptures'),
    # Глобус-бари / алкогольні набори
    'globus-bari': ('3262', 'Home & Garden > Decor > World Globes'),
    'shtofi-podarunkovi': ('650', 'Home & Garden > Kitchen & Dining > Barware > Decanters'),
    'nabari-dlya-alkogolyu': ('649', 'Home & Garden > Kitchen & Dining > Barware'),
    # Ручки / бізнес
    'ruchki-podarunkovi': ('982', 'Office Supplies > Office Instruments > Writing & Drawing Instruments > Pens & Pencils > Pens'),
    'ruchky': ('982', 'Office Supplies > Office Instruments > Writing & Drawing Instruments > Pens & Pencils > Pens'),
    'stilni-nabori': ('6066', 'Office Supplies > Office Instruments > Writing & Drawing Instruments > Pens & Pencils > Pen & Pencil Sets'),
    'biznes-aksesuari': ('922', 'Office Supplies'),
    # Парасольки
    'parasolki': ('4358', 'Home & Garden > Parasols & Rain Umbrellas'),
    'aksesuari-ta-prikrasi': ('167', 'Apparel & Accessories > Clothing Accessories'),
    'aksesuary': ('167', 'Apparel & Accessories > Clothing Accessories'),
    # Сувеніри / зброя-сувенір
    'bulava-pernach': ('220', 'Arts & Entertainment > Hobbies & Creative Arts > Collectibles > Collectible Weapons'),
    'suveniri-skifske-zoloto': ('5609', 'Home & Garden > Decor > Figurines'),
    'podarunkovij-kolazh': ('696', 'Home & Garden > Decor'),
    'originalni-podarunki': ('216', 'Arts & Entertainment > Hobbies & Creative Arts > Collectibles'),
    'ofion-exclusive': ('216', 'Arts & Entertainment > Hobbies & Creative Arts > Collectibles'),
    'podarunkovi-nabory': ('216', 'Arts & Entertainment > Hobbies & Creative Arts > Collectibles'),
}

# name.casefold() → той самий tuple (фолбек, якщо slug інший)
SEGMENT_CATEGORY_NAME_GOOGLE_MAP: dict[str, tuple[str, str]] = {
    'подарункові книги': ('784', 'Media > Books'),
    'книги': ('784', 'Media > Books'),
    'бібліотеки': ('784', 'Media > Books'),
    'бібліотека, книги в шкірі': ('784', 'Media > Books'),
    'колекційні книги': ('784', 'Media > Books'),
    'щоденники': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'щоденники а4': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'щоденники а5': ('927', 'Office Supplies > Filing & Organization > Calendars, Organizers & Planners'),
    'шахи': ('1246', 'Toys & Games > Games > Board Games'),
    'настільні ігри': ('1246', 'Toys & Games > Games > Board Games'),
    'нарди': ('1246', 'Toys & Games > Games > Board Games'),
    'статуетки': ('5609', 'Home & Garden > Decor > Figurines'),
    'бронзові статуетки': ('11', 'Home & Garden > Decor > Artwork > Sculptures & Statues'),
    'бронза': ('11', 'Home & Garden > Decor > Artwork > Sculptures & Statues'),
    'садовий декор': ('6547', 'Home & Garden > Decor > Lawn Ornaments & Garden Sculptures'),
    'глобус-бари': ('3262', 'Home & Garden > Decor > World Globes'),
    'штофи подарункові': ('650', 'Home & Garden > Kitchen & Dining > Barware > Decanters'),
    'набори для алкоголю': ('649', 'Home & Garden > Kitchen & Dining > Barware'),
    'ручки подарункові': ('982', 'Office Supplies > Office Instruments > Writing & Drawing Instruments > Pens & Pencils > Pens'),
    'парасольки': ('4358', 'Home & Garden > Parasols & Rain Umbrellas'),
    'булава пернач': ('220', 'Arts & Entertainment > Hobbies & Creative Arts > Collectibles > Collectible Weapons'),
    'cowparade': ('5609', 'Home & Garden > Decor > Figurines'),
}

# Категорії-книги (для GTIN лише в нових фідах).
BOOK_CATEGORY_SLUGS = frozenset({
    'knigi', 'knyhy', 'books', 'biblioteki', 'biblioteka-knyhy-v-shkiri',
    'biografiya-ta-memuari', 'dityachi-knigi',
    'hobi-ta-sport', 'istoriya', 'istorychni-knyhy', 'klasika', 'klasyka',
    'klasychna-literatura', 'knigi-anglijskoyu',
    'mudrist-i-aforizmi', 'napoyi-ta-sigari', 'rodinni-knigi',
    'vijskova-sprava', 'vlada-i-politika', 'koran', 'tora',
    'kolektsijni-knyhy', 'filosofiya', 'miniaturni-knyhy', 'faksymilni-vydannya',
})
BOOK_CATEGORY_NAMES = frozenset({
    'подарункові книги', 'книги', 'бібліотеки',
    'бібліотека, книги в шкірі', 'колекційні книги',
    'класика', 'класична література', 'історія', 'історичні книги',
})

# Бренди в назві (порядок — довші/специфічніші першими).
KNOWN_FEED_BRANDS: tuple[str, ...] = (
    'CowParade',
    'Italfama',
    'Veronese',
    'Manopoulos',
    'Caran d\'Ache',
    'Montblanc',
    'Waterman',
    'Visconti',
    'TENSO',
    'Tenso',
    'Parker',
    'Cross',
)

_INTERNAL_030_RE = re.compile(r'^030\d{7}$')
_SITE_BRAND_FALLBACKS = frozenset({'ofion', 'офіон'})


def _category_map_entry(cat) -> tuple[str, str] | None:
    slug = (cat.slug or '').lower()
    if slug in SEGMENT_CATEGORY_GOOGLE_MAP:
        return SEGMENT_CATEGORY_GOOGLE_MAP[slug]
    for attr in ('name', 'name_uk', 'name_ru', 'name_en'):
        val = getattr(cat, attr, None)
        if not val:
            continue
        hit = SEGMENT_CATEGORY_NAME_GOOGLE_MAP.get(str(val).casefold())
        if hit:
            return hit
    return None


def get_segment_google_category(product) -> str | None:
    """Google taxonomy id для VIP/Middle; None → тег не емітити."""
    for cat in product.categories.all():
        current = cat
        while current:
            # Явне значення в адмінці має пріоритет.
            if current.google_product_category:
                return str(current.google_product_category).strip()
            mapped = _category_map_entry(current)
            if mapped:
                return mapped[0]
            current = current.parent
    return None


def product_is_book_category(product) -> bool:
    for cat in product.categories.all():
        current = cat
        while current:
            slug = (current.slug or '').lower()
            if slug in BOOK_CATEGORY_SLUGS:
                return True
            for attr in ('name', 'name_uk', 'name_ru', 'name_en'):
                val = getattr(current, attr, None)
                if val and str(val).casefold() in BOOK_CATEGORY_NAMES:
                    return True
            current = current.parent
    return False


def is_internal_030_code(gtin: str) -> bool:
    return bool(gtin and _INTERNAL_030_RE.match(gtin))


def resolve_segment_brand(product, site_brand: str) -> str:
    """manufacturer (не OFION) → розпізнавання в назві → fallback site_brand."""
    mfr = (product.manufacturer or '').strip()
    site = (site_brand or 'OFION').strip()
    if mfr and mfr.casefold() not in _SITE_BRAND_FALLBACKS and mfr.casefold() != site.casefold():
        return mfr[:70]
    name = product.name or ''
    for brand in KNOWN_FEED_BRANDS:
        if re.search(rf'(?<!\w){re.escape(brand)}(?!\w)', name, re.IGNORECASE):
            # Канонічний регістр з таблиці (TENSO, не tenso з назви).
            return brand if brand != 'Tenso' else 'TENSO'
    if mfr:
        return mfr[:70]
    return (site or 'OFION')[:70]


def segment_category_mapping_table() -> list[tuple[str, str, str]]:
    """(site_slug, google_id, google_name) для звіту."""
    return [
        (slug, gid, gname)
        for slug, (gid, gname) in sorted(SEGMENT_CATEGORY_GOOGLE_MAP.items())
    ]
