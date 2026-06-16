from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0015_product_order_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='google_product_category',
            field=models.CharField(
                blank=True,
                help_text='Числовий ID з Google Taxonomy. Книги: 784. '
                          'Якщо порожньо — успадковується від батьківської категорії або 784.',
                max_length=20,
                verbose_name='Google product category ID',
            ),
        ),
    ]
