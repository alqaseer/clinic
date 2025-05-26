from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager
from django.utils.timezone import now
from django.conf import settings
from django.utils import timezone
import datetime
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


class Speciality(models.Model):
    name = models.CharField(max_length=255)
    workspaces = models.ManyToManyField('Workspace', related_name='specialities', blank=True)
    message = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, null=True, blank=True)

class Workspace(models.Model):
    name = models.CharField(max_length=255, unique=True)
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_workspace')
    rooms = models.PositiveIntegerField(default=1)  # Default to 1 room
    days_open = models.JSONField(default=list)  # List of days when the clinic is open
    maximum = models.PositiveIntegerField(default=20)
    maximum_new_referrals = models.PositiveIntegerField(default=15)  # New field
    owner_name = models.CharField(max_length=255,null = True, blank=True)
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
    
    WAITING = 'waiting'
    SENT_FOR_ANESTHESIA = 'sent_for_anesthesia'
    READY = 'ready'
    READINESS_CHOICES = [
        (WAITING, 'Waiting'),
        (SENT_FOR_ANESTHESIA, 'Sent for Anesthesia'),
        (READY, 'Ready'),
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
    readiness = models.CharField(
        max_length=50,
        choices=READINESS_CHOICES,
        default=WAITING
    )
#     status2 = models.CharField(
#     max_length=50,
#     choices=[
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('rejected', 'Rejected'),
#     ],
#     default='pending',
#     null=True,
#     blank=True
# )
    created_at = models.DateTimeField(auto_now_add=True)
    photo_attachment = models.ImageField(upload_to="surgical_attachments/", blank=True, null=True)

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
    system_referral = models.BooleanField(default=False)
    booked_by = models.ForeignKey('Doctor', null=True, blank=True, on_delete=models.SET_NULL)
    diagnosis = models.CharField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.patient_name} - {self.date} at {self.time}"


class Lock(models.Model):
    date = models.DateField()
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='lock')
class ActionLog(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="action_logs")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_description = models.TextField()  # Describes what action was performed
    timestamp = models.DateTimeField(auto_now_add=True)  # Auto logs the date and time

    def __str__(self):
        return f"{self.timestamp} - {self.workspace.name} - {self.user.username if self.user else 'Unknown'} - {self.action_description}"



# Doctor User Manager
class DoctorManager(BaseUserManager):
    def create_doctor(self, username, full_name, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        
        doctor = self.model(
            username=username,
            full_name=full_name,
            **extra_fields
        )
        doctor.set_password(password)  # Store plain password (not recommended for production)
        doctor.save(using=self._db)
        return doctor

# Doctor model
class Doctor(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=50)  # Plain text password (not recommended for production)
    full_name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    clerk = models.BooleanField(default=False)
    def __str__(self):
        return self.full_name


#favorite section


class FavoriteSection(models.Model):
    """Sections to organize favorite patients (e.g., ACL patients, TKR revisions, etc.)"""
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='favorite_sections')
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color for visual distinction
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)  # For custom ordering
    
    class Meta:
        unique_together = ['workspace', 'name']
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class FavoritePatient(models.Model):
    """Favorited patients with their basic information"""
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='favorite_patients')
    civil_id = models.CharField(max_length=12)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    diagnosis = models.TextField(blank=True)
    
    # Source information (where the patient was favorited from)
    SOURCE_CHOICES = [
        ('clinic', 'Clinic Appointment'),
        ('surgical', 'Surgical Booking'),
        ('manual', 'Manual Entry'),
    ]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    source_id = models.PositiveIntegerField(null=True, blank=True)  # ID of the original record
    
    # Organization
    section = models.ForeignKey(FavoriteSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    
    # Status and metadata
    is_active = models.BooleanField(default=True)
    favorited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    favorited_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['workspace', 'civil_id']
        ordering = ['-favorited_at']
    
    def __str__(self):
        return f"{self.name} ({self.civil_id}) - {self.workspace.name}"


class FavoritePatientNote(models.Model):
    """Progress notes for favorite patients"""
    patient = models.ForeignKey(FavoritePatient, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()  # Rich text content (HTML)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note for {self.patient.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class FavoritePatientAttachment(models.Model):
    """File attachments for favorite patients (images, documents, etc.)"""
    note = models.ForeignKey(FavoritePatientNote, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='favorite_patient_attachments/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # image, document, etc.
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment: {self.filename}"