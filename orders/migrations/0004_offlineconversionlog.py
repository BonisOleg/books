from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_keycrm_ids'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfflineConversionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keycrm_order_id', models.PositiveBigIntegerField(unique=True, verbose_name='ID замовлення KeyCRM')),
                ('status', models.CharField(choices=[('uploaded', 'Вивантажено'), ('failed', 'Помилка')], max_length=20, verbose_name='Статус')),
                ('uploaded_at', models.DateTimeField(blank=True, null=True, verbose_name='Час вивантаження')),
                ('error', models.TextField(blank=True, verbose_name='Помилка')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Створено')),
            ],
            options={
                'verbose_name': 'Офлайн-конверсія Google Ads',
                'verbose_name_plural': 'Офлайн-конверсії Google Ads',
                'ordering': ['-created_at'],
            },
        ),
    ]
