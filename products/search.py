"""Нормалізований пошук товарів: кирилиця, лапки, усі мови, без службового артикула."""
import re

from django.db.models import Case, IntegerField, Value, When

from products.schema import _plain_text

_QUOTES_RE = re.compile(r"[«»\"'„“”‚‘’`]")
_FOLD = str.maketrans({'і': 'и', 'ї': 'и', 'є': 'е', 'ґ': 'г'})

_NAME_FIELDS = ('name_uk', 'name_ru', 'name_en', 'name')
_HTML_FIELDS = (
    'short_description_uk', 'short_description_ru', 'short_description_en', 'short_description',
    'description_uk', 'description_ru', 'description_en', 'description',
)
_SOURCE_FIELDS = frozenset({
    *_NAME_FIELDS,
    *_HTML_FIELDS,
    'sku', 'manufacturer',
})

MAX_QUERY_LEN = 100
MAX_TOKENS = 6
MIN_TOKEN_LEN = 2


def normalize_search_text(text):
    if not text:
        return ''
    normalized = str(text).casefold()
    normalized = _QUOTES_RE.sub(' ', normalized)
    normalized = normalized.translate(_FOLD)
    return ' '.join(normalized.split())


def _plain_for_search(html):
    if not html:
        return ''
    return _plain_text(html, max_len=len(html))


def _deduped(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_search_fields(product):
    names = _deduped(
        normalize_search_text(getattr(product, field, '') or '')
        for field in _NAME_FIELDS
    )
    search_name = ' '.join(names)
    parts = [search_name]
    for field in ('sku', 'manufacturer'):
        parts.append(normalize_search_text(getattr(product, field, '') or ''))
    for field in _HTML_FIELDS:
        parts.append(normalize_search_text(_plain_for_search(getattr(product, field, '') or '')))
    return {
        'search_name': search_name,
        'search_text': ' '.join(_deduped(parts)),
    }


def search_tokens(raw):
    normalized = normalize_search_text(raw)[:MAX_QUERY_LEN]
    return [token for token in normalized.split() if len(token) >= MIN_TOKEN_LEN][:MAX_TOKENS]


def apply_search(queryset, raw):
    """Фільтрує queryset і додає rank. Порядок не змінює."""
    tokens = search_tokens(raw)
    if not tokens:
        return queryset.annotate(rank=Value(3, output_field=IntegerField())).none()

    phrase = ' '.join(tokens)
    query = queryset
    for token in tokens:
        query = query.filter(search_text__contains=token)

    stripped = ' '.join(str(raw or '').split())[:MAX_QUERY_LEN]
    return query.annotate(
        rank=Case(
            When(sku__iexact=stripped, then=Value(0)),
            When(search_name__startswith=phrase, then=Value(1)),
            When(search_name__contains=phrase, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
    )


def refresh_search_index(product):
    from products.models import Product
    Product.objects.filter(pk=product.pk).update(**build_search_fields(product))


def source_fields():
    return _SOURCE_FIELDS
