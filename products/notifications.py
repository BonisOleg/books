from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _single_line(value) -> str:
    return ' '.join(str(value or '').split())


def send_consultation_notification(consultation) -> bool:
    """Надсилає заявку на notification_email з SiteSettings."""
    try:
        from core.models import SiteSettings

        settings_obj = SiteSettings.objects.first()
        recipient = ''
        if settings_obj is not None:
            recipient = (getattr(settings_obj, 'notification_email', '') or '').strip()
        if not recipient:
            return False

        product_name = _single_line(consultation.product_name)
        subject = f'Консультація — {product_name}' if product_name else 'Консультація'
        message = (
            f"Ім'я: {consultation.name}\n"
            f"Телефон: {consultation.phone}\n"
            f"Питання: {consultation.question}\n"
            f"Товар: {consultation.product_name}\n"
            f"Посилання: {consultation.product_url}\n"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Failed to send consultation notification email')
        return False
