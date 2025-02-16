from django.contrib import admin
from .models import *
# Custom Admin for Workspace
# Inline for booked surgical cases
class SurgicalBookingInline(admin.TabularInline):  # Display cases in a tabular format
    model = SurgicalBooking
    extra = 0  # No extra blank fields
    fields = ('name', 'civil_id', 'phone', 'procedure', 'date', 'status')  # Fields to show
    readonly_fields = ('name', 'civil_id', 'phone', 'procedure', 'date', 'status')  # Make them non-editable
    ordering = ('date',)  # Order cases by date

    def get_queryset(self, request):
        """Filter to show only booked cases"""
        return super().get_queryset(request).filter(status="booked")


# Custom Admin for Workspace
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'admin_username')  # Show workspace name & admin name
    search_fields = ('name', 'admin__username')  # Allow searching by workspace or admin username
    inlines = [SurgicalBookingInline]  # Show booked cases when viewing workspace

    def admin_username(self, obj):
        """Display the admin of the workspace"""
        return obj.admin.username
    admin_username.short_description = "Owner"

# Custom Admin for User
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'workspace', 'is_staff')  # Display username, workspace, and admin status
    search_fields = ('username', 'workspace__name')  # Allow searching by username or workspace name
    list_filter = ('is_staff', 'is_superuser', 'workspace')  # Filter by admin status and workspace

# Custom Admin for ClinicAppointment
class ClinicAppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient_name', 'workspace', 'date', 'time', 'confirmed', 'appointment_type')
    list_filter = ('workspace', 'confirmed', 'date', 'appointment_type')  # Filters on the right panel
    search_fields = ('patient_name', 'phone_number', 'workspace__name')  # Search by patient name, phone, workspace
    ordering = ('-date', 'time')  # Order by date (descending) and then by time
    actions = ['mark_as_confirmed', 'mark_as_unconfirmed']

    @admin.action(description="Mark selected appointments as confirmed")
    def mark_as_confirmed(self, request, queryset):
        """Bulk action to mark appointments as confirmed."""
        queryset.update(confirmed=True)
        self.message_user(request, "Selected appointments have been marked as confirmed.")

    @admin.action(description="Mark selected appointments as unconfirmed")
    def mark_as_unconfirmed(self, request, queryset):
        """Bulk action to mark appointments as unconfirmed."""
        queryset.update(confirmed=False)
        self.message_user(request, "Selected appointments have been marked as unconfirmed.")

# Register the models with their custom admins
admin.site.register(Workspace, WorkspaceAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(ClinicAppointment, ClinicAppointmentAdmin)
