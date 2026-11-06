import logging
import re
from datetime import datetime, timedelta

from django.db import migrations, models
from django.utils import timezone

logger = logging.getLogger(__name__)

_SOURCE_FIELDS = (
    'shipping_time_uk',
    'shipping_time',
    'shipping_time_en',
    'shipping_time_ru',
)

_RELATIVE_OFFSETS = {
    'сьогодні': 0,
    'today': 0,
    'завтра': 1,
    'tomorrow': 1,
    'післязавтра': 2,
    'після завтра': 2,
    'day after tomorrow': 2,
    'day-after-tomorrow': 2,
}

_PREFIX_RE = re.compile(
    r'^(?:відправимо|відправка|відправлення|ships?|shipping)\s+',
    re.IGNORECASE,
)

_DATE_FORMATS = (
    '%d.%m.%Y',
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%d-%m-%Y',
    '%Y.%m.%d',
    '%d.%m.%y',
    '%d/%m/%y',
    '%d-%m-%y',
)


def parse_shipping_time_text(raw, *, today):
    """Заморожена копія парсера для історичної стабільності міграції."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    normalized = re.sub(r'\s+', ' ', text.casefold()).strip(' .,:;!-')
    offset = _RELATIVE_OFFSETS.get(normalized)
    if offset is not None:
        return today + timedelta(days=offset)

    stripped = _PREFIX_RE.sub('', normalized).strip(' .,:;!-')
    offset = _RELATIVE_OFFSETS.get(stripped)
    if offset is not None:
        return today + timedelta(days=offset)

    for candidate in (text.strip(), normalized):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def convert_shipping_times(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    today = timezone.localdate()
    for product in Product.objects.all().iterator():
        parsed = None
        raw_values = []
        for field in _SOURCE_FIELDS:
            raw = getattr(product, field, None)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            raw_values.append(text)
            candidate = parse_shipping_time_text(text, today=today)
            if candidate is not None:
                parsed = candidate
                break
        if parsed is not None:
            product.shipping_time_date = parsed
            product.save(update_fields=['shipping_time_date'])
            continue
        for raw_text in raw_values:
            logger.warning(
                'Unparseable product shipping_time id=%s sku=%s raw=%r',
                product.pk,
                getattr(product, 'sku', '') or '',
                raw_text,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0026_category_seo_fixes'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='shipping_time_date',
            field=models.DateField(
                blank=True,
                help_text='Дата відправки біля наявності на сторінці товару (ДД.ММ.РРРР). '
                          'Майбутня або сьогоднішня дата показується; минула — приховується '
                          'без підстановки дефолту сайту. Порожньо — береться значення '
                          'з налаштувань сайту; якщо і там порожньо — рядок не показується.',
                null=True,
                verbose_name='Дата відправки',
            ),
        ),
        migrations.RunPython(convert_shipping_times, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='product',
            name='shipping_time_en',
        ),
        migrations.RemoveField(
            model_name='product',
            name='shipping_time_ru',
        ),
        migrations.RemoveField(
            model_name='product',
            name='shipping_time_uk',
        ),
        migrations.RemoveField(
            model_name='product',
            name='shipping_time',
        ),
        migrations.RenameField(
            model_name='product',
            old_name='shipping_time_date',
            new_name='shipping_time',
        ),
    ]
