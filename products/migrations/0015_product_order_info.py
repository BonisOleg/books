from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_fix_unicode_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='order_info',
            field=models.TextField(
                blank=True,
                verbose_name='Інформація для замовлення',
                help_text='Відображається у вкладці «Інформація для замовлення» на сторінці товару. '
                          'Якщо залишити порожнім — показуватиметься стандартний текст.',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='order_info_uk',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення'),
        ),
        migrations.AddField(
            model_name='product',
            name='order_info_en',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення'),
        ),
        migrations.AddField(
            model_name='product',
            name='order_info_ru',
            field=models.TextField(blank=True, null=True, verbose_name='Інформація для замовлення'),
        ),
    ]
