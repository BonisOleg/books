from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_migrate_category_to_categories'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='category',
        ),
        migrations.AlterField(
            model_name='product',
            name='categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='products',
                to='products.category',
                verbose_name='Категорії',
            ),
        ),
    ]
