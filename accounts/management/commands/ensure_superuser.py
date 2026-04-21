"""Ідемпотентне створення/оновлення суперюзера з ENV-змінних.

Безпечна для повторного запуску: якщо користувач уже існує — оновлює пароль
та піднімає прапори is_staff/is_superuser. Пропускає роботу, якщо ENV не
задані (щоб можна було залишити команду в pre-deploy без побічних ефектів).

Використання:
    python manage.py ensure_superuser
        --username admin --email a@x.com --password 'secret'

Або з ENV:
    DJANGO_SUPERUSER_USERNAME=admin
    DJANGO_SUPERUSER_EMAIL=admin@example.com
    DJANGO_SUPERUSER_PASSWORD=very-strong-pwd
    python manage.py ensure_superuser
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Створює або оновлює суперюзера з ENV (ідемпотентно).'

    def add_arguments(self, parser) -> None:
        parser.add_argument('--username', default=os.environ.get('DJANGO_SUPERUSER_USERNAME'))
        parser.add_argument('--email', default=os.environ.get('DJANGO_SUPERUSER_EMAIL', ''))
        parser.add_argument('--password', default=os.environ.get('DJANGO_SUPERUSER_PASSWORD'))

    def handle(self, *args, **options) -> None:
        username: str | None = options['username']
        email: str = options['email'] or ''
        password: str | None = options['password']

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'ensure_superuser: пропущено — DJANGO_SUPERUSER_USERNAME або '
                'DJANGO_SUPERUSER_PASSWORD не задані.'
            ))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = 'створено' if created else 'оновлено'
        self.stdout.write(self.style.SUCCESS(
            f'ensure_superuser: суперюзера "{username}" {action}.'
        ))
