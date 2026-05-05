from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_profile_cabinet_texts'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='notification_email',
            field=models.EmailField(
                blank=True,
                help_text='На цю адресу надходитимуть повідомлення про нові замовлення. '
                          'Якщо порожньо — сповіщення не надсилаються.',
                max_length=254,
                verbose_name='Email для сповіщень про замовлення',
            ),
        ),
    ]
