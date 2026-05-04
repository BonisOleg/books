import os
import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
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
        ).prefetch_related('categories', 'images').order_by('-created_at')[:20]

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


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


@csrf_exempt
@require_POST
@staff_member_required
def tinymce_upload_image(request):
    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': 'Файл не передано'}, status=400)

    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({'error': 'Дозволені лише зображення (JPEG, PNG, GIF, WEBP)'}, status=400)

    if upload.size > MAX_IMAGE_SIZE:
        return JsonResponse({'error': 'Розмір файлу перевищує 5 MB'}, status=400)

    ext = os.path.splitext(upload.name)[1].lower()
    filename = f'tinymce/{uuid.uuid4().hex}{ext}'
    saved_path = default_storage.save(filename, upload)
    url = default_storage.url(saved_path)

    return JsonResponse({'location': url})
