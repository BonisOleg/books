from django.views.generic import ListView, DetailView
from .models import Article, News


class ArticleListView(ListView):
    model = Article
    template_name = 'blog/article_list.html'
    context_object_name = 'articles'
    paginate_by = 12

    def get_queryset(self):
        return Article.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'Статті'
        return ctx


class ArticleDetailView(DetailView):
    model = Article
    template_name = 'blog/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        return Article.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.meta_title or self.object.title
        ctx['page_meta_description'] = self.object.meta_description or self.object.excerpt
        return ctx


class NewsListView(ListView):
    model = News
    template_name = 'blog/news_list.html'
    context_object_name = 'news_list'
    paginate_by = 12

    def get_queryset(self):
        return News.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = 'Новини'
        return ctx


class NewsDetailView(DetailView):
    model = News
    template_name = 'blog/news_detail.html'
    context_object_name = 'news_item'

    def get_queryset(self):
        return News.objects.filter(is_published=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = self.object.meta_title or self.object.title
        ctx['page_meta_description'] = self.object.meta_description or self.object.excerpt
        return ctx
