from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import *  
from .models import *
from django.contrib.auth.decorators import login_required

# Sign-up view
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Save the user
            login(request, user)  # Log in the user
            return redirect('home')  # Redirect to the home page or workspace
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})

# Login view
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')  # Change this later to your workspace
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

# Logout view
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def create_workspace(request):
    if request.method == 'POST':
        form = WorkspaceForm(request.POST)
        if form.is_valid():
            workspace = form.save(commit=False)
            workspace.admin = request.user  # Set the current user as admin
            workspace.save()
            return redirect('workspace_list')  # Redirect to workspace list after creation
    else:
        form = WorkspaceForm()
    return render(request, 'create_workspace.html', {'form': form})

@login_required
def workspace_list(request):
    admin_workspaces = Workspace.objects.filter(admin=request.user)
    editor_workspaces = Workspace.objects.filter(editors=request.user)
    return render(request, 'workspace_list.html', {
        'admin_workspaces': admin_workspaces,
        'editor_workspaces': editor_workspaces,
    })

@login_required
def edit_workspace(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id, admin=request.user)
    if request.method == 'POST':
        form = WorkspaceForm(request.POST, instance=workspace)
        if form.is_valid():
            form.save()
            return redirect('workspace_list')
    else:
        form = WorkspaceForm(instance=workspace)
    return render(request, 'edit_workspace.html', {'form': form, 'workspace': workspace})
