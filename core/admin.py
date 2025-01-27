from django.contrib import admin
from .models import Workspace, User, ClinicAppointment

# Custom Admin for Workspace
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'admin_username', 'get_users')  # Display workspace name, admin, and users
    search_fields = ('name',)  # Allow searching by workspace name

    def admin_username(self, obj):
        """Display the username of the workspace's admin."""
        return obj.admin.username
    admin_username.short_description = "Admin Username"

    def get_users(self, obj):
        """Display all users associated with the workspace."""
        users = User.objects.filter(workspace=obj)
        return ", ".join([user.username for user in users])
    get_users.short_description = "Users"

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
