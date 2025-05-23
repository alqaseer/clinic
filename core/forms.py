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
        fields = ['name', 'phone', 'civil_id', 'diagnosis', 'procedure', 'side', 'date', 'notes', 'photo_attachment']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),  # Use a date picker
        }


class ClinicAppointmentForm(forms.ModelForm):
    class Meta:
        model = ClinicAppointment
        fields = ["patient_name", "civil_id", "phone_number", "appointment_type", "date", "time", "referral_letter"]
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

    