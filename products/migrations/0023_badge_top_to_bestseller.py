from django.db import migrations


def set_bestseller_for_badge_top(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(badge='top').update(is_bestseller=True)


def unset_bestseller_for_badge_top(apps, schema_editor):
    # reverse не відрізняє вручну поставлені галочки на товарах з badge='top' — це прийнятно.
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(badge='top').update(is_bestseller=False)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0022_menu_groups_bestseller'),
    ]

    operations = [
        migrations.RunPython(
            set_bestseller_for_badge_top,
            unset_bestseller_for_badge_top,
        ),
    ]
