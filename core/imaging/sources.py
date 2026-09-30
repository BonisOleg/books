"""Моделі та поля зображень, для яких будуються WebP-варіанти."""

IMAGE_FIELDS = (
    ('core', 'Banner', ('image', 'image_mobile')),
    ('core', 'SiteSettings', ('logo',)),
    ('products', 'Category', ('image',)),
    ('products', 'ProductImage', ('image',)),
    ('products', 'ProductVideo', ('poster',)),
    ('blog', 'Article', ('image',)),
    ('blog', 'News', ('image',)),
)


def iter_image_files():
    from django.apps import apps

    for app_label, model_name, field_names in IMAGE_FIELDS:
        model = apps.get_model(app_label, model_name)
        for obj in model.objects.all().iterator():
            for field_name in field_names:
                field = getattr(obj, field_name, None)
                if not field:
                    continue
                yield obj, field_name, field
