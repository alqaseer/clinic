# Generated by Django 5.1.5 on 2025-01-27 21:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clinicappointment',
            name='civil_id',
        ),
    ]
