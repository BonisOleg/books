"""Тексти помилок Нової Пошти українською. Сирий текст — лише якщо коду немає в мапі."""

NP_ERROR_MESSAGES = {
    '20000100003': 'Невірний ключ API Нової Пошти',
    '20000100004': 'Ключ API Нової Пошти неактивний',
    '20000200028': 'Некоректний номер телефону',
    '20000200068': 'Відправника не знайдено',
    '20000200157': 'Контактну особу відправника не знайдено',
    '20000201204': 'Некоректне прізвище, ім’я або по батькові отримувача',
    '20000300412': 'Некоректна вага відправлення',
    '20000300417': 'Некоректна вага відправлення',
    '20000300418': 'Некоректні габарити місця',
    '20000400455': 'Місто отримувача не знайдено',
    '20000400456': 'Місто відправника не знайдено',
    '20000900721': 'Відділення отримувача не знайдено',
    '20000900722': 'Відділення відправника не знайдено',
    '20001401447': 'Не вказано опис вантажу',
    '20001501508': 'Некоректна сума оголошеної цінності',
    '30000100008': 'Перевищено ліміт запитів до API Нової Пошти',
}

FALLBACK_MESSAGE = 'Нова Пошта відхилила створення ТТН'


def format_np_failure(data):
    return humanize_np_response(data)


def humanize_np_response(data):
    if not isinstance(data, dict):
        return FALLBACK_MESSAGE

    mapped = []
    for code in _as_list(data.get('errorCodes')):
        text = NP_ERROR_MESSAGES.get(str(code).strip())
        if text:
            mapped.append(text)
    if mapped:
        return '; '.join(_unique(mapped))

    parts = _texts(data.get('errors'))
    for warning in _texts(data.get('warnings')):
        if warning.startswith('Попередження:'):
            parts.append(warning)
        else:
            parts.append(f'Попередження: {warning}')
    if parts:
        return '; '.join(_unique(parts))
    return FALLBACK_MESSAGE


def _as_list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _texts(value):
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            item = item.get('message') or item.get('Message') or ''
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _unique(items):
    return list(dict.fromkeys(items))
