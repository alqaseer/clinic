# Generated by Django 4.2.18 on 2025-01-26 19:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_surgicalbooking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='surgicalbooking',
            name='civil_id',
            field=models.CharField(max_length=12),
        ),
    ]
