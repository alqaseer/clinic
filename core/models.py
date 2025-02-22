from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.timezone import now
from django.conf import settings

# Create your models here.

# Custom User model

# Choices for days of the week
DAYS_OF_WEEK = [
    ("Sunday", "Sunday"),
    ("Monday", "Monday"),
    ("Tuesday", "Tuesday"),
    ("Wednesday", "Wednesday"),
    ("Thursday", "Thursday"),
    ("Friday", "Friday"),
    ("Saturday", "Saturday"),
]


class User(AbstractUser):
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, null=True, blank=True)

class Workspace(models.Model):
    name = models.CharField(max_length=255, unique=True)
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_workspace')
    rooms = models.PositiveIntegerField(default=1)  # Default to 1 room
    days_open = models.JSONField(default=list)  # List of days when the clinic is open

    def is_day_open(self, day_name):
        """
        Checks if a specific day is open for booking.
        """
        return day_name in self.days_open

    def __str__(self):
        return self.name

class SurgicalBooking(models.Model):
    RIGHT = 'Right'
    LEFT = 'Left'
    NA = 'Not Applicable'
    SIDE_CHOICES = [
        (RIGHT, 'Right'),
        (LEFT, 'Left'),
        (NA, 'Not Applicable'),
    ]

    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='surgical_bookings')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=8)
    civil_id = models.CharField(max_length=12)
    diagnosis = models.TextField()
    procedure = models.TextField()
    side = models.CharField(max_length=15, choices=SIDE_CHOICES, default=NA)
    date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=[
            ('booked', 'Booked'),
            ('waiting', 'Waiting'),
            ('past', 'Past'),
            ('deleted', 'Deleted')
        ],
        default='waiting'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.civil_id})"



class ClinicAppointment(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="appointments")
    patient_name = models.CharField(max_length=255)
    civil_id = models.CharField(max_length=12)  # New field
    phone_number = models.CharField(max_length=15)
    confirmed = models.CharField(
    max_length=50, 
    choices=[("Unknown", "Unknown"), ("Confirmed", "Confirmed"), ("Cancelled", "Cancelled")], default="Unknown")
    appointment_type = models.CharField(max_length=50, choices=[("New", "New"), ("Follow-Up", "Follow-Up")])
    date = models.DateField()
    time = models.TimeField()
    referral_letter = models.ImageField(upload_to="referral_letters/", blank=True, null=True)

    def __str__(self):
        return f"{self.patient_name} - {self.date} at {self.time}"


class ActionLog(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="action_logs")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_description = models.TextField()  # Describes what action was performed
    timestamp = models.DateTimeField(auto_now_add=True)  # Auto logs the date and time

    def __str__(self):
        return f"{self.timestamp} - {self.workspace.name} - {self.user.username if self.user else 'Unknown'} - {self.action_description}"
