"""
Data migration: copy original field values into the Ukrainian (_uk) translation
columns for Article and News models.

Safe to run multiple times — only updates rows where _uk is NULL or empty.
"""
from django.db import migrations


def copy_to_uk(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        for table in ('blog_article', 'blog_news'):
            for field in ('title', 'content', 'excerpt', 'meta_title', 'meta_description'):
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
        ('blog', '0004_article_content_en_article_content_ru_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_uk, noop),
    ]
