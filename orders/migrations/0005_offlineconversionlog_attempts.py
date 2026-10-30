from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_offlineconversionlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='offlineconversionlog',
            name='attempts',
            field=models.PositiveIntegerField(default=0, verbose_name='Спроби'),
        ),
        migrations.AddField(
            model_name='offlineconversionlog',
            name='last_attempt_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Остання спроба'),
        ),
    ]
