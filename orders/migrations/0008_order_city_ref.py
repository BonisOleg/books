from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_np_ttn'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='city_ref',
            field=models.CharField(
                blank=True,
                default='',
                max_length=100,
                verbose_name='Ref міста',
            ),
        ),
    ]
