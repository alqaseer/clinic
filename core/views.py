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
from django.http import HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Count
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password








def home(request):
    return render(request, "home.html")



# Sign-up view for Admin
def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True  # Make this user an admin
            
            # 🔴 Fix: Hash the password before saving
            user.set_password(form.cleaned_data["password"])  
            user.save()

            # Create a workspace and assign it to the user
            workspace_name = request.POST.get("workspace_name").replace(" ", "").lower()
            workspace = Workspace.objects.create(name=workspace_name, admin=user)

            # Assign the workspace to the user and save
            user.workspace = workspace
            user.save()

            login(request, user)
            return redirect("workspace_main", workspace_name=workspace_name)
    else:
        form = CustomUserCreationForm()
    
    return render(request, "signup.html", {"form": form})



# Login view
# def login_view(request, workspace_name):
#     workspace = get_object_or_404(Workspace, name=workspace_name)
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')
#         user = authenticate(request, username=username, password=password)
        
#         if user is not None and user.workspace == workspace:
#             login(request, user)
#             return redirect('workspace_main', workspace_name=workspace_name)
#         else:
#             return render(request, 'login.html', {'error': 'Invalid credentials or workspace mismatch', 'workspace': workspace})
#     return render(request, 'login.html', {'workspace': workspace})


def login_view(request):
    if request.method == "POST":
        workspace_name = request.POST.get("workspace_name").strip()
        username = request.POST.get("username").strip()
        password = request.POST.get("password").strip()
        remember_me = request.POST.get("remember_me") == "on"

        # Validate workspace
        try:
            workspace = Workspace.objects.get(name=workspace_name)
        except Workspace.DoesNotExist:
            messages.error(request, "Workspace does not exist. Please check the name.")
            return redirect("login")

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None and user.workspace == workspace:
            login(request, user)

            # Set session expiry based on "Remember Me"
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # Expires when browser closes

            return redirect("workspace_main", workspace_name=workspace_name)
        else:
            messages.error(request, "Invalid username or password for this workspace.")
            return redirect("login")

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

    # Count booked cases (future date, since ClinicAppointment has no status field)
    booked_cases_count = SurgicalBooking.objects.filter(
        workspace=workspace,
        date__gte=now().date()  # Only future cases
    ).count()

    # Count waiting list cases from SurgicalBooking (no date, not deleted)
    waiting_list_count = SurgicalBooking.objects.filter(
        workspace=workspace,
        date__isnull=True,
        status__in=["waiting", "booked"]  # Exclude deleted
    ).count()

    # Get list of users in the workspace (directly from `User` model)
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
    ).order_by('-created_at')  # Arrange by creation date, newest first

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
        day_name = date.strftime("%A")
        is_open = day_name in workspace.days_open

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
        "days_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "blank_slots": blank_slots,
    }
    return render(request, "calendar.html", context)








@login_required
def settings_page(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    if request.method == "POST":
        # Handle form submission
        days_open = request.POST.getlist("days_open")
        rooms = request.POST.get("rooms")

        if not rooms:
            rooms = workspace.rooms  # Use the current number of rooms as the default value
        else:
            rooms = int(rooms)

        workspace.days_open = days_open
        workspace.rooms = rooms
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
            "rooms_range": rooms_range,  # Pass the range to the template
        },
    )



@login_required
def day_appointments(request, workspace_name, date):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()

    # Get appointments for the selected day
    appointments = ClinicAppointment.objects.filter(workspace=workspace, date=date_obj)
    timeplots = ["08:00","08:15","08:30","08:45","09:00","09:15","09:30","09:45","10:00","10:15","10:30","10:45","11:00","11:15","11:30","11:45","12:00","12:15","12:30"]
    context = {
        "timeslots": timeplots,
        "workspace": workspace,
        "date": date_obj,
        "appointments": appointments,
    }
    return render(request, "day_appointments.html", context)


@login_required
def add_appointment(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    selected_date = request.GET.get("date")  # Date from URL

    # Parse date correctly
    try:
        if isinstance(selected_date, str):
            try:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.strptime(selected_date, "%b. %d, %Y").date()
    except ValueError:
        selected_date = datetime.today().date()

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
    time_slot_counts = {}
    for slot in time_slots:
        time_slot_counts[slot] = ClinicAppointment.objects.filter(
            workspace=workspace,
            date=selected_date,
            time=slot
        ).count()

    time_slots = [(slot, time_slot_counts.get(slot, 0)) for slot in time_slots]

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            appointment.date = selected_date  # Assign the date manually before saving
            appointment.save()
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
            messages.error(request, "Error adding user. Please check the details.")
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

