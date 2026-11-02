from django.apps import AppConfig


class SuppliersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'suppliers'
    verbose_name = 'Постачальники'

    def ready(self):
        from suppliers.parsers.registry import ensure_parsers_loaded
        ensure_parsers_loaded()
