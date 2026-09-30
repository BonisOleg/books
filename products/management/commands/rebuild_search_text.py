from django.core.management.base import BaseCommand

from products.models import Product
from products.search import build_search_fields


class Command(BaseCommand):
    help = 'Перебудовує search_name і search_text для всіх товарів.'

    def handle(self, *args, **options):
        count = 0
        for product in Product.objects.iterator():
            Product.objects.filter(pk=product.pk).update(**build_search_fields(product))
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Оновлено індекс пошуку: {count}'))
