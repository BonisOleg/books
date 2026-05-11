from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_page_show_in_header'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='default_order_info',
            field=models.TextField(
                blank=True,
                verbose_name='Інформація для замовлення (глобальна)',
                help_text='Відображається на сторінках усіх товарів, де поле «Інформація для замовлення» '
                          'залишено порожнім. Якщо і це поле порожнє — показується стандартний текст.',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='default_order_info_uk',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення (глобальна)'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='default_order_info_en',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення (глобальна)'),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='default_order_info_ru',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення (глобальна)'),
        ),
    ]
