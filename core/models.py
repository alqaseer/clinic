from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.timezone import now
from django.conf import settings
from django.utils import timezone
import datetime

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

# Session choices
SESSION_CHOICES = [
    ('AM', 'Morning'),
    ('PM', 'Afternoon'),
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
    rooms = models.PositiveIntegerField(default=1)
    owner_name = models.CharField(max_length=255, null=True, blank=True)
    
    # OLD FIELDS (keep for migration)
    days_open = models.JSONField(default=list)  # Old format: list of day names
    maximum = models.PositiveIntegerField(default=20)  # Old field
    maximum_new_referrals = models.PositiveIntegerField(default=15)  # Old field
    
    # NEW FIELDS
    session_config = models.JSONField(default=dict, blank=True)  # New session-based structure
    give_new_referrals_time = models.BooleanField(default=True)  # New boolean field
    
    def is_day_open(self, day_name):
        """Check if a day has any open sessions - use new format if available"""
        if self.session_config and day_name in self.session_config:
            return len(self.session_config[day_name].get('sessions', {})) > 0
        # Fallback to old format
        elif isinstance(self.days_open, list):
            return day_name in self.days_open
        return False
    
    def is_session_open(self, day_name, session):
        """Check if a specific day and session (AM/PM) is open for booking"""
        if not self.session_config or day_name not in self.session_config:
            return False
        return session in self.session_config.get(day_name, {}).get('sessions', {})
    
    def get_session_maximum(self, day_name, session, is_new_referral=False):
        """Get the maximum appointments for a specific day and session"""
        if not self.session_config or day_name not in self.session_config:
            # Fallback to old fields if new config doesn't exist
            if is_new_referral:
                return self.maximum_new_referrals
            return self.maximum
            
        day_data = self.session_config.get(day_name, {})
        session_data = day_data.get('sessions', {}).get(session, {})
        
        if is_new_referral:
            return session_data.get('max_new_referrals', self.maximum_new_referrals)
        return session_data.get('max_total', self.maximum)
    
    def get_available_sessions(self, day_name):
        """Get list of available sessions for a given day"""
        if not self.session_config or day_name not in self.session_config:
            return []
        return list(self.session_config.get(day_name, {}).get('sessions', {}).keys())
    
    def add_session(self, day_name, session, max_total, max_new_referrals):
        """Add a new session to a day"""
        if not self.session_config:
            self.session_config = {}
            
        if day_name not in self.session_config:
            self.session_config[day_name] = {"sessions": {}}
        
        if "sessions" not in self.session_config[day_name]:
            self.session_config[day_name]["sessions"] = {}
        
        self.session_config[day_name]["sessions"][session] = {
            "max_total": max_total,
            "max_new_referrals": max_new_referrals
        }
        self.save()
    
    def remove_session(self, day_name, session):
        """Remove a session from a day"""
        if (self.session_config and day_name in self.session_config and 
            "sessions" in self.session_config[day_name]):
            self.session_config[day_name]["sessions"].pop(session, None)
            
            # Remove the day entirely if no sessions left
            if not self.session_config[day_name]["sessions"]:
                self.session_config.pop(day_name, None)
        self.save()
    
    def update_session_limits(self, day_name, session, max_total=None, max_new_referrals=None):
        """Update limits for a specific session"""
        if (self.session_config and day_name in self.session_config and 
            "sessions" in self.session_config[day_name] and 
            session in self.session_config[day_name]["sessions"]):
            
            if max_total is not None:
                self.session_config[day_name]["sessions"][session]["max_total"] = max_total
            if max_new_referrals is not None:
                self.session_config[day_name]["sessions"][session]["max_new_referrals"] = max_new_referrals
            
            self.save()
    
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
        max_length=20,
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
    created_at = models.DateTimeField(auto_now_add=True)
    photo_attachment = models.ImageField(upload_to="surgical_attachments/", blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.civil_id})"

class ClinicAppointment(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="appointments")
    patient_name = models.CharField(max_length=255)
    civil_id = models.CharField(max_length=12)
    phone_number = models.CharField(max_length=15)
    confirmed = models.CharField(
        max_length=50, 
        choices=[("Unknown", "Unknown"), ("Confirmed", "Confirmed"), ("Cancelled", "Cancelled")], 
        default="Unknown"
    )
    appointment_type = models.CharField(max_length=50, choices=[("New", "New"), ("Follow-Up", "Follow-Up")])
    date = models.DateField()
    time = models.TimeField()
    
    # NEW FIELD - Session field to track AM/PM (nullable for migration)
    session = models.CharField(max_length=2, choices=SESSION_CHOICES, null=True, blank=True)
    
    referral_letter = models.ImageField(upload_to="referral_letters/", blank=True, null=True)
    system_referral = models.BooleanField(default=False)
    booked_by = models.ForeignKey('Doctor', null=True, blank=True, on_delete=models.SET_NULL)
    diagnosis = models.CharField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Auto-determine session based on time if not explicitly set
        if not self.session and self.time:
            # Times before 13:00 (1:00 PM) are AM, after are PM
            if self.time < datetime.time(13, 0):
                self.session = 'AM'
            else:
                self.session = 'PM'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.patient_name} - {self.date} at {self.time}"

class Lock(models.Model):
    date = models.DateField()
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='lock')
    # NEW FIELD - Optional session-specific locks (nullable for migration)
    session = models.CharField(max_length=2, choices=SESSION_CHOICES, null=True, blank=True)
    # PM lock field - True for PM lock, False for AM lock (default for backward compatibility)
    pm = models.BooleanField(default=False)
    
    class Meta:
        # Remove unique constraint temporarily for migration
        pass

    def __str__(self):
        session_str = "PM" if self.pm else "AM"
        return f"Lock for {self.workspace.name} - {self.date} ({session_str})"
    
    @property
    def session_name(self):
        """Helper property to get readable session name"""
        return "PM" if self.pm else "AM"

class ActionLog(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="action_logs")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp} - {self.workspace.name} - {self.user.username if self.user else 'Unknown'} - {self.action_description}"

class DoctorManager(BaseUserManager):
    def create_doctor(self, username, full_name, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        
        doctor = self.model(
            username=username,
            full_name=full_name,
            **extra_fields
        )
        doctor.set_password(password)
        doctor.save(using=self._db)
        return doctor

class Doctor(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=50)
    full_name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    clerk = models.BooleanField(default=False)
    
    def __str__(self):
        return self.full_name

class FavoriteSection(models.Model):
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='favorite_sections')
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#3B82F6')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['workspace', 'name']
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name

class FavoritePatient(models.Model):
    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='favorite_patients')
    civil_id = models.CharField(max_length=12)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    diagnosis = models.TextField(blank=True)
    
    SOURCE_CHOICES = [
        ('clinic', 'Clinic Appointment'),
        ('surgical', 'Surgical Booking'),
        ('manual', 'Manual Entry'),
    ]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    source_id = models.PositiveIntegerField(null=True, blank=True)
    
    section = models.ForeignKey(FavoriteSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients')
    
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
    patient = models.ForeignKey(FavoritePatient, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note for {self.patient.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class FavoritePatientAttachment(models.Model):
    note = models.ForeignKey(FavoritePatientNote, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='favorite_patient_attachments/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment: {self.filename}"