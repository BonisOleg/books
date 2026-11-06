"""Валідація та хелпери для cover_link статей/новин."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_cover_link(value: str) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    lower = text.casefold()
    if lower.startswith(('http://', 'https://')):
        URLValidator(schemes=('http', 'https'))(text)
        return
    if text.startswith('/') and not text.startswith('//'):
        if any(ch.isspace() for ch in text) or '\\' in text:
            raise ValidationError(
                'Відносне посилання не може містити пробіли або зворотні слеші.',
                code='invalid',
            )
        return
    raise ValidationError(
        'Вкажіть абсолютне http(s)-посилання або відносний шлях на кшталт /catalog/.',
        code='invalid',
    )


def resolve_cover_href(cover_link: str, fallback: str) -> str:
    link = (cover_link or '').strip()
    return link or fallback


def cover_link_is_external(cover_link: str) -> bool:
    link = (cover_link or '').strip().casefold()
    return link.startswith(('http://', 'https://'))
