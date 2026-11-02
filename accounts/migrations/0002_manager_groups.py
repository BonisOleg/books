"""Групи менеджерів каталогу та замовлень.

Окремої моделі виробника немає: поле Product.manufacturer змінюється
разом із правом change на товар.

delete лише для фото товару. Знімок — допоміжний файл картки, а позиція
замовлення зберігає назву й артикул окремо (OrderItem.product_name /
product_sku). Прибрати помилкове фото менеджер може, не знищуючи товар,
категорію, бейдж чи фільтр: їхнє видалення лишається суперкористувачу.
"""

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_PRODUCTS = 'Менеджер товарів'
GROUP_ORDERS = 'Менеджер замовлень'

# (app_label, model, actions) — без delete, крім productimage.
PRODUCT_MANAGER_PERMS = (
    ('products', 'product', ('view', 'add', 'change')),
    ('products', 'category', ('view', 'add', 'change')),
    ('products', 'badge', ('view', 'add', 'change')),
    ('products', 'productimage', ('view', 'add', 'change', 'delete')),
    ('products', 'filtergroup', ('view', 'add', 'change')),
    ('products', 'filteroption', ('view', 'add', 'change')),
)

ORDER_MANAGER_PERMS = (
    ('orders', 'order', ('view', 'change')),
    ('orders', 'orderitem', ('view', 'change')),
    ('products', 'product', ('view',)),
)


def _ensure_permissions(apps, schema_editor):
    """Створити content types і permissions до призначення груп.

    У стані міграції AppConfig.models_module порожній, тож create_permissions
    на історичному конфігу виходить одразу. Беремо живі app_config (там є
    models_module), а записи Permission/ContentType пишемо в ту саму БД.
    """
    db = schema_editor.connection.alias
    labels = [app_config.label for app_config in apps.get_app_configs()]
    for label in labels:
        try:
            app_config = global_apps.get_app_config(label)
        except LookupError:
            continue
        create_permissions(
            app_config,
            verbosity=0,
            interactive=False,
            using=db,
            apps=global_apps,
        )


def _permissions_for(apps, spec):
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    collected = []
    for app_label, model_name, actions in spec:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        codenames = [f'{action}_{model_name}' for action in actions]
        rows = list(
            Permission.objects.filter(
                content_type=content_type,
                codename__in=codenames,
            )
        )
        found = {row.codename for row in rows}
        missing = [codename for codename in codenames if codename not in found]
        if missing:
            raise RuntimeError(
                f'Немає прав {app_label}.{model_name}: {", ".join(missing)}'
            )
        collected.extend(rows)
    return collected


def _grant(apps, group_name, spec):
    Group = apps.get_model('auth', 'Group')
    group, _created = Group.objects.get_or_create(name=group_name)
    group.permissions.set(_permissions_for(apps, spec))


def create_manager_groups(apps, schema_editor):
    _ensure_permissions(apps, schema_editor)
    _grant(apps, GROUP_PRODUCTS, PRODUCT_MANAGER_PERMS)
    _grant(apps, GROUP_ORDERS, ORDER_MANAGER_PERMS)


def remove_manager_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=(GROUP_PRODUCTS, GROUP_ORDERS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('products', '0020_trim_product_names'),
        ('orders', '0006_order_ads_attribution_and_conversion_log'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_manager_groups, remove_manager_groups),
    ]
