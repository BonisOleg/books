"""
Management command: fix_html_descriptions

Decodes double-encoded HTML entities in Product.description and
Product.short_description fields.

Problem: content pasted via TinyMCE source-view or copied from AI tools
sometimes ends up stored as entity-escaped HTML (e.g. &lt;h1&gt; instead of
<h1>). Django renders such content correctly only when the template does NOT
use |safe; but since description fields intentionally use |safe for rich text,
the encoded tags become visible as literal text on the page.

Run on Render after deploy:
    python manage.py fix_html_descriptions
    python manage.py fix_html_descriptions --dry-run
"""

import html as html_module
import re

from django.core.management.base import BaseCommand

from products.models import Product

_DATA_ATTRS_RE = re.compile(
    r'\s+data-(start|end|section-id)="[^"]*"',
    flags=re.IGNORECASE,
)


def _needs_unescape(text: str) -> bool:
    return bool(text) and ("&lt;" in text or "&amp;lt;" in text)


def _clean(text: str) -> str:
    """Unescape HTML entities and strip AI-injected data-* attributes."""
    if not text:
        return text

    cleaned = html_module.unescape(text)

    # second pass in case of double-encoding (&amp;lt; → &lt; → <)
    if "&lt;" in cleaned:
        cleaned = html_module.unescape(cleaned)

    # remove data-start / data-end / data-section-id injected by AI tools
    cleaned = _DATA_ATTRS_RE.sub("", cleaned)

    return cleaned


class Command(BaseCommand):
    help = "Decode double-encoded HTML in Product description and short_description"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be changed without saving to the database",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        fixed = 0
        skipped = 0

        products = Product.objects.only("id", "name", "description", "short_description")

        for product in products.iterator():
            desc_dirty = _needs_unescape(product.description)
            short_dirty = _needs_unescape(product.short_description)

            # also clean AI attributes even when no entity encoding is present
            desc_has_ai_attrs = _DATA_ATTRS_RE.search(product.description or "")
            short_has_ai_attrs = _DATA_ATTRS_RE.search(product.short_description or "")

            if not (desc_dirty or short_dirty or desc_has_ai_attrs or short_has_ai_attrs):
                skipped += 1
                continue

            new_desc = _clean(product.description)
            new_short = _clean(product.short_description)

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY-RUN] Would fix: {product.name!r} (id={product.id})"
                    )
                )
                if desc_dirty or desc_has_ai_attrs:
                    self.stdout.write(f"  description before: {product.description[:120]!r}")
                    self.stdout.write(f"  description after:  {new_desc[:120]!r}")
                if short_dirty or short_has_ai_attrs:
                    self.stdout.write(f"  short_description before: {product.short_description[:120]!r}")
                    self.stdout.write(f"  short_description after:  {new_short[:120]!r}")
            else:
                update_fields = []
                if new_desc != product.description:
                    product.description = new_desc
                    update_fields.append("description")
                if new_short != product.short_description:
                    product.short_description = new_short
                    update_fields.append("short_description")

                if update_fields:
                    product.save(update_fields=update_fields)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Fixed: {product.name!r} (id={product.id}) — fields: {update_fields}"
                        )
                    )

            fixed += 1

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run complete. Would fix {fixed}, skip {skipped}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. Fixed {fixed}, skipped {skipped}."))
