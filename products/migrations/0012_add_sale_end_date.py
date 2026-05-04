from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_product_remove_category_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='sale_end_date',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Кінець акції (таймер)',
                help_text=(
                    'Встановіть дату завершення — таймер запуститься автоматично. '
                    'Очистіть поле, коли акція закінчується.'
                ),
            ),
        ),
    ]
