from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from blog.models import Article, News
from products.models import Category, Product

from .models import Page


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


class PageDetailView(DetailView):
    model = Page
    context_object_name = 'page'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Page, slug=self.kwargs['slug'], is_published=True
        )

    def get_template_names(self):
        if self.request.GET.get('modal') == '1' or self.request.headers.get('HX-Request'):
            return ['core/page_modal.html']
        return ['core/page_detail.html']

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = ctx['page']
        ctx['page_title'] = page.meta_title or page.title
        ctx['page_meta_description'] = page.meta_description
        return ctx
