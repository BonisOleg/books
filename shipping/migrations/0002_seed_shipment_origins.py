from django.db import migrations

ORIGINS = [
    {
        'name': 'Хмельницький №7',
        'kind': 'warehouse',
        'city_name': 'Хмельницький',
        'warehouse_name': '№7',
    },
    {
        'name': 'Київ №129',
        'kind': 'warehouse',
        'city_name': 'Київ',
        'warehouse_name': '№129',
    },
    {
        'name': 'Київ, адресний забір, вул. Золотоустівська 10-12',
        'kind': 'address_pickup',
        'city_name': 'Київ',
        'street_name': 'Золотоустівська',
        'building': '10-12',
    },
    {
        'name': 'Дніпро №64',
        'kind': 'warehouse',
        'city_name': 'Дніпро',
        'warehouse_name': '№64',
    },
    {
        'name': 'Вишгород №1',
        'kind': 'warehouse',
        'city_name': 'Вишгород',
        'warehouse_name': '№1',
    },
    {
        'name': 'Кагарлик №1',
        'kind': 'warehouse',
        'city_name': 'Кагарлик',
        'warehouse_name': '№1',
    },
    {
        'name': 'Зимна Вода №1',
        'kind': 'warehouse',
        'city_name': 'Зимна Вода',
        'warehouse_name': '№1',
    },
]


def seed_origins(apps, schema_editor):
    ShipmentOrigin = apps.get_model('shipping', 'ShipmentOrigin')
    for row in ORIGINS:
        defaults = {
            'kind': row['kind'],
            'city_name': row.get('city_name', ''),
            'city_ref': '',
            'warehouse_name': row.get('warehouse_name', ''),
            'warehouse_ref': '',
            'street_name': row.get('street_name', ''),
            'street_ref': '',
            'building': row.get('building', ''),
            'is_active': True,
            'is_default': False,
        }
        ShipmentOrigin.objects.get_or_create(name=row['name'], defaults=defaults)


def unseed_origins(apps, schema_editor):
    ShipmentOrigin = apps.get_model('shipping', 'ShipmentOrigin')
    ShipmentOrigin.objects.filter(name__in=[row['name'] for row in ORIGINS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('shipping', '0001_np_ttn'),
    ]

    operations = [
        migrations.RunPython(seed_origins, unseed_origins),
    ]
