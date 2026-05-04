from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_populate_uk_translations'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='products_m2m',
                to='products.category',
                verbose_name='Категорії',
            ),
        ),
    ]
