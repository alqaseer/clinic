from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path('signup/', views.signup, name='signup'),
    path("login/", views.login_view, name="login"),
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
    path("editappointments/edit/<str:workspace_name>/<int:appointment_id>/", views.edit_appointment, name="edit_appointment"),
    path("update-confirmed-status/<int:appointment_id>/", views.update_confirmed_status, name="update_confirmed_status"),
    path('delete_surgical_case/<int:case_id>/', views.delete_surgical_case, name='delete_surgical_case'),
    path('workspace/<str:workspace_name>/cases/edit/<int:case_id>/', views.edit_surgical_booking, name='edit_surgical_booking'),
    path('restore_surgical_case/<int:case_id>/', views.restore_surgical_case, name='restore_surgical_case'),
    path("workspace/<str:workspace_name>/users/", views.users_management, name="users_management"),
    path("workspace/<str:workspace_name>/users/delete/<int:user_id>/", views.delete_user, name="delete_user"),
    path("workspace/<str:workspace_name>/appointments/search/", views.search_appointments_page, name="search_appointments_page"),
    path('check-availability/', views.check_availability, name='check_availability'),
    path("action-log/", views.action_log_view, name="action_log"),
    path("download-my-data/", views.download_workspace_data, name="download_my_data"),
    path('workspace/<str:workspace_name>/lock/<str:date>/', views.create_lock, name='create_lock'),
    path('workspace/<str:workspace_name>/unlock/<str:date>/', views.delete_lock, name='delete_lock'),


    # Referrals
    path('manage-specialities/', views.manage_specialities, name='manage_specialities'),

    # Doctor URLs
    path('doctor/login/', views.doctor_login, name='doctor_login'),
    path('doctor/login2/', views.doctor_login2, name='doctor_login2'),
    path('doctor/logout/', views.doctor_logout, name='doctor_logout'),
    path('doctor/logout2/', views.doctor_logout2, name='doctor_logout2'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/book-appointment/', views.book_appointment, name='book_appointment'),
    path('doctor/register/', views.doctor_register, name='doctor_register'),
    path('doctor/change-appointment-date/', views.change_appointment_date, name='change_appointment_date'),
    path('doctor/search-appointments/', views.doctor_search_appointments, name='doctor_search_appointments'),
    path('refer/', views.doctor_dashboard, name='refer'),

    


    #clerk
    path('doctor/calendar/', views.doctor_calendar, name='doctor_calendar'),
    path('doctor/appointments/<int:year>/<int:month>/<int:day>/', views.doctor_day_appointments, name='doctor_day_appointments'),
    path('doctor/appointments/<int:year>/<int:month>/<int:day>/print-all/', views.print_all_appointments, name='print_all_appointments'),
    path('clerk/', views.doctor_calendar, name='doctor_calendar'),

    # 2️⃣ API endpoint for AJAX search
    path("workspace/<str:workspace_name>/appointments/search/ajax/", views.search_appointments_ajax, name="search_appointments_ajax"),


    #patient lookup
    path('patient-lookup/', views.patient_lookup, name='patient_lookup'),



]

