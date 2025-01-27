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

# Sign-up view for Admin
def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True  # Make this user an admin
            user.save()
            
            # Create a workspace for this admin
            workspace_name = request.POST.get('workspace_name').replace(" ", "").lower()
            Workspace.objects.create(name=workspace_name, admin=user)
            
            login(request, user)
            return redirect('workspace_main', workspace_name=workspace_name)
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})

# Login view
def login_view(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None and user.workspace == workspace:
            login(request, user)
            return redirect('workspace_main', workspace_name=workspace_name)
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials or workspace mismatch', 'workspace': workspace})
    return render(request, 'login.html', {'workspace': workspace})

def logout_view(request):
    # If the user is authenticated, get their workspace name
    workspace_name = None
    if request.user.is_authenticated:
        workspace = request.user.workspace
        if workspace:
            workspace_name = workspace.name

    # Log out the user
    logout(request)

    # Redirect to the login page for the specific workspace
    if workspace_name:
        return redirect('login', workspace_name=workspace_name)
    else:
        return redirect('signup')  # Redirect to signup if no workspace is found


# Workspace Main Page
@login_required
def workspace_main(request, workspace_name):
    print(workspace_name)
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure the user belongs to this workspace
    if request.user != workspace.admin and request.user.workspace != workspace:
        return redirect('login')  # Prevent unauthorized access

    # Admin functionality: Add users
    if request.method == 'POST' and request.user == workspace.admin:
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username and password:
            if not User.objects.filter(username=username, workspace=workspace).exists():
                User.objects.create_user(username=username, password=password, workspace=workspace)
            else:
                return render(request, 'workspace_main.html', {
                    'workspace': workspace,
                    'error': 'Username already exists in this workspace.'
                })

    return render(request, 'workspace_main.html', {'workspace': workspace})

@login_required
def booked_cases(request, workspace_name):
    """View for cases with dates from today onward, arranged chronologically."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    today = now().date()
    cases = SurgicalBooking.objects.filter(
        workspace=workspace, status='booked', date__gte=today
    ).order_by('date')  # Arrange chronologically by date

    return render(request, 'booked_cases.html', {'cases': cases, 'workspace': workspace})


@login_required
def waiting_list(request, workspace_name):
    """View for cases with no date, arranged by creation date."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    cases = SurgicalBooking.objects.filter(
        workspace=workspace, status='waiting'
    ).order_by('-created_at')  # Arrange by creation date, newest first

    return render(request, 'waiting_list.html', {'cases': cases, 'workspace': workspace})


@login_required
def past_cases(request, workspace_name):
    """View for cases with dates in the past, arranged chronologically."""
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Ensure user belongs to this workspace
    if request.user.workspace != workspace and request.user != workspace.admin:
        return redirect('login')

    today = now().date()
    cases = SurgicalBooking.objects.filter(
        workspace=workspace, status='booked', date__lt=today
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

    # Get the first day of the month and number of days in the month
    first_day, days_in_month = calendar.monthrange(current_year, current_month)

    # Total slots available for each day (rooms * 16 slots per room)
    total_slots_per_day = workspace.rooms * 16

    # Generate the list of days for the calendar
    days = []
    for day in range(1, days_in_month + 1):
        date = datetime(current_year, current_month, day)
        day_name = date.strftime("%A")
        is_open = day_name in workspace.days_open

        # Count the number of surgical bookings for this specific date and workspace
        booked_cases_count = SurgicalBooking.objects.filter(workspace=workspace, date=date, status='booked').count()

        days.append({
            'date': date,
            'is_open': is_open,
            'booked_cases_count': booked_cases_count,
            'is_fully_booked': booked_cases_count >= total_slots_per_day,
        })

    # Calculate navigation for next and previous months
    next_month = (current_month % 12) + 1
    next_year = current_year + 1 if next_month == 1 else current_year
    prev_month = current_month - 1 if current_month > 1 else 12
    prev_year = current_year - 1 if prev_month == 12 else current_year

    # Create a list of blank slots for days before the first day of the month
    blank_slots = list(range(first_day))  # Create a list of integers for blank slots

    context = {
        'workspace': workspace,
        'days': days,
        'current_year': current_year,
        'current_month': current_month,
        'month_name': calendar.month_name[current_month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'days_of_week': ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        'blank_slots': blank_slots,  # Add blank slots to the context
    }
    return render(request, 'calendar.html', context)







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

    context = {
        "workspace": workspace,
        "date": date_obj,
        "appointments": appointments,
    }
    return render(request, "day_appointments.html", context)


@login_required
def add_appointment(request, workspace_name):
    workspace = get_object_or_404(Workspace, name=workspace_name)

    # Get the date from the query parameter or default to today's date
    selected_date = request.GET.get("date", datetime.today().date())
    try:
        if isinstance(selected_date, str):
            # Try to parse the date in the expected format or fallback to another format
            try:
                selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.strptime(selected_date, "%b. %d, %Y").date()
    except ValueError:
        # If parsing fails, default to today's date
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

    # Combine time slots and counts
    time_slots = [(slot, time_slot_counts.get(slot, 0)) for slot in time_slots]

    if request.method == "POST":
        form = ClinicAppointmentForm(request.POST, request.FILES)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.workspace = workspace
            appointment.save()
            return redirect("day_appointments", workspace_name=workspace_name, date=appointment.date)
    else:
        # Pre-fill the date field with the selected date
        form = ClinicAppointmentForm(initial={"date": selected_date})

    return render(
        request,
        "add_appointment.html",
        {
            "form": form,
            "workspace": workspace,
            "time_slots": time_slots,
            "selected_date": selected_date,  # Pass the selected date to the template
        },
    )




