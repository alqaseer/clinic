from django.contrib.auth.forms import UserCreationForm
from .models import *
from django import forms

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User  # Use your custom User model
        fields = ['username', 'email', 'password1', 'password2']

class WorkspaceForm(forms.ModelForm):
    editors = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Workspace
        fields = ['name', 'editors']

