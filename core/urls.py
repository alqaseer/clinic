from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('workspace/create/', views.create_workspace, name='create_workspace'),
    path('workspaces/', views.workspace_list, name='workspace_list'),
    path('workspace/<int:workspace_id>/edit/', views.edit_workspace, name='edit_workspace'),


]
