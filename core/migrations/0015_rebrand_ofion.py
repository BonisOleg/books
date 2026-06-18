"""Rebrand: Магазин книжок → OFION."""
from django.db import migrations, models

OLD_SITE_NAME = 'Магазин книжок'
NEW_SITE_NAME = 'OFION'
NEW_HOME_TITLE = 'OFION – статусні подарунки для керівників, партнерів і близьких'
OLD_HOME_TITLE = 'Магазин книжок — елітні книги, подарунки та ексклюзивні товари'


def rebrand_site_settings(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    for obj in SiteSettings.objects.all():
        changed = False
        if obj.site_name.strip().lower() == OLD_SITE_NAME.lower():
            obj.site_name = NEW_SITE_NAME
            changed = True

        title_fields = ('seo_home_title', 'seo_home_title_uk')
        for field in title_fields:
            if not hasattr(obj, field):
                continue
            current = (getattr(obj, field) or '').strip()
            if not current or current == OLD_HOME_TITLE or current.lower().startswith('магазин книжок'):
                setattr(obj, field, NEW_HOME_TITLE)
                changed = True

        if changed:
            obj.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_sitesettings_default_order_info'),
    ]

    operations = [
        migrations.RunPython(rebrand_site_settings, noop),
        migrations.AlterField(
            model_name='sitesettings',
            name='site_name',
            field=models.CharField(default='OFION', max_length=200, verbose_name='Назва сайту'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='seo_home_title',
            field=models.CharField(
                blank=True,
                default='OFION – статусні подарунки для керівників, партнерів і близьких',
                max_length=200,
                verbose_name='SEO title головної',
            ),
        ),
    ]
