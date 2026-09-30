import posixpath

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from core.imaging.variants import field_local_path, read_meta

register = template.Library()


def _flag(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ('', '0', 'false', 'none')
    return bool(value)


def _row_flag(value, *, first_only=False) -> bool:
    """True/False як є. Число з forloop.counter: 1–4 eager, лише 1 — priority."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1 if first_only else 1 <= value <= 4
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        return number == 1 if first_only else 1 <= number <= 4
    return _flag(value) if not first_only else False


def _variant_entries(field):
    """Повертає (url, width, height, [(url, width), ...])."""
    if not field:
        return '', None, None, []
    try:
        original_url = field.url
    except Exception:
        return '', None, None, []

    path = field_local_path(field)
    meta = read_meta(path) if path else None
    if not meta:
        width = height = None
        if path and path.is_file():
            try:
                from PIL import Image
                with Image.open(path) as image:
                    width, height = image.size
            except Exception:
                width = height = None
        return original_url, width, height, []

    parent = posixpath.dirname(field.name or '')
    entries = []
    storage = field.storage
    for item in meta.get('variants') or []:
        filename = item.get('file')
        variant_width = item.get('width')
        if not filename or not variant_width:
            continue
        relative = posixpath.join(parent, filename) if parent else filename
        try:
            url = storage.url(relative)
        except Exception:
            continue
        entries.append((url, int(variant_width)))
    return original_url, meta.get('width'), meta.get('height'), entries


def _srcset(entries) -> str:
    return ', '.join(f'{url} {width}w' for url, width in entries)


@register.simple_tag
def image_srcset(field):
    _, _, _, entries = _variant_entries(field)
    return _srcset(entries)


@register.simple_tag
def image_variant(field, width):
    original, _, _, entries = _variant_entries(field)
    if not entries:
        return original
    requested = int(width)
    larger = [item for item in entries if item[1] >= requested]
    if larger:
        return min(larger, key=lambda item: item[1])[0]
    return max(entries, key=lambda item: item[1])[0]


@register.simple_tag
def responsive_img(
    field,
    alt='',
    css_class='',
    sizes='100vw',
    eager=False,
    priority=False,
    hold=False,
    mobile=None,
    img_id='',
    itemprop='',
):
    original, width, height, entries = _variant_entries(field)
    if not original:
        return ''

    sources = []
    if mobile:
        _, _, _, mobile_entries = _variant_entries(mobile)
        if mobile_entries:
            sources.append(format_html(
                '<source media="(max-width: 767px)" type="image/webp" srcset="{}" sizes="{}">',
                _srcset(mobile_entries),
                sizes,
            ))
    if entries:
        sources.append(format_html(
            '<source type="image/webp" srcset="{}" sizes="{}">',
            _srcset(entries),
            sizes,
        ))

    is_eager = _row_flag(eager)
    is_priority = _row_flag(priority, first_only=True)
    is_hold = _flag(hold)
    srcset = _srcset(entries)
    attrs_tail = format_html(
        '{}{}{}{}{}',
        format_html(' class="{}"', css_class) if css_class else '',
        format_html(' id="{}"', img_id) if img_id else '',
        format_html(' itemprop="{}"', itemprop) if itemprop else '',
        format_html(' width="{}"', width) if width else '',
        format_html(' height="{}"', height) if height else '',
    )
    priority_attr = mark_safe(' fetchpriority="high"') if is_priority else ''

    if is_hold:
        held = format_html(
            '<img alt="{}"{}{}{} decoding="async">',
            alt or '',
            attrs_tail,
            format_html(' data-src="{}"', original),
            format_html(' data-srcset="{}" data-sizes="{}"', srcset, sizes) if srcset else '',
        )
        fallback = format_html(
            '<img src="{}" alt="{}"{}{} loading="lazy" decoding="async">',
            original,
            alt or '',
            attrs_tail,
            format_html(' srcset="{}" sizes="{}"', srcset, sizes) if srcset else '',
        )
        return format_html('{}<noscript>{}</noscript>', held, fallback)

    img = format_html(
        '<img src="{}" alt="{}"{}{} loading="{}" decoding="async"{}>',
        original,
        alt or '',
        attrs_tail,
        format_html(' sizes="{}"', sizes) if srcset else '',
        'eager' if is_eager else 'lazy',
        priority_attr,
    )
    if not sources:
        return img
    return format_html(
        '<picture>{}{}</picture>',
        format_html_join('', '{}', ((source,) for source in sources)),
        img,
    )
