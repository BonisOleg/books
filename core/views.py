from django.views.generic import TemplateView
from products.models import Product, Category
from blog.models import Article, News


class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['categories'] = Category.objects.filter(
            parent__isnull=True, is_active=True
        ).order_by('order')[:20]

        context['hit_products'] = Product.objects.filter(
            is_active=True
        ).select_related('category').prefetch_related('images').order_by('-created_at')[:20]

        context['latest_news'] = News.objects.filter(
            is_published=True
        ).order_by('-created_at')[:4]

        context['latest_articles'] = Article.objects.filter(
            is_published=True
        ).order_by('-created_at')[:4]

        return context
