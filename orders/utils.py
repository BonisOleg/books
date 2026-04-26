from __future__ import annotations

import logging
import secrets
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def send_order_confirmation_email(order, request=None) -> bool:
    if not order.email:
        return False
    try:
        host = settings.SITE_DOMAIN
        protocol = settings.SITE_PROTOCOL
        if request is not None:
            host = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
        ctx = {
            'order': order,
            'site_name': getattr(settings, 'SITE_NAME', 'Магазин'),
            'site_url': f'{protocol}://{host}',
        }
        subject = f"Замовлення #{order.order_number} прийнято"
        text_body = render_to_string('orders/emails/order_confirmation.txt', ctx)
        html_body = render_to_string('orders/emails/order_confirmation.html', ctx)
        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.email],
            html_message=html_body,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Failed to send order confirmation email')
        return False


def create_account_for_order(order, request=None) -> Optional[object]:
    User = get_user_model()
    if not order.email:
        return None
    if User.objects.filter(email=order.email).exists():
        return None

    base_username = order.email.split('@')[0]
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base_username}{suffix}"

    user = User.objects.create_user(
        username=username,
        email=order.email,
        first_name=order.first_name,
        last_name=order.last_name,
        password=secrets.token_urlsafe(16),
    )
    if hasattr(user, 'phone'):
        user.phone = order.phone
    if hasattr(user, 'patronymic'):
        user.patronymic = order.patronymic
    user.save()

    order.user = user
    order.save(update_fields=['user'])

    _send_set_password_email(user, request)
    return user


def _send_set_password_email(user, request=None) -> None:
    try:
        host = settings.SITE_DOMAIN
        protocol = settings.SITE_PROTOCOL
        if request is not None:
            host = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        try:
            path = reverse(
                'accounts:password_reset_confirm',
                kwargs={'uidb64': uid, 'token': token},
            )
        except Exception:
            path = f'/accounts/password-set/?uid={uid}&token={token}'

        ctx = {
            'user': user,
            'reset_url': f'{protocol}://{host}{path}',
            'site_name': getattr(settings, 'SITE_NAME', 'Магазин'),
        }
        subject = 'Встановіть пароль для входу в особистий кабінет'
        text_body = render_to_string('orders/emails/set_password.txt', ctx)
        html_body = render_to_string('orders/emails/set_password.html', ctx)
        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send set-password email')
