from django.db import migrations


def copy_fk_to_m2m(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.filter(category__isnull=False).iterator():
        product.categories.add(product.category_id)


def reverse_m2m_to_fk(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.prefetch_related('categories').iterator():
        first = product.categories.first()
        if first:
            product.category_id = first.pk
            product.save(update_fields=['category_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_product_categories_add'),
    ]

    operations = [
        migrations.RunPython(copy_fk_to_m2m, reverse_code=reverse_m2m_to_fk),
    ]
