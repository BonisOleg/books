"""
Data migration: copy original field values into the Ukrainian (_uk) translation
columns for Promotion, GiftPickerQuestion, GiftPickerOption.

Safe to run multiple times — only updates rows where _uk is NULL or empty.
"""
from django.db import migrations


_TABLES = {
    'promotions_promotion': ('title', 'description'),
    'promotions_giftpickerquestion': ('text',),
    'promotions_giftpickeroption': ('text',),
}


def copy_to_uk(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        for table, fields in _TABLES.items():
            for field in fields:
                cur.execute(
                    f"UPDATE {table}"
                    f" SET {field}_uk = {field}"
                    f" WHERE ({field}_uk IS NULL OR {field}_uk = '')"
                    f" AND ({field} IS NOT NULL AND {field} != '')"
                )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0003_giftpickeroption_text_en_giftpickeroption_text_ru_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_uk, noop),
    ]
