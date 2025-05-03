from django.shortcuts import render, redirect, get_object_or_404, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import *
from .models import *
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from datetime import datetime, timedelta
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
        # Calculate the cutoff date (14 days ago)
        
        cutoff_date = now().date() - timedelta(weeks=12)  

        # Find old appointments
        old_appointments = ClinicAppointment.objects.filter(date__lt=cutoff_date)

        for appointment in old_appointments:
            # Delete referral letter file if exists
            if appointment.referral_letter:
                file_path = os.path.join(settings.MEDIA_ROOT, str(appointment.referral_letter))
                if os.path.exists(file_path):
                    os.remove(file_path)
                    

            # Delete the database entry
            appointment.referral_letter = None
            appointment.save()

    # Count booked cases (future date, since ClinicAppointment has no status field)
    booked_cases_count = SurgicalBooking.objects.filter(
    workspace=workspace,
    date__gte=now().date(),
    status='booked'
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

    return render(request, 'booked_cases.html', {'cases': cases, 'workspace': workspace})


@login_required
def waiting_list(request, workspace_name):
    """View for cases where date is empty and status is NOT deleted, arranged by creation date."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    cases = SurgicalBooking.objects.filter(
        workspace=workspace, 
        date__isnull=True,  # Date is empty (null)
        status__in=['booked', 'waiting', 'past']  # Exclude 'deleted' cases
    ).order_by('created_at')  # Arrange by creation date, newest first

    return render(request, 'waiting_list.html', {'cases': cases, 'workspace': workspace})


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

    return render(request, 'past_cases.html', {'cases': cases, 'workspace': workspace})


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
        form = SurgicalBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.workspace = workspace  # Assign the booking to the current workspace
            if booking.date:
                booking.status = 'booked'
            else:
                booking.status = 'waiting'
            booking.save()

            # ✅ Add new ActionLog entry
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
    print(first_day)
    # Adjust first_day to make Sunday 0 instead of Monday 0
    first_day = (first_day + 1) % 7  # Convert from Monday=0 to Sunday=0
    print(first_day)
    # Total slots per day (rooms * 16 slots per room)
    total_slots_per_day = workspace.rooms * 16

    # Get all booked cases for the month
    booked_cases = ClinicAppointment.objects.filter(
        workspace=workspace,
        date__year=current_year,
        date__month=current_month
    ).values("date").annotate(count=Count("id"))

    # Convert queryset into a dictionary {date: count}
    booked_cases_dict = {item["date"]: item["count"] for item in booked_cases}

    # Generate calendar days
    days = []
    for day in range(1, days_in_month + 1):
        date = datetime(current_year, current_month, day).date()
        day_name = date.strftime("%A")  # Gets the full day name (e.g., "Sunday")
        is_open = workspace.is_day_open(day_name)  # Compare with exact day name from settings
        print(f"{day_name} {date} {is_open}")
        # Get booked cases from dictionary (default to 0 if not found)
        booked_cases_count = booked_cases_dict.get(date, 0)

        days.append({
            "date": date,
            "is_open": is_open,
            "booked_cases_count": booked_cases_count,
            "is_fully_booked": booked_cases_count >= total_slots_per_day,
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
        "today": today,  # Pass today's date to the template

    }
    return render(request, "calendar.html", context)

@login_required
def settings_page(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    if request.method == "POST":
        # Handle form submission
        days_open = request.POST.getlist("days_open")
        rooms = request.POST.get("rooms")
        maximum = request.POST.get("maximum")  # Get the maximum value from the form

        if not rooms:
            rooms = workspace.rooms  # Use the current number of rooms as the default value
        else:
            rooms = int(rooms)
            
        if not maximum:
            maximum = workspace.maximum  # Use the current maximum as the default value
        else:
            try:
                maximum = int(maximum)
                if maximum < 1:  # Ensure maximum is at least 1
                    maximum = 1
            except ValueError:
                maximum = workspace.maximum  # If invalid input, keep current value

        # Ensure days are stored in the correct format
        days_open = [day for day in days_open]  # This ensures we store the full day names
        workspace.days_open = days_open
        workspace.rooms = rooms
        workspace.maximum = maximum  # Save the maximum value
        workspace.save()

        # Redirect to the workspace main page
        return redirect("workspace_main", workspace_name=workspace_name)

    days_of_week = [
        ("Sunday", "Sunday"),
        ("Monday", "Monday"),
        ("Tuesday", "Tuesday"),
        ("Wednesday", "Wednesday"),
        ("Thursday", "Thursday"),
        ("Friday", "Friday"),
        ("Saturday", "Saturday"),
    ]

    rooms_range = range(1, 6)  # Number of rooms, from 1 to 5

    return render(
        request,
        "settings.html",
        {
            "workspace": workspace,
            "days_of_week": days_of_week,
            "rooms_range": rooms_range,
        },
    )

@login_required
def day_appointments(request, workspace_name, date):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Get appointments for the selected day
    appointments = ClinicAppointment.objects.filter(workspace=workspace, date=date_obj)
    timeplots = ["08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45","12:00","12:15","12:30"]
    
    # Check if the day is locked
    is_locked = Lock.objects.filter(workspace=workspace, date=date_obj).exists()
    
    context = {
        "timeslots": timeplots,
        "workspace": workspace,
        "date": date_obj,
        "appointments": appointments,
        "is_locked": is_locked,  # Add the lock status to the context
    }
    return render(request, "day_appointments.html", context)


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

    # Generate time slots
    morning_start = datetime.strptime("08:00", "%H:%M")
    morning_end = datetime.strptime("12:15", "%H:%M")

    def generate_time_slots(start, end):
        slots = []
        while start <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=15)
        return slots

    time_slots = generate_time_slots(morning_start, morning_end)

    # Count booked patients for each time slot
    time_slot_counts = {slot: 0 for slot in time_slots}
    for slot in time_slots:
        time_slot_counts[slot] = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=selected_date,
            time=slot
        ).count()

    time_slots = [(slot, time_slot_counts[slot]) for slot in time_slots]

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            appointment.date = selected_date  # Assign the selected date before saving
            appointment.save()

            # ✅ Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Added clinic appointment for {appointment.patient_name} (Civil ID: {appointment.civil_id}) on {appointment.date} at {appointment.time}."
            )

            # Check if the number of appointments for this day has reached the maximum
            appointments_count = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=selected_date
            ).count()
            
            # If the count equals the maximum and no lock exists, create a lock
            if appointments_count == workspace.maximum:
                # Check if a lock already exists for this day
                lock_exists = Lock.objects.filter(
                    workspace=workspace, 
                    date=selected_date
                ).exists()
                
                if not lock_exists:
                    # Create a lock for this day
                    Lock.objects.create(
                        workspace=workspace,
                        date=selected_date
                    )
                    
                    # Log the automatic locking
                    ActionLog.objects.create(
                        workspace=workspace,
                        user=request.user,
                        action_description=f"Day {selected_date} automatically locked as it reached maximum capacity ({workspace.maximum} appointments)."
                    )
                    
                    # Add a message to inform the user
                    messages.info(request, f"This day has reached its maximum capacity and has been automatically locked.")

            return redirect("day_appointments", workspace_name=workspace_name, date=appointment.date)
    else:
        form = ClinicAppointmentForm()

    return render(request, "add_appointment.html", {
        "form": form,
        "workspace": workspace,
        "time_slots": time_slots,
        "selected_date": selected_date,
    })

@login_required
def edit_appointment(request, workspace_name, appointment_id):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    appointment = get_object_or_404(ClinicAppointment, id=appointment_id)

    selected_date = appointment.date
    morning_start = datetime.strptime("08:00", "%H:%M")
    morning_end = datetime.strptime("12:15", "%H:%M")

    def generate_time_slots(start, end):
        slots = []
        while start <= end:
            slots.append(start.strftime("%H:%M"))
            start += timedelta(minutes=15)
        return slots

    time_slots = generate_time_slots(morning_start, morning_end)

    time_slot_counts = {}
    for slot in time_slots:
        count = ClinicAppointment.objects.filter(
            workspace=workspace, date=selected_date, time=slot
        ).exclude(id=appointment.id).count()

        # Ensure the patient's current appointment is counted in its slot
        if slot == appointment.time.strftime("%H:%M"):
            count += 1

        time_slot_counts[slot] = count

    time_slots = [(slot, time_slot_counts.get(slot, 0)) for slot in time_slots]

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES, instance=appointment)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            appointment.save()

            # ✅ Add new ActionLog entry
            ActionLog.objects.create(
                workspace=workspace,
                user=request.user,
                action_description=f"Updated appointment for {appointment.patient_name} (Civil ID: {appointment.civil_id})"
            )


            return redirect("day_appointments", workspace_name=workspace_name, date=appointment.date)
    else:
        form = ClinicAppointmentForm(instance=appointment)

    return render(request, "edit_appointment.html", {
        "form": form,
        "workspace": workspace,
        "time_slots": time_slots,
        "selected_date": selected_date,
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
        form = SurgicalBookingForm(request.POST, instance=case)
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
        
        # Check if it's a form for updating maximum_new_referrals
        elif 'update_referrals' in request.POST:
            workspace_id = request.POST.get('workspace_id')
            workspace = get_object_or_404(Workspace, id=workspace_id)
            
            form = WorkspaceReferralForm(request.POST)
            if form.is_valid():
                workspace.maximum_new_referrals = form.cleaned_data['maximum_new_referrals']
                workspace.save()
                messages.success(request, f"Updated maximum new referrals for {workspace.name}")
            else:
                messages.error(request, "Invalid value for maximum new referrals")
        
        return redirect('manage_specialities')
    
    # For each speciality, create a dictionary of forms for its workspaces
    workspace_forms = {}
    for speciality in specialities:
        workspace_forms[speciality.id] = {}
        for workspace in speciality.workspaces.all():
            workspace_forms[speciality.id][workspace.id] = WorkspaceReferralForm(
                initial={'maximum_new_referrals': workspace.maximum_new_referrals}
            )
    
    context = {
        'specialities': specialities,
        'all_workspaces': all_workspaces,
        'workspace_forms': workspace_forms,
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

# Find next available appointment slot
def find_available_appointment(speciality):
    # Get all workspaces with this speciality
    workspaces = speciality.workspaces.all()
    
    if not workspaces.exists():
        return None, None, None
    
    # Get tomorrow's date
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # Time slots (convert to datetime.time objects)
    time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45",
            "10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45",
            "12:00","12:15","12:30"
        ]
    ]
    
    # Default 8:00 AM slot for booking when no empty slots are found
    default_slot = datetime.strptime("08:00", "%H:%M").time()
    
    # Check up to 120 days ahead starting from tomorrow
    for day_offset in range(120):
        check_date = tomorrow + timedelta(days=day_offset)
        day_name = check_date.strftime("%A")
        print(f"checking date : {check_date}")
        
        # Keep track of the best workspace for this day
        best_workspace = None
        lowest_referral_count = float('inf')  # Start with infinity for comparison
        best_slot = None
        
        # For tracking workspaces without available slots
        valid_workspaces_without_slots = []
        
        # Check all workspaces for this specific day
        open_workspaces = []
        for workspace in workspaces:
            # Skip workspaces that aren't open on this day
            if not workspace.is_day_open(day_name):
                print(f"Skipping workspace {workspace} - not open on {day_name}")
                continue
            
            # Check if the day is locked for this workspace
            if Lock.objects.filter(workspace=workspace, date=check_date).exists():
                print(f"Skipping workspace {workspace} on {check_date} - day is locked")
                continue
                
            open_workspaces.append(workspace)
            print(f"open workspaces {workspace}")
            
            # Count existing appointments for this date in this workspace
            total_appointments = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=check_date
            ).count()
            print(f"count total appointment {total_appointments}")

            # Count new referrals for this date in this workspace
            new_referrals = ClinicAppointment.objects.filter(
                workspace=workspace,
                date=check_date,
                appointment_type="New",
                system_referral=True
            ).count()
            print(f"count new referrals {new_referrals}")

            # Skip workspaces that have reached their limit
            if (total_appointments >= workspace.maximum or 
                new_referrals >= workspace.maximum_new_referrals):
                print(f'skipping {workspace} ... total appointment = {total_appointments}>= workspace maximum = {workspace.maximum} OR new_referrals = {new_referrals} >= workspace.maximum_new_referrals = {workspace.maximum_new_referrals}')
                continue
            
            # Track this workspace as a valid one (meets all conditions)
            valid_workspaces_without_slots.append((workspace, new_referrals))
            
            # If this workspace has fewer referrals than our current best, update our best
            if new_referrals < lowest_referral_count:
                # Find the first available time slot
                occupied_times = ClinicAppointment.objects.filter(
                    workspace=workspace,
                    date=check_date
                ).values_list('time', flat=True)
                
                slot_found = False
                for slot in time_slots:
                    if slot not in occupied_times:
                        # Found an available slot in this workspace
                        best_workspace = workspace
                        lowest_referral_count = new_referrals
                        best_slot = slot
                        slot_found = True
                        break
        
        # If we found a workspace with an available slot on this day, return it
        if best_workspace and best_slot:
            return best_workspace, check_date, best_slot
        
        # If all conditions are met but no empty slot is found, book at 8:00 AM in the workspace with lowest referrals
        if valid_workspaces_without_slots:
            # Sort workspaces by referral count to get the one with lowest referrals
            valid_workspaces_without_slots.sort(key=lambda x: x[1])
            best_workspace = valid_workspaces_without_slots[0][0]
            return best_workspace, check_date, default_slot
    
    # No available slots found in any workspace within the time range
    return None, None, None


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
    
    # Find available slot
    workspace, appointment_date, appointment_time = find_available_appointment(speciality)
    
    if not workspace or not appointment_date or not appointment_time:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'message': f"No available appointments for {speciality.name} speciality"})
        else:
            messages.error(request, f"No available appointments for {speciality.name} speciality")
            return redirect('doctor_dashboard')
    
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
        system_referral=True,
        booked_by=doctor,
        diagnosis=diagnosis
    )
    
    # Return response based on content type
    if request.content_type == 'application/json':
        return JsonResponse({
            'success': True,
            'message': 'Appointment booked successfully',
            'appointment_id': appointment.id,
            'speciality_name': speciality.name,
            'clinic_name': workspace.owner_name or workspace.name,
            'appointment_date': appointment_date.strftime('%d %b %Y'),
            'appointment_time': appointment_time.strftime('%H:%M'),
            'workspace_id': workspace.id  # Add this line
        })
    else:
        messages.success(
            request, 
            f"Appointment booked successfully for {patient_name} with {speciality.name} speciality on "
            f"{appointment_date.strftime('%d %b %Y')} at {appointment_time.strftime('%H:%M')}"
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
        print(f"Received data: appointment_id={appointment_id}, workspace_id={workspace_id}")
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
        print(f"Found workspace: {workspace.name}, days_open={workspace.days_open}")
        print(f"Workspace limits: maximum={workspace.maximum}, maximum_new_referrals={workspace.maximum_new_referrals}")
    except Workspace.DoesNotExist:
        print(f"ERROR: Workspace with id={workspace_id} not found")
        return JsonResponse({'success': False, 'message': 'Workspace not found'})
    
    # Get time slots
    time_slots = [
        datetime.strptime(time_str, "%H:%M").time() 
        for time_str in [
            "08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45",
            "10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45",
            "12:00","12:15","12:30"
        ]
    ]
    print(f"Generated {len(time_slots)} time slots")
    
    # Default 8:00 AM slot for booking when no empty slots are found
    default_slot = datetime.strptime("08:00", "%H:%M").time()
    
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
        
        # Check if the day is locked
        if Lock.objects.filter(workspace=workspace, date=check_date).exists():
            print(f"Skipping date {check_date}: Day is locked")
            continue
        
        # Count existing appointments for this date
        total_appointments = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=check_date
        ).count()
        
        # Count new referrals for this date
        new_referrals = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=check_date,
            appointment_type="New",
            system_referral=True
        ).count()
        
        print(f"Date {check_date}: total_appointments={total_appointments}, new_referrals={new_referrals}")
        
        # Check if limits are reached
        if (total_appointments >= workspace.maximum or 
            new_referrals >= workspace.maximum_new_referrals):
            print(f"Skipping date {check_date}: Limits reached - total={total_appointments}/{workspace.maximum}, new_referrals={new_referrals}/{workspace.maximum_new_referrals}")
            continue
        
        # This is a valid date - track it even if there are no available slots
        valid_dates_without_slots.append(check_date)
        
        # Find available time slot
        occupied_times = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=check_date
        ).values_list('time', flat=True)
        print(f"Occupied times for {check_date}: {list(occupied_times)}")
        
        for slot in time_slots:
            if slot not in occupied_times:
                print(f"Found available slot: {check_date} at {slot}")
                
                # Update the appointment
                old_date = appointment.date
                old_time = appointment.time
                
                try:
                    appointment.date = check_date
                    appointment.time = slot
                    appointment.save()
                    print(f"Updated appointment: date={check_date}, time={slot}")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Appointment date changed successfully',
                        'new_date': check_date.strftime('%d %b %Y'),
                        'new_time': slot.strftime('%H:%M'),
                        'old_date': old_date.strftime('%d %b %Y'),
                        'old_time': old_time.strftime('%H:%M')
                    })
                except Exception as e:
                    print(f"ERROR saving appointment: {str(e)}")
                    return JsonResponse({'success': False, 'message': f'Error saving appointment: {str(e)}'})
    
    # If we found valid dates but no empty slots, book at 8:00 AM on the earliest valid date
    if valid_dates_without_slots:
        earliest_valid_date = valid_dates_without_slots[0]
        print(f"No available slots found, but there are valid dates. Booking at 8:00 AM on {earliest_valid_date}")
        
        old_date = appointment.date
        old_time = appointment.time
        
        try:
            appointment.date = earliest_valid_date
            appointment.time = default_slot
            appointment.save()
            print(f"Updated appointment to default slot: date={earliest_valid_date}, time={default_slot}")
            
            return JsonResponse({
                'success': True,
                'message': 'Appointment date changed successfully (using default 8:00 AM slot)',
                'new_date': earliest_valid_date.strftime('%d %b %Y'),
                'new_time': default_slot.strftime('%H:%M'),
                'old_date': old_date.strftime('%d %b %Y'),
                'old_time': old_time.strftime('%H:%M')
            })
        except Exception as e:
            print(f"ERROR saving appointment to default slot: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Error saving appointment: {str(e)}'})
    
    print("ERROR: No available dates found after checking 60 days")
    return JsonResponse({'success': False, 'message': 'No available dates found'})



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
