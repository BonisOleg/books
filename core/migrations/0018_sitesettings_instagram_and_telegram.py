"""Instagram OFION у sameAs; прибрати плейсхолдер Telegram.

sameAs на головній збирається з полів *_url. Порожній telegram.org або t.me
без шляху — не профіль, тож його очищаємо. Справжній t.me/<шлях> лишається.
"""
from django.db import migrations

INSTAGRAM_URL = 'https://www.instagram.com/ofion.com.ua/'


def set_ofion_social_urls(apps, schema_editor):
    from core.seo import is_placeholder_social_url

    SiteSettings = apps.get_model('core', 'SiteSettings')
    names = {field.name for field in SiteSettings._meta.concrete_fields}
    if 'instagram_url' in names:
        SiteSettings.objects.all().update(instagram_url=INSTAGRAM_URL)
    if 'telegram_url' not in names:
        return
    qs = SiteSettings.objects.all()
    rewrite = getattr(qs, 'rewrite', None)
    if callable(rewrite):
        qs = rewrite(False)
    for row in qs.iterator():
        if is_placeholder_social_url(row.telegram_url):
            SiteSettings.objects.filter(pk=row.pk).update(telegram_url='')


def noop_reverse(apps, schema_editor):
    """Попередні URL у репозиторії не збережені — відкат нічого не змінює."""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_default_shipping_time'),
    ]

    operations = [
        migrations.RunPython(set_ofion_social_urls, noop_reverse),
    ]
