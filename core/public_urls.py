"""Публічні абсолютні URL з фіксованим SITE_DOMAIN (канонічний хост)."""
from __future__ import annotations

from django.conf import settings


def canonical_host() -> str:
    """Хост без www — єдиний канонічний домен для SEO, sitemap, schema."""
    domain = (
        getattr(settings, 'SITE_DOMAIN', '')
        or getattr(settings, 'CUSTOM_DOMAIN', '')
        or 'localhost:8000'
    ).strip().lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def public_base_url() -> str:
    protocol = getattr(settings, 'SITE_PROTOCOL', 'https') or 'https'
    return f'{protocol}://{canonical_host()}'


def build_public_absolute_uri(path: str = '/') -> str:
    """Абсолютний URL на канонічному хості. Query string не включаємо."""
    if not path:
        path = '/'
    if path.startswith(('http://', 'https://')):
        return path
    if path.startswith('//'):
        protocol = getattr(settings, 'SITE_PROTOCOL', 'https') or 'https'
        return f'{protocol}:{path}'
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{public_base_url()}{path}'
