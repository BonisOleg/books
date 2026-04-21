from django.urls import path
from . import views

app_name = 'import_export_app'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('export/', views.export_view, name='export'),
    path('import/', views.import_view, name='import_action'),
]
