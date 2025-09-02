from django.urls import path
from . import views

urlpatterns = [
    path('create-razorpay-order/', views.create_razorpay_order, name='create_razorpay_order'),
    path('razorpay-webhook/', views.razorpay_webhook, name='razorpay_webhook'),
    path('confirm-paid-itinerary-creation/', views.confirm_paid_itinerary_creation, name='confirm_paid_itinerary_creation'),
    path('create-prepaid-order/', views.create_prepaid_order, name='create_prepaid_order'),
    path('confirm-prepaid-purchase/', views.confirm_prepaid_purchase, name='confirm_prepaid_purchase'),
    path('add-money/', views.add_money, name='add_money'),
    path('payment-success/', views.payment_success, name='payment_success'),
]