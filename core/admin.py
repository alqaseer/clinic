from django.contrib import admin
from django import forms  # Add this import
from .models import *

# Inline for booked surgical cases
class SurgicalBookingInline(admin.TabularInline):
    model = SurgicalBooking
    extra = 0
    fields = ('name', 'civil_id', 'phone', 'procedure', 'date', 'status')
    readonly_fields = ('name', 'civil_id', 'phone', 'procedure', 'date', 'status')
    ordering = ('date',)

    def get_queryset(self, request):
        """Filter to show only booked cases"""
        return super().get_queryset(request).filter(status="booked")

# Inline for Specialities in Workspace admin
class SpecialityInline(admin.TabularInline):
    model = Speciality.workspaces.through
    extra = 1
    verbose_name = "Speciality"
    verbose_name_plural = "Specialities"

# Create a ModelForm for the Workspace model
class WorkspaceAdminForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make days_open field not required
        if 'days_open' in self.fields:
            self.fields['days_open'].required = False

# Admin for Speciality
class SpecialityAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_workspaces')
    search_fields = ('name', 'workspaces__name')
    filter_horizontal = ('workspaces',)
    
    def get_workspaces(self, obj):
        """Display the workspaces associated with this speciality"""
        return ", ".join([workspace.name for workspace in obj.workspaces.all()])
    get_workspaces.short_description = "Workspaces"

# Custom Admin for Workspace
class WorkspaceAdmin(admin.ModelAdmin):
    form = WorkspaceAdminForm  # Use the custom form
    list_display = ('name', 'admin_username', 'get_specialities')
    search_fields = ('name', 'admin__username', 'specialities__name')
    inlines = [SurgicalBookingInline, SpecialityInline]

    def admin_username(self, obj):
        """Display the admin of the workspace"""
        return obj.admin.username
    admin_username.short_description = "Owner"
    
    def get_specialities(self, obj):
        """Display the specialities associated with this workspace"""
        return ", ".join([speciality.name for speciality in obj.specialities.all()])
    get_specialities.short_description = "Specialities"

# Custom Admin for User
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'workspace', 'is_staff')
    search_fields = ('username', 'workspace__name')
    list_filter = ('is_staff', 'is_superuser', 'workspace')

# Custom Admin for ClinicAppointment
class ClinicAppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient_name', 'workspace', 'date', 'time', 'confirmed', 'appointment_type')
    list_filter = ('workspace', 'confirmed', 'date', 'appointment_type')
    search_fields = ('patient_name', 'phone_number', 'workspace__name')
    ordering = ('-date', 'time')
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


# Custom Admin for Doctor
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('username', 'full_name', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('username', 'full_name')
    fieldsets = (
        (None, {
            'fields': ('username', 'password', 'full_name')
        }),
        ('Status', {
            'fields': ('active',)
        }),
    )

# Register the models with their custom admins
admin.site.register(Workspace, WorkspaceAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(ClinicAppointment, ClinicAppointmentAdmin)
admin.site.register(Speciality, SpecialityAdmin)

# Register any other models that don't have custom admins
admin.site.register(SurgicalBooking)
admin.site.register(Lock)
admin.site.register(ActionLog)
admin.site.register(Doctor, DoctorAdmin)