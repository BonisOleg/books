from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Ядро сайту'

    def ready(self):
        from core.signals import connect_image_signals
        connect_image_signals()
