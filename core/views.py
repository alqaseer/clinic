from django.shortcuts import render, redirect, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import *
from .models import *
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from datetime import datetime, timedelta, time
from calendar import monthrange
from django.contrib import messages
import calendar
from django.urls import reverse
from django.http import HttpResponse, Http404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Count
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
import pandas as pd
import io
from django.utils.timezone import make_naive
from django.utils.timezone import is_aware
import os
from django.utils.timezone import now
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.views.generic import ListView
from django.db.models import Q
from django.views.decorators.http import require_GET
import calendar
import random
from django.core.files.storage import default_storage

def home(request):
    # If the user is logged in as a regular user, check for a workspace
    if request.user.is_authenticated:
        user_workspace = Workspace.objects.filter(user=request.user).first()
        if user_workspace:
            return redirect("workspace_main", workspace_name=user_workspace.name)
    
    
    # If user is not logged in or has no workspace, show home page
    return render(request, "home.html")


def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True  # Make this user an admin
            
            # Hash the password before saving
            user.set_password(form.cleaned_data["password"])  
            user.save()

            # Get the full name from the form
            full_name = form.cleaned_data["full_name"]

            # Create a workspace and assign it to the user
            workspace_name = request.POST.get("workspace_name").replace(" ", "").lower()
            workspace = Workspace.objects.create(
                name=workspace_name, 
                admin=user,
                owner_name=full_name  # Set the owner_name to the full name
            )

            # Assign the workspace to the user and save
            user.workspace = workspace
            user.save()

            login(request, user)
            return redirect("workspace_main", workspace_name=workspace_name)
    else:
        form = CustomUserCreationForm()
    
    return render(request, "signup.html", {"form": form})




def login_view(request):
    # If the user is already authenticated, redirect them to their workspace or home
    if request.user.is_authenticated:
        user_workspace = Workspace.objects.filter(user=request.user).first()
        if user_workspace:
            return redirect("workspace_main", workspace_name=user_workspace.name)
        else:
            return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        remember_me = request.POST.get("remember_me") == "on"

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Set session expiry based on "Remember Me"
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Expires when browser closes

            # Check if the user has a workspace
            user_workspace = Workspace.objects.filter(user=user).first()

            if user_workspace:
                return redirect("workspace_main", workspace_name=user_workspace.name)
            else:
                return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")

    # Clear any lock/unlock messages
    storage = messages.get_messages(request)
    for message in list(storage):
        if 'locked' in str(message) or 'unlocked' in str(message):
            # Skip this message
            pass
        else:
            # Keep other messages by adding them back
            messages.add_message(request, message.level, message.message)

    # Make sure to return an HttpResponse object
    return render(request, "login.html")


def logout_view(request):
    # If the user is authenticated, get their workspace name
    
    # Log out the user
    logout(request)

    # Redirect to the login page for the specific workspace
    
    return redirect('home')
    
def check_availability(request):
    username = request.GET.get('username', None)
    email = request.GET.get('email', None)
    workspace_name = request.GET.get('workspace_name', None)

    response = {'available': True}  # Default response

    if username and User.objects.filter(username=username).exists():
        response = {'available': False, 'message': 'Username is already taken.'}

    if email and User.objects.filter(email=email).exists():
        response = {'available': False, 'message': 'Email is already in use.'}

    if workspace_name and Workspace.objects.filter(name=workspace_name).exists():
        response = {'available': False, 'message': 'Workspace name is already taken.'}

    return JsonResponse(response)

# Workspace Main Page
@login_required
def workspace_main(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure the user belongs to this workspace
    if request.user != workspace.admin and request.user.workspace != workspace:
        return redirect('login')  # Prevent unauthorized access

    # Check if the logged-in user is "alqaseer"
    if request.user.username == "alqaseer":
        # Calculate the cutoff date for referral letters (12 weeks ago)
        cutoff_date_letters = now().date() - timedelta(weeks=12)  

        # Find old appointments
        old_appointments = ClinicAppointment.objects.filter(date__lt=cutoff_date_letters)

        for appointment in old_appointments:
            # Delete referral letter file if exists
            if appointment.referral_letter:
                file_path = os.path.join(settings.MEDIA_ROOT, str(appointment.referral_letter))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
            # Delete the database entry
            appointment.referral_letter = None
            appointment.save()
            
        # Calculate the cutoff date for surgical photos (2 years ago)
        cutoff_date_photos = now().date() - timedelta(days=730)  # 365*2
        print("looking and deleting old surgical booking's photos")
        # Find old surgical bookings with photos
        old_bookings = SurgicalBooking.objects.filter(
            created_at__lt=cutoff_date_photos,
            photo_attachment__isnull=False
        )
        
        for booking in old_bookings:
            # Delete the photo file if it exists
            if booking.photo_attachment:
                
                file_path = os.path.join(settings.MEDIA_ROOT, str(booking.photo_attachment))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
            # Clear the photo field in the database
            booking.photo_attachment = None
            booking.save()
            
            # Log the action
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Automatically removed old photo for {booking.name} (Civil ID: {booking.civil_id}) due to 2-year retention policy."
            )

    # Count booked cases (future date, since ClinicAppointment has no status field)
    booked_cases_count = SurgicalBooking.objects.filter(
        workspace=workspace,
        date__gte=now().date(),
        status__in=["waiting", "booked"]
    ).count()

    # Count waiting list cases from SurgicalBooking (no date, not deleted)
    waiting_list_count = SurgicalBooking.objects.filter(
        workspace=workspace,
        date__isnull=True,
        status__in=["waiting", "booked"]  # Exclude deleted
    ).count()

    # Get list of users in the workspace (directly from User model)
    users = User.objects.filter(workspace=workspace)

    return render(request, 'workspace_main.html', {
        "workspace": workspace,
        "booked_cases_count": booked_cases_count,
        "waiting_list_count": waiting_list_count,
        "users": users
    })

@login_required
def booked_cases(request, workspace_name):
    """View for cases with dates from today onward and status is not deleted, arranged chronologically."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    today = now().date()

    cases = SurgicalBooking.objects.filter(
        workspace=workspace, 
        date__gte=today,  # Filter cases where date is today or in the future
        status__in=['booked', 'waiting', 'past']  # Exclude 'deleted' cases
    ).order_by('date')  # Arrange chronologically by date

    # Get list of civil IDs that are already favorited in this workspace
    favorited_civil_ids = list(
        FavoritePatient.objects.filter(
            workspace=workspace,
            is_active=True
        ).values_list('civil_id', flat=True)
    )

    return render(request, 'booked_cases.html', {
        'cases': cases, 
        'workspace': workspace,
        'favorited_civil_ids': favorited_civil_ids,  # Add this for favorite functionality
    })



@login_required
def waiting_list(request, workspace_name):
    """View for cases where date is empty and status is NOT deleted, arranged by creation date."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    # Base queryset - cases where date is empty and status is NOT deleted
    cases = SurgicalBooking.objects.filter(
        workspace=workspace, 
        date__isnull=True,  # Date is empty (null)
        status__in=['waiting', 'booked', 'past']  # All statuses except 'deleted'
    )
    
    # Filter by readiness if specified
    readiness_filter = request.GET.get('readiness')
    if readiness_filter and readiness_filter != 'all':
        cases = cases.filter(readiness=readiness_filter)
    
    # Order by creation date
    cases = cases.order_by('created_at')

    # Get list of civil IDs that are already favorited in this workspace
    favorited_civil_ids = list(
        FavoritePatient.objects.filter(
            workspace=workspace,
            is_active=True
        ).values_list('civil_id', flat=True)
    )

    return render(request, 'waiting_list.html', {
        'cases': cases, 
        'workspace': workspace,
        'favorited_civil_ids': favorited_civil_ids,  # Add this for favorite functionality
    })


@login_required
def past_cases(request, workspace_name):
    """View for cases with dates in the past and status is not deleted, arranged chronologically."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    today = now().date()

    cases = SurgicalBooking.objects.filter(
        workspace=workspace, 
        date__lt=today,  # Filter cases where date is in the past
        status__in=['booked', 'waiting', 'past']  # Exclude 'deleted' cases
    ).order_by('date')  # Arrange chronologically by date

    # Get list of civil IDs that are already favorited in this workspace
    favorited_civil_ids = list(
        FavoritePatient.objects.filter(
            workspace=workspace,
            is_active=True
        ).values_list('civil_id', flat=True)
    )

    return render(request, 'past_cases.html', {
        'cases': cases, 
        'workspace': workspace,
        'favorited_civil_ids': favorited_civil_ids,  # Add this for favorite functionality
    })


@login_required
def deleted_cases(request, workspace_name):
    """View for cases that are deleted, arranged by creation date."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    cases = SurgicalBooking.objects.filter(
        workspace=workspace, status='deleted'
    ).order_by('-created_at')  # Arrange by creation date, newest first

    return render(request, 'deleted_cases.html', {'cases': cases, 'workspace': workspace})


@login_required
def add_surgical_booking(request, workspace_name):
    # Get the workspace the user is logged into
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure the user belongs to this workspace or is its admin
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    if request.method == 'POST':
        form = SurgicalBookingForm(request.POST, request.FILES)  # Updated to handle file uploads
        if form.is_valid():
            booking = form.save(commit=False)
            booking.workspace = workspace  # Assign the booking to the current workspace
            
            # Note: Remove the automatic status assignment since user can now choose
            # The status will be set based on the form selection
            booking.save()

            # Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Added surgical booking for {booking.name} (Civil ID: {booking.civil_id}) (Procedure: {booking.procedure})."
            )

            return redirect('booked_cases', workspace_name=workspace_name)  # Redirect to booked cases
    else:
        form = SurgicalBookingForm()

    return render(request, 'add_surgical_booking.html', {'form': form, 'workspace': workspace})

@login_required
def calendar_view(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    today = datetime.today()
    current_year = int(request.GET.get('year', today.year))
    current_month = int(request.GET.get('month', today.month))

    # Get first day of month and number of days
    first_day, days_in_month = calendar.monthrange(current_year, current_month)
    # Adjust first_day to make Sunday 0 instead of Monday 0
    first_day = (first_day + 1) % 7  # Convert from Monday=0 to Sunday=0

    # Get all appointments for the month
    appointments = ClinicAppointment.objects.filter(
        workspace=workspace,
        date__year=current_year,
        date__month=current_month
    )

    # Helper function to determine if appointment is AM or PM based on time
    def is_am_time(appointment):
        if isinstance(appointment.time, int):
            # Convert integer like 1400 to hours
            hours = appointment.time // 100
            return hours < 14
        elif hasattr(appointment.time, 'hour'):
            # It's a time object
            return appointment.time.hour < 14
        else:
            # It's a string, parse it
            try:
                time_obj = datetime.strptime(str(appointment.time), "%H:%M").time()
                return time_obj.hour < 14
            except:
                return True  # Default to AM if we can't parse

    # Group appointments by date and session
    appointments_by_date = {}
    for appointment in appointments:
        date = appointment.date
        
        # Determine session based on actual time, not the session field
        if is_am_time(appointment):
            session = 'AM'
        else:
            session = 'PM'
        
        if date not in appointments_by_date:
            appointments_by_date[date] = {'AM': 0, 'PM': 0, 'total': 0}
        
        appointments_by_date[date][session] += 1
        appointments_by_date[date]['total'] += 1

    # Get all locks for the month with session information
    locks = Lock.objects.filter(
        workspace=workspace,
        date__year=current_year,
        date__month=current_month
    )

    # Group locks by date and session
    locks_by_date = {}
    for lock in locks:
        date = lock.date
        if date not in locks_by_date:
            locks_by_date[date] = {'AM': False, 'PM': False}
        
        # pm=False means AM lock, pm=True means PM lock
        if lock.pm:
            locks_by_date[date]['PM'] = True
        else:
            locks_by_date[date]['AM'] = True

    # Generate calendar days
    days = []
    for day in range(1, days_in_month + 1):
        date = datetime(current_year, current_month, day).date()
        day_name = date.strftime("%A")  # Gets the full day name (e.g., "Sunday")
        
        # Check which sessions are available for this day
        available_sessions = workspace.get_available_sessions(day_name)
        has_am = 'AM' in available_sessions
        has_pm = 'PM' in available_sessions
        is_open = has_am or has_pm
        
        # Get appointment counts for this date
        date_appointments = appointments_by_date.get(date, {'AM': 0, 'PM': 0, 'total': 0})
        am_count = date_appointments['AM']
        pm_count = date_appointments['PM']
        total_count = date_appointments['total']
        
        # Check if there are actual appointments regardless of session configuration
        has_am_appointments = am_count > 0
        has_pm_appointments = pm_count > 0
        has_any_appointments = total_count > 0
        
        # Calculate maximum capacity for the day
        max_capacity = 0
        if has_am:
            max_capacity += workspace.get_session_maximum(day_name, 'AM', is_new_referral=False)
        if has_pm:
            max_capacity += workspace.get_session_maximum(day_name, 'PM', is_new_referral=False)
        
        # Check if fully booked (only if day is configured as open)
        is_fully_booked = (total_count >= max_capacity if max_capacity > 0 and is_open else False)
        
        # Get lock information for this date
        date_locks = locks_by_date.get(date, {'AM': False, 'PM': False})
        am_locked = date_locks['AM']
        pm_locked = date_locks['PM']
        is_locked = am_locked or pm_locked  # Any session locked means day has locks

        days.append({
            "date": date,
            "is_open": is_open,
            "has_am": has_am,
            "has_pm": has_pm,
            "am_count": am_count,
            "pm_count": pm_count,
            "total_count": total_count,
            "max_capacity": max_capacity,
            "is_fully_booked": is_fully_booked,
            "is_locked": is_locked,
            "am_locked": am_locked,
            "pm_locked": pm_locked,
            "has_am_appointments": has_am_appointments,
            "has_pm_appointments": has_pm_appointments,
            "has_any_appointments": has_any_appointments,
        })

    # Calculate navigation
    next_month = (current_month % 12) + 1
    next_year = current_year + 1 if next_month == 1 else current_year
    prev_month = current_month - 1 if current_month > 1 else 12
    prev_year = current_year - 1 if prev_month == 12 else current_year

    # Create blank slots for calendar alignment
    blank_slots = list(range(first_day))
    today = timezone.now().date()  
    
    context = {
        "workspace": workspace,
        "days": days,
        "current_year": current_year,
        "current_month": current_month,
        "month_name": calendar.month_name[current_month],
        "prev_month": prev_month,
        "prev_year": prev_year,
        "next_month": next_month,
        "next_year": next_year,
        "days_of_week": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "blank_slots": blank_slots,
        "today": today,
    }
    return render(request, "calendar.html", context)

@login_required
def settings_page(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    if request.method == "POST":
        # Handle session-based form submission
        rooms = request.POST.get("rooms")
        give_new_referrals_time = request.POST.get("give_new_referrals_time") == "on"
        
        # Process rooms
        if not rooms:
            rooms = workspace.rooms
        else:
            rooms = int(rooms)
        
        # Build new session configuration
        new_session_config = {}
        
        days_of_week = [
            "Sunday", "Monday", "Tuesday", "Wednesday", 
            "Thursday", "Friday", "Saturday"
        ]
        
        # Get existing session config to preserve max_new_referrals values
        existing_config = workspace.session_config if workspace.session_config else {}
        
        for day in days_of_week:
            day_key = day.lower()
            
            # Check AM session
            am_enabled = request.POST.get(f"{day_key}_am_enabled") == "on"
            pm_enabled = request.POST.get(f"{day_key}_pm_enabled") == "on"
            
            if am_enabled or pm_enabled:
                new_session_config[day] = {"sessions": {}}
                
                if am_enabled:
                    am_max_total = request.POST.get(f"{day_key}_am_max_total")
                    try:
                        am_max_total = int(am_max_total) if am_max_total else 20
                        if am_max_total < 1:
                            am_max_total = 20
                    except (ValueError, TypeError):
                        am_max_total = 20
                    
                    # Preserve existing max_new_referrals or default to 15
                    existing_am_max_new = existing_config.get(day, {}).get("sessions", {}).get("AM", {}).get("max_new_referrals")
                    am_max_new_referrals = existing_am_max_new if existing_am_max_new is not None else 15
                    
                    new_session_config[day]["sessions"]["AM"] = {
                        "max_total": am_max_total,
                        "max_new_referrals": am_max_new_referrals
                    }
                
                if pm_enabled:
                    pm_max_total = request.POST.get(f"{day_key}_pm_max_total")
                    try:
                        pm_max_total = int(pm_max_total) if pm_max_total else 20
                        if pm_max_total < 1:
                            pm_max_total = 20
                    except (ValueError, TypeError):
                        pm_max_total = 20
                    
                    # Preserve existing max_new_referrals or default to 15
                    existing_pm_max_new = existing_config.get(day, {}).get("sessions", {}).get("PM", {}).get("max_new_referrals")
                    pm_max_new_referrals = existing_pm_max_new if existing_pm_max_new is not None else 15
                    
                    new_session_config[day]["sessions"]["PM"] = {
                        "max_total": pm_max_total,
                        "max_new_referrals": pm_max_new_referrals
                    }
        
        # Save to workspace
        workspace.session_config = new_session_config
        workspace.rooms = rooms
        workspace.give_new_referrals_time = give_new_referrals_time
        workspace.save()
        
        # Log the action
        ActionLog.objects.create(
            workspace=workspace,
            user=request.user,
            action_description=f"Updated workspace settings, session configuration, and new referrals time preference."
        )
        
        messages.success(request, "Settings updated successfully!")
        return redirect("workspace_main", workspace_name=workspace_name)

    # Prepare data for template
    days_of_week = [
        ("Sunday", "Sunday"),
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
    ]
    
    rooms_range = range(1, 6)
    
    # Get session configuration
    session_config = workspace.session_config if workspace.session_config else {}
    
    # Process session data for each day to avoid template filters
    days_data = []
    for day_key, day_label in days_of_week:
        day_sessions = session_config.get(day_key, {}).get('sessions', {})
        
        # AM Session data
        am_enabled = 'AM' in day_sessions
        am_max_total = day_sessions.get('AM', {}).get('max_total', '') if am_enabled else ''
        
        # PM Session data  
        pm_enabled = 'PM' in day_sessions
        pm_max_total = day_sessions.get('PM', {}).get('max_total', '') if pm_enabled else ''
        
        days_data.append({
            'key': day_key,
            'label': day_label,
            'lower_key': day_key.lower(),
            'am_enabled': am_enabled,
            'am_max_total': am_max_total,
            'pm_enabled': pm_enabled,
            'pm_max_total': pm_max_total,
        })
    
    # Calculate stats for display
    active_days_count = len(session_config)
    total_sessions_count = sum(
        len(day_data.get('sessions', {})) 
        for day_data in session_config.values()
    )

    return render(
        request,
        "settings.html",
        {
            "workspace": workspace,
            "days_data": days_data,  # Pre-processed day data
            "rooms_range": rooms_range,
            "active_days_count": active_days_count,
            "total_sessions_count": total_sessions_count,
        },
    )

@login_required
def day_appointments(request, workspace_name, date):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Get appointments for the selected day
    appointments = ClinicAppointment.objects.filter(workspace=workspace, date=date_obj)
    
    # Define all possible time slots
    all_am_slots = ["08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45","12:00","12:15","12:30"]
    all_pm_slots = ["14:00","14:15","14:30","14:45","15:00","15:15","15:30","15:45","16:00","16:15","16:30","16:45","17:00","17:15","17:30"]
    
    # Helper function to check if appointment time is AM or PM
    def is_am_time(appointment):
        if isinstance(appointment.time, int):
            # Convert integer like 1400 to hours
            hours = appointment.time // 100
            return hours < 14
        elif hasattr(appointment.time, 'hour'):
            # It's a time object
            return appointment.time.hour < 14
        else:
            # It's a string, parse it
            try:
                time_obj = datetime.strptime(str(appointment.time), "%H:%M").time()
                return time_obj.hour < 14
            except:
                return True  # Default to AM if we can't parse
    
    # Check if there are any AM appointments (before 14:00)
    has_am_appointments = any(is_am_time(appt) for appt in appointments)
    
    # Check if there are any PM appointments (14:00 and after)
    has_pm_appointments = any(not is_am_time(appt) for appt in appointments)
    
    # Determine which time slots to show based on appointments
    timeslots = []
    if has_am_appointments:
        timeslots.extend(all_am_slots)
    if has_pm_appointments:
        timeslots.extend(all_pm_slots)
    
    # Get the day name for checking if sessions are open
    day_name = date_obj.strftime('%A')
    
    # Check if AM and PM sessions are open for this day
    is_am_open = workspace.is_session_open(day_name, 'AM')
    is_pm_open = workspace.is_session_open(day_name, 'PM')
    
    # Check for session-specific locks
    am_lock_exists = Lock.objects.filter(workspace=workspace, date=date_obj, pm=False).exists()
    pm_lock_exists = Lock.objects.filter(workspace=workspace, date=date_obj, pm=True).exists()
    
    # Determine if "Add Appointment" button should be shown
    show_add_appointment = True
    
    # If user is workspace admin, always show button
    if request.user == workspace.admin:
        show_add_appointment = True
    else:
        # Apply the business logic for non-admin users
        if is_am_open and is_pm_open:
            # Both sessions are open
            if am_lock_exists and pm_lock_exists:
                # Both sessions are locked - don't show button
                show_add_appointment = False
            else:
                # At least one session is not locked - show button
                show_add_appointment = True
        elif is_am_open and not is_pm_open:
            # Only AM is open
            if am_lock_exists:
                # AM is locked - don't show button
                show_add_appointment = False
            else:
                # AM is not locked - show button
                show_add_appointment = True
        elif is_pm_open and not is_am_open:
            # Only PM is open
            if pm_lock_exists:
                # PM is locked - don't show button
                show_add_appointment = False
            else:
                # PM is not locked - show button
                show_add_appointment = True
        else:
            # Neither session is open - always show button
            show_add_appointment = True
    
    # Check if the day is locked (for display purposes - keeping original logic)
    is_locked = am_lock_exists or pm_lock_exists
    
    # Get list of civil IDs that are already favorited in this workspace
    favorited_civil_ids = list(
        FavoritePatient.objects.filter(
            workspace=workspace,
            is_active=True
        ).values_list('civil_id', flat=True)
    )
    
    context = {
        "timeslots": timeslots,
        "workspace": workspace,
        "date": date_obj,
        "appointments": appointments,
        "is_locked": is_locked,
        "am_lock_exists": am_lock_exists,
        "pm_lock_exists": pm_lock_exists,
        "is_am_open": is_am_open,
        "is_pm_open": is_pm_open,
        "show_add_appointment": show_add_appointment,
        "favorited_civil_ids": favorited_civil_ids,
        "has_am_appointments": has_am_appointments,
        "has_pm_appointments": has_pm_appointments,
        "has_any_appointments": appointments.exists(),
    }
    return render(request, "day_appointments.html", context)

@login_required
@require_POST
def toggle_session_lock(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Only allow workspace admin to toggle locks
    if request.user != workspace.admin:
        return JsonResponse({'success': False, 'message': 'Permission denied'})
    
    try:
        data = json.loads(request.body)
        session = data.get('session')  # 'AM' or 'PM'
        action = data.get('action')    # 'create' or 'delete'
        date_str = data.get('date')    # 'YYYY-MM-DD'
        
        if not all([session, action, date_str]):
            return JsonResponse({'success': False, 'message': 'Missing required parameters'})
        
        if session not in ['AM', 'PM']:
            return JsonResponse({'success': False, 'message': 'Invalid session'})
        
        if action not in ['create', 'delete']:
            return JsonResponse({'success': False, 'message': 'Invalid action'})
        
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Invalid date format'})
        
        # Determine the pm field value based on session
        pm_value = True if session == 'PM' else False
        
        if action == 'create':
            # Create the lock
            lock, created = Lock.objects.get_or_create(
                workspace=workspace,
                date=date_obj,
                pm=pm_value
            )
            
            if created:
                # Log the action
                ActionLog.objects.create(
                    workspace=workspace,
                    user=request.user,
                    action_description=f"Locked {session} session for {date_obj}"
                )
                
                message = f"{session} session locked successfully"
            else:
                message = f"{session} session was already locked"
                
        else:  # action == 'delete'
            # Delete the lock
            deleted_count = Lock.objects.filter(
                workspace=workspace,
                date=date_obj,
                pm=pm_value
            ).delete()[0]
            
            if deleted_count > 0:
                # Log the action
                ActionLog.objects.create(
                    workspace=workspace,
                    user=request.user,
                    action_description=f"Unlocked {session} session for {date_obj}"
                )
                
                message = f"{session} session unlocked successfully"
            else:
                message = f"{session} session was not locked"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'session': session,
            'action': action,
            'date': date_str
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'})

@login_required
def add_appointment(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    selected_date_str = request.GET.get("date")  # Date from URL
    selected_date = None
    
    print("Raw selected_date_str from URL:", selected_date_str)  # Debugging output

    # Parse date correctly
    if selected_date_str:
        selected_date_str = selected_date_str.replace("Sept.", "Sep.")

        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                selected_date = datetime.strptime(selected_date_str, "%b. %d, %Y").date()  # Handles "Feb. 18, 2025"
            except ValueError:
                try:
                    selected_date = datetime.strptime(selected_date_str, "%B %d, %Y").date()  # Handles "March 25, 2025"
                except ValueError:
                    selected_date = None  # If parsing fails, set to None
    
    # Default to today if the date is missing or invalid
    if not selected_date:
        selected_date = None
    
    print("Final selected_date:", selected_date)  # Debugging output

    # Get day name and check which sessions are available
    day_name = selected_date.strftime("%A") if selected_date else ""
    available_sessions = workspace.get_available_sessions(day_name) if selected_date else []
    has_am = 'AM' in available_sessions
    has_pm = 'PM' in available_sessions

    # Check for session-specific locks
    am_lock_exists = Lock.objects.filter(workspace=workspace, date=selected_date, pm=False).exists() if selected_date else False
    pm_lock_exists = Lock.objects.filter(workspace=workspace, date=selected_date, pm=True).exists() if selected_date else False
    
    # Check if user is workspace owner (can override locks)
    is_workspace_owner = request.user == workspace.admin
    
    # Determine if sessions should be disabled (locked and user is not owner)
    am_disabled = am_lock_exists and not is_workspace_owner
    pm_disabled = pm_lock_exists and not is_workspace_owner

    # Generate AM time slots (8:00 AM to 12:15 PM)
    def generate_time_slots(start_time, end_time):
        slots = []
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        while start <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=15)
        return slots

    am_time_slots = generate_time_slots("08:00", "12:15")
    pm_time_slots = generate_time_slots("14:00", "17:30")  # 2:00 PM to 5:30 PM

    # Count booked patients for each time slot
    am_slot_counts = {}
    pm_slot_counts = {}
    
    if selected_date:
        for slot in am_time_slots:
            am_slot_counts[slot] = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=selected_date,
                time=slot,
                session='AM'
            ).count()

        for slot in pm_time_slots:
            pm_slot_counts[slot] = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=selected_date,
                time=slot,
                session='PM'
            ).count()

    # Get session maximums
    am_max = workspace.get_session_maximum(day_name, 'AM', is_new_referral=False) if has_am else 0
    pm_max = workspace.get_session_maximum(day_name, 'PM', is_new_referral=False) if has_pm else 0

    # Prepare slot data with disabled status
    am_slots = [(slot, am_slot_counts.get(slot, 0), workspace.rooms, am_disabled) for slot in am_time_slots]
    pm_slots = [(slot, pm_slot_counts.get(slot, 0), workspace.rooms, pm_disabled) for slot in pm_time_slots]

    # Determine collapse behavior - always allow both sessions
    # If PM is not open, collapse PM
    # If AM is not open, collapse AM  
    # If both open, show both expanded
    # If none open, show both expanded
    # Also collapse if session is locked for non-owners
    am_collapsed = (not has_am and has_pm) or (am_disabled and not pm_disabled)
    pm_collapsed = (not has_pm and has_am) or (pm_disabled and not am_disabled)

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            appointment.date = selected_date  # Assign the selected date before saving
            
            # Determine session based on time if not already set
            selected_time = appointment.time
            
            # Convert time string to time object if needed
            if isinstance(selected_time, str):
                selected_time = datetime.strptime(selected_time, "%H:%M").time()
            
            if selected_time < time(14, 0):  # Use the `time` class directly
                appointment.session = 'AM'
                session_max = am_max
                session_pm_value = False  # AM lock
                session_disabled = am_disabled
            else:
                appointment.session = 'PM'
                session_max = pm_max
                session_pm_value = True   # PM lock
                session_disabled = pm_disabled
            
            # Check if the user is trying to book in a locked session (and is not the owner)
            if session_disabled:
                messages.error(request, f"The {appointment.session} session is locked and cannot accept new appointments.")
                return render(request, "add_appointment.html", {
                    "form": form,
                    "workspace": workspace,
                    "am_slots": am_slots,
                    "pm_slots": pm_slots,
                    "selected_date": selected_date,
                    "has_am": has_am,
                    "has_pm": has_pm,
                    "am_collapsed": am_collapsed,
                    "pm_collapsed": pm_collapsed,
                    "am_disabled": am_disabled,
                    "pm_disabled": pm_disabled,
                    "am_lock_exists": am_lock_exists,
                    "pm_lock_exists": pm_lock_exists,
                    "is_workspace_owner": is_workspace_owner,
                    "day_name": day_name,
                })
            
            appointment.save()

            # Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Added clinic appointment for {appointment.patient_name} (Civil ID: {appointment.civil_id}) on {appointment.date} at {appointment.time} ({appointment.session} session)."
            )

            # Check if the session has reached its maximum capacity
            session_appointments_count = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=selected_date,
                session=appointment.session
            ).count()
            
            # Check if this specific session should be locked
            # Only lock if the session is configured (has a maximum > 0) and has reached that maximum
            if session_max > 0 and session_appointments_count >= session_max:
                # Check if a session-specific lock already exists
                lock_exists = Lock.objects.filter(
                    workspace=workspace, 
                    date=selected_date,
                    pm=session_pm_value
                ).exists()
                
                if not lock_exists:
                    # Create a session-specific lock
                    Lock.objects.create(
                        workspace=workspace,
                        date=selected_date,
                        pm=session_pm_value
                    )
                    
                    # Log the automatic locking
                    ActionLog.objects.create(
                        workspace=workspace,
                        user=request.user,
                        action_description=f"Day {selected_date} {appointment.session} session automatically locked as it reached maximum capacity ({session_max} appointments)."
                    )
                    
                    # Add a message to inform the user
                    messages.info(request, f"The {appointment.session} session has reached its maximum capacity and has been automatically locked.")

            return redirect("day_appointments", workspace_name=workspace_name, date=appointment.date)
    else:
        form = ClinicAppointmentForm()

    return render(request, "add_appointment.html", {
        "form": form,
        "workspace": workspace,
        "am_slots": am_slots,
        "pm_slots": pm_slots,
        "selected_date": selected_date,
        "has_am": has_am,
        "has_pm": has_pm,
        "am_collapsed": am_collapsed,
        "pm_collapsed": pm_collapsed,
        "am_disabled": am_disabled,
        "pm_disabled": pm_disabled,
        "am_lock_exists": am_lock_exists,
        "pm_lock_exists": pm_lock_exists,
        "is_workspace_owner": is_workspace_owner,
        "day_name": day_name,
    })

@login_required
def edit_appointment(request, workspace_name, appointment_id):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    appointment = get_object_or_404(ClinicAppointment, id=appointment_id)

    selected_date = appointment.date
    day_name = selected_date.strftime("%A")
    
    # Get available sessions for this day
    available_sessions = workspace.get_available_sessions(day_name)
    has_am = 'AM' in available_sessions
    has_pm = 'PM' in available_sessions

    # Generate time slots for both sessions
    def generate_time_slots(start_time, end_time):
        slots = []
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        while start <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=15)
        return slots

    am_time_slots = generate_time_slots("08:00", "12:15")
    pm_time_slots = generate_time_slots("14:00", "17:30")

    # Helper function to convert appointment time to string format
    def get_appointment_time_str(appointment):
        if isinstance(appointment.time, int):
            # Convert integer like 1400 to "14:00"
            hours = appointment.time // 100
            minutes = appointment.time % 100
            return f"{hours:02d}:{minutes:02d}"
        elif hasattr(appointment.time, 'strftime'):
            # It's already a time object
            return appointment.time.strftime("%H:%M")
        else:
            # It's already a string
            return str(appointment.time)

    appointment_time_str = get_appointment_time_str(appointment)

    # Count appointments for each time slot (excluding current appointment)
    am_slot_counts = {}
    pm_slot_counts = {}
    
    for slot in am_time_slots:
        count = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=selected_date,
            time=slot,
            session='AM'
        ).exclude(id=appointment.id).count()
        
        # Include current appointment if it's in this slot
        if slot == appointment_time_str and appointment.session == 'AM':
            count += 1
            
        am_slot_counts[slot] = count

    for slot in pm_time_slots:
        count = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=selected_date,
            time=slot,
            session='PM'
        ).exclude(id=appointment.id).count()
        
        # Include current appointment if it's in this slot
        if slot == appointment_time_str and appointment.session == 'PM':
            count += 1
            
        pm_slot_counts[slot] = count

    # Prepare slot data with room counts for red indication
    am_slots = [(slot, am_slot_counts.get(slot, 0), workspace.rooms) for slot in am_time_slots]
    pm_slots = [(slot, pm_slot_counts.get(slot, 0), workspace.rooms) for slot in pm_time_slots]

    # Determine collapse behavior (same logic as add appointment)
    am_collapsed = not has_am and has_pm
    pm_collapsed = not has_pm and has_am

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES, instance=appointment)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            
            # Determine session based on time if not already set
            selected_time = appointment.time
            
            # Convert to time object for comparison
            if isinstance(selected_time, str):
                selected_time_obj = datetime.strptime(selected_time, "%H:%M").time()
            elif isinstance(selected_time, int):
                # Convert integer to time object
                hours = selected_time // 100
                minutes = selected_time % 100
                selected_time_obj = datetime.time(hours, minutes)
            elif hasattr(selected_time, 'hour'):
                # It's already a time object
                selected_time_obj = selected_time
            else:
                # Fallback - assume it's a string representation
                selected_time_obj = datetime.strptime(str(selected_time), "%H:%M").time()
            
            if selected_time_obj < time(14, 0):  # Before 2:00 PM
                appointment.session = 'AM'
            else:
                appointment.session = 'PM'
            
            appointment.save()

            # Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Updated appointment for {appointment.patient_name} (Civil ID: {appointment.civil_id}) to {appointment.date} at {get_appointment_time_str(appointment)} ({appointment.session} session)."
            )

            return redirect("day_appointments", workspace_name=workspace_name, date=appointment.date)
    else:
        form = ClinicAppointmentForm(instance=appointment)

    # Add formatted appointment time to context for template use
    appointment.formatted_time = appointment_time_str

    return render(request, "edit_appointment.html", {
        "form": form,
        "workspace": workspace,
        "am_slots": am_slots,
        "pm_slots": pm_slots,
        "selected_date": selected_date,
        "has_am": has_am,
        "has_pm": has_pm,
        "am_collapsed": am_collapsed,
        "pm_collapsed": pm_collapsed,
        "day_name": day_name,
        "appointment": appointment,
    })

@login_required
def get_session_data(request, workspace_name):
    """AJAX view to get session data for a specific date"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    date_str = request.GET.get('date')
    appointment_id = request.GET.get('appointment_id')  # For edit mode
    
    if not date_str:
        return JsonResponse({'error': 'Date parameter required'}, status=400)
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    day_name = selected_date.strftime("%A")
    
    # Get available sessions for this day
    available_sessions = workspace.get_available_sessions(day_name)
    has_am = 'AM' in available_sessions
    has_pm = 'PM' in available_sessions
    
    # Generate time slots
    def generate_time_slots(start_time, end_time):
        slots = []
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        while start <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=15)
        return slots

    am_time_slots = generate_time_slots("08:00", "12:15")
    pm_time_slots = generate_time_slots("14:00", "17:30")

    # Count appointments for each time slot
    am_slot_counts = {}
    pm_slot_counts = {}
    
    # Base query - exclude current appointment if editing
    base_query = ClinicAppointment.objects.filter(workspace=workspace, date=selected_date)
    if appointment_id:
        base_query = base_query.exclude(id=appointment_id)
    
    for slot in am_time_slots:
        am_slot_counts[slot] = base_query.filter(time=slot, session='AM').count()

    for slot in pm_time_slots:
        pm_slot_counts[slot] = base_query.filter(time=slot, session='PM').count()

    # Prepare response data
    am_slots = []
    for slot in am_time_slots:
        count = am_slot_counts.get(slot, 0)
        am_slots.append({
            'time': slot,
            'count': count,
            'is_full': count >= workspace.rooms
        })

    pm_slots = []
    for slot in pm_time_slots:
        count = pm_slot_counts.get(slot, 0)
        pm_slots.append({
            'time': slot,
            'count': count,
            'is_full': count >= workspace.rooms
        })

    # Determine collapse behavior
    am_collapsed = not has_am and has_pm
    pm_collapsed = not has_pm and has_am

    return JsonResponse({
        'success': True,
        'day_name': day_name,
        'has_am': has_am,
        'has_pm': has_pm,
        'am_collapsed': am_collapsed,
        'pm_collapsed': pm_collapsed,
        'am_slots': am_slots,
        'pm_slots': pm_slots,
        'rooms': workspace.rooms
    })

@csrf_exempt  # Allow AJAX requests
@login_required
def update_confirmed_status(request, appointment_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_status = data.get("confirmed")

            appointment = ClinicAppointment.objects.get(id=appointment_id)
            appointment.confirmed = new_status
            appointment.save()

            return JsonResponse({"success": True, "new_status": new_status})
        except ClinicAppointment.DoesNotExist:
            return JsonResponse({"success": False, "error": "Appointment not found."})
    return JsonResponse({"success": False, "error": "Invalid request."})



@login_required
@csrf_exempt
def delete_surgical_case(request, case_id):
    """Marks a surgical case as 'deleted' instead of removing it."""
    if request.method == "POST":
        try:
            case = SurgicalBooking.objects.get(id=case_id)
            case.status = "deleted"
            case.save()
            ActionLog.objects.create(
                workspace=request.user.workspace,
                user=request.user,
                action_description=f"deleted booked case {case.name} (Civil ID: {case.civil_id}) "
            )
            return JsonResponse({"success": True})
        except SurgicalBooking.DoesNotExist:
            return JsonResponse({"success": False, "error": "Case not found."}, status=404)
    
    return JsonResponse({"success": False, "error": "Invalid request."}, status=400)

@login_required
def edit_surgical_booking(request, workspace_name, case_id):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    case = get_object_or_404(SurgicalBooking, id=case_id, workspace=workspace)

    # Get the next URL from either GET or POST request
    next_url = request.GET.get("next", request.POST.get("next", request.META.get("HTTP_REFERER", None)))

    if request.method == "POST":
        # Add request.FILES parameter to handle file uploads
        form = SurgicalBookingForm(request.POST, request.FILES, instance=case)
        if form.is_valid():
            form.save()
            # ✅ Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Updated surgical booking for {case.name} (Civil ID: {case.civil_id})."
            )

            return redirect(next_url) if next_url else redirect("booked_cases", workspace_name=workspace_name)  # Redirect to previous page or booked cases
            
    else:
        form = SurgicalBookingForm(instance=case)

    return render(request, "edit_surgical_booking.html", {"form": form, "workspace": workspace, "next_url": next_url})



@login_required
@require_POST
def restore_surgical_case(request, case_id):
    """Restores a deleted surgical case by changing its status to 'waiting'."""
    case = get_object_or_404(SurgicalBooking, id=case_id, status='deleted')

    case.status = 'waiting'
    case.save()
    # ✅ Add new ActionLog entry
    ActionLog.objects.create(
        workspace=request.user.workspace,
        user=request.user,
        action_description=f"undeleted surgical booking for {case.name} (Civil ID: {case.civil_id})."
    )


    return JsonResponse({"success": True})


User = get_user_model()


@login_required
def users_management(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure only the admin can access
    if request.user != workspace.admin:
        return redirect("workspace_main", workspace_name=workspace.name)

    users = User.objects.filter(workspace=workspace).exclude(id=workspace.admin.id)

    if request.method == "POST":
        form = UserCreationForm2(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.workspace = workspace  # Assign workspace
            user.save()
            messages.success(request, f"User {user.username} added successfully.")
            return redirect("users_management", workspace_name=workspace.name)
        else:
            # messages.error(request, "Error adding user. Please check the details.")
            messages.error(request, "Error :{form.errors}")
    else:
        form = UserCreationForm2()

    return render(
        request,
        "users_management.html",
        {"workspace": workspace, "users": users, "form": form},
    )




@login_required
@require_POST
def delete_user(request, workspace_name, user_id):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure only the admin can delete users
    if request.user != workspace.admin:
        return JsonResponse({"success": False, "error": "Not authorized"}, status=403)

    user = get_object_or_404(User, id=user_id, workspace=workspace)

    # Prevent admin from deleting himself
    if user == workspace.admin:
        return JsonResponse({"success": False, "error": "Cannot remove admin"}, status=400)

    user.delete()
    return JsonResponse({"success": True})


@login_required
def search_appointments_page(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    return render(request, "search_appointments.html", {"workspace": workspace})

@login_required
def search_appointments_ajax(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse([], safe=False)

    appointments = ClinicAppointment.objects.filter(workspace=workspace).filter(
        patient_name__icontains=query
    ) | ClinicAppointment.objects.filter(
        workspace=workspace
    ).filter(
        civil_id__icontains=query
    ) | ClinicAppointment.objects.filter(
        workspace=workspace
    ).filter(
        phone_number__icontains=query
    )

    results = [
        {
            "id": appt.id,
            "patient_name": appt.patient_name,
            "civil_id": appt.civil_id,
            "phone_number": appt.phone_number,
            "date": appt.date.strftime("%Y-%m-%d"),
            "time": appt.time.strftime("%H:%M"),
            "future": appt.date >= now().date(),
        }
        for appt in appointments
    ]

    return JsonResponse(results, safe=False)

@login_required
def action_log_view(request):
    workspace = request.user.workspace  # Get the user's workspace

    if not workspace:
        return redirect("home")  # Redirect if no workspace is assigned

    actions = ActionLog.objects.filter(workspace=workspace).order_by("-timestamp")  # Order by newest first
    paginator = Paginator(actions, 100)  # 100 actions per page

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "action_log.html", {
        "page_obj": page_obj,
        "workspace": workspace  # Pass workspace to template
    })



@login_required
def download_workspace_data(request):
    """Generates an Excel file with the user's workspace data and sends it as a download."""

    # Ensure the user belongs to a workspace
    workspace = request.user.workspace
    if not workspace:
        raise Http404("You are not assigned to any workspace.")

    # Fetch Appointments
    appointments = ClinicAppointment.objects.filter(workspace=workspace).values(
        "patient_name", "civil_id", "phone_number", "confirmed", "appointment_type",
        "date", "time", "referral_letter"
    )

    # Fetch Surgical Bookings
    bookings = SurgicalBooking.objects.filter(workspace=workspace).values(
        "name", "civil_id", "phone", "diagnosis", "procedure", "side",
        "date", "notes", "status", "created_at"
    )

    # Convert QuerySets to DataFrames
    df_appointments = pd.DataFrame(list(appointments))
    df_bookings = pd.DataFrame(list(bookings))

    # Function to convert only timezone-aware datetimes
    def make_datetime_naive(df, columns):
        for col in columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: make_naive(x) if isinstance(x, pd.Timestamp) and is_aware(x) else x)

    # Convert only datetime fields (ignore date fields)
    make_datetime_naive(df_bookings, ["created_at"])

    # Create an in-memory Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book  # Get the workbook object
        
        if not df_appointments.empty:
            df_appointments.to_excel(writer, sheet_name="Appointments", index=False)
            worksheet = writer.sheets["Appointments"]  # Get the sheet
            worksheet.set_column("F:F", 20)  # Widen "date" column (column F)
        
        if not df_bookings.empty:
            df_bookings.to_excel(writer, sheet_name="Surgical Bookings", index=False)
            worksheet = writer.sheets["Surgical Bookings"]
            worksheet.set_column("G:G", 20)  # Widen "date" column (column G)
            worksheet.set_column("I:I", 20)  # Widen "created_at" column (column I)

    output.seek(0)

    # Send the file as an HTTP response for download
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{workspace.name}.xlsx"'
    return response



@login_required
def create_lock(request, workspace_name, date):
    """Creates a Lock object for a specific date and workspace."""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Get the referring URL to redirect back to
    referring_url = request.META.get('HTTP_REFERER')
    
    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    try:
        # Parse the date string into a datetime object
        lock_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Check if lock already exists
        existing_lock = Lock.objects.filter(workspace=workspace, date=lock_date).first()
        
        if not existing_lock:
            # Create new lock
            Lock.objects.create(workspace=workspace, date=lock_date)
            
            # Add action log entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Locked date {lock_date.strftime('%Y-%m-%d')}."
            )
            
            messages.success(request, f"Date {lock_date.strftime('%Y-%m-%d')} has been locked.")
        else:
            messages.info(request, f"Date {lock_date.strftime('%Y-%m-%d')} was already locked.")
    except ValueError:
        messages.error(request, "Invalid date format.")
    
    # Redirect back to referring page if available, otherwise to calendar view
    if referring_url:
        return redirect(referring_url)
    else:
        return redirect('calendar_view', workspace_name=workspace_name)


@login_required
def delete_lock(request, workspace_name, date):
    """Deletes a Lock object for a specific date and workspace."""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Get the referring URL to redirect back to
    referring_url = request.META.get('HTTP_REFERER')
    
    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    try:
        # Parse the date string into a datetime object
        lock_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Try to find and delete the lock
        lock = Lock.objects.filter(workspace=workspace, date=lock_date).first()
        
        if lock:
            lock.delete()
            
            # Add action log entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Unlocked date {lock_date.strftime('%Y-%m-%d')}."
            )
            
            messages.success(request, f"Date {lock_date.strftime('%Y-%m-%d')} has been unlocked.")
        else:
            messages.info(request, f"No lock found for date {lock_date.strftime('%Y-%m-%d')}.")
    except ValueError:
        messages.error(request, "Invalid date format.")
    
    # Redirect back to referring page if available, otherwise to calendar view
    if referring_url:
        return redirect(referring_url)
    else:
        return redirect('calendar_view', workspace_name=workspace_name)
    





































########################################################################################### REFERRAL SYSTEM ################################################################################################### 
class WorkspaceReferralForm(forms.Form):
    maximum_new_referrals = forms.IntegerField(min_value=0, label="Max New Referrals")

@login_required
def manage_specialities(request):
    specialities = Speciality.objects.all()
    all_workspaces = Workspace.objects.all()
    
    if request.method == 'POST':
        # Check if it's a form for adding/removing workspaces
        if 'speciality_id' in request.POST and 'workspace_id' in request.POST:
            speciality = get_object_or_404(Speciality, id=request.POST['speciality_id'])
            workspace = get_object_or_404(Workspace, id=request.POST['workspace_id'])
            
            # Add or remove workspace from speciality
            action = request.POST.get('action')
            if action == 'add':
                speciality.workspaces.add(workspace)
                messages.success(request, f"Added {workspace.name} to {speciality.name}")
            elif action == 'remove':
                speciality.workspaces.remove(workspace)
                messages.success(request, f"Removed {workspace.name} from {speciality.name}")
        
        # Check if it's a form for updating session maximum_new_referrals
        elif 'update_session_referrals' in request.POST:
            workspace_id = request.POST.get('workspace_id')
            day_name = request.POST.get('day_name')
            session_name = request.POST.get('session_name')
            new_max_referrals = request.POST.get('max_new_referrals')
            
            workspace = get_object_or_404(Workspace, id=workspace_id)
            
            try:
                new_max_referrals = int(new_max_referrals)
                if new_max_referrals >= 0:
                    # Update the session configuration
                    workspace.update_session_limits(day_name, session_name, max_new_referrals=new_max_referrals)
                    messages.success(request, f"Updated maximum new referrals for {workspace.name} - {day_name} {session_name} session")
                else:
                    messages.error(request, "Maximum new referrals must be 0 or greater")
            except (ValueError, TypeError):
                messages.error(request, "Invalid value for maximum new referrals")
        
        return redirect('manage_specialities')
    
    # Prepare speciality data with workspace sessions
    speciality_data = []
    for speciality in specialities:
        workspace_list = []
        for workspace in speciality.workspaces.all():
            sessions = []
            
            # Get all configured sessions for this workspace
            if workspace.session_config:
                for day_name, day_data in workspace.session_config.items():
                    day_sessions = day_data.get('sessions', {})
                    for session_name, session_data in day_sessions.items():
                        sessions.append({
                            'day_name': day_name,
                            'session_name': session_name,
                            'max_total': session_data.get('max_total', 0),
                            'max_new_referrals': session_data.get('max_new_referrals', 0),
                        })
            
            # Sort by day order and then by session (AM before PM)
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            session_order = ['AM', 'PM']
            
            sessions.sort(
                key=lambda x: (day_order.index(x['day_name']) if x['day_name'] in day_order else 999,
                              session_order.index(x['session_name']) if x['session_name'] in session_order else 999)
            )
            
            workspace_list.append({
                'workspace': workspace,
                'sessions': sessions
            })
        
        speciality_data.append({
            'speciality': speciality,
            'workspaces': workspace_list
        })
    
    context = {
        'speciality_data': speciality_data,
        'all_workspaces': all_workspaces,
    }
    
    return render(request, 'manage_specialities_standalone.html', context)

def doctor_register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        full_name = request.POST.get('full_name')
        
        # Validate input
        if not username or not password or not full_name:
            messages.error(request, "All fields are required")
        elif Doctor.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists")
        else:
            # Create the doctor with active=False by default
            doctor = Doctor.objects.create(
                username=username,
                password=password,
                full_name=full_name,
                active=False  # Always inactive by default
            )
            # Redirect to thank you page
            return render(request, 'doctor_register_thanks.html')
    
    return render(request, 'doctor_register.html')





def doctor_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Add debug messages to see what's being submitted
        print(f"Login attempt: Username: {username}, Password: {password}")
        
        # Try to find the doctor first without checking password
        try:
            doctor = Doctor.objects.get(username=username)
            print(f"Found doctor: {doctor.full_name}, Stored password: {doctor.password}")
            
            # Now check password separately
            if doctor.password == password and doctor.active:
                request.session['doctor_id'] = doctor.id
                request.session['doctor_name'] = doctor.full_name
                return redirect('doctor_dashboard')
            else:
                if doctor.password != password:
                    print(f"Password mismatch. Entered: '{password}', Stored: '{doctor.password}'")
                    messages.error(request, 'Incorrect password')
                elif not doctor.active:
                    messages.error(request, 'This account is inactive')
        except Doctor.DoesNotExist:
            print(f"No doctor found with username: {username}")
            messages.error(request, 'Invalid username')
    
    return render(request, 'doctor_login.html')

# Doctor logout
def doctor_logout(request):
    request.session.pop('doctor_id', None)
    request.session.pop('doctor_name', None)
    return redirect('doctor_login')


def doctor_login2(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Add debug messages to see what's being submitted
        print(f"Login attempt: Username: {username}, Password: {password}")
        
        # Try to find the doctor first without checking password
        try:
            doctor = Doctor.objects.get(username=username)
            print(f"Found doctor: {doctor.full_name}, Stored password: {doctor.password}")
            
            # Now check password separately
            if doctor.password == password and doctor.active:
                request.session['doctor_id'] = doctor.id
                request.session['doctor_name'] = doctor.full_name
                return redirect('doctor_calendar')
            else:
                if doctor.password != password:
                    print(f"Password mismatch. Entered: '{password}', Stored: '{doctor.password}'")
                    messages.error(request, 'Incorrect password')
                elif not doctor.active:
                    messages.error(request, 'This account is inactive')
        except Doctor.DoesNotExist:
            print(f"No doctor found with username: {username}")
            messages.error(request, 'Invalid username')
    
    return render(request, 'doctor_login2.html')

# Doctor logout
def doctor_logout2(request):
    request.session.pop('doctor_id', None)
    request.session.pop('doctor_name', None)
    return redirect('doctor_login2')




# Doctor authentication middleware
def doctor_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'doctor_id' not in request.session:
            return redirect('doctor_login')
        return view_func(request, *args, **kwargs)
    return wrapper

# Doctor dashboard
@doctor_required
def doctor_dashboard(request):
    doctor_id = request.session.get('doctor_id')
    doctor = get_object_or_404(Doctor, id=doctor_id)
    specialities = Speciality.objects.all()
    
    return render(request, 'doctor_dashboard.html', {
        'doctor': doctor,
        'specialities': specialities
    })

# Find next available appointment slot with AM/PM session support
def find_available_appointment(speciality, am_only=False):
    # Get all workspaces with this speciality
    workspaces = speciality.workspaces.all()
    
    if not workspaces.exists():
        return None, None, None
    
    # Get tomorrow's date
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # AM Time slots (8:00 AM to 12:30 PM)
    am_time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45",
            "10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45",
            "12:00","12:15","12:30"
        ]
    ]
    
    # PM Time slots (2:00 PM to 5:30 PM)
    pm_time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "14:00","14:15","14:30","14:45","15:00","15:15","15:30","15:45",
            "16:00","16:15","16:30","16:45","17:00","17:15","17:30"
        ]
    ]
    
    # Default slots for booking when no empty slots are found
    default_am_slot = datetime.strptime("08:00", "%H:%M").time()
    default_pm_slot = datetime.strptime("14:00", "%H:%M").time()
    
    # Check up to 120 days ahead starting from tomorrow
    for day_offset in range(120):
        check_date = tomorrow + timedelta(days=day_offset)
        day_name = check_date.strftime("%A")
        print(f"checking date : {check_date}")
        
        # Keep track of the best workspace for this day
        best_workspace = None
        lowest_referral_count = float('inf')
        best_slot = None
        best_session = None
        
        # For tracking workspaces without available slots
        valid_workspaces_without_slots = []
        
        # Check all workspaces for this specific day
        for workspace in workspaces:
            # Skip workspaces that aren't open on this day
            if not workspace.is_day_open(day_name):
                print(f"Skipping workspace {workspace} - not open on {day_name}")
                continue
            
            # Get available sessions for this day
            available_sessions = workspace.get_available_sessions(day_name)
            has_am = 'AM' in available_sessions
            has_pm = 'PM' in available_sessions
            
            # If user wants AM only, skip if no AM session
            if am_only and not has_am:
                continue
            
            # Check for session-specific locks
            am_locked = Lock.objects.filter(workspace=workspace, date=check_date, pm=False).exists()
            pm_locked = Lock.objects.filter(workspace=workspace, date=check_date, pm=True).exists()
            
            # Skip workspace entirely if all available sessions are locked
            if has_am and has_pm:
                if am_locked and pm_locked:
                    print(f"Skipping workspace {workspace} on {check_date} - both sessions locked")
                    continue
            elif has_am and am_locked:
                print(f"Skipping workspace {workspace} on {check_date} - AM session locked")
                continue
            elif has_pm and pm_locked:
                print(f"Skipping workspace {workspace} on {check_date} - PM session locked")
                continue
            
            print(f"open workspaces {workspace}")
            
            # Sessions to check (based on availability, locks, and user preference)
            sessions_to_check = []
            if has_am and not am_locked and (not am_only or am_only):
                sessions_to_check.append(('AM', am_time_slots))
            if has_pm and not pm_locked and not am_only:
                sessions_to_check.append(('PM', pm_time_slots))
            
            # Check each available session
            for session_name, time_slots in sessions_to_check:
                # Count existing appointments for this session
                total_appointments = ClinicAppointment.objects.filter(
                    workspace=workspace,
                    date=check_date,
                    session=session_name
                ).count()
                
                # Count new referrals for this session
                new_referrals = ClinicAppointment.objects.filter(
                    workspace=workspace,
                    date=check_date,
                    session=session_name,
                    appointment_type="New",
                    system_referral=True
                ).count()
                
                print(f"Session {session_name}: total={total_appointments}, new_referrals={new_referrals}")
                
                # Get session maximums
                session_max_total = workspace.get_session_maximum(day_name, session_name, is_new_referral=False)
                session_max_new = workspace.get_session_maximum(day_name, session_name, is_new_referral=True)
                
                # Skip sessions that have reached their limit
                if (total_appointments >= session_max_total or 
                    new_referrals >= session_max_new):
                    print(f'Skipping {workspace} {session_name} session - limits reached')
                    continue
                
                # Track this workspace+session as valid
                valid_workspaces_without_slots.append((workspace, new_referrals, session_name))
                
                # If this session has fewer referrals than our current best, check for slots
                if new_referrals < lowest_referral_count:
                    # Find the first available time slot in this session
                    occupied_times = ClinicAppointment.objects.filter(
                        workspace=workspace,
                        date=check_date,
                        session=session_name
                    ).values_list('time', flat=True)
                    
                    for slot in time_slots:
                        if slot not in occupied_times:
                            # Found an available slot in this session
                            best_workspace = workspace
                            lowest_referral_count = new_referrals
                            best_slot = slot
                            best_session = session_name
                            break
                    
                    if best_slot:
                        break  # Found a slot, no need to check other sessions
        
        # If we found a workspace with an available slot on this day, return it
        if best_workspace and best_slot and best_session:
            return best_workspace, check_date, best_slot
        
        # If all conditions are met but no empty slot is found, book at default time
        if valid_workspaces_without_slots:
            # Sort by referral count to get the one with lowest referrals
            valid_workspaces_without_slots.sort(key=lambda x: x[1])
            best_workspace = valid_workspaces_without_slots[0][0]
            best_session = valid_workspaces_without_slots[0][2]
            
            # Use appropriate default slot based on session
            default_slot = default_am_slot if best_session == 'AM' else default_pm_slot
            return best_workspace, check_date, default_slot
    
    # No available slots found in any workspace within the time range
    return None, None, None

# Doctor appointment booking
# Doctor appointment booking
@doctor_required
@require_POST
def book_appointment(request):
    # Get doctor info from session
    doctor_id = request.session.get('doctor_id')
    doctor = get_object_or_404(Doctor, id=doctor_id)
    
    # Check content type to determine how to parse the data
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            patient_name = data.get('patient_name')
            civil_id = data.get('civil_id')
            phone_number = data.get('phone_number')
            speciality_id = data.get('speciality')
            diagnosis = data.get('diagnosis')
            is_urgent = data.get('is_urgent', False)
            am_only = data.get('am_only', False)  # New field
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    else:
        # For form submissions
        patient_name = request.POST.get('patient_name')
        civil_id = request.POST.get('civil_id')
        phone_number = request.POST.get('phone_number')
        speciality_id = request.POST.get('speciality')
        diagnosis = request.POST.get('diagnosis')
        is_urgent = request.POST.get('is_urgent') == 'on'
        am_only = request.POST.get('am_only') == 'on'  # New field
    
    # Validate input
    if not patient_name or not civil_id or not phone_number or not speciality_id:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'All fields are required'})
        else:
            messages.error(request, "All fields are required")
            return redirect('doctor_dashboard')
    
    # Validate civil ID length
    if len(civil_id) != 12:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'Civil ID must be exactly 12 digits'})
        else:
            messages.error(request, "Civil ID must be exactly 12 digits")
            return redirect('doctor_dashboard')
    
    # Validate phone number length
    if len(phone_number) != 8:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'Phone number must be exactly 8 digits'})
        else:
            messages.error(request, "Phone number must be exactly 8 digits")
            return redirect('doctor_dashboard')
    
    # Get speciality
    try:
        speciality = Speciality.objects.get(id=speciality_id)
    except Speciality.DoesNotExist:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': 'Invalid speciality'})
        else:
            messages.error(request, "Invalid speciality")
            return redirect('doctor_dashboard')
    
    # Find available slot with AM-only preference
    workspace, appointment_date, appointment_time = find_available_appointment(speciality, am_only=am_only)
    
    if not workspace or not appointment_date or not appointment_time:
        session_msg = " (AM slots only)" if am_only else ""
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': f"No available appointments for {speciality.name} speciality{session_msg}"})
        else:
            messages.error(request, f"No available appointments for {speciality.name} speciality{session_msg}")
            return redirect('doctor_dashboard')
    
    # Determine session based on appointment time
    session = 'AM' if appointment_time.hour < 14 else 'PM'
    
    # Create appointment
    appointment = ClinicAppointment.objects.create(
        workspace=workspace,
        patient_name=patient_name,
        civil_id=civil_id,
        phone_number=phone_number,
        confirmed="Unknown",
        appointment_type="New",
        date=appointment_date,
        time=appointment_time,
        session=session,  # Set the session
        system_referral=True,
        booked_by=doctor,
        diagnosis=diagnosis
    )
    
    # Check workspace setting for showing time to new referrals
    show_time = workspace.give_new_referrals_time
    
    # Return response based on content type
    if request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'message': 'Appointment booked successfully',
            'appointment_id': appointment.id,
            'speciality_name': speciality.name,
            'clinic_name': workspace.owner_name or workspace.name,
            'appointment_date': appointment_date.strftime('%d %b %Y'),
            'appointment_time': appointment_time.strftime('%H:%M') if show_time else None,
            'workspace_id': workspace.id,
            'session': session,  # Include session info
            'show_time': show_time  # Include the boolean to control frontend display
        })
    else:
        if show_time:
            time_msg = f" at {appointment_time.strftime('%H:%M')}"
        else:
            time_msg = ""
        
        messages.success(
            request, 
            f"Appointment booked successfully for {patient_name} with {speciality.name} speciality on "
            f"{appointment_date.strftime('%d %b %Y')}{time_msg} ({session} session)"
        )
        return redirect('doctor_dashboard')


@doctor_required
@csrf_protect
@require_POST
def change_appointment_date(request):
    print("==== STARTING change_appointment_date function ====")
    try:
        data = json.loads(request.body)
        appointment_id = data.get('appointment_id')
        workspace_id = data.get('workspace_id')
        am_only = data.get('am_only', False)  # New parameter for AM-only preference
        print(f"Received data: appointment_id={appointment_id}, workspace_id={workspace_id}, am_only={am_only}")
    except json.JSONDecodeError:
        print("ERROR: Invalid JSON data")
        return JsonResponse({'success': False, 'message': 'Invalid JSON data'})
    
    # Get the appointment
    try:
        appointment = ClinicAppointment.objects.get(id=appointment_id)
        print(f"Found appointment: {appointment.id}, date={appointment.date}, time={appointment.time}")
    except ClinicAppointment.DoesNotExist:
        print(f"ERROR: Appointment with id={appointment_id} not found")
        return JsonResponse({'success': False, 'message': 'Appointment not found'})
    
    # Get the workspace
    try:
        workspace = Workspace.objects.get(id=workspace_id)
        print(f"Found workspace: {workspace.name}")
    except Workspace.DoesNotExist:
        print(f"ERROR: Workspace with id={workspace_id} not found")
        return JsonResponse({'success': False, 'message': 'Workspace not found'})
    
    # AM Time slots (8:00 AM to 12:30 PM)
    am_time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45",
            "10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45",
            "12:00","12:15","12:30"
        ]
    ]
    
    # PM Time slots (2:00 PM to 5:30 PM)
    pm_time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "14:00","14:15","14:30","14:45","15:00","15:15","15:30","15:45",
            "16:00","16:15","16:30","16:45","17:00","17:15","17:30"
        ]
    ]
    
    # Default slots for booking when no empty slots are found
    default_am_slot = datetime.strptime("08:00", "%H:%M").time()
    default_pm_slot = datetime.strptime("14:00", "%H:%M").time()
    
    print(f"Generated {len(am_time_slots)} AM slots and {len(pm_time_slots)} PM slots")
    
    # Find a new date (starting from the day after the current appointment)
    start_date = appointment.date + timedelta(days=1)
    print(f"Starting search from date: {start_date}")
    
    # To track valid days without available slots
    valid_dates_without_slots = []
    
    for day_offset in range(60):  # Look up to 60 days ahead
        check_date = start_date + timedelta(days=day_offset)
        day_name = check_date.strftime("%A")
        print(f"\nChecking date: {check_date} ({day_name})")
        
        # Check if this day is open for the workspace
        if not workspace.is_day_open(day_name):
            print(f"Skipping date {check_date}: Day {day_name} is not open for this workspace")
            continue
        
        # Get available sessions for this day
        available_sessions = workspace.get_available_sessions(day_name)
        has_am = 'AM' in available_sessions
        has_pm = 'PM' in available_sessions
        
        # If user wants AM only, skip if no AM session
        if am_only and not has_am:
            print(f"Skipping date {check_date}: AM-only requested but no AM session available")
            continue
        
        # Check for session-specific locks
        am_locked = Lock.objects.filter(workspace=workspace, date=check_date, pm=False).exists()
        pm_locked = Lock.objects.filter(workspace=workspace, date=check_date, pm=True).exists()
        
        # Skip workspace entirely if all available sessions are locked
        if has_am and has_pm:
            if am_locked and pm_locked:
                print(f"Skipping date {check_date}: Both sessions locked")
                continue
        elif has_am and am_locked:
            print(f"Skipping date {check_date}: AM session locked")
            continue
        elif has_pm and pm_locked:
            print(f"Skipping date {check_date}: PM session locked")
            continue
        
        # Sessions to check (based on availability, locks, and user preference)
        sessions_to_check = []
        if has_am and not am_locked and (not am_only or am_only):
            sessions_to_check.append(('AM', am_time_slots))
        if has_pm and not pm_locked and not am_only:
            sessions_to_check.append(('PM', pm_time_slots))
        
        print(f"Sessions to check: {[s[0] for s in sessions_to_check]}")
        
        # Check each available session
        found_slot = False
        best_session = None
        best_slot = None
        valid_session_found = False
        
        for session_name, time_slots in sessions_to_check:
            # Count existing appointments for this session
            total_appointments = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=check_date,
                session=session_name
            ).count()
            
            # Count new referrals for this session
            new_referrals = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=check_date,
                session=session_name,
                appointment_type="New",
                system_referral=True
            ).count()
            
            print(f"Session {session_name}: total={total_appointments}, new_referrals={new_referrals}")
            
            # Get session maximums
            session_max_total = workspace.get_session_maximum(day_name, session_name, is_new_referral=False)
            session_max_new = workspace.get_session_maximum(day_name, session_name, is_new_referral=True)
            
            # Skip sessions that have reached their limit
            if (total_appointments >= session_max_total or 
                new_referrals >= session_max_new):
                print(f'Skipping {session_name} session - limits reached')
                continue
            
            # This session is valid (has capacity)
            valid_session_found = True
            valid_dates_without_slots.append((check_date, session_name))
            
            # Find available time slot in this session
            occupied_times = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=check_date,
                session=session_name
            ).values_list('time', flat=True)
            
            print(f"Occupied times for {check_date} {session_name}: {list(occupied_times)}")
            
            for slot in time_slots:
                if slot not in occupied_times:
                    print(f"Found available slot: {check_date} at {slot} ({session_name} session)")
                    found_slot = True
                    best_session = session_name
                    best_slot = slot
                    break
            
            if found_slot:
                break  # Found a slot, no need to check other sessions
        
        # If we found an available slot, update the appointment
        if found_slot and best_slot and best_session:
            old_date = appointment.date
            old_time = appointment.time
            
            try:
                appointment.date = check_date
                appointment.time = best_slot
                appointment.session = best_session  # Update session
                appointment.save()
                print(f"Updated appointment: date={check_date}, time={best_slot}, session={best_session}")
                
                # Check workspace setting for showing time to new referrals
                show_time = workspace.give_new_referrals_time
                
                return JsonResponse({
                    'success': True,
                    'message': 'Appointment date changed successfully',
                    'new_date': check_date.strftime('%d %b %Y'),
                    'new_time': best_slot.strftime('%H:%M') if show_time else None,
                    'new_session': best_session,
                    'old_date': old_date.strftime('%d %b %Y'),
                    'old_time': old_time.strftime('%H:%M'),
                    'show_time': show_time  # Include the boolean to control frontend display
                })
            except Exception as e:
                print(f"ERROR saving appointment: {str(e)}")
                return JsonResponse({'success': False, 'message': f'Error saving appointment: {str(e)}'})
    
    # If we found valid sessions but no empty slots, book at default time
    if valid_dates_without_slots:
        # Get the earliest valid date and session
        earliest_date, earliest_session = valid_dates_without_slots[0]
        default_slot = default_am_slot if earliest_session == 'AM' else default_pm_slot
        
        print(f"No available slots found, but there are valid sessions. Booking at default time on {earliest_date} ({earliest_session})")
        
        old_date = appointment.date
        old_time = appointment.time
        
        try:
            appointment.date = earliest_date
            appointment.time = default_slot
            appointment.session = earliest_session  # Update session
            appointment.save()
            print(f"Updated appointment to default slot: date={earliest_date}, time={default_slot}, session={earliest_session}")
            
            # Check workspace setting for showing time to new referrals
            show_time = workspace.give_new_referrals_time
            
            return JsonResponse({
                'success': True,
                'message': f'Appointment date changed successfully (using default {earliest_session} slot)',
                'new_date': earliest_date.strftime('%d %b %Y'),
                'new_time': default_slot.strftime('%H:%M') if show_time else None,
                'new_session': earliest_session,
                'old_date': old_date.strftime('%d %b %Y'),
                'old_time': old_time.strftime('%H:%M'),
                'show_time': show_time  # Include the boolean to control frontend display
            })
        except Exception as e:
            print(f"ERROR saving appointment to default slot: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Error saving appointment: {str(e)}'})
    
    session_msg = " (AM slots only)" if am_only else ""
    print(f"ERROR: No available dates found after checking 60 days{session_msg}")
    return JsonResponse({'success': False, 'message': f'No available dates found{session_msg}'})



@doctor_required
def doctor_search_appointments(request):
    """
    Search for appointments by Civil ID
    """
    civil_id = request.GET.get('civil_id')
    
    if not civil_id or len(civil_id) != 12:
        return JsonResponse({
            'success': False,
            'message': 'Invalid Civil ID'
        })
    
    # Query appointments for this Civil ID
    appointments = ClinicAppointment.objects.filter(civil_id=civil_id).order_by('-date', '-time')
    
    appointments_data = []
    for appointment in appointments:
        # Get the workspace name and speciality name
        workspace_name = appointment.workspace.owner_name or appointment.workspace.name
        
        # Try to get speciality name
        speciality_name = "Unknown"
        for speciality in appointment.workspace.specialities.all():
            speciality_name = speciality.name
            break  # Just take the first one for simplicity
        
        appointments_data.append({
            'id': appointment.id,
            'patient_name': appointment.patient_name,
            'date': appointment.date.strftime('%d %b %Y'),
            'time': appointment.time.strftime('%H:%M'),
            'confirmed': appointment.confirmed,
            'clinic_name': workspace_name,
            'speciality_name': speciality_name
        })
    
    return JsonResponse({
        'success': True,
        'appointments': appointments_data
    })



### printing appointment

def doctor_calendar(request):
    # Check if doctor is logged in
    if 'doctor_id' not in request.session:
        return redirect('doctor_login2')
    
    today = timezone.now().date()
    
    # Load data for 3 months: previous, current, and next
    start_of_prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    start_of_current_month = today.replace(day=1)
    if today.month == 12:
        start_of_next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        start_of_next_month = today.replace(month=today.month + 1, day=1)
    
    # Calculate end of next month
    if start_of_next_month.month == 12:
        end_of_next_month = start_of_next_month.replace(year=start_of_next_month.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_next_month = start_of_next_month.replace(month=start_of_next_month.month + 1, day=1) - timedelta(days=1)
    
    # Get all clinic appointments within the 3-month range
    appointments = ClinicAppointment.objects.filter(
        date__gte=start_of_prev_month,
        date__lte=end_of_next_month
    ).select_related('workspace')
    
    # Get all specialities for filtering
    specialities = Speciality.objects.all()
    
    # Group appointments by date and collect clinic names
    appointments_by_date = {}
    
    for appointment in appointments:
        # Check if the clinic has a speciality
        if specialities.filter(workspaces=appointment.workspace).exists():
            date_str = appointment.date.strftime('%Y-%m-%d')
            
            if date_str not in appointments_by_date:
                appointments_by_date[date_str] = set()
            
            # Add clinic name or owner name
            clinic_name = appointment.workspace.owner_name or appointment.workspace.name
            appointments_by_date[date_str].add(clinic_name)
    
    context = {
        'today': today,
        'appointments_by_date': appointments_by_date,
    }
    return render(request, 'doctor_calendar.html', context)


@doctor_required
def doctor_day_appointments(request, year, month, day):
    # Convert string parameters to integers if they aren't already
    year = int(year)
    month = int(month)
    day = int(day)
    
    # Create date object - fixed to use the date constructor correctly
    from datetime import date  # Add this import
    selected_date = date(year, month, day)
    
    # Get all specialities
    specialities = Speciality.objects.all()
    
    # Find all clinics that have appointments for this day AND have a speciality
    # First, get all appointments for this day
    day_appointments = ClinicAppointment.objects.filter(date=selected_date)
    
    # Get unique workspaces from these appointments
    workspace_ids = day_appointments.values_list('workspace_id', flat=True).distinct()
    
    # Get the actual workspace objects
    workspaces_with_appointments = Workspace.objects.filter(id__in=workspace_ids)
    
    # Filter to only include workspaces with specialities
    clinics_with_speciality = []
    for clinic in workspaces_with_appointments:
        if specialities.filter(workspaces=clinic).exists():
            clinics_with_speciality.append(clinic)
    
    # Get selected clinic if any
    selected_clinic_id = request.GET.get('clinic')
    selected_clinic = None
    
    # By default, collect all appointments for all clinics with speciality
    all_clinic_appointments = []
    
    if selected_clinic_id:
        # If a specific clinic is selected, only show its appointments
        selected_clinic = get_object_or_404(Workspace, id=selected_clinic_id)
        if specialities.filter(workspaces=selected_clinic).exists():
            appointments = ClinicAppointment.objects.filter(
                workspace=selected_clinic,
                date=selected_date
            ).order_by('time')
            
            # Get all time slots with appointments
            timeslots = set()
            for appointment in appointments:
                timeslots.add(appointment.time.strftime('%H:%M'))
            timeslots = sorted(list(timeslots))
            
            all_clinic_appointments = [{
                'clinic': selected_clinic,
                'appointments': appointments,
                'timeslots': timeslots
            }]
    else:
        # If no clinic is selected, show appointments for all clinics with speciality
        for clinic in clinics_with_speciality:
            appointments = ClinicAppointment.objects.filter(
                workspace=clinic,
                date=selected_date
            ).order_by('time')
            
            # Get all time slots with appointments
            timeslots = set()
            for appointment in appointments:
                timeslots.add(appointment.time.strftime('%H:%M'))
            timeslots = sorted(list(timeslots))
            
            if appointments.exists():
                all_clinic_appointments.append({
                    'clinic': clinic,
                    'appointments': appointments,
                    'timeslots': timeslots
                })
    
    context = {
        'selected_date': selected_date,
        'open_clinics': clinics_with_speciality,  # These are the clinics with appointments and specialities
        'selected_clinic_id': selected_clinic_id,
        'all_clinic_appointments': all_clinic_appointments,
    }
    
    return render(request, 'doctor_day_appointments.html', context)


@doctor_required
def print_all_appointments(request, year, month, day):
    # Convert string parameters to integers if they aren't already
    year = int(year)
    month = int(month)
    day = int(day)
    
    # Create date object
    selected_date = datetime.date(year, month, day)
    
    # Get the day name
    day_name = selected_date.strftime("%A")
    
    # Get all workspaces and filter in Python
    all_workspaces = Workspace.objects.all()
    open_workspaces = [workspace for workspace in all_workspaces if day_name in workspace.days_open]
    
    # Get all specialities
    specialities = Speciality.objects.all()
    
    # Filter out workspaces that don't belong to any speciality
    workspaces_with_speciality = []
    for workspace in open_workspaces:
        if specialities.filter(workspaces=workspace).exists():
            workspaces_with_speciality.append(workspace)
    
    # Get appointments for all workspaces with specialities
    all_appointments = []
    for workspace in workspaces_with_speciality:
        workspace_appointments = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=selected_date
        ).order_by('time')
        
        if workspace_appointments:
            all_appointments.append({
                'workspace': workspace,
                'appointments': workspace_appointments
            })
    
    context = {
        'selected_date': selected_date,
        'all_appointments': all_appointments,
    }
    
    return render(request, 'print_all_appointments.html', context)


from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from .models import ClinicAppointment, SurgicalBooking

def patient_lookup(request):
    # Get the query parameter from the request
    phone_number = request.GET.get('phone_number')
    civil_id = request.GET.get('civil_id')
    
    # Check if at least one parameter is provided
    if not phone_number and not civil_id:
        return JsonResponse({'error': 'Please provide either phone_number or civil_id'}, status=400)
    
    # Initialize query filter for ClinicAppointment
    clinic_q_filter = Q()
    # Initialize query filter for SurgicalBooking
    surgical_q_filter = Q()
    
    # Build the query based on provided parameters
    if phone_number:
        clinic_q_filter |= Q(phone_number=phone_number)  # ClinicAppointment uses 'phone_number'
        surgical_q_filter |= Q(phone=phone_number)  # SurgicalBooking uses 'phone'
    
    if civil_id:
        clinic_q_filter |= Q(civil_id=civil_id)
        surgical_q_filter |= Q(civil_id=civil_id)
    
    # Query both models
    surgical_bookings = SurgicalBooking.objects.filter(surgical_q_filter).order_by('-created_at')
    clinic_appointments = ClinicAppointment.objects.filter(clinic_q_filter).order_by('-date', '-time')
    
    # Get the latest entries
    latest_surgical = surgical_bookings.first()
    latest_clinic = clinic_appointments.first()
    
    # Determine which entry is more recent
    latest_entry = None
    
    if latest_surgical and latest_clinic:
        # Compare creation date of surgical booking with appointment date+time
        surgical_datetime = latest_surgical.created_at
        clinic_datetime = timezone.datetime.combine(latest_clinic.date, latest_clinic.time)
        
        # Make timezone aware if needed
        if not clinic_datetime.tzinfo:
            clinic_datetime = timezone.make_aware(clinic_datetime)
        
        if surgical_datetime > clinic_datetime:
            latest_entry = latest_surgical
        else:
            latest_entry = latest_clinic
    elif latest_surgical:
        latest_entry = latest_surgical
    elif latest_clinic:
        latest_entry = latest_clinic
    
    # Return the response
    if latest_entry:
        if isinstance(latest_entry, SurgicalBooking):
            response_data = {
                'phone_number': latest_entry.phone,  # SurgicalBooking uses 'phone'
                'patient_name': latest_entry.name,   # SurgicalBooking uses 'name'
                'civil_id': latest_entry.civil_id
            }
        else:  # ClinicAppointment
            response_data = {
                'phone_number': latest_entry.phone_number,  # ClinicAppointment uses 'phone_number'
                'patient_name': latest_entry.patient_name,  # ClinicAppointment uses 'patient_name'
                'civil_id': latest_entry.civil_id
            }
        
        return JsonResponse(response_data)
    else:
        return JsonResponse({'error': 'No patient found with the provided information'}, status=404)

# This is the fixed system_referrals_list view function section
# The issue was with how the 'referred_at' attribute was being handled

@require_GET
def system_referrals_list(request):
    """
    View to list all system referrals (appointments with system_referral=True)
    with filtering, searching and pagination
    """
    # Base queryset - get appointments with system_referral=True ordered by creation date (newest first)
    try:
        appointments = ClinicAppointment.objects.filter(
            system_referral=True
        ).order_by('-created_at')
    except:
        # Fallback if created_at field doesn't exist
        appointments = ClinicAppointment.objects.filter(
            system_referral=True
        ).order_by('-date', '-time')
    
    # Get all specialities for the filter dropdowns
    specialities = Speciality.objects.all().order_by('name')
    
    # Handle search query
    search_query = request.GET.get('search', '')
    if search_query:
        appointments = appointments.filter(
            Q(patient_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(civil_id__icontains=search_query)
        )
    
    # Handle speciality filter
    speciality_id = request.GET.get('speciality', 'all')
    selected_speciality = speciality_id  # Store for template
    
    if speciality_id and speciality_id != 'all':
        try:
            # Get the speciality object
            speciality = Speciality.objects.get(id=speciality_id)
            
            # Get all workspaces associated with this speciality
            workspace_ids = speciality.workspaces.values_list('id', flat=True)
            
            # Filter appointments by these workspaces
            appointments = appointments.filter(workspace_id__in=workspace_ids)
        except Speciality.DoesNotExist:
            pass
    
    # Handle workspace filter (only applied if speciality is selected)
    workspace_id = request.GET.get('workspace', 'all')
    selected_workspace = workspace_id  # Store for template
    
    if workspace_id and workspace_id != 'all' and speciality_id and speciality_id != 'all':
        try:
            # Filter appointments by selected workspace
            appointments = appointments.filter(workspace_id=workspace_id)
        except:
            pass
    
    # Generate a list of workspaces for the selected speciality (for the dynamic dropdown)
    workspaces = []
    if speciality_id and speciality_id != 'all':
        try:
            speciality = Speciality.objects.get(id=speciality_id)
            workspaces = speciality.workspaces.all().order_by('owner_name', 'name')
        except Speciality.DoesNotExist:
            workspaces = []
    
    # Handle the 'referred_at' attribute for each appointment
    # This is a key fix to ensure the proper column data is shown
    for appointment in appointments:
        if not hasattr(appointment, 'created_at') or not appointment.created_at:
            # Set a placeholder for referred_at if created_at doesn't exist
            appointment.referred_at = 'No record'
        else:
            # Format the created_at timestamp as referred_at
            appointment.referred_at = appointment.created_at.strftime('%d %b %Y %H:%M')
    
    # Pagination
    paginator = Paginator(appointments, 100)  # 100 referrals per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # If it's an AJAX request, return JSON
        appointment_data = []
        for appointment in page_obj:
            # Get the referring doctor name if available
            referring_doctor = None
            if appointment.booked_by:
                referring_doctor = appointment.booked_by.full_name
                
            appointment_data.append({
                'id': appointment.id,
                'patient_name': appointment.patient_name,
                'civil_id': appointment.civil_id,
                'phone_number': appointment.phone_number,
                'date': appointment.date.strftime('%d %b %Y'),
                'time': appointment.time.strftime('%H:%M'),
                'referred_at': getattr(appointment, 'referred_at', 'No record'),
                'diagnosis': appointment.diagnosis or 'No diagnosis',
                'workspace_name': appointment.workspace.owner_name or appointment.workspace.name,
                'confirmed': appointment.confirmed,
                'referred_by': referring_doctor or 'Not specified',
            })
        
        return JsonResponse({
            'appointments': appointment_data,
            'page': page_obj.number,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
        })
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'specialities': specialities,
        'workspaces': workspaces,
        'selected_speciality': selected_speciality,
        'selected_workspace': selected_workspace,
    }
    
    # Use the standalone template
    return render(request, 'system_referrals_standalone.html', context)

@require_GET
def api_workspaces_by_speciality(request, speciality_id):
    """
    API endpoint to get workspaces filtered by speciality
    """
    try:
        speciality = Speciality.objects.get(id=speciality_id)
        workspaces = speciality.workspaces.all().order_by('owner_name', 'name')
        
        workspace_data = [
            {
                'id': workspace.id,
                'name': workspace.name,
                'owner_name': workspace.owner_name or workspace.name,
            }
            for workspace in workspaces
        ]
        
        return JsonResponse({'workspaces': workspace_data})
    except Speciality.DoesNotExist:
        return JsonResponse({'error': 'Speciality not found'}, status=404)

@login_required
def system_referrals_stats(request):
    """
    View for displaying system referral statistics.
    Only accessible by workspace owners (admins).
    Filters referrals by created_at date instead of appointment date.
    """
    user = request.user
    
    # Check if user is a workspace admin
    if not hasattr(user, 'admin_workspace'):
        return render(request, 'error.html', {'message': 'You do not have permission to access this page.'})
    
    # Get current month and year or from request parameters
    today = timezone.now().date()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    # Create date range for filtering based on created_at instead of appointment date
    start_date = datetime(selected_year, selected_month, 1)
    
    # Calculate end date (last day of the month)
    if selected_month == 12:
        end_date = datetime(selected_year + 1, 1, 1) - timedelta(seconds=1)
    else:
        end_date = datetime(selected_year, selected_month + 1, 1) - timedelta(seconds=1)
    
    # Get all system referrals created in the selected period
    referrals = ClinicAppointment.objects.filter(
        system_referral=True,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Calculate statistics
    total_referrals = referrals.count()
    new_referrals = referrals.filter(appointment_type="New").count()
    followup_referrals = referrals.filter(appointment_type="Follow-Up").count()
    
    # Get referrals grouped by speciality
    speciality_stats = []
    for speciality in Speciality.objects.all():
        # Count referrals for each workspace in this speciality
        count = 0
        for workspace in speciality.workspaces.all():
            count += referrals.filter(workspace=workspace).count()
        
        if count > 0:  # Only include specialities with referrals
            speciality_stats.append({
                'name': speciality.name,
                'count': count
            })
    
    # Sort specialities by count in descending order
    speciality_stats = sorted(speciality_stats, key=lambda x: x['count'], reverse=True)
    
    # Prepare data for specialities chart
    specialities_labels = json.dumps([s['name'] for s in speciality_stats])
    specialities_data = json.dumps([s['count'] for s in speciality_stats])
    
    # Get referrals grouped by clinic (workspace)
    # Only include workspaces that belong to at least one speciality
    workspace_stats = []
    speciality_workspaces = Speciality.objects.values_list('workspaces', flat=True).distinct()
    for workspace in Workspace.objects.filter(id__in=speciality_workspaces):
        count = referrals.filter(workspace=workspace).count()
        if count > 0:  # Only include workspaces with referrals
            workspace_stats.append({
                'name': workspace.owner_name or workspace.name,
                'count': count
            })
    
    # Sort workspaces by count in descending order
    workspace_stats = sorted(workspace_stats, key=lambda x: x['count'], reverse=True)
    
    # Prepare data for clinics chart
    clinics_labels = json.dumps([w['name'] for w in workspace_stats])
    clinics_data = json.dumps([w['count'] for w in workspace_stats])
    
    # Get top 10 referring doctors
    doctor_stats = []
    doctor_referrals = referrals.values('booked_by').annotate(count=Count('booked_by')).order_by('-count')
    
    for dr_ref in doctor_referrals[:10]:  # Limit to top 10
        if dr_ref['booked_by'] is not None:  # Exclude referrals with no doctor
            try:
                doctor = Doctor.objects.get(id=dr_ref['booked_by'])
                doctor_stats.append({
                    'doctor_name': doctor.full_name,
                    'count': dr_ref['count'],
                    'percentage': round((dr_ref['count'] / total_referrals) * 100 if total_referrals > 0 else 0)
                })
            except Doctor.DoesNotExist:
                # Skip if doctor no longer exists
                continue
    
    # Prepare month and year options for the filters
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    
    # Generate list of years starting from the earliest appointment year to current year
    earliest_referral = ClinicAppointment.objects.filter(system_referral=True).order_by('created_at').first()
    if earliest_referral and earliest_referral.created_at:
        start_year = earliest_referral.created_at.year
    else:
        start_year = today.year
        
    years = list(range(start_year, today.year + 1))
    
    # Add month name to context
    month_names = [
        "", "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    context = {
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'years': years,
        'total_referrals': total_referrals,
        'new_referrals': new_referrals,
        'followup_referrals': followup_referrals,
        'speciality_stats': speciality_stats,
        'workspace_stats': workspace_stats,
        'top_doctors': doctor_stats,
        'specialities_labels': specialities_labels,
        'specialities_data': specialities_data,
        'clinics_labels': clinics_labels,
        'clinics_data': clinics_data,
        'month_name': month_names[selected_month],  # Add month name to context
    }
    
    return render(request, 'system_referrals_stats.html', context)


#favorite_patients
@login_required
def favorite_patients_list(request, workspace_name):
    """Main view for favorite patients list with filtering"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    # Get filter parameters
    section_filter = request.GET.get('section')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    patients = FavoritePatient.objects.filter(
        workspace=workspace,
        is_active=True
    )
    
    # Apply filters
    if section_filter:
        if section_filter == 'no_section':
            patients = patients.filter(section__isnull=True)
        else:
            patients = patients.filter(section_id=section_filter)
    
    if search_query:
        patients = patients.filter(
            Q(name__icontains=search_query) |
            Q(civil_id__icontains=search_query) |
            Q(diagnosis__icontains=search_query)
        )
    
    # Get all sections for the dropdown
    sections = FavoriteSection.objects.filter(workspace=workspace)
    
    context = {
        'workspace': workspace,
        'patients': patients,
        'sections': sections,
        'current_section': section_filter,
        'search_query': search_query,
    }
    
    return render(request, 'favorite_patients/list.html', context)

@login_required
def favorite_patient_detail(request, workspace_name, patient_id):
    """Detailed view of a favorite patient with notes"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    patient = get_object_or_404(FavoritePatient, id=patient_id, workspace=workspace, is_active=True)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    # Get notes with attachments
    notes = patient.notes.all()
    
    # Handle note form submission
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        attachments = request.FILES.getlist('attachments')
        
        # Validate that either content or attachments are provided
        if not content and not attachments:
            messages.error(request, "Please provide either note content or attachments.")
            return redirect('favorite_patient_detail', workspace_name=workspace_name, patient_id=patient_id)
        
        # Create the note
        note = FavoritePatientNote.objects.create(
            patient=patient,
            content=content,
            added_by=request.user
        )
        
        # Handle file attachments
        for attachment_file in attachments:
            if attachment_file:
                # Determine file type
                file_extension = os.path.splitext(attachment_file.name)[1].lower()
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    file_type = 'image'
                elif file_extension in ['.pdf']:
                    file_type = 'document'
                elif file_extension in ['.doc', '.docx']:
                    file_type = 'document'
                else:
                    file_type = 'other'
                
                # Create attachment
                FavoritePatientAttachment.objects.create(
                    note=note,
                    file=attachment_file,
                    filename=attachment_file.name,
                    file_type=file_type
                )
        
        # Log action
        ActionLog.objects.create(
            workspace=workspace,
            user=request.user,
            action_description=f"Added note for favorite patient {patient.name} (Civil ID: {patient.civil_id})"
        )
        
        messages.success(request, "Note added successfully!")
        return redirect('favorite_patient_detail', workspace_name=workspace_name, patient_id=patient_id)
    
    context = {
        'workspace': workspace,
        'patient': patient,
        'notes': notes,
    }
    
    return render(request, 'favorite_patients/detail.html', context)


@login_required
def create_favorite_section(request, workspace_name):
    """Create a new favorite section"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    # Define a list of nice colors for sections
    nice_colors = [
        '#3B82F6',  # Blue
        '#10B981',  # Emerald
        '#8B5CF6',  # Violet
        '#F59E0B',  # Amber
        '#EF4444',  # Red
        '#06B6D4',  # Cyan
        '#84CC16',  # Lime
        '#F97316',  # Orange
        '#EC4899',  # Pink
        '#6366F1',  # Indigo
        '#14B8A6',  # Teal
        '#A855F7',  # Purple
        '#22C55E',  # Green
        '#DC2626',  # Red-600
        '#7C3AED',  # Violet-600
        '#059669',  # Emerald-600
        '#0284C7',  # Sky-600
        '#CA8A04',  # Yellow-600
    ]
    
    if request.method == 'POST':
        form = FavoriteSectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.workspace = workspace
            section.created_by = request.user
            
            # Automatically assign a random color
            # Get colors already used in this workspace
            used_colors = list(
                FavoriteSection.objects.filter(workspace=workspace)
                .values_list('color', flat=True)
            )
            
            # Filter out already used colors for better variety
            available_colors = [color for color in nice_colors if color not in used_colors]
            
            # If all colors are used, fall back to the full list
            if not available_colors:
                available_colors = nice_colors
            
            # Assign random color automatically
            section.color = random.choice(available_colors)
            
            section.save()
            
            # Log action
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Created favorite section: {section.name}"
            )
            
            messages.success(request, f"Section '{section.name}' created successfully!")
            return redirect('favorite_patients_list', workspace_name=workspace_name)
    else:
        form = FavoriteSectionForm()
    
    context = {
        'workspace': workspace,
        'form': form,
    }
    
    return render(request, 'favorite_patients/create_section.html', context)

@login_required
def add_favorite_patient(request, workspace_name):
    """Manually add a favorite patient"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    if request.method == 'POST':
        form = FavoritePatientForm(request.POST, workspace=workspace)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.workspace = workspace
            patient.favorited_by = request.user
            patient.source = 'manual'
            
            try:
                patient.save()
                
                # Log action
                ActionLog.objects.create(
                    workspace=workspace,
                    user=request.user,
                    action_description=f"Added favorite patient: {patient.name} (Civil ID: {patient.civil_id})"
                )
                
                messages.success(request, f"Patient '{patient.name}' added to favorites!")
                return redirect('favorite_patients_list', workspace_name=workspace_name)
            
            except Exception as e:
                if 'unique constraint' in str(e).lower():
                    messages.error(request, "This patient is already in your favorites list.")
                else:
                    messages.error(request, "An error occurred while adding the patient.")
    else:
        form = FavoritePatientForm(workspace=workspace)
    
    context = {
        'workspace': workspace,
        'form': form,
    }
    
    return render(request, 'favorite_patients/add_patient.html', context)

@login_required
@require_POST
@csrf_protect
def favorite_from_clinic(request, workspace_name, appointment_id):
    """Add patient to favorites from clinic appointment"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    appointment = get_object_or_404(ClinicAppointment, id=appointment_id, workspace=workspace)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Check if patient already exists in favorites
    existing = FavoritePatient.objects.filter(
        workspace=workspace,
        civil_id=appointment.civil_id
    ).first()
    
    if existing:
        if existing.is_active:
            return JsonResponse({'success': False, 'message': 'Patient is already in favorites'})
        else:
            # Reactivate if was previously deleted
            existing.is_active = True
            existing.favorited_by = request.user
            existing.save()
            message = f"Patient '{existing.name}' reactivated in favorites!"
    else:
        # Create new favorite patient
        favorite = FavoritePatient.objects.create(
            workspace=workspace,
            civil_id=appointment.civil_id,
            name=appointment.patient_name,
            phone=appointment.phone_number,
            diagnosis=appointment.diagnosis or '',
            source='clinic',
            source_id=appointment.id,
            favorited_by=request.user
        )
        message = f"Patient '{favorite.name}' added to favorites!"
    
    # Log action
    ActionLog.objects.create(
        workspace=workspace,
        user=request.user,
        action_description=f"Added clinic patient to favorites: {appointment.patient_name} (Civil ID: {appointment.civil_id})"
    )
    
    return JsonResponse({'success': True, 'message': message})

@login_required
@require_POST
@csrf_protect
def favorite_from_surgical(request, workspace_name, booking_id):
    """Add patient to favorites from surgical booking"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    booking = get_object_or_404(SurgicalBooking, id=booking_id, workspace=workspace)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Check if patient already exists in favorites
    existing = FavoritePatient.objects.filter(
        workspace=workspace,
        civil_id=booking.civil_id
    ).first()
    
    if existing:
        if existing.is_active:
            return JsonResponse({'success': False, 'message': 'Patient is already in favorites'})
        else:
            # Reactivate if was previously deleted
            existing.is_active = True
            existing.favorited_by = request.user
            existing.save()
            message = f"Patient '{existing.name}' reactivated in favorites!"
    else:
        # Create new favorite patient
        favorite = FavoritePatient.objects.create(
            workspace=workspace,
            civil_id=booking.civil_id,
            name=booking.name,
            phone=booking.phone,
            diagnosis=booking.diagnosis,
            source='surgical',
            source_id=booking.id,
            favorited_by=request.user
        )
        message = f"Patient '{favorite.name}' added to favorites!"
    
    # Log action
    ActionLog.objects.create(
        workspace=workspace,
        user=request.user,
        action_description=f"Added surgical patient to favorites: {booking.name} (Civil ID: {booking.civil_id})"
    )
    
    return JsonResponse({'success': True, 'message': message})

@login_required
@require_POST
@csrf_protect
def delete_favorite_patient(request, workspace_name, patient_id):
    """Soft delete a favorite patient"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    patient = get_object_or_404(FavoritePatient, id=patient_id, workspace=workspace)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return JsonResponse({'success': False, 'message': 'Access denied'})
    
    # Soft delete
    patient.is_active = False
    patient.save()
    
    # Log action
    ActionLog.objects.create(
        workspace=workspace,
        user=request.user,
        action_description=f"Removed favorite patient: {patient.name} (Civil ID: {patient.civil_id})"
    )
    
    return JsonResponse({'success': True, 'message': f"Patient '{patient.name}' removed from favorites"})

@login_required
def edit_favorite_patient(request, workspace_name, patient_id):
    """Edit favorite patient details"""
    workspace = get_object_or_404(Workspace, name=workspace_name)
    patient = get_object_or_404(FavoritePatient, id=patient_id, workspace=workspace, is_active=True)
    
    # Ensure user belongs to workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')
    
    if request.method == 'POST':
        form = FavoritePatientForm(request.POST, instance=patient, workspace=workspace)
        if form.is_valid():
            form.save()
            
            # Log action
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Updated favorite patient: {patient.name} (Civil ID: {patient.civil_id})"
            )
            
            messages.success(request, "Patient updated successfully!")
            return redirect('favorite_patient_detail', workspace_name=workspace_name, patient_id=patient_id)
    else:
        form = FavoritePatientForm(instance=patient, workspace=workspace)
    
    context = {
        'workspace': workspace,
        'patient': patient,
        'form': form,
    }
    
    return render(request, 'favorite_patients/edit_patient.html', context)