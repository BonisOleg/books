from django.urls import path
from . import views

app_name = 'promotions'

urlpatterns = [
    path('gift-picker/', views.gift_picker, name='gift_picker'),
    path('gift-picker/results/', views.gift_picker_results, name='gift_picker_results'),
]
