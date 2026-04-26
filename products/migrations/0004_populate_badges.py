from django.db import migrations


BADGE_PRESETS = [
    ('sale', 'Акція', 'red', 0),
    ('top', 'Топ продажів', 'orange', 1),
    ('new', 'Новинка', 'green', 2),
]


def create_default_badges(apps, schema_editor):
    Badge = apps.get_model('products', 'Badge')
    Product = apps.get_model('products', 'Product')

    badge_by_slug = {}
    for slug, name, color, order in BADGE_PRESETS:
        badge, _ = Badge.objects.get_or_create(
            slug=slug,
            defaults={
                'name': name,
                'color': color,
                'order': order,
                'is_active': True,
            },
        )
        badge_by_slug[slug] = badge

    for product in Product.objects.exclude(badge='').iterator():
        badge = badge_by_slug.get(product.badge)
        if badge:
            product.badge_obj = badge
            product.save(update_fields=['badge_obj'])


def remove_default_badges(apps, schema_editor):
    Badge = apps.get_model('products', 'Badge')
    Badge.objects.filter(slug__in=[s for s, *_ in BADGE_PRESETS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_badge_alter_category_image_alter_product_badge_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_badges, remove_default_badges),
    ]
