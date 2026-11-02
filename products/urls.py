from django.urls import path

from . import views
from .consultation import consultation_request

app_name = 'products'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('search/suggest/', views.SearchSuggestView.as_view(), name='search_suggest'),
    path('product/<slug:slug>/', views.ProductDetailView.as_view(), name='detail'),
    path('product/<slug:slug>/consult/', consultation_request, name='consult'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='category'),
]
