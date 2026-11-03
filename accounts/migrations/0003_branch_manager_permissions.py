"""Права нових розділів для груп менеджерів.

Додає permissions, не замінюючи набір із 0002. Постачальники нікому
не призначаються: синхронізація фіду й підтвердження цін лишаються
суперкористувачу.
"""

import importlib

from django.db import migrations

_groups = importlib.import_module('accounts.migrations.0002_manager_groups')
GROUP_ORDERS = _groups.GROUP_ORDERS
GROUP_PRODUCTS = _groups.GROUP_PRODUCTS
_ensure_permissions = _groups._ensure_permissions
_permissions_for = _groups._permissions_for

# Групи меню каталогу і фільтри атрибутів — менеджер товарів.
PRODUCT_MANAGER_EXTRA = (
    ('products', 'productgroup', ('view', 'add', 'change')),
    ('products', 'filterattribute', ('view', 'add', 'change')),
    ('products', 'filtervalue', ('view', 'add', 'change')),
)

# Заявки на консультацію і ТТН Нової Пошти — менеджер замовлень.
ORDER_MANAGER_EXTRA = (
    ('products', 'consultationrequest', ('view', 'change')),
    ('shipping', 'shipmentorigin', ('view', 'add', 'change')),
    ('shipping', 'npttnsettings', ('view', 'add', 'change')),
)


def _add(apps, group_name, spec):
    Group = apps.get_model('auth', 'Group')
    group, _created = Group.objects.get_or_create(name=group_name)
    group.permissions.add(*_permissions_for(apps, spec))


def _remove(apps, group_name, spec):
    Group = apps.get_model('auth', 'Group')
    group = Group.objects.filter(name=group_name).first()
    if group is None:
        return
    group.permissions.remove(*_permissions_for(apps, spec))


def grant_branch_permissions(apps, schema_editor):
    _ensure_permissions(apps, schema_editor)
    _add(apps, GROUP_PRODUCTS, PRODUCT_MANAGER_EXTRA)
    _add(apps, GROUP_ORDERS, ORDER_MANAGER_EXTRA)


def revoke_branch_permissions(apps, schema_editor):
    _remove(apps, GROUP_PRODUCTS, PRODUCT_MANAGER_EXTRA)
    _remove(apps, GROUP_ORDERS, ORDER_MANAGER_EXTRA)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_manager_groups'),
        ('products', '0024_merge_20261102_1752'),
        ('shipping', '0002_seed_shipment_origins'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(grant_branch_permissions, revoke_branch_permissions),
    ]
