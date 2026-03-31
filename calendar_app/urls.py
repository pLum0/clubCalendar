from django.urls import path
from . import views

urlpatterns = [
    path('', views.calendar_view, name='calendar'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/rsvp/', views.rsvp, name='rsvp'),
    path('event/<int:event_id>/guest-rsvp/', views.guest_rsvp, name='guest_rsvp'),
    path('event/<int:event_id>/update-occurrence/', views.update_occurrence, name='update_occurrence'),
    path('login/', views.login_user, name='login_user'),
    path('user/settings/', views.update_user_settings, name='update_user_settings'),
    path('preferences/', views.save_preferences, name='save_preferences'),
    path('upcoming/', views.upcoming_events, name='upcoming_events'),
    path('admin-panel/', views.admin_wrapper, name='admin_wrapper'),
]
