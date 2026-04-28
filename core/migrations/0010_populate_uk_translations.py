"""
Data migration: copy original field values into the Ukrainian (_uk) translation
columns for core models: SiteSettings, FAQ, Banner, Page, SEOTemplate.

Safe to run multiple times — only updates rows where _uk is NULL or empty.
"""
from django.db import migrations


_TABLES = {
    'core_sitesettings': (
        'site_description', 'promo_banner_text',
        'seo_home_title', 'seo_home_description',
    ),
    'core_faq': ('question', 'answer'),
    'core_banner': ('alt_text',),
    'core_page': ('title', 'content', 'meta_title', 'meta_description'),
    'core_seotemplate': ('meta_title_template', 'meta_description_template'),
}


def copy_to_uk(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        for table, fields in _TABLES.items():
            for field in fields:
                cur.execute(
                    f"UPDATE {table}"
                    f" SET {field}_uk = {field}"
                    f" WHERE ({field}_uk IS NULL OR {field}_uk = '')"
                    f" AND ({field} IS NOT NULL AND {field} != '')"
                )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_banner_alt_text_en_banner_alt_text_ru_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_uk, noop),
    ]
