"""SEO helpers: titles, canonical, meta description, JSON-LD, HTML demote."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.utils.html import strip_tags

from core.public_urls import build_public_absolute_uri, public_base_url

_NBSP_RE = re.compile(r'[\xa0\u202f\u2007]+')
_MULTI_SPACE_RE = re.compile(r' +')
_H1_OPEN_RE = re.compile(r'<h1(\s[^>]*)?>', re.IGNORECASE)
_H1_CLOSE_RE = re.compile(r'</h1\s*>', re.IGNORECASE)


def normalize_product_name(value: str | None) -> str:
    """Trim leading/trailing spaces and NBSP from product titles."""
    if value is None:
        return ''
    text = _NBSP_RE.sub(' ', str(value))
    text = _MULTI_SPACE_RE.sub(' ', text)
    return text.strip()


def truncate_at_word(text: str, max_len: int = 160) -> str:
    """Cut plain text to max_len on a whole-word boundary."""
    text = _MULTI_SPACE_RE.sub(' ', (text or '').replace('\xa0', ' ')).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' \t.,;:!?—–-')


def strip_site_suffix(title: str, site_name: str | None = None) -> str:
    """Remove every «| SITE_NAME» segment (trailing or mid-title)."""
    site_name = (site_name or getattr(settings, 'SITE_NAME', 'OFION') or 'OFION').strip()
    title = (title or '').strip()
    if not title or not site_name:
        return title
    pattern = re.compile(rf'\s*\|\s*{re.escape(site_name)}\b', re.IGNORECASE)
    title = pattern.sub('', title)
    title = _MULTI_SPACE_RE.sub(' ', title).strip(' |')
    return title.strip()


def with_site_suffix(title: str, site_name: str | None = None) -> str:
    """Ensure title ends with exactly one «| SITE_NAME»."""
    site_name = (site_name or getattr(settings, 'SITE_NAME', 'OFION') or 'OFION').strip()
    base = strip_site_suffix(title, site_name)
    if not base:
        return site_name
    if base.casefold() == site_name.casefold():
        return site_name
    return f'{base} | {site_name}'


def page_suffix(page_number: int | None) -> str:
    try:
        n = int(page_number or 1)
    except (TypeError, ValueError):
        n = 1
    if n >= 2:
        return f' — сторінка {n}'
    return ''


def apply_pagination_seo(ctx: dict[str, Any], page_number: int | None) -> dict[str, Any]:
    """Append « — сторінка N» to title/description for N >= 2.

    Strips any embedded site suffix from title first so the template can
    re-append a single «| SITE_NAME» after the page marker.
    """
    suffix = page_suffix(page_number)
    if not suffix:
        return ctx
    title = strip_site_suffix(ctx.get('page_title') or '')
    if title and suffix not in title:
        ctx['page_title'] = f'{title}{suffix}'
    elif title:
        ctx['page_title'] = title
    desc = ctx.get('page_meta_description') or ''
    if desc and suffix not in desc:
        ctx['page_meta_description'] = f'{desc}{suffix}'
    return ctx


def request_has_facet_filters(request) -> bool:
    """True when the URL has a non-empty f_<slug> parameter."""
    params = getattr(request, 'GET', None)
    if params is None:
        return False
    getlist = getattr(params, 'getlist', None)
    for key in params:
        if not isinstance(key, str) or not key.startswith('f_') or len(key) < 3:
            continue
        raw_values = getlist(key) if getlist else [params.get(key)]
        if any(str(value).strip() for value in raw_values if value is not None):
            return True
    return False


def canonical_for_request(request) -> str:
    """Canonical URL; include ?page=N only when N >= 2.

    Attribute filters (f_*) canonicalize to the bare path, without page.
    """
    url = build_public_absolute_uri(getattr(request, 'path', '/') or '/')
    if request_has_facet_filters(request):
        return url
    raw = request.GET.get('page') if hasattr(request, 'GET') else None
    if raw is None or raw == '':
        return url
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return url
    if n >= 2:
        return f'{url}?{urlencode({"page": n})}'
    return url


def demote_h1_html(html: str, css_class: str = 'seo-h2') -> str:
    """Replace h1 → h2 at render time; preserve look via css_class. DB unchanged."""
    if not html:
        return html

    def _open(match: re.Match) -> str:
        attrs = match.group(1) or ''
        class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attrs, re.IGNORECASE)
        if class_match:
            classes = class_match.group(2).split()
            if css_class and css_class not in classes:
                classes.append(css_class)
            new_class = ' '.join(classes)
            attrs = (
                attrs[: class_match.start()]
                + f'class="{new_class}"'
                + attrs[class_match.end() :]
            )
        elif css_class:
            attrs = f'{attrs} class="{css_class}"'
        return f'<h2{attrs}>'

    result = _H1_OPEN_RE.sub(_open, str(html))
    result = _H1_CLOSE_RE.sub('</h2>', result)
    return result


def _first_sentence(text: str, max_len: int = 80) -> str:
    text = _MULTI_SPACE_RE.sub(' ', (text or '').replace('\xa0', ' ')).strip()
    if not text:
        return ''
    for sep in ('. ', '! ', '? ', '.\n', '!\n', '?\n'):
        if sep in text:
            text = text.split(sep, 1)[0].rstrip('.')
            break
    return truncate_at_word(text, max_len)


def product_key_characteristic(product) -> str:
    """Short unique trait: first attribute, else short_description, else manufacturer."""
    attrs = getattr(product, 'attributes', None)
    if attrs is not None:
        first = attrs.all()[:1]
        if first:
            attr = first[0]
            name = (attr.name or '').strip()
            value = (attr.value or '').strip()
            if name and value:
                return f'{name}: {value}'
            return value or name
    short = strip_tags(getattr(product, 'short_description', '') or '').strip()
    if short:
        return _first_sentence(short)
    manufacturer = (getattr(product, 'manufacturer', '') or '').strip()
    if manufacturer:
        return manufacturer
    return ''


def build_product_meta_description(
    product,
    site_name: str | None = None,
    max_len: int = 160,
) -> str:
    """Custom SEO field if set; else auto template, always <= max_len."""
    site_name = (site_name or getattr(settings, 'SITE_NAME', 'OFION') or 'OFION').strip()
    custom = (getattr(product, 'meta_description', '') or '').strip()
    if custom:
        from products.schema import _plain_text
        return truncate_at_word(_plain_text(custom, max_len=max_len * 2), max_len)

    name = normalize_product_name(getattr(product, 'name', '') or '') or 'Товар'
    key = product_key_characteristic(product)
    if key:
        raw = f'{name} — купити в {site_name}. {key}. Доставка по Україні.'
    else:
        raw = f'{name} — купити в {site_name}. Доставка по Україні.'
    return truncate_at_word(raw, max_len)


def product_image_alt(product_name: str, index: int, *, is_main: bool = False) -> str:
    """Main photo = name; thumbnails = «Name — фото N» (N from 1)."""
    name = normalize_product_name(product_name) or 'Товар'
    if is_main:
        return name
    n = max(1, int(index))
    return f'{name} — фото {n}'


# Корені соцмереж без профілю: telegram.org, t.me, instagram.com тощо.
_SOCIAL_ROOT_HOSTS = frozenset({
    'telegram.org',
    't.me',
    'telegram.me',
    'instagram.com',
    'facebook.com',
    'fb.com',
    'youtube.com',
    'youtu.be',
    'tiktok.com',
    'viber.com',
})


def is_placeholder_social_url(url: str | None) -> bool:
    """True, якщо це лише корінь соцмережі без шляху профілю."""
    raw = (url or '').strip()
    if not raw:
        return False
    parsed = urlsplit(raw if '://' in raw else f'https://{raw}')
    host = (parsed.hostname or '').lower().rstrip('.')
    if host.startswith('www.'):
        host = host[4:]
    if host not in _SOCIAL_ROOT_HOSTS:
        return False
    return not (parsed.path or '').strip('/')


def get_home_json_ld(site, request=None) -> dict[str, Any] | None:
    """Organization + WebSite @graph from SiteSettings only (no invented fields)."""
    if site is None:
        return None

    base = public_base_url()
    site_url = f'{base}/'
    name = (site.site_name or '').strip() or getattr(settings, 'SITE_NAME', 'OFION')

    organization: dict[str, Any] = {
        '@type': 'Organization',
        'name': name,
        'url': site_url,
    }

    logo = getattr(site, 'logo', None)
    if logo:
        try:
            organization['logo'] = build_public_absolute_uri(logo.url)
        except (ValueError, AttributeError):
            pass

    phones = [p for p in [site.phone_1, site.phone_2, site.phone_3] if (p or '').strip()]
    email = (site.email or '').strip()
    if phones or email:
        contact: dict[str, Any] = {
            '@type': 'ContactPoint',
            'contactType': 'customer service',
        }
        if phones:
            contact['telephone'] = phones[0]
        if email:
            contact['email'] = email
        organization['contactPoint'] = contact

    same_as = []
    for attr in (
        'telegram_url', 'viber_url', 'facebook_url',
        'instagram_url', 'youtube_url', 'tiktok_url',
    ):
        url = (getattr(site, attr, '') or '').strip()
        if url and not is_placeholder_social_url(url):
            same_as.append(url)
    if same_as:
        organization['sameAs'] = same_as

    website: dict[str, Any] = {
        '@type': 'WebSite',
        'name': name,
        'url': site_url,
    }

    return {
        '@context': 'https://schema.org',
        '@graph': [organization, website],
    }
