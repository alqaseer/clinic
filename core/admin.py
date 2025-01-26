from django.contrib import admin
from .models import Workspace, User

# Register your models here.
admin.site.register(User)
admin.site.register(Workspace)
