from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('success/<int:order_id>/', views.order_success, name='success'),
    path('oneclick/<int:product_id>/', views.oneclick, name='oneclick'),
    path('pay/liqpay/<int:order_id>/', views.pay_liqpay, name='pay_liqpay'),
    path('pay/mono/<int:order_id>/', views.pay_mono, name='pay_mono'),
    path('callback/liqpay/', views.liqpay_callback, name='liqpay_callback'),
    path('callback/mono/', views.mono_callback, name='mono_callback'),
]
