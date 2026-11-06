from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_article_news_published_at_ordering'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='cover_link',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Абсолютне http(s) або відносний шлях (/catalog/). Порожньо — на сторінку запису.',
                max_length=500,
                verbose_name='Посилання із заставки',
            ),
        ),
        migrations.AddField(
            model_name='news',
            name='cover_link',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Абсолютне http(s) або відносний шлях (/catalog/). Порожньо — на сторінку запису.',
                max_length=500,
                verbose_name='Посилання із заставки',
            ),
        ),
    ]
