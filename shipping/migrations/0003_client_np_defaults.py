"""Типова точка «Київ №129» і параметри ТТН для кабінету Нової Пошти.

Імені відправника в моделі немає: «ФОП Барабан Л.В.» береться з кабінету НП.
default_weight не змінюється. auto_create_ttn лишається вимкненим.
"""

from django.db import migrations

ORIGIN_NAME = 'Київ №129'
SENDER_PHONE = '+380989913455'


def configure_np(apps, schema_editor):
    ShipmentOrigin = apps.get_model('shipping', 'ShipmentOrigin')
    NPTTNSettings = apps.get_model('shipping', 'NPTTNSettings')

    origin = ShipmentOrigin.objects.filter(name=ORIGIN_NAME).first()
    if origin is None:
        origin = ShipmentOrigin.objects.create(
            name=ORIGIN_NAME,
            kind='warehouse',
            city_name='Київ',
            warehouse_name='№129',
            is_active=True,
            is_default=False,
        )
    ShipmentOrigin.objects.exclude(pk=origin.pk).update(is_default=False)
    ShipmentOrigin.objects.filter(pk=origin.pk).update(is_active=True, is_default=True)

    payload = {
        'payer_type': 'Recipient',
        'cod_mode': 'afterpayment',
        'sender_phone': SENDER_PHONE,
        'sender_type': 'Organization',
        'auto_create_ttn': False,
    }
    row = NPTTNSettings.objects.order_by('pk').first()
    if row is None:
        NPTTNSettings.objects.create(pk=1, **payload)
        return
    for key, value in payload.items():
        setattr(row, key, value)
    row.save(update_fields=list(payload))


def clear_default_origin(apps, schema_editor):
    ShipmentOrigin = apps.get_model('shipping', 'ShipmentOrigin')
    ShipmentOrigin.objects.filter(name=ORIGIN_NAME).update(is_default=False)


class Migration(migrations.Migration):

    dependencies = [
        ('shipping', '0002_seed_shipment_origins'),
    ]

    operations = [
        migrations.RunPython(configure_np, clear_default_origin),
    ]
