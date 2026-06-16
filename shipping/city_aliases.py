import re

CITY_ALIASES = {
    'kyiv': 'Київ',
    'kiev': 'Київ',
    'kharkiv': 'Харків',
    'kharkov': 'Харків',
    'odesa': 'Одеса',
    'odessa': 'Одеса',
    'lviv': 'Львів',
    'lvov': 'Львів',
    'dnipro': 'Дніпро',
    'dnepr': 'Дніпро',
    'dnipropetrovsk': 'Дніпро',
    'zaporizhzhia': 'Запоріжжя',
    'zaporozhye': 'Запоріжжя',
    'zaporizhia': 'Запоріжжя',
    'vinnytsia': 'Вінниця',
    'vinnitsa': 'Вінниця',
    'poltava': 'Полтава',
    'chernihiv': 'Чернігів',
    'chernigov': 'Чернігів',
    'cherkasy': 'Черкаси',
    'sumy': 'Суми',
    'zhytomyr': 'Житомир',
    'zhitomir': 'Житомир',
    'rivne': 'Рівне',
    'rovno': 'Рівне',
    'ivanofrankivsk': 'Івано-Франківськ',
    'ivano-frankivsk': 'Івано-Франківськ',
    'ternopil': 'Тернопіль',
    'lutsk': 'Луцьк',
    'uzhhorod': 'Ужгород',
    'uzhgorod': 'Ужгород',
    'mykolaiv': 'Миколаїв',
    'nikolaev': 'Миколаїв',
    'kherson': 'Херсон',
    'khmelnytskyi': 'Хмельницький',
    'khmelnitsky': 'Хмельницький',
    'chernivtsi': 'Чернівці',
    'cherkassy': 'Черкаси',
    'kropyvnytskyi': 'Кропивницький',
    'krivoyrog': 'Кривий Ріг',
    'kryvyirih': 'Кривий Ріг',
    'mariupol': 'Маріуполь',
    'kamianske': 'Кам\'янське',
    'kamenskoe': 'Кам\'янське',
    'bila': 'Біла Церква',
    'bilatserkva': 'Біла Церква',
    'kremenchuk': 'Кремінчук',
    'kremenchug': 'Кремінчук',
    'melitopol': 'Мелітополь',
    'nikopol': 'Нікополь',
    'brovary': 'Бровари',
    'berdiansk': 'Бердянськ',
    'berdyansk': 'Бердянськ',
    'pavlohrad': 'Павлоград',
    'sloviansk': 'Слов\'янськ',
    'slavyansk': 'Слов\'янськ',
    'uman': 'Умань',
    'konotop': 'Конотоп',
    'kamianetspodilskyi': 'Кам\'янець-Подільський',
    'kamyanets': 'Кам\'янець-Подільський',
    'oleksandriia': 'Олександрія',
    'alexandria': 'Олександрія',
    'mukachevo': 'Мукачево',
    'mukacheve': 'Мукачево',
    'yalta': 'Ялта',
    'simferopol': 'Сімферополь',
    'sevastopol': 'Севастополь',
}

_CYRILLIC_RE = re.compile(r'[а-яіїєґА-ЯІЇЄҐ]')


def _normalize_key(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def resolve_city_query(query):
    """Map Latin city names to Ukrainian for Nova Poshta API."""
    text = (query or '').strip()
    if not text or _CYRILLIC_RE.search(text):
        return text

    normalized = _normalize_key(text)
    return CITY_ALIASES.get(normalized, text)
