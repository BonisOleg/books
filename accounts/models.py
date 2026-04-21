from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    phone = models.CharField('Телефон', max_length=30, blank=True)
    patronymic = models.CharField('По батькові', max_length=150, blank=True)

    class Meta:
        verbose_name = 'Користувач'
        verbose_name_plural = 'Користувачі'
