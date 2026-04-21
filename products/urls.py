from django.urls import path
from . import views
from .feeds import google_merchant_feed

app_name = 'products'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('feed/google-merchant.xml', google_merchant_feed, name='google_merchant_feed'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='detail'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='category'),
]
