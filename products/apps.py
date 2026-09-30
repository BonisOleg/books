from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'
    verbose_name = 'Товари'

    def ready(self):
        from products.signals import connect_product_search
        connect_product_search()
