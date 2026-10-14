"""VIP / Middle Google Shopping feeds — окремо від /feeds/google-merchant.xml.

Релігійне виключення та exclude_from_feeds діють лише тут.
Старий merchant-фід лишається без змін (див. feed_utils.feed_eligible_queryset).
"""
from __future__ import annotations

import html
import re
from decimal import Decimal
from email.utils import formatdate
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

# Застарілі константи (feed_report / імпорти) — VIP тепер через _category_is_vip_book_or_diary.
VIP_CATEGORY_NAMES = ('Книги', 'Щоденники', 'Колекція книг', 'Книги та автори')
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

# Назва/slug: Книги*, Колекція книг, Книги та автори, Щоденники* (А4/А5 тощо).
_VIP_BOOK_NAME_RE = re.compile(
    r'(?:'
    r'^книги(?:\s|$)|'
    r'^подарункові\s+книги|'
    r'колекція\s+книг|'
    r'книги\s+та\s+автори'
    r')',
    re.IGNORECASE | re.UNICODE,
)
_VIP_DIARY_NAME_RE = re.compile(r'^щоденник', re.IGNORECASE | re.UNICODE)
_VIP_BOOK_SLUG_RE = re.compile(
    r'(?:^|-)(?:knyhy|knigi|books|kolekts[iі]ya-knyg|knigi-ta-avtor)(?:-|$)',
    re.IGNORECASE,
)
_VIP_DIARY_SLUG_RE = re.compile(
    r'(?:shodenn|shchodenn|ezhednevn|diar)',
    re.IGNORECASE,
)

# «Ікони» + підкатегорії — повне виключення з нових фідів.
ICON_CATEGORY_NAMES = ('Ікони', 'Иконы', 'Icons')
ICON_CATEGORY_SLUGS = ('ikoni', 'ikony', 'icons')

# Word-start стеми (без біблі/библи/ікон/хрест/релігі/свят/храм/архангел — окремі правила).
# Скан scratch DB (ofion_feedcheck_scratch): соломон/ангельськ/будд* безпечні на title+desc;
# ангел/притч — title+category; архангел/хрест — title+desc з гербовим вікном (див. нижче).
_RELIGIOUS_STEMS = (
    'коран',
    'євангел', 'евангел',
    # молит — молитва/молитовник/молитвослов (не лише молитв*)
    'молит',
    'триптих',
    'псалтир',
    'четк', 'чотк',
    'лампад',
    # церкв*/церков* (церква, церковний); не «церк» як підрядок усередині чужих слів.
    'церкв', 'церков',
    'православ',
    # Книга мудрості Соломона (6191–6193); у scratch — лише title TP, без FP.
    'соломон',
    # «ангельська варта» тощо; покриває ангельськ* (не лише «ангел»).
    'ангельськ',
)

# Повні межі слова (не iconic; тора≠автора/історія/томах).
_RELIGIOUS_WORDS = (
    'тора', 'тори', 'тору', 'торы', 'torah',
    'bible', 'biblical', 'quran', 'koran', 'gospel',
    'prayer', 'icon', 'triptych',
    'psalter', 'rosary',
    # CowParade Buddha тощо; latin angel НЕ додаємо (Angeles / angelic).
    'buddha',
)

# Лише назва + категорія + product_type (не довгі описи):
# ангел/притч: FP у desc (Франс / горщик / Сковорода).
_TITLE_CATEGORY_RELIGIOUS_STEMS = (
    r'ангел(?!ин)',
    r'притч',
)

# архангел/хрест — і в description; гербове/держ./військ. вікно знімає лише desc-hit
# (title/category/product_type ніколи не звільняються). Реліг. контекст у вікні бʼє виняток.
_ARCHANGEL_CROSS_STEMS = (
    r'архангел',
    r'архістратиг',
    r'архистратиг',
    r'(?<!пере)(?:хрест|крест)(?!л)',
    r'crucifix',
    r'cross(?!с)',
)

# ~вікно навколо збігу: герб/емблема/символіка/СБУ/ЗСУ/орден/військ/геральд…
_HERALDIC_CONTEXT_RE = re.compile(
    r'(?:'
    r'герб|'
    r'емблем|'
    # символіка / ціле «символ*» (не «символізує»)
    r'символік|'
    r'(?<!\w)символ(?:у|а|ом|і|и|ів|ами|ах)?(?!\w)|'
    r'сбу|'
    r'зсу|'
    r'орден|'
    r'військ|'
    r'геральд|'
    r'хрест\w*\s+за\s+заслуг'
    r')',
    re.IGNORECASE | re.UNICODE,
)
# Релігійний контекст у тому ж вікні скасовує гербовий виняток.
# (?<!\w) — не «икон» у «виконана», не випадкові підрядки.
_RELIGIOUS_BEATS_HERALDIC_RE = re.compile(
    r'(?<!\w)(?:'
    r'наперсн|'
    r'(?:ікон|икон)(?!ом|ограф)|'
    r'молит|'
    r'церк|'
    r'православ|'
    r'свят(?:ий|ого|і|ой|ые|ая|ое)|'
    r'духовн'
    r')',
    re.IGNORECASE | re.UNICODE,
)
_ARCH_CROSS_WINDOW_CHARS = 60
_ARCH_CROSS_WINDOW_WORDS = 6

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
    # ікон/икон: ікона/іконостас/иконопис; не іконом*, не іконограф* (1328).
    stem_parts.append(r'(?:ікон|икон)(?!ом|ограф)[аиуіоє]*')
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
    # святий/святого/святі + імʼя (\w+, не «&mdash;»/тире); не Валентин (46737).
    # «свята» — не маркетингове «для/або…» і не «свята — на знак» (1017 після unescape).
    _svyata_stop = (
        r'для|або|чи|на|в|у|з|і|й|та|по|від|до|як|що|це|не|коли|'
        r'після|перед|будь|людині|підвищення'
    )
    _svyat_name_stop = r'валентин\w*'
    stem_parts.append(
        rf'свят(?:ий|ого|і)(?!\w)\s+(?!(?:{_svyat_name_stop})\b)\w+'
    )
    stem_parts.append(
        rf'свята(?!\w)\s+(?!(?:{_svyata_stop}|{_svyat_name_stop})\b)\w+'
    )
    stem_parts.append(r'святе(?!\w)\s+письмо')
    stem_parts.append(
        rf'свят(?:ой|ого|ые)(?!\w)\s+(?!(?:{_svyat_name_stop})\b)\w+'
    )
    stem_parts.append(
        rf'святая(?!\w)\s+(?!(?:{_svyata_stop}|{_svyat_name_stop})\b)\w+'
    )
    stem_parts.append(r'святое(?!\w)\s+писани')
    # будд* — Будда/Будди…; не «буддь» і не випадкові будд+приголосна.
    stem_parts.append(r'будд(?:а|и|у|е|ою|ів|ам|ами|ах)?(?!\w)')
    stems = '|'.join(stem_parts)
    words = '|'.join(re.escape(w) for w in _RELIGIOUS_WORDS)
    # (?<!\w) — старт слова; для words також (?!\w).
    return re.compile(
        rf'(?<!\w)(?:(?:{stems})|(?:(?:{words})(?!\w)))',
        re.IGNORECASE | re.UNICODE,
    )


def _compile_title_category_only_regex() -> re.Pattern[str]:
    """ангел/притч — лише назва+категорія+product_type (не description)."""
    stems = '|'.join(_TITLE_CATEGORY_RELIGIOUS_STEMS)
    return re.compile(
        rf'(?<!\w)(?:{stems})',
        re.IGNORECASE | re.UNICODE,
    )


def _compile_archangel_cross_regex() -> re.Pattern[str]:
    """архангел*/хрест* — title+desc; desc може мати гербовий виняток."""
    stems = '|'.join(_ARCHANGEL_CROSS_STEMS)
    return re.compile(
        rf'(?<!\w)(?:{stems})',
        re.IGNORECASE | re.UNICODE,
    )


RELIGIOUS_TEXT_RE = _compile_religious_regex()
RELIGIOUS_TITLE_CATEGORY_ONLY_RE = _compile_title_category_only_regex()
ARCHANGEL_CROSS_RE = _compile_archangel_cross_regex()


def _strip_html(text: str) -> str:
    """Прибирає теги й HTML-сутності (&mdash; → —), щоб не ловити FP на entity."""
    return html.unescape(_HTML_TAG_RE.sub(' ', text))


def format_religious_text_reason(matches: list[str]) -> str:
    return f'Релігійні ключові слова в назві/описі ({", ".join(matches)})'


def _unique_regex_matches(cre: re.Pattern[str], text: str) -> list[str]:
    """Унікальні збіги (порядок збережено, регістр як у тексті)."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in cre.finditer(text):
        raw = m.group(0)
        key = raw.casefold()
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


def _context_window(text: str, start: int, end: int) -> str:
    """Мале вікно навколо збігу: речення або ~60 символів / ~6 слів з кожного боку."""
    if not text:
        return ''
    # Межі речення (. ! ? ; …) — якщо близько.
    sent_start = start
    for i in range(start - 1, max(-1, start - 200), -1):
        if text[i] in '.!?;…\n':
            sent_start = i + 1
            break
    else:
        sent_start = max(0, start - 200)
    sent_end = end
    for i in range(end, min(len(text), end + 200)):
        if text[i] in '.!?;…\n':
            sent_end = i
            break
    else:
        sent_end = min(len(text), end + 200)

    # Символьне вікно ~60.
    char_lo = max(0, start - _ARCH_CROSS_WINDOW_CHARS)
    char_hi = min(len(text), end + _ARCH_CROSS_WINDOW_CHARS)

    # Словне вікно ~6 з кожного боку.
    before = text[:start]
    after = text[end:]
    before_words = re.findall(r'\S+', before)
    after_words = re.findall(r'\S+', after)
    word_before = ' '.join(before_words[-_ARCH_CROSS_WINDOW_WORDS:])
    word_after = ' '.join(after_words[:_ARCH_CROSS_WINDOW_WORDS])
    # Позиції словного вікна в оригіналі (наближено через зріз char).
    word_lo = max(0, start - len(word_before) - 8)
    word_hi = min(len(text), end + len(word_after) + 8)

    lo = max(0, min(sent_start, char_lo, word_lo))
    # Якщо речення дуже довге — не тягнемо все: обмежуємо union char/word,
    # але дозволяємо повне речення лише якщо воно не ширше за 2× char-вікно.
    if sent_end - sent_start <= (_ARCH_CROSS_WINDOW_CHARS * 2 + (end - start)):
        hi = min(len(text), max(sent_end, char_hi, word_hi))
        lo = max(0, min(lo, sent_start))
    else:
        hi = min(len(text), max(char_hi, word_hi))
    return text[lo:hi]


def _archangel_cross_heraldic_exempt(text: str, start: int, end: int) -> bool:
    """True = ігнорувати збіг (гербовий/держ. контекст без реліг. override)."""
    window = _context_window(text, start, end)
    if not window:
        return False
    if _RELIGIOUS_BEATS_HERALDIC_RE.search(window):
        return False
    return bool(_HERALDIC_CONTEXT_RE.search(window))


def _unique_archangel_cross_matches(
    text: str,
    *,
    allow_heraldic_exception: bool,
) -> list[str]:
    """Збіги архангел/хрест; опційно з гербовим винятком у вікні."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in ARCHANGEL_CROSS_RE.finditer(text):
        if allow_heraldic_exception and _archangel_cross_heraldic_exempt(
            text, m.start(), m.end(),
        ):
            continue
        raw = m.group(0)
        key = raw.casefold()
        if key not in seen:
            seen.add(key)
            out.append(raw)
    return out


def find_religious_matches(text: str) -> list[str]:
    """Збіги для довільного рядка: base + ангел/притч + архангел/хрест (з герб. вікном).

    На Product — product_religious_matches: ангел/притч лише title+category;
    архангел/хрест у title ніколи не звільняються, у desc — з винятком.
    """
    seen: set[str] = set()
    out: list[str] = []
    for cre in (RELIGIOUS_TEXT_RE, RELIGIOUS_TITLE_CATEGORY_ONLY_RE):
        for raw in _unique_regex_matches(cre, text):
            key = raw.casefold()
            if key not in seen:
                seen.add(key)
                out.append(raw)
    for raw in _unique_archangel_cross_matches(text, allow_heraldic_exception=True):
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


def _category_is_vip_book_or_diary(cat) -> bool:
    """True якщо категорія — Книги / Колекція книг / Книги та автори / Щоденники*."""
    slug = (cat.slug or '')
    if _VIP_DIARY_SLUG_RE.search(slug) or _VIP_BOOK_SLUG_RE.search(slug):
        return True
    for name in _localized_names(cat):
        n = (name or '').strip()
        if _VIP_DIARY_NAME_RE.search(n) or _VIP_BOOK_NAME_RE.search(n):
            return True
    return False


def _product_category_chain(product):
    """Усі категорії товару + їхні предки (для VIP walk і title-blob)."""
    cats = getattr(product, 'categories', None)
    if cats is None:
        return []
    try:
        cat_iter = list(cats.all())
    except Exception:
        return []
    seen: set[int] = set()
    chain = []
    for cat in cat_iter:
        nodes = list(cat.get_ancestors()) + [cat]
        for node in nodes:
            nid = getattr(node, 'id', None)
            if nid is not None and nid in seen:
                continue
            if nid is not None:
                seen.add(nid)
            chain.append(node)
    return chain


def _product_type_path_text(product) -> str:
    """Шлях product_type (як у фідах) для релігійного скану."""
    try:
        from .feed_utils import product_type_path, product_type_path_with_site_prefix
        return ' '.join(filter(None, [
            product_type_path(product),
            product_type_path_with_site_prefix(product),
        ]))
    except Exception:
        return ''


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
    ptype = _product_type_path_text(product)
    if ptype:
        parts.append(ptype)
    return _strip_html(' '.join(parts))


def _product_title_category_blob(product) -> str:
    """Назва + категорії (+ предки) + product_type — без description."""
    parts: list[str] = []
    for attr in ('name', 'name_uk', 'name_ru', 'name_en'):
        val = getattr(product, attr, None)
        if val:
            parts.append(str(val))
    for cat in _product_category_chain(product):
        parts.extend(_localized_names(cat))
        slug = getattr(cat, 'slug', None)
        if slug:
            parts.append(str(slug))
    ptype = _product_type_path_text(product)
    if ptype:
        parts.append(ptype)
    return _strip_html(' '.join(parts))


def _product_description_blob(product) -> str:
    """Лише description / short_description (для гербового винятку архангел/хрест)."""
    parts: list[str] = []
    for attr in (
        'description', 'description_uk', 'description_ru', 'description_en',
        'short_description', 'short_description_uk',
        'short_description_ru', 'short_description_en',
    ):
        val = getattr(product, attr, None)
        if val:
            parts.append(str(val))
    return _strip_html(' '.join(parts))


def product_religious_matches(product) -> list[str]:
    """Base по title+desc; ангел/притч — title+category; архангел/хрест — title завжди,
    desc — з гербовим вікном (реліг. контекст бʼє виняток)."""
    seen: set[str] = set()
    out: list[str] = []

    def _add(raws: list[str]) -> None:
        for raw in raws:
            key = raw.casefold()
            if key not in seen:
                seen.add(key)
                out.append(raw)

    _add(_unique_regex_matches(RELIGIOUS_TEXT_RE, _product_text_blob(product)))
    title_blob = _product_title_category_blob(product)
    _add(_unique_regex_matches(RELIGIOUS_TITLE_CATEGORY_ONLY_RE, title_blob))
    # Title/category/product_type — без винятку.
    _add(_unique_archangel_cross_matches(title_blob, allow_heraldic_exception=False))
    # Description — гербове вікно може зняти hit.
    _add(_unique_archangel_cross_matches(
        _product_description_blob(product),
        allow_heraldic_exception=True,
    ))
    return out


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
    """ID категорій Книги/Щоденники* (за name/slug pattern) + усі нащадки.

    Не hardcoded exact slug-list: «Щоденники А5», «Колекція книг», «Книги та автори»
    теж стають коренями; product_is_vip додатково ходить предками категорій товару.
    """
    roots = [
        cat.id for cat in Category.objects.all()
        if _category_is_vip_book_or_diary(cat)
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
    """VIP: будь-яка категорія товару або її предок — Книги/Щоденники*; інакше ціна."""
    # Спочатку walk предків (надійно для вкладених «Кабінет > Щоденники А5»).
    for cat in _product_category_chain(product):
        if _category_is_vip_book_or_diary(cat):
            return True
    if vip_category_ids is None:
        vip_category_ids = get_vip_category_ids()
    if vip_category_ids:
        try:
            if product.categories.filter(id__in=vip_category_ids).exists():
                return True
        except Exception:
            pass
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
    # RFC 822 — лише нові фіди; google-merchant.xml без lastBuildDate (byte-identical).
    SubElement(channel, 'lastBuildDate').text = formatdate(
        timeval=None, localtime=False, usegmt=True,
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
