
from django.urls import path
from . import views

app_name = 'planner'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create_trip/', views.create_trip, name='create_trip'),
    path('create_paid_trip/', views.create_paid_trip, name='create_paid_trip'),
    path('trip_detail/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('process_trip/<int:trip_id>/', views.process_trip, name='process_trip'),
    path('chat_with_agent/<int:trip_id>/', views.chat_with_agent, name='chat_with_agent'),
    path('download_trip_pdf/<int:trip_id>/', views.download_trip_pdf, name='download_trip_pdf'),
    path('trip/<int:trip_id>/finalize/', views.finalize_trip, name='finalize_trip'),
    path('trip/<int:trip_id>/checkpoint/<int:checkpoint_id>/complete/', views.mark_checkpoint_complete, name='mark_checkpoint_complete'),
    path('trip/<int:trip_id>/checkpoint/<int:checkpoint_id>/feedback/', views.submit_checkpoint_feedback, name='submit_checkpoint_feedback'),
]