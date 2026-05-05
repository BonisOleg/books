"""Загальні утиліти для імпорту/експорту: безпечна генерація URL-slug.

URL pattern сайту приймає тільки [-a-zA-Z0-9_]+ (дефолтний Django <slug:>).
Тому slug ОБОВ'ЯЗКОВО має бути ASCII.
"""
from django.utils.text import slugify as _django_slugify

_TRANSLIT = {
    # uk lowercase
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e',
    'є': 'ie', 'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i',
    'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ь': '', 'ю': 'iu', 'я': 'ia',
    # ru extras lowercase
    'ё': 'yo', 'ы': 'y', 'э': 'e', 'ъ': '',
    # uk uppercase
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'H', 'Ґ': 'G', 'Д': 'D', 'Е': 'E',
    'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z', 'И': 'Y', 'І': 'I', 'Ї': 'I', 'Й': 'I',
    'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
    'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
    'Ш': 'Sh', 'Щ': 'Shch', 'Ь': '', 'Ю': 'Yu', 'Я': 'Ya',
    'Ё': 'Yo', 'Ы': 'Y', 'Э': 'E', 'Ъ': '',
    # apostrophes
    "'": '', '\u2019': '', '\u02bc': '',
}


def transliterate(text):
    if not text:
        return ''
    return ''.join(_TRANSLIT.get(c, c) for c in str(text))


def ascii_slug(text, *, fallback='item', max_length=200):
    """Повертає ASCII-сумісний slug.

    1) пробуємо `slugify(text, allow_unicode=False)` (виріже все не-ASCII);
    2) якщо результат порожній — транслітеруємо й знову slugify;
    3) якщо й це порожнє — те саме для fallback;
    4) гарантований дефолт 'item'.
    """
    for candidate in (text, transliterate(text)):
        if not candidate:
            continue
        s = _django_slugify(candidate, allow_unicode=False)
        if s:
            return s[:max_length]

    if fallback:
        s = _django_slugify(transliterate(fallback), allow_unicode=False)
        if s:
            return s[:max_length]

    return 'item'
