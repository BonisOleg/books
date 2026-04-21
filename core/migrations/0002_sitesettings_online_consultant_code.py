from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='online_consultant_code',
            field=models.TextField(
                blank=True,
                verbose_name='Код онлайн-консультанта',
                help_text='Вставте скрипт-код від Tawk.to, JivoSite, Crisp або іншого чат-сервісу'
            ),
        ),
    ]
