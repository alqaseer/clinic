from django.contrib.auth.forms import UserCreationForm
from .models import *
from django import forms

class CustomUserCreationForm(forms.ModelForm):
    workspace_name = forms.CharField(
        max_length=255,
        help_text="No spaces allowed in the workspace name.",
        required=True,
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        widgets = {
            'password': forms.PasswordInput(),
        }



class WorkspaceForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ['name']


class SurgicalBookingForm(forms.ModelForm):
    class Meta:
        model = SurgicalBooking
        fields = ['name', 'phone', 'civil_id', 'diagnosis', 'procedure', 'side', 'date', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),  # Use a date picker
        }


class ClinicAppointmentForm(forms.ModelForm):
    class Meta:
        model = ClinicAppointment
        fields = ["patient_name", "phone_number", "appointment_type", "date", "time", "referral_letter"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
        }
