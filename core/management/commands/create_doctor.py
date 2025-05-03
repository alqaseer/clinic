from django.core.management.base import BaseCommand
from core.models import Doctor

class Command(BaseCommand):
    help = 'Creates a new doctor user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username for the doctor')
        parser.add_argument('password', type=str, help='Password for the doctor')
        parser.add_argument('full_name', type=str, help='Full name of the doctor')
        parser.add_argument('--active', action='store_true', help='Set doctor as active')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        full_name = options['full_name']
        active = options.get('active', True)
        
        # Check if username already exists
        if Doctor.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'Doctor with username "{username}" already exists'))
            return
        
        try:
            doctor = Doctor.objects.create(
                username=username,
                password=password,
                full_name=full_name,
                active=active
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created doctor "{full_name}" with username "{username}"'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create doctor: {str(e)}'))