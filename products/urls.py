from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('search/suggest/', views.SearchSuggestView.as_view(), name='search_suggest'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='detail'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='category'),
]
