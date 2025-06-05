from django.contrib.auth.forms import UserCreationForm
from .models import *
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm



class CustomUserCreationForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=255,
        help_text="Enter your full name.",
        required=True,
        widget=forms.TextInput(attrs={
            "class": "w-full border border-gray-300 p-3 rounded-md bg-gray-50 text-lg focus:ring-blue-500 focus:border-blue-500"
        })
    )
    
    workspace_name = forms.CharField(
        max_length=255,
        help_text="Enter your workspace name.",
        required=True,
        widget=forms.TextInput(attrs={
            "class": "w-full border border-gray-300 p-3 rounded-md bg-gray-50 text-lg focus:ring-blue-500 focus:border-blue-500"
        })
    )

    class Meta:
        model = User
        fields = ["full_name", "username", "email", "password"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "w-full border border-gray-300 p-3 rounded-md bg-gray-50 text-lg focus:ring-blue-500 focus:border-blue-500"
            }),
            "email": forms.EmailInput(attrs={
                "class": "w-full border border-gray-300 p-3 rounded-md bg-gray-50 text-lg focus:ring-blue-500 focus:border-blue-500"
            }),
            "password": forms.PasswordInput(attrs={
                "class": "w-full border border-gray-300 p-3 rounded-md bg-gray-50 text-lg focus:ring-blue-500 focus:border-blue-500"
            }),
        }


class SurgicalBookingForm(forms.ModelForm):
    class Meta:
        model = SurgicalBooking
        fields = ['name', 'phone', 'civil_id', 'diagnosis', 'procedure', 'side', 'date', 'notes', 'photo_attachment', 'readiness']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),  # Use a date picker
            'readiness': forms.Select(attrs={'class': 'form-select'}),  # Style the readiness dropdown
        }


class ClinicAppointmentForm(forms.ModelForm):
    class Meta:
        model = ClinicAppointment
        fields = ["patient_name", "civil_id", "phone_number", "appointment_type", "date", "time", "diagnosis", "referral_letter"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_civil_id(self):
        civil_id = self.cleaned_data.get("civil_id")
        if len(civil_id) != 12 or not civil_id.isdigit():
            raise forms.ValidationError("Civil ID must be exactly 12 digits.")
        return civil_id




class UserCreationForm2(UserCreationForm):  # Extend Django's UserCreationForm
    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]  # Django expects password1 and password2

#favorite patient form
# Add these to your forms.py

from django import forms
from .models import FavoriteSection, FavoritePatient, FavoritePatientNote

class FavoriteSectionForm(forms.ModelForm):
    class Meta:
        model = FavoriteSection
        fields = ['name']  # Remove 'color' from here
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Section name (e.g., ACL Patients, TKR Revisions)'
            })
        }

class FavoritePatientForm(forms.ModelForm):
    class Meta:
        model = FavoritePatient
        fields = ['name', 'civil_id', 'phone', 'diagnosis', 'section']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'civil_id': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'maxlength': '12',
                'minlength': '12',
                'pattern': r'\d{12}'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'diagnosis': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 3
            }),
            'section': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            })
        }

    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace:
            self.fields['section'].queryset = FavoriteSection.objects.filter(workspace=workspace)
            self.fields['section'].empty_label = "No section (General)"

class FavoritePatientNoteForm(forms.ModelForm):
    class Meta:
        model = FavoritePatientNote
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 4,
                'placeholder': 'Write your note here...'
            })
        }