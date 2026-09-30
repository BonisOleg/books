from django.db import migrations, models


def populate_search_index(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    from products.search import build_search_fields
    for product in Product.objects.iterator():
        Product.objects.filter(pk=product.pk).update(**build_search_fields(product))


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_category_google_product_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='search_name',
            field=models.TextField(blank=True, default='', editable=False, verbose_name='Індекс назви'),
        ),
        migrations.AddField(
            model_name='product',
            name='search_text',
            field=models.TextField(blank=True, default='', editable=False, verbose_name='Індекс пошуку'),
        ),
        migrations.RunPython(populate_search_index, migrations.RunPython.noop),
    ]
