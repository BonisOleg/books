import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_add_sale_end_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='FilterGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text='Заголовок блоку фільтру на сайті. Наприклад: «Бюджет», «Наявність».',
                    max_length=100, verbose_name='Назва групи',
                )),
                ('name_uk', models.CharField(
                    help_text='Заголовок блоку фільтру на сайті. Наприклад: «Бюджет», «Наявність».',
                    max_length=100, null=True, verbose_name='Назва групи',
                )),
                ('name_en', models.CharField(
                    help_text='Заголовок блоку фільтру на сайті. Наприклад: «Бюджет», «Наявність».',
                    max_length=100, null=True, verbose_name='Назва групи',
                )),
                ('name_ru', models.CharField(
                    help_text='Заголовок блоку фільтру на сайті. Наприклад: «Бюджет», «Наявність».',
                    max_length=100, null=True, verbose_name='Назва групи',
                )),
                ('filter_type', models.CharField(
                    choices=[
                        ('price_range', 'Діапазон ціни'),
                        ('stock', 'Наявність'),
                        ('badge', 'Мітки (бейджі)'),
                        ('subcategory', 'Підкатегорії'),
                    ],
                    help_text='Визначає, як цей фільтр застосовується до товарів.',
                    max_length=20, verbose_name='Тип фільтру',
                )),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активний')),
                ('categories', models.ManyToManyField(
                    blank=True,
                    help_text='Залиш пустим — фільтр показується у всіх категоріях.',
                    related_name='filter_groups',
                    to='products.category',
                    verbose_name='Категорії',
                )),
            ],
            options={
                'verbose_name': 'Група фільтрів',
                'verbose_name_plural': 'Групи фільтрів',
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='FilterOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(
                    help_text='Текст, що бачить відвідувач. Наприклад: «В наявності», «Акція».',
                    max_length=100, verbose_name='Підпис',
                )),
                ('label_uk', models.CharField(
                    help_text='Текст, що бачить відвідувач. Наприклад: «В наявності», «Акція».',
                    max_length=100, null=True, verbose_name='Підпис',
                )),
                ('label_en', models.CharField(
                    help_text='Текст, що бачить відвідувач. Наприклад: «В наявності», «Акція».',
                    max_length=100, null=True, verbose_name='Підпис',
                )),
                ('label_ru', models.CharField(
                    help_text='Текст, що бачить відвідувач. Наприклад: «В наявності», «Акція».',
                    max_length=100, null=True, verbose_name='Підпис',
                )),
                ('value', models.CharField(
                    help_text='Технічний ключ без пробілів. Наприклад: in_stock, sale, new.',
                    max_length=100, verbose_name='Значення (value)',
                )),
                ('order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='options',
                    to='products.filtergroup',
                    verbose_name='Група',
                )),
            ],
            options={
                'verbose_name': 'Варіант фільтру',
                'verbose_name_plural': 'Варіанти фільтру',
                'ordering': ['order'],
            },
        ),
    ]
