"""VIP / Middle Google Shopping feeds — окремо від /feeds/google-merchant.xml.

Релігійне виключення та exclude_from_feeds діють лише тут.
Старий merchant-фід лишається без змін (див. feed_utils.feed_eligible_queryset).
"""
from __future__ import annotations

import re
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

from django.core.cache import cache
from django.db.models import Q

from .feed_utils import (
    build_feed_item,
    get_base_price,
    get_base_url,
    get_site_brand,
)
from .models import Category, Product

FEED_SEGMENT_CACHE_TTL = 3600
VIP_PRICE_THRESHOLD = Decimal('10000')

# Категорії, що завжди VIP (будь-яка ціна), з підкатегоріями.
VIP_CATEGORY_NAMES = ('Книги', 'Щоденники')
VIP_CATEGORY_SLUGS = (
    'knyhy',
    'knigi',
    'books',
    'shchodennyky',
    'shchodenniki',
    'ezhednevniki',
    'diaries',
    'schodenniki',
)

# «Ікони» + підкатегорії — повне виключення з нових фідів.
ICON_CATEGORY_NAMES = ('Ікони', 'Иконы', 'Icons')
ICON_CATEGORY_SLUGS = ('ikoni', 'ikony', 'icons')

# Word-start стеми (без біблі/библи/ікон/хрест/релігі/свят/храм — окремі правила нижче).
_RELIGIOUS_STEMS = (
    'коран',
    'євангел', 'евангел',
    # молит — молитва/молитовник/молитвослов (не лише молитв*)
    'молит',
    'триптих',
    'псалтир',
    'четк', 'чотк',
    'лампад',
    'архангел',
    'архістратиг', 'архистратиг',
    # церкв*/церков* (церква, церковний); не «церк» як підрядок усередині чужих слів.
    'церкв', 'церков',
    'православ',
)

# Повні межі слова (не iconic; тора≠автора/історія/томах).
_RELIGIOUS_WORDS = (
    'тора', 'тори', 'тору', 'торы', 'torah',
    'bible', 'biblical', 'quran', 'koran', 'gospel',
    'prayer', 'icon', 'triptych',
    'psalter', 'rosary',
)

_HTML_TAG_RE = re.compile(r'<[^>]+>', re.UNICODE)

_SEGMENT_EXCLUSION_LABELS = {
    'no_image': 'Немає фото',
    'no_price': 'Ціна ≤ 0',
    'inactive': 'Неактивний',
    'manual_product': 'Прапорець exclude_from_feeds на товарі',
    'manual_category': 'Прапорець exclude_from_feeds на категорії',
    'icons_category': 'Категорія «Ікони» (і підкатегорії)',
    'religious_text': 'Релігійні ключові слова в назві/описі',
}


def _compile_religious_regex() -> re.Pattern[str]:
    """Релігійні ключові слова з вузькими правилами (без бібліотека/кресло/іконом…)."""
    stem_parts = [re.escape(s) for s in _RELIGIOUS_STEMS]
    # біблі/библи: Біблія/…/Біблій як ціле слово (+ bible/biblical); не бібліотека/біблійний.
    stem_parts.append(r'біблі(?:я|ю|ї|и|е|й)(?!\w)')
    stem_parts.append(r'библи(?:я|ю|и|е|й)(?!\w)')
    # ікон/икон: ікона/іконостас/иконопис; не іконом*.
    stem_parts.append(r'(?:ікон|икон)(?!ом)[аиуіоє]*')
    # хрест/крест/cross/crucifix: word-start; не кресл*/крісл*, перехрест*, кросс*.
    stem_parts.append(r'(?<!пере)(?:хрест|крест)(?!л)')
    stem_parts.append(r'crucifix')
    stem_parts.append(r'cross(?!с)')  # не кросс*
    # храм/храму/храмі/храмов* — не «храмів» (світські «храми Єгипту» у шахах).
    stem_parts.append(r'храм(?:у|ом|і|овий|ова|ове|ові)?(?!\w)')
    # Іменник «релігія/религия». Lookahead (?!йн)/(?!оз) раніше відсікав УСІ прикметники
    # («релігійного мистецтва» не ловилось) — заради світських описів на кшталт
    # «релігійних діячів» у «Промови, що змінили світ». Тому: іменник окремо;
    # прикметник — лише з релігійним контекстом (мистецтв/тематик/…), не «діяч*».
    stem_parts.append(r'релігі(?:я|ю|ї|є|єю|ями)(?!\w)')
    stem_parts.append(r'религи(?:я|ю|и|ей|ею|ями)(?!\w)')
    stem_parts.append(
        r'релігійн\w*(?=\s+(?:мистецтв|тематик|сюжет|мотив|зміст|обряд|культ|символ|ікон|икон))'
    )
    stem_parts.append(
        r'религиозн\w*(?=\s+(?:искусств|тематик|сюжет|мотив|содержан|обряд|культ|символ|икон))'
    )
    # святий/святого/святі + імʼя; «свята» лише якщо далі не маркетингове «для/або/чи…»
    # (род. відм. «свято» → «свята» у «на державні свята» — FP). Не святковий.
    _svyata_stop = (
        r'для|або|чи|на|в|у|з|і|й|та|по|від|до|як|що|це|не|коли|'
        r'після|перед|будь|людині|підвищення'
    )
    stem_parts.append(r'свят(?:ий|ого|і)(?!\w)\s+\S+')
    stem_parts.append(rf'свята(?!\w)\s+(?!(?:{_svyata_stop})\b)\S+')
    stem_parts.append(r'святе(?!\w)\s+письмо')
    stem_parts.append(r'свят(?:ой|ого|ые)(?!\w)\s+\S+')
    stem_parts.append(rf'святая(?!\w)\s+(?!(?:{_svyata_stop})\b)\S+')
    stem_parts.append(r'святое(?!\w)\s+писани')
    stems = '|'.join(stem_parts)
    words = '|'.join(re.escape(w) for w in _RELIGIOUS_WORDS)
    # (?<!\w) — старт слова; для words також (?!\w).
    return re.compile(
        rf'(?<!\w)(?:(?:{stems})|(?:(?:{words})(?!\w)))',
        re.IGNORECASE | re.UNICODE,
    )


RELIGIOUS_TEXT_RE = _compile_religious_regex()


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(' ', text)


def format_religious_text_reason(matches: list[str]) -> str:
    return f'Релігійні ключові слова в назві/описі ({", ".join(matches)})'


def find_religious_matches(text: str) -> list[str]:
    """Унікальні збіги (порядок збережено, регістр як у тексті)."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in RELIGIOUS_TEXT_RE.finditer(text):
        raw = m.group(0)
        key = raw.casefold()
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


def _localized_names(obj) -> list[str]:
    names = []
    for attr in ('name', 'name_uk', 'name_ru', 'name_en'):
        val = getattr(obj, attr, None)
        if val:
            names.append(str(val))
    return names


def _category_matches_names_or_slugs(cat, names: tuple[str, ...], slugs: tuple[str, ...]) -> bool:
    slug = (cat.slug or '').lower()
    if slug in {s.lower() for s in slugs}:
        return True
    targets = {n.casefold() for n in names}
    return any((n or '').casefold() in targets for n in _localized_names(cat))


def _product_text_blob(product) -> str:
    parts: list[str] = []
    for attr in (
        'name', 'name_uk', 'name_ru', 'name_en',
        'description', 'description_uk', 'description_ru', 'description_en',
        'short_description', 'short_description_uk',
        'short_description_ru', 'short_description_en',
    ):
        val = getattr(product, attr, None)
        if val:
            parts.append(str(val))
    return _strip_html(' '.join(parts))


def product_religious_matches(product) -> list[str]:
    return find_religious_matches(_product_text_blob(product))


def product_matches_religious_text(product) -> bool:
    return bool(product_religious_matches(product))


def get_icon_category_ids() -> set[int]:
    """ID категорії «Ікони» та всіх нащадків."""
    roots = [
        cat.id for cat in Category.objects.all()
        if _category_matches_names_or_slugs(cat, ICON_CATEGORY_NAMES, ICON_CATEGORY_SLUGS)
    ]
    return _expand_category_ids(roots)


def get_manual_excluded_category_ids() -> set[int]:
    """Категорії з exclude_from_feeds + нащадки (якщо колонка є)."""
    if not _model_has_field(Category, 'exclude_from_feeds'):
        return set()
    if not _db_has_column(Category, 'exclude_from_feeds'):
        return set()
    roots = list(
        Category.objects.filter(exclude_from_feeds=True).values_list('id', flat=True)
    )
    return _expand_category_ids(list(roots))


def get_vip_category_ids() -> set[int]:
    roots = [
        cat.id for cat in Category.objects.all()
        if _category_matches_names_or_slugs(cat, VIP_CATEGORY_NAMES, VIP_CATEGORY_SLUGS)
    ]
    return _expand_category_ids(roots)


def _expand_category_ids(root_ids: list[int]) -> set[int]:
    ids: set[int] = set(root_ids)
    frontier = list(root_ids)
    while frontier:
        children = list(
            Category.objects.filter(parent_id__in=frontier).values_list('id', flat=True)
        )
        frontier = [cid for cid in children if cid not in ids]
        ids.update(frontier)
    return ids


def _model_has_field(model, field_name: str) -> bool:
    return any(f.name == field_name for f in model._meta.get_fields())


def _db_has_column(model, field_name: str, using: str = 'default') -> bool:
    from django.db import connections
    table = model._meta.db_table
    try:
        with connections[using].cursor() as cursor:
            desc = connections[using].introspection.get_table_description(cursor, table)
    except Exception:
        return False
    return any(col.name == field_name for col in desc)


def base_eligible_queryset():
    """Та сама політика активності/ціни/фото, що в старому фіду."""
    return (
        Product.objects.filter(is_active=True, price__gt=0, images__isnull=False)
        .distinct()
        .prefetch_related('categories', 'categories__parent', 'images')
        .order_by('-updated_at')
    )


def segment_exclusion_q(
    icon_ids: set[int] | None = None,
    manual_cat_ids: set[int] | None = None,
) -> Q:
    """Q для exclude() — релігія / ручні прапорці (лише нові фіди)."""
    if icon_ids is None:
        icon_ids = get_icon_category_ids()
    if manual_cat_ids is None:
        manual_cat_ids = get_manual_excluded_category_ids()

    q = Q()
    if _model_has_field(Product, 'exclude_from_feeds') and _db_has_column(Product, 'exclude_from_feeds'):
        q |= Q(exclude_from_feeds=True)
    if manual_cat_ids:
        q |= Q(categories__id__in=manual_cat_ids)
    if icon_ids:
        q |= Q(categories__id__in=icon_ids)
    return q


def non_religious_eligible_queryset():
    qs = base_eligible_queryset()
    excl = segment_exclusion_q()
    if excl:
        qs = qs.exclude(excl)
    # Keyword-фільтр у Python — складний regex з межами слів надійніший за icontains.
    kept_ids = [
        p.pk for p in qs
        if not product_matches_religious_text(p)
    ]
    return qs.filter(pk__in=kept_ids).distinct()


def product_is_vip(product, vip_category_ids: set[int] | None = None) -> bool:
    if vip_category_ids is None:
        vip_category_ids = get_vip_category_ids()
    if vip_category_ids and product.categories.filter(id__in=vip_category_ids).exists():
        return True
    return get_base_price(product) >= VIP_PRICE_THRESHOLD


def vip_queryset():
    vip_ids = get_vip_category_ids()
    qs = non_religious_eligible_queryset()
    result_ids = [p.pk for p in qs if product_is_vip(p, vip_ids)]
    return qs.filter(pk__in=result_ids).distinct()


def middle_queryset():
    vip_ids = get_vip_category_ids()
    qs = non_religious_eligible_queryset()
    result_ids = [p.pk for p in qs if not product_is_vip(p, vip_ids)]
    return qs.filter(pk__in=result_ids).distinct()


def get_segment_exclusion_reasons(
    product,
    *,
    icon_ids: set[int] | None = None,
    manual_cat_ids: set[int] | None = None,
) -> list[str]:
    """Причини виключення з VIP/Middle (не зі старого merchant)."""
    if icon_ids is None:
        icon_ids = get_icon_category_ids()
    if manual_cat_ids is None:
        manual_cat_ids = get_manual_excluded_category_ids()

    reasons: list[str] = []
    if not product.is_active:
        reasons.append('inactive')
    if not product.images.exists():
        reasons.append('no_image')
    if product.price <= 0:
        reasons.append('no_price')
    if _safe_bool_flag(product, 'exclude_from_feeds'):
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


def _safe_bool_flag(obj, field_name: str) -> bool:
    """Читає boolean-прапорець без падіння, якщо колонки ще немає в БД."""
    if field_name in obj.__dict__:
        return bool(obj.__dict__[field_name])
    try:
        return bool(getattr(obj, field_name, False))
    except Exception:
        return False


def exclusion_reason_labels(reasons: list[str]) -> list[str]:
    """Коди → підписи; готовий рядок religious_text (з matches) лишається як є."""
    labels: list[str] = []
    for r in reasons:
        if r in _SEGMENT_EXCLUSION_LABELS:
            labels.append(_SEGMENT_EXCLUSION_LABELS[r])
        elif r.startswith('Релігійні ключові слова в назві/описі'):
            labels.append(r)
        else:
            labels.append(r)
    return labels


def build_segment_feed_xml(segment: str) -> str:
    """segment: 'VIP' | 'Middle'."""
    base_url = get_base_url()
    site_brand = get_site_brand()

    root = Element('rss')
    root.set('xmlns:g', 'http://base.google.com/ns/1.0')
    root.set('version', '2.0')
    channel = SubElement(root, 'channel')

    SubElement(channel, 'title').text = f'{site_brand} — {segment}'
    SubElement(channel, 'link').text = base_url
    SubElement(channel, 'description').text = (
        f'Каталог {segment} (без релігійної тематики)'
    )

    qs = vip_queryset() if segment == 'VIP' else middle_queryset()
    for product in qs:
        build_feed_item(
            channel,
            product,
            base_url,
            site_brand,
            custom_label_0=segment,
            product_type_with_site_prefix=True,
            segment_mode=True,
        )

    xml_str = tostring(root, encoding='unicode', xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


def get_cached_segment_feed_xml(segment: str) -> str:
    key = f'feed_segment_{segment.lower()}'
    xml = cache.get(key)
    if xml is None:
        xml = build_segment_feed_xml(segment)
        cache.set(key, xml, FEED_SEGMENT_CACHE_TTL)
    return xml
