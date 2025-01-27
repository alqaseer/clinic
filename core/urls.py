from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('workspace/<str:workspace_name>/login/', views.login_view, name='login'),
    path('workspace/<str:workspace_name>/', views.workspace_main, name='workspace_main'),
    path('logout/', views.logout_view, name='logout'),
    path('workspace/<str:workspace_name>/cases/booked/', views.booked_cases, name='booked_cases'),
    path('workspace/<str:workspace_name>/cases/waiting/', views.waiting_list, name='waiting_list'),
    path('workspace/<str:workspace_name>/cases/past/', views.past_cases, name='past_cases'),
    path('workspace/<str:workspace_name>/cases/deleted/', views.deleted_cases, name='deleted_cases'),
    path('workspace/<str:workspace_name>/surgical/add/', views.add_surgical_booking, name='add_surgical_booking'),
    path('calendar/<str:workspace_name>/', views.calendar_view, name='calendar'),
    path("settings/<str:workspace_name>/", views.settings_page, name="settings_page"),
    path("calendar/<str:workspace_name>/", views.calendar_view, name="calendar_view"),
    path("appointments/add/<str:workspace_name>/", views.add_appointment, name="add_appointment"),
    path("appointments/<str:workspace_name>/<str:date>/", views.day_appointments, name="day_appointments"),
    



]

