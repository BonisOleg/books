from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0004_populate_uk_translations'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotion',
            name='auto_synced',
            field=models.BooleanField(
                default=False,
                help_text='Встановлено автоматично з поля «Кінець акції (таймер)» товару.',
                verbose_name='Авто-синхронізовано',
            ),
        ),
        migrations.AlterField(
            model_name='promotion',
            name='title',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Необов\'язково. Якщо залишити порожнім — таймер покажеться без заголовку.',
                max_length=200,
                verbose_name='Назва акції',
            ),
        ),
    ]
