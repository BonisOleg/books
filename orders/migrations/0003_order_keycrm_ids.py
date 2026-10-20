from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_alter_order_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='keycrm_order_id',
            field=models.PositiveBigIntegerField(
                blank=True, null=True, verbose_name='ID замовлення KeyCRM',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='keycrm_payment_id',
            field=models.PositiveBigIntegerField(
                blank=True, null=True, verbose_name='ID оплати KeyCRM',
            ),
        ),
    ]
