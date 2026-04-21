from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('articles/', views.ArticleListView.as_view(), name='articles'),
    path('articles/<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('news/', views.NewsListView.as_view(), name='news_list'),
    path('news/<slug:slug>/', views.NewsDetailView.as_view(), name='news_detail'),
]
