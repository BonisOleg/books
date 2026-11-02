from django.utils import timezone
from django.views.generic import ListView, DetailView

from .models import Article, News


def _post_schema(obj, request, schema_type):
    """JSON-LD картки публікації: дата — published_at у локальному часі."""
    schema = {
        '@context': 'https://schema.org',
        '@type': schema_type,
        'headline': obj.title,
        'datePublished': timezone.localtime(obj.published_at).isoformat(),
        'dateModified': timezone.localtime(obj.updated_at).isoformat(),
        'url': request.build_absolute_uri(obj.get_absolute_url()),
    }
    description = obj.meta_description or obj.excerpt
    if description:
        schema['description'] = description
    if obj.image:
        schema['image'] = request.build_absolute_uri(obj.image.url)
    return schema


class ArticleListView(ListView):
    model = Article
    template_name = 'blog/article_list.html'
    context_object_name = 'articles'
    paginate_by = 12

    def get_queryset(self):
        return Article.objects.published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'Статті'
        return ctx


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'blog/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        return Article.objects.published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.meta_title or self.object.title
        ctx['page_meta_description'] = self.object.meta_description or self.object.excerpt
        ctx['article_schema'] = _post_schema(self.object, self.request, 'BlogPosting')
        return ctx


class NewsListView(ListView):
    model = News
    template_name = 'blog/news_list.html'
    context_object_name = 'news_list'
    paginate_by = 12

    def get_queryset(self):
        return News.objects.published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'Новини'
        return ctx


class NewsDetailView(DetailView):
    model = News
    template_name = 'blog/news_detail.html'
    context_object_name = 'news_item'

    def get_queryset(self):
        return News.objects.published()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.meta_title or self.object.title
        ctx['page_meta_description'] = self.object.meta_description or self.object.excerpt
        ctx['news_schema'] = _post_schema(self.object, self.request, 'NewsArticle')
        return ctx
