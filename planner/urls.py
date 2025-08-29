from django.urls import path
from . import views

urlpatterns = [
    path('create_trip/', views.create_trip, name='create_trip'),
    path('trip_detail/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('process_trip/<int:trip_id>/', views.process_trip, name='process_trip'),
    path('chat_with_agent/<int:trip_id>/', views.chat_with_agent, name='chat_with_agent'),
]