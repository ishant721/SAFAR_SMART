
from django.urls import path
from . import views

app_name = 'planner'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create_trip/', views.create_trip, name='create_trip'),
    path('create_paid_trip/', views.create_paid_trip, name='create_paid_trip'),
    path('trip_detail/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('process_trip/<int:trip_id>/', views.process_trip, name='process_trip'),
    path('trip/<int:trip_id>/chat/', views.chat_with_agent, name='chat_with_agent'),
    path('trip/<int:trip_id>/start_journey/', views.start_journey, name='start_journey'),
    path('get_realtime_weather/', views.get_realtime_weather, name='get_realtime_weather'),
    path('trip/<int:trip_id>/download_pdf/', views.download_trip_pdf, name='download_trip_pdf'),
    path('trip/<int:trip_id>/finalize/', views.finalize_trip, name='finalize_trip'),
    path('trip/<int:trip_id>/checkpoint/<int:checkpoint_id>/complete/', views.mark_checkpoint_complete, name='mark_checkpoint_complete'),
    path('trip/<int:trip_id>/checkpoint/<int:checkpoint_id>/feedback/', views.submit_checkpoint_feedback, name='submit_checkpoint_feedback'),
]