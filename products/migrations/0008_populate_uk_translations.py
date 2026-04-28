"""
Data migration: copy original field values into the Ukrainian (_uk) translation
columns for all product-related models.

Safe to run multiple times — only updates rows where _uk is NULL or empty.
"""
from django.db import migrations


def copy_to_uk(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cur:
        # Product
        cur.execute(
            "UPDATE products_product"
            " SET name_uk = name"
            " WHERE (name_uk IS NULL OR name_uk = '') AND (name IS NOT NULL AND name != '')"
        )
        cur.execute(
            "UPDATE products_product"
            " SET description_uk = description"
            " WHERE (description_uk IS NULL OR description_uk = '') AND (description IS NOT NULL AND description != '')"
        )
        cur.execute(
            "UPDATE products_product"
            " SET short_description_uk = short_description"
            " WHERE (short_description_uk IS NULL OR short_description_uk = '') AND (short_description IS NOT NULL AND short_description != '')"
        )
        cur.execute(
            "UPDATE products_product"
            " SET meta_title_uk = meta_title"
            " WHERE (meta_title_uk IS NULL OR meta_title_uk = '') AND (meta_title IS NOT NULL AND meta_title != '')"
        )
        cur.execute(
            "UPDATE products_product"
            " SET meta_description_uk = meta_description"
            " WHERE (meta_description_uk IS NULL OR meta_description_uk = '') AND (meta_description IS NOT NULL AND meta_description != '')"
        )

        # Category
        cur.execute(
            "UPDATE products_category"
            " SET name_uk = name"
            " WHERE (name_uk IS NULL OR name_uk = '') AND (name IS NOT NULL AND name != '')"
        )
        cur.execute(
            "UPDATE products_category"
            " SET description_uk = description"
            " WHERE (description_uk IS NULL OR description_uk = '') AND (description IS NOT NULL AND description != '')"
        )
        cur.execute(
            "UPDATE products_category"
            " SET meta_title_uk = meta_title"
            " WHERE (meta_title_uk IS NULL OR meta_title_uk = '') AND (meta_title IS NOT NULL AND meta_title != '')"
        )
        cur.execute(
            "UPDATE products_category"
            " SET meta_description_uk = meta_description"
            " WHERE (meta_description_uk IS NULL OR meta_description_uk = '') AND (meta_description IS NOT NULL AND meta_description != '')"
        )

        # Badge
        cur.execute(
            "UPDATE products_badge"
            " SET name_uk = name"
            " WHERE (name_uk IS NULL OR name_uk = '') AND (name IS NOT NULL AND name != '')"
        )

        # ProductAttribute
        cur.execute(
            "UPDATE products_productattribute"
            " SET name_uk = name"
            " WHERE (name_uk IS NULL OR name_uk = '') AND (name IS NOT NULL AND name != '')"
        )
        cur.execute(
            "UPDATE products_productattribute"
            " SET value_uk = value"
            " WHERE (value_uk IS NULL OR value_uk = '') AND (value IS NOT NULL AND value != '')"
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_badge_name_en_badge_name_ru_badge_name_uk_and_more'),
    ]

    operations = [
        migrations.RunPython(copy_to_uk, noop),
    ]
