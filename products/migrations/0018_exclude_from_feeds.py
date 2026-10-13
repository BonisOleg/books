from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0017_product_search_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='exclude_from_feeds',
            field=models.BooleanField(
                default=False,
                help_text='Товари цієї категорії (і підкатегорій) не потрапляють у /feeds/feed_vip.xml '
                          'та /feeds/feed_middle.xml. Старий google-merchant.xml не змінюється.',
                verbose_name='Виключити з VIP/Middle фідів',
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='exclude_from_feeds',
            field=models.BooleanField(
                default=False,
                help_text='Товар не потрапляє у /feeds/feed_vip.xml та /feeds/feed_middle.xml. '
                          'Старий google-merchant.xml не змінюється.',
                verbose_name='Виключити з VIP/Middle фідів',
            ),
        ),
    ]
