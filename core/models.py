from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):
    pass  # Extend this later if needed

# Workspace model
class Workspace(models.Model):
    name = models.CharField(max_length=255)
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='workspace_admin')
    editors = models.ManyToManyField(User, related_name='workspace_editors')

    def __str__(self):
        return self.name
