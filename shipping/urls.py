from django.urls import path
from . import views

app_name = 'shipping'

urlpatterns = [
    path('api/cities/', views.api_cities, name='api_cities'),
    path('api/warehouses/', views.api_warehouses, name='api_warehouses'),
]
