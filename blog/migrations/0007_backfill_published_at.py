"""Копіює created_at у published_at, щоб наявні записи лишились видимими."""
from django.db import migrations
from django.db.models import F


def backfill_published_at(apps, schema_editor):
    for model_name in ('Article', 'News'):
        model = apps.get_model('blog', model_name)
        model.objects.all().update(published_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0006_article_news_published_at'),
    ]

    operations = [
        migrations.RunPython(backfill_published_at, migrations.RunPython.noop),
    ]
