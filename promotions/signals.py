from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender='products.Product')
def sync_promotion_on_sale_end_date(sender, instance, **kwargs):
    """
    Якщо на товарі встановлено sale_end_date у майбутньому —
    автоматично створює або оновлює авто-синхронізовану Promotion.
    Якщо sale_end_date знято або вже минула — деактивує її.
    """
    from .models import Promotion

    now = timezone.now()

    if instance.sale_end_date and instance.sale_end_date > now:
        promo, created = Promotion.objects.get_or_create(
            product=instance,
            auto_synced=True,
            defaults={
                'title': '',
                'start_date': now,
                'end_date': instance.sale_end_date,
                'is_active': True,
            },
        )
        if not created:
            Promotion.objects.filter(pk=promo.pk).update(
                end_date=instance.sale_end_date,
                is_active=True,
            )
    else:
        Promotion.objects.filter(
            product=instance, auto_synced=True
        ).update(is_active=False)
