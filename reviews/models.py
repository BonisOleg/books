from django.db import models
from django.conf import settings
from products.models import Product


class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    product = models.ForeignKey(
        Product, verbose_name='Товар',
        related_name='reviews', on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Користувач',
        on_delete=models.SET_NULL, null=True, blank=True
    )
    author_name = models.CharField('Ім\'я автора', max_length=100, blank=True)
    rating = models.PositiveSmallIntegerField('Оцінка', choices=RATING_CHOICES, default=5)
    text = models.TextField('Текст відгуку')
    is_approved = models.BooleanField('Схвалено', default=False)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Відгук'
        verbose_name_plural = 'Відгуки'
        ordering = ['-created_at']

    def __str__(self):
        name = self.author_name or (self.user.get_full_name() if self.user else 'Анонім')
        return f"{name} - {self.rating}/5 - {self.product.name[:40]}"

    @property
    def display_name(self):
        if self.author_name:
            return self.author_name
        if self.user:
            return self.user.get_full_name() or self.user.username
        return 'Анонім'
